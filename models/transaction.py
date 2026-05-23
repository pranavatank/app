"""
models/transaction.py — CRUD for the Transactions table.
"""

import re
from datetime import datetime

from core.database import get_connection
from config import fy_date_range


INTERNAL_TRANSFER_CATEGORY = "Internal Transfer"

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
        return "Credit"
    if canon == "Expense":
        return "Debit"
    return canon


def _norm_text(value: str | None) -> str:
    return (value or "").strip().lower()


def _digits(value: str | None) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def _date_diff_days(d1: str, d2: str) -> int:
    try:
        dt1 = datetime.fromisoformat(d1).date()
        dt2 = datetime.fromisoformat(d2).date()
        return abs((dt1 - dt2).days)
    except Exception:
        return 999


def _transfer_like(txn: dict) -> bool:
    blob = " ".join([
        _norm_text(txn.get("mode")),
        _norm_text(txn.get("category")),
        _norm_text(txn.get("description")),
        _norm_text(txn.get("reference_no")),
    ])
    keys = ["transfer", "trf", "neft", "rtgs", "imps", "upi", "utr", "ib", "fund", "a/c", "account"]
    return any(k in blob for k in keys)


def _person_tokens(txn: dict) -> set[str]:
    raw = " ".join([
        _norm_text(txn.get("person_name")),
        _norm_text(txn.get("first_name")),
        _norm_text(txn.get("middle_name")),
        _norm_text(txn.get("last_name")),
    ])
    return {t for t in re.split(r"\W+", raw) if len(t) >= 3}


def _account_digits_tokens(txn: dict) -> set[str]:
    tokens = set()
    full_no = _digits(txn.get("account_number_full"))
    masked = _digits(txn.get("account_number_masked"))
    if len(full_no) >= 4:
        tokens.add(full_no[-4:])
    if len(masked) >= 4:
        tokens.add(masked[-4:])
    return tokens


def _counterparty_signal(a: dict, b: dict) -> tuple[int, bool]:
    score = 0
    clue = False

    a_ref = _norm_text(a.get("reference_no"))
    b_ref = _norm_text(b.get("reference_no"))
    a_blob = " ".join([_norm_text(a.get("description")), a_ref])
    b_blob = " ".join([_norm_text(b.get("description")), b_ref])

    if a_ref and b_ref and a_ref == b_ref:
        score += 8
        clue = True
    elif (a_ref and a_ref in b_blob) or (b_ref and b_ref in a_blob):
        score += 4
        clue = True

    for token in _person_tokens(a):
        if token in b_blob:
            score += 1
            clue = True
    for token in _person_tokens(b):
        if token in a_blob:
            score += 1
            clue = True

    for code in [_norm_text(a.get("ifsc_code")), _norm_text(b.get("ifsc_code"))]:
        if code and (code in a_blob or code in b_blob):
            score += 3
            clue = True

    for bank in [_norm_text(a.get("bank_name")), _norm_text(b.get("bank_name"))]:
        if bank and (bank in a_blob or bank in b_blob):
            score += 2
            clue = True

    for d in _account_digits_tokens(a):
        if d and d in b_blob:
            score += 2
            clue = True
    for d in _account_digits_tokens(b):
        if d and d in a_blob:
            score += 2
            clue = True

    return score, clue


def reprocess_internal_transfers(account_id: int = None, person_id: int = None,
                                 financial_year: str = None) -> tuple[int, int]:
    """Auto-link likely internal transfer pairs and mark them as Internal Transfer.

    Returns: (pairs_linked, transactions_marked)
    """
    conn = get_connection()

    filters = []
    filters_for_update = []
    params = []
    if account_id is not None:
        filters.append("t.account_id = ?")
        filters_for_update.append("account_id = ?")
        params.append(account_id)
    if person_id is not None:
        filters.append("t.person_id = ?")
        filters_for_update.append("person_id = ?")
        params.append(person_id)
    if financial_year:
        start, end = fy_date_range(financial_year)
        filters.append("t.transaction_date BETWEEN ? AND ?")
        filters_for_update.append("transaction_date BETWEEN ? AND ?")
        params.extend([start.isoformat(), end.isoformat()])

    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    where_update = f"WHERE {' AND '.join(filters_for_update)}" if filters_for_update else ""

    # Reset previously auto-marked links in the selected scope.
    conn.execute(f"""
        UPDATE Transactions
        SET linked_transaction_id = NULL,
            internal_transfer_group_id = NULL,
            is_internal_transfer = 0,
            category = CASE WHEN category = ? THEN NULL ELSE category END
        {where_update}
    """, (INTERNAL_TRANSFER_CATEGORY, *params))

    rows = conn.execute(f"""
        SELECT
            t.transaction_id, t.account_id, t.person_id, t.transaction_date,
            t.transaction_type, t.amount, t.mode, t.category, t.reference_no,
            t.description,
            p.full_name AS person_name, p.first_name, p.middle_name, p.last_name,
            ba.bank_name, ba.ifsc_code, ba.account_holder_name,
            ba.account_number_masked, ba.account_number_full
        FROM Transactions t
        JOIN Person p ON p.person_id = t.person_id
        JOIN BankAccount ba ON ba.account_id = t.account_id
        {where}
        ORDER BY t.transaction_date, t.transaction_id
    """, params).fetchall()

    txns = [dict(r) for r in rows]
    debits = [
        t for t in txns
        if t.get("transaction_type") == "Expense" and _transfer_like(t)
    ]
    credits = [
        t for t in txns
        if t.get("transaction_type") == "Income"
    ]

    used = set()
    pairs = []
    for d in debits:
        best = None
        best_score = -1
        candidate_count = 0
        best_has_clue = False
        for c in credits:
            if c["transaction_id"] in used:
                continue
            if d["account_id"] == c["account_id"]:
                continue
            if abs(float(d["amount"]) - float(c["amount"])) > 0.01:
                continue
            day_gap = _date_diff_days(d["transaction_date"], c["transaction_date"])
            if day_gap > 2:
                continue
            candidate_count += 1

            score = 3 if day_gap == 0 else 2 if day_gap == 1 else 1
            clue_score, has_clue = _counterparty_signal(d, c)
            score += clue_score
            if score > best_score:
                best_score = score
                best = c
                best_has_clue = has_clue

        # Accept either a high-confidence clue-based match, or a unique exact-day amount match.
        if best is not None and (
            (best_has_clue and best_score >= 5)
            or (not best_has_clue and candidate_count == 1 and best_score >= 3)
        ):
            used.add(best["transaction_id"])
            pairs.append((d, best))

    if not pairs:
        conn.commit()
        conn.close()
        return 0, 0

    group_row = conn.execute(
        "SELECT COALESCE(MAX(internal_transfer_group_id), 0) AS g FROM Transactions"
    ).fetchone()
    next_group = int(group_row["g"] or 0) + 1

    for d, c in pairs:
        gid = next_group
        next_group += 1
        conn.execute("""
            UPDATE Transactions
            SET linked_transaction_id = ?,
                internal_transfer_group_id = ?,
                is_internal_transfer = 1,
                category = ?
            WHERE transaction_id = ?
        """, (c["transaction_id"], gid, INTERNAL_TRANSFER_CATEGORY, d["transaction_id"]))
        conn.execute("""
            UPDATE Transactions
            SET linked_transaction_id = ?,
                internal_transfer_group_id = ?,
                is_internal_transfer = 1,
                category = ?
            WHERE transaction_id = ?
        """, (d["transaction_id"], gid, INTERNAL_TRANSFER_CATEGORY, c["transaction_id"]))

    conn.commit()
    conn.close()
    return len(pairs), len(pairs) * 2


def add_transaction(account_id: int, person_id: int, transaction_date: str,
                    transaction_type: str, amount: float,
                    category: str = None, mode: str = None,
                    description: str = None, balance_after: float = None,
                    reference_no: str = None,
                    source: str = "Manual") -> int:
    """Insert a transaction. Returns new transaction_id."""
    txn_type = normalize_transaction_type(transaction_type)
    conn = get_connection()
    cur = conn.execute("""
        INSERT INTO Transactions
            (account_id, person_id, transaction_date, transaction_type,
                         category, mode, amount, reference_no, description, balance_after, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (account_id, person_id, transaction_date, txn_type,
                    category, mode, amount, reference_no, description, balance_after, source))
    conn.commit()
    txn_id = cur.lastrowid
    conn.close()
    return txn_id


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
    conn.execute(
        "DELETE FROM Transactions WHERE transaction_id = ?", (transaction_id,)
    )
    conn.commit()
    conn.close()


# ── Summary Queries ───────────────────────────────────────────────────────────

def get_income_total(person_id: int = None, financial_year: str = None, category: str = None) -> float:
    return _sum_by_type("Income", person_id, financial_year, category)


def get_expense_total(person_id: int = None, financial_year: str = None, category: str = None) -> float:
    return _sum_by_type("Expense", person_id, financial_year, category)


def _sum_by_type(txn_type: str, person_id: int = None,
                 financial_year: str = None, category: str = None) -> float:
    query  = (
        "SELECT SUM(amount) AS total FROM Transactions "
        "WHERE transaction_type = ? AND COALESCE(is_internal_transfer, 0) = 0"
    )
    params = [txn_type]

    if person_id:
        query += " AND person_id = ?"
        params.append(person_id)

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
                         financial_year: str = None) -> list[dict]:
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
