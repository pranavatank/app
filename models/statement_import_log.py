"""
models/statement_import_log.py — CRUD for StatementImportLog table.
"""

from core.database import get_connection


def log_import(account_id: int, person_id: int, bank_name: str,
               file_name: str, file_type: str,
               records_imported: int, status: str = "Success") -> int:
    """Log a statement import. Returns new import_id."""
    conn = get_connection()
    cur = conn.execute("""
        INSERT INTO StatementImportLog
            (account_id, person_id, bank_name, file_name, file_type,
             records_imported, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (account_id, person_id, bank_name, file_name,
          file_type, records_imported, status))
    conn.commit()
    import_id = cur.lastrowid
    conn.close()
    return import_id


def get_import_logs(account_id: int = None,
                    person_id: int = None) -> list[dict]:
    query  = """
        SELECT sil.*, p.full_name AS person_name, ba.bank_name AS account_bank
        FROM StatementImportLog sil
        JOIN Person p ON sil.person_id = p.person_id
        JOIN BankAccount ba ON sil.account_id = ba.account_id
        WHERE 1=1
    """
    params = []
    if account_id:
        query += " AND sil.account_id = ?"
        params.append(account_id)
    if person_id:
        query += " AND sil.person_id = ?"
        params.append(person_id)
    query += " ORDER BY sil.import_date DESC"

    conn = get_connection()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]
