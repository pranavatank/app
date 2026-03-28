"""
models/fixed_deposit.py — CRUD for the FixedDeposit table.
"""

from typing import Optional

from core.database import get_connection


def add_fd(account_id: int, person_id: int, principal_amount: float,
           start_date: str, tenure_months: int, interest_rate: float,
           compounding_type: str, maturity_date: str,
           maturity_amount: float) -> int:
    """Insert a Fixed Deposit record. Returns new fd_id."""
    conn = get_connection()
    cur = conn.execute("""
        INSERT INTO FixedDeposit
            (account_id, person_id, principal_amount, start_date,
             tenure_months, interest_rate, compounding_type,
             maturity_date, maturity_amount, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Active')
    """, (account_id, person_id, principal_amount, start_date,
          tenure_months, interest_rate, compounding_type,
          maturity_date, maturity_amount))
    conn.commit()
    fd_id = cur.lastrowid
    conn.close()
    return fd_id


def fd_exists_for_statement(account_id: int, person_id: int,
                            principal_amount: float, start_date: str) -> bool:
    """Best-effort duplicate check for statement-created FD entries."""
    conn = get_connection()
    row = conn.execute("""
        SELECT COUNT(*) AS cnt
        FROM FixedDeposit
        WHERE account_id = ?
          AND person_id = ?
          AND principal_amount = ?
          AND start_date = ?
          AND status IN ('Active', 'Pending Details')
    """, (account_id, person_id, principal_amount, start_date)).fetchone()
    conn.close()
    return row["cnt"] > 0


def add_fd_from_statement(account_id: int, person_id: int, principal_amount: float,
                          start_date: str,
                          tenure_months: Optional[int] = None,
                          interest_rate: Optional[float] = None,
                          compounding_type: Optional[str] = None,
                          maturity_date: Optional[str] = None,
                          maturity_amount: Optional[float] = None,
                          source_description: Optional[str] = None) -> int:
    """
    Insert an FD inferred from statement narration.
    Unknown details remain NULL by design and can be filled later.
    Returns fd_id, or 0 if a likely duplicate already exists.
    """
    if fd_exists_for_statement(account_id, person_id, principal_amount, start_date):
        return 0

    conn = get_connection()
    cur = conn.execute("""
        INSERT INTO FixedDeposit
            (account_id, person_id, principal_amount, start_date,
             tenure_months, interest_rate, compounding_type,
             maturity_date, maturity_amount, status, source_description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        account_id,
        person_id,
        principal_amount,
        start_date,
        tenure_months,
        interest_rate,
        compounding_type,
        maturity_date,
        maturity_amount,
        "Pending Details",
        (source_description or "")[:500],
    ))
    conn.commit()
    fd_id = cur.lastrowid
    conn.close()
    return fd_id


def get_all_fds(person_id: int = None, status: str = None) -> list[dict]:
    """Return FDs with optional person and status filters."""
    query  = """
        SELECT fd.*, ba.bank_name, p.full_name AS person_name
        FROM FixedDeposit fd
        JOIN BankAccount ba ON fd.account_id = ba.account_id
        JOIN Person p ON fd.person_id = p.person_id
        WHERE 1=1
    """
    params = []
    if person_id:
        query += " AND fd.person_id = ?"
        params.append(person_id)
    if status:
        query += " AND fd.status = ?"
        params.append(status)
    query += " ORDER BY fd.maturity_date"

    conn = get_connection()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_fd(fd_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM FixedDeposit WHERE fd_id = ?", (fd_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_fd_status(fd_id: int, status: str) -> None:
    """Update FD status: Active / Matured / Closed."""
    conn = get_connection()
    conn.execute(
        "UPDATE FixedDeposit SET status = ? WHERE fd_id = ?", (status, fd_id)
    )
    conn.commit()
    conn.close()


def update_fd(fd_id: int, principal_amount: float, start_date: str,
              tenure_months: int, interest_rate: float,
              compounding_type: str, maturity_date: str,
              maturity_amount: float, status: str) -> None:
    conn = get_connection()
    conn.execute("""
        UPDATE FixedDeposit
        SET principal_amount = ?, start_date = ?, tenure_months = ?,
            interest_rate = ?, compounding_type = ?, maturity_date = ?,
            maturity_amount = ?, status = ?
        WHERE fd_id = ?
    """, (principal_amount, start_date, tenure_months, interest_rate,
          compounding_type, maturity_date, maturity_amount, status, fd_id))
    conn.commit()
    conn.close()


def delete_fd(fd_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM FixedDeposit WHERE fd_id = ?", (fd_id,))
    conn.commit()
    conn.close()
