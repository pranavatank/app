"""
models/transaction.py — CRUD for the Transactions table.
"""

import re
from datetime import datetime

from core.database import get_connection
from config import fy_date_range


INTERNAL_TRANSFER_CATEGORY = "Internal Transfer"
TRANSFER_CREDIT_CATEGORIES = {"Other Income", INTERNAL_TRANSFER_CATEGORY, None, ""}
TRANSFER_DEBIT_CATEGORIES = {"Other Expense", INTERNAL_TRANSFER_CATEGORY, None, ""}
TRANSFER_MAX_DAY_GAP = 2
_FD_NARRATION = re.compile(r"REDEEM|\bFD\b|/FD/|PAYIN")

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


def _load_transfer_rows(conn, person_id=None, financial_year=None) -> tuple[list[dict], dict[int, str]]:
    """Load transaction rows for transfer detection with owner name mapping.

    Returns: (list of transaction dicts, dict mapping person_id to full_name)
    """
    filters = []
    params = []

    if person_id is not None:
        filters.append("t.person_id = ?")
        params.append(person_id)

    if financial_year:
        start, end = fy_date_range(financial_year)
        filters.append("t.transaction_date BETWEEN ? AND ?")
        params.extend([start.isoformat(), end.isoformat()])

    where = f"WHERE {' AND '.join(filters)}" if filters else ""

    rows = conn.execute(f"""
        SELECT
            t.transaction_id, t.account_id, t.person_id, t.transaction_date,
            t.transaction_type, t.amount, t.category, t.description,
            p.full_name
        FROM Transactions t
        JOIN Person p ON p.person_id = t.person_id
        {where}
        ORDER BY t.transaction_date, t.transaction_id
    """, params).fetchall()

    txns = [dict(r) for r in rows]
    owner_names = {}
    for r in rows:
        owner_names[r["person_id"]] = r["full_name"]

    return txns, owner_names


def find_internal_transfers(txns: list[dict], owner_names: dict[int, str]) -> tuple[list[tuple[int, int]], list[int]]:
    """Find internal transfer pairs and self-transfers.

    Returns: (list of (debit_txn_id, credit_txn_id) pairs, list of self-credit transaction ids)
    """
    debits = [
        t for t in txns
        if t.get("transaction_type") == "Expense" and t.get("category") in TRANSFER_DEBIT_CATEGORIES
    ]
    credits = [
        t for t in txns
        if t.get("transaction_type") == "Income" and t.get("category") in TRANSFER_CREDIT_CATEGORIES
    ]

    pairs = []
    used_credits = set()

    for d in debits:
        candidates = []
        for c in credits:
            if c["transaction_id"] in used_credits:
                continue
            if d["account_id"] == c["account_id"]:
                continue
            if abs(float(d["amount"]) - float(c["amount"])) > 0.01:
                continue
            day_gap = _date_diff_days(d["transaction_date"], c["transaction_date"])
            if day_gap > TRANSFER_MAX_DAY_GAP:
                continue
            candidates.append(c)

        if len(candidates) == 1:
            c = candidates[0]
            cluster_debits = [
                t for t in debits
                if abs(float(t["amount"]) - float(c["amount"])) <= 0.01
                and _date_diff_days(t["transaction_date"], c["transaction_date"]) <= TRANSFER_MAX_DAY_GAP
            ]
            cluster_credits = [
                t for t in credits
                if t["transaction_id"] not in used_credits
                and abs(float(t["amount"]) - float(d["amount"])) <= 0.01
                and _date_diff_days(t["transaction_date"], d["transaction_date"]) <= TRANSFER_MAX_DAY_GAP
            ]

            if len(cluster_debits) == 1 and len(cluster_credits) == 1:
                pairs.append((d["transaction_id"], c["transaction_id"]))
                used_credits.add(c["transaction_id"])

    self_credit_ids = []
    for c in credits:
        if c["transaction_id"] not in used_credits:
            person_id = c["person_id"]
            if person_id in owner_names:
                full_name = owner_names[person_id]
                tokens = [t for t in re.split(r"\W+", full_name.upper()) if t]
                if len(tokens) >= 2:
                    key = tokens[0] + tokens[1][:4]
                    if len(key) >= 8:
                        desc_upper = (c.get("description") or "").upper()
                        desc_clean = re.sub(r"[^A-Z0-9]", "", desc_upper)
                        if key in desc_clean and not _FD_NARRATION.search(desc_upper):
                            self_credit_ids.append(c["transaction_id"])

    return pairs, self_credit_ids


def reprocess_internal_transfers(person_id: int = None, financial_year: str = None) -> tuple[int, int]:
    """Auto-link internal transfer pairs and mark self-transfers.

    Returns: (pairs_linked, transactions_marked)
    """
    conn = get_connection()

    filters_for_update = []
    params = []
    if person_id is not None:
        filters_for_update.append("person_id = ?")
        params.append(person_id)
    if financial_year:
        start, end = fy_date_range(financial_year)
        filters_for_update.append("transaction_date BETWEEN ? AND ?")
        params.extend([start.isoformat(), end.isoformat()])

    where_update = f"WHERE {' AND '.join(filters_for_update)}" if filters_for_update else ""

    conn.execute(f"""
        UPDATE Transactions
        SET linked_transaction_id = NULL,
            internal_transfer_group_id = NULL,
            is_internal_transfer = 0
        {where_update}
    """, params)

    txns, owner_names = _load_transfer_rows(conn, person_id=person_id, financial_year=financial_year)
    pairs, self_credit_ids = find_internal_transfers(txns, owner_names)

    if not pairs and not self_credit_ids:
        conn.commit()
        conn.close()
        return 0, 0

    group_row = conn.execute(
        "SELECT COALESCE(MAX(internal_transfer_group_id), 0) AS g FROM Transactions"
    ).fetchone()
    next_group = int(group_row["g"] or 0) + 1

    for debit_id, credit_id in pairs:
        gid = next_group
        next_group += 1
        conn.execute("""
            UPDATE Transactions
            SET linked_transaction_id = ?,
                internal_transfer_group_id = ?,
                is_internal_transfer = 1
            WHERE transaction_id = ?
        """, (credit_id, gid, debit_id))
        conn.execute("""
            UPDATE Transactions
            SET linked_transaction_id = ?,
                internal_transfer_group_id = ?,
                is_internal_transfer = 1
            WHERE transaction_id = ?
        """, (debit_id, gid, credit_id))

    for txn_id in self_credit_ids:
        conn.execute("""
            UPDATE Transactions
            SET is_internal_transfer = 1
            WHERE transaction_id = ?
        """, (txn_id,))

    conn.commit()
    conn.close()
    return len(pairs), len(pairs) * 2 + len(self_credit_ids)


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
        LEFT JOIN Bank b ON lower(b.bank_name) = lower(ba.bank_name)
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
                       balance_after: float | None = None) -> None:
    txn_type = normalize_transaction_type(transaction_type)
    conn = get_connection()
    conn.execute("""
        UPDATE Transactions
        SET transaction_date = ?, transaction_type = ?, amount = ?,
                        category = ?, mode = ?, description = ?,
                        reference_no = ?, balance_after = ?
        WHERE transaction_id = ?
    """, (transaction_date, txn_type, amount,
                    category, mode, description, reference_no, balance_after, transaction_id))
    conn.commit()
    conn.close()


def delete_transaction(transaction_id: int) -> None:
    conn = get_connection()
    _detach_transaction_refs(conn, [transaction_id])
    conn.execute(
        "DELETE FROM Transactions WHERE transaction_id = ?", (transaction_id,)
    )
    conn.commit()
    conn.close()


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
    
    query += " ORDER BY transaction_date"
    
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
        SELECT transaction_id, transaction_type, amount, transaction_date
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

    query += " ORDER BY transaction_date ASC"

    conn = get_connection()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def backfill_deposit_account_numbers() -> int:
    """
    Backfill deposit_account_no on existing transactions with NULL values.
    Extracts from the description field using the same logic as statement parsing.
    Idempotent: running multiple times will not duplicate or corrupt data.

    Returns the number of transactions updated.
    """
    from engines.statement.assemble import normalize_account_no

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

        conn.commit()
        return updated
    finally:
        conn.close()
