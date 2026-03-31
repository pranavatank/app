"""
models/transaction.py — CRUD for the Transactions table.
"""

from core.database import get_connection
from config import fy_date_range


def add_transaction(account_id: int, person_id: int, transaction_date: str,
                    transaction_type: str, amount: float,
                    category: str = None, mode: str = None,
                    description: str = None, balance_after: float = None,
                    source: str = "Manual") -> int:
    """Insert a transaction. Returns new transaction_id."""
    conn = get_connection()
    cur = conn.execute("""
        INSERT INTO Transactions
            (account_id, person_id, transaction_date, transaction_type,
             category, mode, amount, description, balance_after, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (account_id, person_id, transaction_date, transaction_type,
          category, mode, amount, description, balance_after, source))
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
        SELECT t.*, ba.bank_name, p.full_name AS person_name
        FROM Transactions t
        JOIN BankAccount ba ON t.account_id = ba.account_id
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
                       description: str = None) -> None:
    conn = get_connection()
    conn.execute("""
        UPDATE Transactions
        SET transaction_date = ?, transaction_type = ?, amount = ?,
            category = ?, mode = ?, description = ?
        WHERE transaction_id = ?
    """, (transaction_date, transaction_type, amount,
          category, mode, description, transaction_id))
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
    query  = "SELECT SUM(amount) AS total FROM Transactions WHERE transaction_type = ?"
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
                    amount: float, description: str) -> bool:
    """Simple duplicate check for statement imports."""
    conn = get_connection()
    row = conn.execute("""
        SELECT COUNT(*) AS cnt FROM Transactions
        WHERE account_id = ? AND transaction_date = ?
          AND amount = ? AND description = ?
    """, (account_id, transaction_date, amount, description)).fetchone()
    conn.close()
    return row["cnt"] > 0
