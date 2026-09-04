"""
models/form26as.py — Form 26AS TDS records model.

Form 26AS Part-A contains TDS deducted by deductors (employers, banks, etc.)
We store each row so it can be reconciled against AIS TDS records.
"""

from core.database import get_connection


def save_form26as_import(
    person_id: int,
    financial_year: str,
    records: list[dict],
    source_file: str = "",
    raw_text: str = "",
) -> int:
    """
    Upsert a Form 26AS import for person + FY.
    Returns import_id.
    """
    conn = get_connection()
    cur  = conn.cursor()

    total_tds = sum(r.get("tds_deducted") or 0 for r in records)

    # Replace existing import for same person + FY
    cur.execute(
        "DELETE FROM Form26ASImport WHERE person_id = ? AND financial_year = ?",
        (person_id, financial_year),
    )
    cur.execute("""
        INSERT INTO Form26ASImport
            (person_id, financial_year, source_file, total_tds, raw_text)
        VALUES (?, ?, ?, ?, ?)
    """, (person_id, financial_year, source_file, total_tds, raw_text))
    import_id = cur.lastrowid

    rows = [
        (
            import_id,
            r.get("section"),
            r.get("deductor_name"),
            r.get("deductor_tan"),
            r.get("transaction_date"),
            r.get("amount_paid") or 0,
            r.get("tds_deducted") or 0,
            r.get("tds_deposited") or 0,
            r.get("status"),
            r.get("certificate_no"),
            r.get("remarks"),
            r.get("raw_line"),
        )
        for r in records
    ]
    cur.executemany("""
        INSERT INTO Form26ASRecord
            (import_id, section, deductor_name, deductor_tan,
             transaction_date, amount_paid, tds_deducted, tds_deposited,
             status, certificate_no, remarks, raw_line)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)

    conn.commit()
    conn.close()
    return import_id


def get_form26as_import(person_id: int, financial_year: str) -> dict | None:
    conn = get_connection()
    row  = conn.execute("""
        SELECT * FROM Form26ASImport
        WHERE person_id = ? AND financial_year = ?
        ORDER BY import_date DESC LIMIT 1
    """, (person_id, financial_year)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_form26as_records(import_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM Form26ASRecord WHERE import_id = ?
        ORDER BY record_id
    """, (import_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_form26as_import(person_id: int, financial_year: str) -> None:
    conn = get_connection()
    conn.execute(
        "DELETE FROM Form26ASImport WHERE person_id = ? AND financial_year = ?",
        (person_id, financial_year),
    )
    conn.commit()
    conn.close()


def manual_add_record(
    person_id: int,
    financial_year: str,
    section: str,
    deductor_name: str,
    deductor_tan: str,
    transaction_date: str,
    amount_paid: float,
    tds_deducted: float,
    tds_deposited: float,
    status: str = "F",
) -> None:
    """Add a single TDS record manually (no PDF import needed)."""
    imp = get_form26as_import(person_id, financial_year)
    if imp is None:
        import_id = save_form26as_import(
            person_id, financial_year, [], source_file="Manual")
    else:
        import_id = imp["import_id"]

    conn = get_connection()
    conn.execute("""
        INSERT INTO Form26ASRecord
            (import_id, section, deductor_name, deductor_tan,
             transaction_date, amount_paid, tds_deducted, tds_deposited, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (import_id, section, deductor_name, deductor_tan,
          transaction_date, amount_paid, tds_deducted, tds_deposited, status))
    # Recalculate total_tds
    total = conn.execute(
        "SELECT SUM(tds_deducted) as s FROM Form26ASRecord WHERE import_id = ?",
        (import_id,)
    ).fetchone()["s"] or 0
    conn.execute(
        "UPDATE Form26ASImport SET total_tds = ? WHERE import_id = ?",
        (total, import_id)
    )
    conn.commit()
    conn.close()
