"""
models/savings_interest.py — CRUD for SavingsInterestRecord table.
"""

from core.database import get_connection


def upsert_savings_interest(account_id: int, financial_year: str,
                             avg_monthly_balance: float,
                             interest_rate: float,
                             interest_earned: float) -> None:
    """Insert or update a savings interest record for an account and FY."""
    conn = get_connection()
    existing = conn.execute("""
        SELECT record_id FROM SavingsInterestRecord
        WHERE account_id = ? AND financial_year = ?
    """, (account_id, financial_year)).fetchone()

    if existing:
        conn.execute("""
            UPDATE SavingsInterestRecord
            SET avg_monthly_balance = ?, interest_rate = ?, interest_earned = ?
            WHERE record_id = ?
        """, (avg_monthly_balance, interest_rate,
              interest_earned, existing["record_id"]))
    else:
        conn.execute("""
            INSERT INTO SavingsInterestRecord
                (account_id, financial_year, avg_monthly_balance,
                 interest_rate, interest_earned)
            VALUES (?, ?, ?, ?, ?)
        """, (account_id, financial_year, avg_monthly_balance,
              interest_rate, interest_earned))

    conn.commit()
    conn.close()


def get_savings_interest_by_fy(financial_year: str,
                                person_id: int = None) -> list[dict]:
    """Return savings interest records for a FY."""
    query = """
        SELECT sir.*, ba.bank_name,
               COALESCE(NULLIF(b.nickname, ''), ba.bank_name) AS bank_display_name,
               ba.account_type, p.full_name AS person_name
        FROM SavingsInterestRecord sir
        JOIN BankAccount ba ON sir.account_id = ba.account_id
        LEFT JOIN Bank b ON lower(b.bank_name) = lower(ba.bank_name)
        JOIN Person p ON ba.person_id = p.person_id
        WHERE sir.financial_year = ?
    """
    params = [financial_year]
    if person_id:
        query += " AND ba.person_id = ?"
        params.append(person_id)

    conn = get_connection()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_total_savings_interest(financial_year: str,
                                person_id: int = None) -> float:
    """Sum of savings interest earned for a FY."""
    query  = """
        SELECT SUM(sir.interest_earned) AS total
        FROM SavingsInterestRecord sir
        JOIN BankAccount ba ON sir.account_id = ba.account_id
        WHERE sir.financial_year = ?
    """
    params = [financial_year]
    if person_id:
        query += " AND ba.person_id = ?"
        params.append(person_id)

    conn = get_connection()
    row = conn.execute(query, params).fetchone()
    conn.close()
    return row["total"] or 0.0
