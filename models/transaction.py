"""
models/transaction.py — CRUD for the Transactions table.
"""

import re
from contextlib import closing
from datetime import datetime
from collections import defaultdict

from core.database import get_connection
from config import fy_date_range


INTERNAL_TRANSFER_CATEGORY = "Internal Transfer"
TRANSFER_CREDIT_CATEGORIES = {"Other Income", INTERNAL_TRANSFER_CATEGORY, None, ""}
TRANSFER_DEBIT_CATEGORIES = {"Other Expense", INTERNAL_TRANSFER_CATEGORY, None, ""}
TRANSFER_MAX_DAY_GAP = 2


_TYPE_ALIAS_TO_CANON = {
    "income": "Income",
    "credit": "Income",
    "expense": "Expense",
    "debit": "Expense",
    "transfer": "Transfer",
}


def normalize_transaction_type(value: str | None) -> str:
    """Normalize UI/db aliases to canonical DB values."""
    raw = (value or "").strip().lower()
    return _TYPE_ALIAS_TO_CANON.get(raw, value or "")


def display_transaction_type(value: str | None) -> str:
    """Convert canonical DB values to user-facing labels."""
    canon = normalize_transaction_type(value)
    if canon == "Income":
        return "Income"
    if canon == "Expense":
        return "Expense"
    return canon




def _date_diff_days(d1: str, d2: str) -> int:
    try:
        dt1 = datetime.fromisoformat(d1).date()
        dt2 = datetime.fromisoformat(d2).date()
        return abs((dt1 - dt2).days)
    except Exception:
        return 999


def _transfer_pair_valid(left, right):
    return (
        left["account_id"] != right["account_id"]
        and {left["transaction_type"], right["transaction_type"]} == {"Income", "Expense"}
        and left["amount"] > 0
        and round(left["amount"] * 100) == round(right["amount"] * 100)
    )


def _link_transfer_pair(conn, left_id, right_id, group_id):
    conn.executemany("""
        UPDATE Transactions
        SET linked_transaction_id = ?, internal_transfer_group_id = ?, is_internal_transfer = 1
        WHERE transaction_id = ?
    """, ((right_id, group_id, left_id), (left_id, group_id, right_id)))
    conn.execute(
        "UPDATE IncomeExpectation SET actual_transaction_id = NULL WHERE actual_transaction_id IN (?, ?)",
        (left_id, right_id),
    )


def _next_transfer_group(conn):
    return conn.execute(
        "SELECT COALESCE(MAX(internal_transfer_group_id), 0) + 1 FROM Transactions"
    ).fetchone()[0]


def _clear_transfer_pair(conn, transaction_id):
    transaction = conn.execute(
        "SELECT linked_transaction_id FROM Transactions WHERE transaction_id = ?", (transaction_id,),
    ).fetchone()
    if transaction and transaction["linked_transaction_id"] is not None:
        conn.execute("""
            UPDATE Transactions
            SET linked_transaction_id = NULL, internal_transfer_group_id = NULL, is_internal_transfer = 0
            WHERE transaction_id = ? OR linked_transaction_id = ?
        """, (transaction_id, transaction_id))


def _get_transfer_pair(conn, left_id, right_id):
    rows = conn.execute(
        "SELECT * FROM Transactions WHERE transaction_id IN (?, ?)", (left_id, right_id),
    ).fetchall()
    if len(rows) != 2 or not _transfer_pair_valid(*rows):
        raise ValueError("Choose an equal debit and credit from two different accounts.")
    return rows


def link_internal_transfer(left_id, right_id):
    """Confirm the two ledger entries for a family transfer."""
    with closing(get_connection()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        rows = _get_transfer_pair(conn, left_id, right_id)
        if any(row["linked_transaction_id"] is not None for row in rows):
            raise ValueError("Unlink the existing transfer pair first.")
        _link_transfer_pair(conn, left_id, right_id, _next_transfer_group(conn))


def unlink_internal_transfer(transaction_id):
    with closing(get_connection()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        _clear_transfer_pair(conn, transaction_id)


def get_transfer_counterparts(transaction_id):
    left = get_transaction(transaction_id)
    if not left or left["transaction_type"] not in {"Income", "Expense"}:
        return []
    opposite = "Expense" if left["transaction_type"] == "Income" else "Income"
    rows = get_transactions(transaction_type=opposite)
    return [
        row for row in rows
        if row["linked_transaction_id"] is None and _transfer_pair_valid(left, row)
    ]


def reprocess_internal_transfers(person_id: int = None, financial_year: str = None) -> tuple[int, int]:
    """Link unambiguous pairs with the same bank reference. Preserve saved pairs."""
    date_range = fy_date_range(financial_year) if financial_year else None

    def in_scope(row):
        matches_person = person_id is None or row["person_id"] == person_id
        return matches_person and (
            date_range is None
            or date_range[0].isoformat() <= row["transaction_date"] <= date_range[1].isoformat()
        )

    with closing(get_connection()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        candidates = defaultdict(list)
        rows = conn.execute("""
            SELECT transaction_id, account_id, person_id, transaction_date, transaction_type,
                   amount, reference_no, category
            FROM Transactions
            WHERE linked_transaction_id IS NULL AND COALESCE(is_internal_transfer, 0) = 0
              AND reference_no IS NOT NULL AND amount > 0
        """)
        for row in rows:
            categories = TRANSFER_DEBIT_CATEGORIES if row["transaction_type"] == "Expense" else TRANSFER_CREDIT_CATEGORIES
            if row["category"] not in categories:
                continue
            ref = re.sub(r"[^A-Z0-9]", "", row["reference_no"].upper())
            if len(ref) >= 8 and any(char.isdigit() for char in ref) and len(set(ref)) > 2:
                candidates[(ref, round(row["amount"] * 100))].append(row)

        group_id = _next_transfer_group(conn)
        count = 0
        for rows in candidates.values():
            if len(rows) != 2 or not any(in_scope(row) for row in rows):
                continue
            left, right = rows
            if _transfer_pair_valid(left, right) and _date_diff_days(left["transaction_date"], right["transaction_date"]) <= TRANSFER_MAX_DAY_GAP:
                _link_transfer_pair(conn, left["transaction_id"], right["transaction_id"], group_id + count)
                count += 1
        return count, count * 2


def add_transaction(account_id: int, person_id: int, transaction_date: str,
                    transaction_type: str, amount: float,
                    category: str = None, mode: str = None,
                    description: str = None, balance_after: float = None,
                    reference_no: str = None,
                    deposit_account_no: str = None,
                    source: str = "Manual") -> int:
    """Insert a transaction. Returns new transaction_id."""
    txn_type = normalize_transaction_type(transaction_type)
    conn = get_connection()
    cur = conn.execute("""
        INSERT INTO Transactions
            (account_id, person_id, transaction_date, transaction_type,
                         category, mode, amount, reference_no, description, deposit_account_no, balance_after, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (account_id, person_id, transaction_date, txn_type,
                    category, mode, amount, reference_no, description, deposit_account_no, balance_after, source))
    conn.commit()
    txn_id = cur.lastrowid
    conn.close()
    return txn_id


def add_transactions_batch(account_id: int, person_id: int, transactions: list[dict], source: str = "Statement Import") -> list[int]:
    """Insert multiple transactions in a single DB transaction. Returns list of new ids.

    Each item in `transactions` should be a dict with keys: transaction_date, transaction_type, amount,
    category, mode, description, reference_no, deposit_account_no, balance_after (optional).
    """
    conn = get_connection()
    ids = []
    try:
        for txn in transactions:
            txn_type = normalize_transaction_type(txn.get("transaction_type"))
            cur = conn.execute(
                """
                INSERT INTO Transactions
                    (account_id, person_id, transaction_date, transaction_type,
                                 category, mode, amount, reference_no, description, deposit_account_no, balance_after, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    account_id, person_id, txn.get("transaction_date"), txn_type,
                    txn.get("category"), txn.get("mode"), txn.get("amount"), txn.get("reference_no"),
                    txn.get("description"), txn.get("deposit_account_no"), txn.get("balance_after"), source
                )
            )
            ids.append(cur.lastrowid)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return ids


def _detach_transaction_refs(conn, ids: list[int]) -> None:
    """Detach transaction references from related tables before deletion."""
    if not ids:
        return

    placeholders = ",".join(["?"] * len(ids))

    conn.execute(f"""
        UPDATE Transactions
        SET linked_transaction_id=NULL, internal_transfer_group_id=NULL, is_internal_transfer=0
        WHERE linked_transaction_id IN ({placeholders})
    """, ids)

    conn.execute(f"""
        UPDATE FixedDeposit
        SET linked_transaction_id=NULL
        WHERE linked_transaction_id IN ({placeholders})
    """, ids)

    conn.execute(f"""
        UPDATE FixedDeposit
        SET source_transaction_id=NULL
        WHERE source_transaction_id IN ({placeholders})
    """, ids)

    conn.execute(f"""
        UPDATE IncomeExpectation
        SET actual_transaction_id=NULL
        WHERE actual_transaction_id IN ({placeholders})
    """, ids)


def delete_transactions_by_ids(ids: list[int]) -> None:
    if not ids:
        return
    conn = get_connection()
    try:
        _detach_transaction_refs(conn, ids)
        q = f"DELETE FROM Transactions WHERE transaction_id IN ({','.join(['?']*len(ids))})"
        conn.execute(q, ids)
        conn.commit()
    finally:
        conn.close()


def get_transactions(account_id: int = None, person_id: int = None,
                     financial_year: str = None,
                     transaction_type: str = None) -> list[dict]:
    """
    Fetch transactions with optional filters.
    financial_year: e.g. '2024-25' → filters by date range Apr–Mar.
    """
    query  = """
        SELECT t.*, ba.bank_name,
               COALESCE(NULLIF(b.nickname, ''), ba.bank_name) AS bank_display_name,
               p.full_name AS person_name
        FROM Transactions t
        JOIN BankAccount ba ON t.account_id = ba.account_id
        LEFT JOIN Bank b ON b.bank_id = (
            SELECT bank_id FROM Bank WHERE lower(bank_name) = lower(ba.bank_name)
            ORDER BY bank_id LIMIT 1
        )
        JOIN Person p ON t.person_id = p.person_id
        WHERE 1=1
    """
    params = []

    if account_id is not None:
        query += " AND t.account_id = ?"
        params.append(account_id)

    if person_id is not None:
        query += " AND t.person_id = ?"
        params.append(person_id)

    if financial_year:
        start, end = fy_date_range(financial_year)
        query += " AND t.transaction_date BETWEEN ? AND ?"
        params.extend([start.isoformat(), end.isoformat()])

    if transaction_type:
        transaction_type = normalize_transaction_type(transaction_type)
        query += " AND t.transaction_type = ?"
        params.append(transaction_type)

    query += " ORDER BY t.transaction_date DESC, t.transaction_id DESC"

    conn = get_connection()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_transaction(transaction_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM Transactions WHERE transaction_id = ?", (transaction_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_transaction(transaction_id: int, transaction_date: str,
                       transaction_type: str, amount: float,
                       category: str = None, mode: str = None,
                       description: str = None,
                       reference_no: str = None,
                       balance_after: float | None = None,
                       account_id: int = None,
                       person_id: int = None) -> None:
    txn_type = normalize_transaction_type(transaction_type)

    # Build SET clause dynamically
    set_clauses = [
        "transaction_date = ?",
        "transaction_type = ?",
        "amount = ?",
        "category = ?",
        "mode = ?",
        "description = ?",
        "reference_no = ?",
        "balance_after = ?"
    ]
    params = [
        transaction_date, txn_type, amount,
        category, mode, description, reference_no, balance_after
    ]

    if account_id is not None:
        set_clauses.append("account_id = ?")
        params.append(account_id)

    if person_id is not None:
        set_clauses.append("person_id = ?")
        params.append(person_id)

    params.append(transaction_id)

    with closing(get_connection()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        original = conn.execute(
            "SELECT transaction_date FROM Transactions WHERE transaction_id = ?", (transaction_id,),
        ).fetchone()
        if original is None:
            return
        conn.execute(f"""
            UPDATE Transactions
            SET {', '.join(set_clauses)}
            WHERE transaction_id = ?
        """, params)
        updated = conn.execute(
            "SELECT * FROM Transactions WHERE transaction_id = ?", (transaction_id,),
        ).fetchone()
        if updated is None:
            return
        linked_id = updated["linked_transaction_id"]
        if linked_id is not None:
            try:
                _get_transfer_pair(conn, transaction_id, linked_id)
            except ValueError:
                _clear_transfer_pair(conn, transaction_id)
        conn.execute("""
            UPDATE IncomeExpectation SET actual_transaction_id = NULL
            WHERE actual_transaction_id = ?
              AND (account_id <> ? OR person_id <> ? OR ? <> 'Income' OR ? <= 0
                OR ? IN ('Internal Transfer', 'FD Maturity') OR ? <> 0 OR ? <> ?)
        """, (transaction_id, updated["account_id"], updated["person_id"], txn_type, amount,
              category, updated["is_internal_transfer"] or 0, original["transaction_date"], transaction_date))


def delete_transaction(transaction_id: int) -> None:
    delete_transactions_by_ids([transaction_id])


# ── Summary Queries ───────────────────────────────────────────────────────────

def get_income_total(person_id: int = None, financial_year: str = None,
                     category: str = None, account_id: int = None) -> float:
    return _sum_by_type("Income", person_id, financial_year, category, account_id)


def get_expense_total(person_id: int = None, financial_year: str = None,
                      category: str = None, account_id: int = None) -> float:
    return _sum_by_type("Expense", person_id, financial_year, category, account_id)


def _sum_by_type(txn_type: str, person_id: int = None,
                 financial_year: str = None, category: str = None,
                 account_id: int = None) -> float:
    query  = (
        "SELECT SUM(amount) AS total FROM Transactions "
        "WHERE transaction_type = ? AND COALESCE(is_internal_transfer, 0) = 0"
    )
    params = [txn_type]

    if person_id:
        query += " AND person_id = ?"
        params.append(person_id)

    if account_id:
        query += " AND account_id = ?"
        params.append(account_id)

    if financial_year:
        start, end = fy_date_range(financial_year)
        query += " AND transaction_date BETWEEN ? AND ?"
        params.extend([start.isoformat(), end.isoformat()])

    if category:
        query += " AND category = ?"
        params.append(category)

    conn = get_connection()
    row = conn.execute(query, params).fetchone()
    conn.close()
    return row["total"] or 0.0


def get_category_summary(person_id: int = None,
                         financial_year: str = None,
                         account_id: int = None) -> list[dict]:
    """Return per-category totals for the Expense type."""
    query  = """
        SELECT category, SUM(amount) AS total
        FROM Transactions
        WHERE transaction_type = 'Expense'
                    AND COALESCE(is_internal_transfer, 0) = 0
    """
    params = []

    if person_id:
        query += " AND person_id = ?"
        params.append(person_id)

    if account_id:
        query += " AND account_id = ?"
        params.append(account_id)

    if financial_year:
        start, end = fy_date_range(financial_year)
        query += " AND transaction_date BETWEEN ? AND ?"
        params.extend([start.isoformat(), end.isoformat()])

    query += " GROUP BY category ORDER BY total DESC"

    conn = get_connection()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_transactions_by_account(account_id: int, start_date: str = None,
                                end_date: str = None) -> list[dict]:
    """Get transactions for an account within date range."""
    query = "SELECT * FROM Transactions WHERE account_id = ?"
    params = [account_id]

    if start_date:
        query += " AND transaction_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND transaction_date <= ?"
        params.append(end_date)

    query += " ORDER BY transaction_date, transaction_id"

    conn = get_connection()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def check_duplicate(account_id: int, transaction_date: str,
                    amount: float, description: str,
                    transaction_type: str | None = None,
                    reference_no: str | None = None,
                    balance_after: float | None = None) -> bool:
    """Duplicate check for statement imports."""
    filters = ["account_id = ?", "transaction_date = ?", "amount = ?"]
    params = [account_id, transaction_date, amount]

    if description is not None:
        filters.append("description = ?")
        params.append(description)

    if transaction_type:
        filters.append("transaction_type = ?")
        params.append(normalize_transaction_type(transaction_type))

    if reference_no:
        filters.append("reference_no = ?")
        params.append(reference_no)

    if balance_after is not None:
        filters.append("balance_after = ?")
        params.append(balance_after)

    conn = get_connection()
    row = conn.execute(
        f"SELECT COUNT(*) AS cnt FROM Transactions WHERE {' AND '.join(filters)}",
        params,
    ).fetchone()
    conn.close()
    return row["cnt"] > 0


def get_account_transactions_for_balance(account_id: int) -> list[dict]:
    """Get all transactions for an account in chronological order for balance calculation."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT transaction_id, transaction_type, amount, transaction_date, balance_after, source
        FROM Transactions
        WHERE account_id = ?
        ORDER BY transaction_date ASC, transaction_id ASC
    """, (account_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def set_transaction_balances(pairs: list[tuple[float, int]]) -> None:
    """Update balance_after for multiple transactions in a single transaction."""
    if not pairs:
        return
    conn = get_connection()
    try:
        for balance_after, transaction_id in pairs:
            conn.execute(
                "UPDATE Transactions SET balance_after = ? WHERE transaction_id = ?",
                (balance_after, transaction_id)
            )
        conn.commit()
    finally:
        conn.close()


def get_balance_points(account_id: int, start_date: str = None, end_date: str = None) -> list[dict]:
    """Get balance history points for an account, optionally filtered by date range."""
    query = """
        SELECT transaction_date AS date, balance_after AS balance
        FROM Transactions
        WHERE account_id = ?
    """
    params = [account_id]

    if start_date:
        query += " AND transaction_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND transaction_date <= ?"
        params.append(end_date)

    query += " ORDER BY transaction_date ASC, transaction_id ASC"

    conn = get_connection()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def backfill_deposit_account_numbers(conn=None) -> int:
    """
    Backfill deposit_account_no on existing transactions with NULL values.
    Extracts from the description field using the same logic as statement parsing.
    Idempotent: running multiple times will not duplicate or corrupt data.

    Returns the number of transactions updated.
    """
    from engines.statement.assemble import normalize_account_no

    owns_connection = conn is None
    if conn is None:
        conn = get_connection()
    try:
        # Get all transactions with NULL deposit_account_no but non-null description
        rows = conn.execute("""
            SELECT transaction_id, description
            FROM Transactions
            WHERE deposit_account_no IS NULL
              AND description IS NOT NULL
              AND description != ''
        """).fetchall()

        updated = 0
        for row in rows:
            transaction_id = row[0]
            description = row[1]

            # Extract account number from description
            account_no = normalize_account_no(description)

            if account_no:
                conn.execute("""
                    UPDATE Transactions
                    SET deposit_account_no = ?
                    WHERE transaction_id = ?
                """, (account_no, transaction_id))
                updated += 1

        if owns_connection:
            conn.commit()
        return updated
    finally:
        if owns_connection:
            conn.close()
