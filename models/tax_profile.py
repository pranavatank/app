"""
models/tax_profile.py — CRUD for TaxProfile table.
"""

from core.database import get_connection


def upsert_tax_profile(person_id: int, financial_year: str, **fields) -> int:
    """
    Insert or update a tax profile for a person + FY.
    Pass tax fields as keyword arguments matching column names.
    Returns the tax_id.
    """
    existing = get_tax_profile(person_id, financial_year)

    allowed = [
        "salary_income", "fd_interest_income", "savings_interest_income",
        "other_income", "gross_total_income", "deductions_80c",
        "deductions_80d", "home_loan_interest", "hra_exemption",
        "standard_deduction", "taxable_income_old_regime",
        "taxable_income_new_regime", "tax_old_regime", "tax_new_regime",
        "cess_amount", "total_tax_old", "total_tax_new",
        "rebate_87a_old", "rebate_87a_new", "tds_deducted",
        "tcs_collected", "advance_tax_paid", "self_assessment_tax",
    ]
    safe_fields = {k: v for k, v in fields.items() if k in allowed}

    conn = get_connection()
    if existing:
        if safe_fields:
            set_clause = ", ".join(f"{k} = ?" for k in safe_fields)
            values     = list(safe_fields.values()) + [existing["tax_id"]]
            conn.execute(
                f"UPDATE TaxProfile SET {set_clause} WHERE tax_id = ?", values
            )
        conn.commit()
        tax_id = existing["tax_id"]
    else:
        cols   = ["person_id", "financial_year"] + list(safe_fields.keys())
        vals   = [person_id, financial_year] + list(safe_fields.values())
        ph     = ", ".join("?" for _ in vals)
        cur    = conn.execute(
            f"INSERT INTO TaxProfile ({', '.join(cols)}) VALUES ({ph})", vals
        )
        conn.commit()
        tax_id = cur.lastrowid

    conn.close()
    return tax_id


def get_tax_profile(person_id: int, financial_year: str) -> dict | None:
    conn = get_connection()
    row  = conn.execute("""
        SELECT * FROM TaxProfile
        WHERE person_id = ? AND financial_year = ?
    """, (person_id, financial_year)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_tax_profiles(person_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM TaxProfile WHERE person_id = ?
        ORDER BY financial_year DESC
    """, (person_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_tax_profile(person_id: int, financial_year: str) -> None:
    conn = get_connection()
    conn.execute("""
        DELETE FROM TaxProfile
        WHERE person_id = ? AND financial_year = ?
    """, (person_id, financial_year))
    conn.commit()
    conn.close()
