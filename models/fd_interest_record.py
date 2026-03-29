"""
models/fd_interest_record.py — CRUD for FDInterestRecord table.
"""

from core.database import get_connection


def upsert_fd_interest(fd_id: int, financial_year: str,
                       interest_earned: float, assessment_year: str) -> None:
    """Insert or replace an FD interest record for a given FY."""
    conn = get_connection()
    conn.execute(
        "DELETE FROM FDInterestRecord WHERE fd_id = ? AND financial_year = ?",
        (fd_id, financial_year)
    )
    conn.execute("""
        INSERT INTO FDInterestRecord
            (fd_id, financial_year, interest_earned, assessment_year)
        VALUES (?, ?, ?, ?)
    """, (fd_id, financial_year, interest_earned, assessment_year))
    conn.commit()
    conn.close()


def get_fd_interest_by_fy(financial_year: str,
                           person_id: int = None) -> list[dict]:
    """Return FD interest records for a FY, optionally filtered by person."""
    query = """
        SELECT fir.*, fd.principal_amount, fd.interest_rate,
               p.full_name AS person_name, ba.bank_name
        FROM FDInterestRecord fir
        JOIN FixedDeposit fd ON fir.fd_id = fd.fd_id
        JOIN Person p ON fd.person_id = p.person_id
        JOIN BankAccount ba ON fd.account_id = ba.account_id
        WHERE fir.financial_year = ?
    """
    params = [financial_year]
    if person_id:
        query += " AND fd.person_id = ?"
        params.append(person_id)

    conn = get_connection()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_total_fd_interest(financial_year: str,
                          person_id: int = None) -> float:
    """Sum of FD interest for a FY."""
    query  = """
        SELECT SUM(fir.interest_earned) AS total
        FROM FDInterestRecord fir
        JOIN FixedDeposit fd ON fir.fd_id = fd.fd_id
        WHERE fir.financial_year = ?
    """
    params = [financial_year]
    if person_id:
        query += " AND fd.person_id = ?"
        params.append(person_id)

    conn = get_connection()
    row = conn.execute(query, params).fetchone()
    conn.close()
    return row["total"] or 0.0


def delete_fd_interest_records(fd_id: int) -> None:
    conn = get_connection()
    conn.execute(
        "DELETE FROM FDInterestRecord WHERE fd_id = ?", (fd_id,)
    )
    conn.commit()
    conn.close()
