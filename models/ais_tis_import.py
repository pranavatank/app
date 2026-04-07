"""
models/ais_tis_import.py — AIS/TIS import data model
"""

import sqlite3
from core.database import get_connection


def create_ais_tis_table():
    """Create AIS/TIS import table if not exists."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS AISTISImport (
            import_id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER NOT NULL REFERENCES Person(person_id),
            financial_year TEXT NOT NULL,
            import_date TEXT NOT NULL DEFAULT (datetime('now')),
            source_type TEXT NOT NULL,
            raw_json TEXT NOT NULL,
            salary_income REAL DEFAULT 0,
            fd_interest REAL DEFAULT 0,
            savings_interest REAL DEFAULT 0,
            other_interest REAL DEFAULT 0,
            dividend_income REAL DEFAULT 0,
            rental_income REAL DEFAULT 0,
            other_income REAL DEFAULT 0,
            tds_deducted REAL DEFAULT 0,
            UNIQUE(person_id, financial_year, source_type)
        )
    """)
    conn.commit()
    conn.close()


def create_ais_tis_detail_tables() -> None:
    """Create tables to store detailed AIS/TIS import breakdowns."""
    create_ais_tis_table()
    conn = get_connection()
    cur = conn.cursor()

    # Store every extracted line from a PDF import (lossless storage).
    cur.execute("""
        CREATE TABLE IF NOT EXISTS AISTISImportLine (
            line_id INTEGER PRIMARY KEY AUTOINCREMENT,
            import_id INTEGER NOT NULL REFERENCES AISTISImport(import_id) ON DELETE CASCADE,
            line_no INTEGER NOT NULL,
            text TEXT NOT NULL
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_AISTISImportLine_import_id ON AISTISImportLine(import_id)")

    # Store structured records parsed from AIS/TIS sources (PDF text or JSON-derived breakdown).
    cur.execute("""
        CREATE TABLE IF NOT EXISTS AISTISImportRecord (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            import_id INTEGER NOT NULL REFERENCES AISTISImport(import_id) ON DELETE CASCADE,
            record_type TEXT NOT NULL,
            information_code TEXT,
            information_description TEXT,
            information_source TEXT,
            source_tan TEXT,
            bucket TEXT,
            count INTEGER,
            amount REAL,
            amount_reported REAL,
            amount_processed REAL,
            amount_accepted REAL,
            quarter TEXT,
            payment_date TEXT,
            amount_paid REAL,
            tds_deducted REAL,
            tds_deposited REAL,
            status TEXT,
            raw_line TEXT
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_AISTISImportRecord_import_id ON AISTISImportRecord(import_id)")

    # Migrate older schema if table existed without newer columns.
    cols = {row[1] for row in cur.execute("PRAGMA table_info(AISTISImportRecord)").fetchall()}
    if "source_tan" not in cols:
        cur.execute("ALTER TABLE AISTISImportRecord ADD COLUMN source_tan TEXT")
    if "amount_reported" not in cols:
        cur.execute("ALTER TABLE AISTISImportRecord ADD COLUMN amount_reported REAL")
    if "amount_processed" not in cols:
        cur.execute("ALTER TABLE AISTISImportRecord ADD COLUMN amount_processed REAL")
    if "amount_accepted" not in cols:
        cur.execute("ALTER TABLE AISTISImportRecord ADD COLUMN amount_accepted REAL")

    conn.commit()
    conn.close()


def save_ais_tis_data(person_id: int, financial_year: str, source_type: str,
                       raw_json: str, data: dict) -> int:
    """Save or update AIS/TIS import data."""
    create_ais_tis_table()
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        INSERT OR REPLACE INTO AISTISImport
        (person_id, financial_year, source_type, raw_json,
         salary_income, fd_interest, savings_interest, other_interest,
         dividend_income, rental_income, other_income, tds_deducted)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        person_id, financial_year, source_type, raw_json,
        data.get('salary_income', 0),
        data.get('fd_interest', 0),
        data.get('savings_interest', 0),
        data.get('other_interest', 0),
        data.get('dividend_income', 0),
        data.get('rental_income', 0),
        data.get('other_income', 0),
        data.get('tds_deducted', 0)
    ))
    
    conn.commit()

    # For INSERT OR REPLACE, lastrowid can be unreliable in some cases.
    row = cur.execute(
        "SELECT import_id FROM AISTISImport WHERE person_id = ? AND financial_year = ? AND source_type = ?",
        (person_id, financial_year, source_type),
    ).fetchone()

    conn.close()
    return int(row["import_id"]) if row else 0


def save_ais_tis_pdf_lines(import_id: int, extracted_text: str) -> None:
    """Store every extracted line from a PDF import."""
    create_ais_tis_detail_tables()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM AISTISImportLine WHERE import_id = ?", (import_id,))

    lines = (extracted_text or "").splitlines()
    cur.executemany(
        "INSERT INTO AISTISImportLine(import_id, line_no, text) VALUES (?, ?, ?)",
        [(import_id, i + 1, ln) for i, ln in enumerate(lines)],
    )
    conn.commit()
    conn.close()


def save_ais_tis_records(import_id: int, records: list[dict]) -> None:
    """Store parsed structured records for an import."""
    create_ais_tis_detail_tables()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM AISTISImportRecord WHERE import_id = ?", (import_id,))

    rows = []
    for r in (records or []):
        rows.append(
            (
                import_id,
                r.get("record_type") or "unknown",
                r.get("information_code") or r.get("code"),
                r.get("information_description") or r.get("description"),
                r.get("information_source") or r.get("source"),
                r.get("source_tan"),
                r.get("bucket"),
                r.get("count"),
                r.get("amount"),
                r.get("amount_reported"),
                r.get("amount_processed"),
                r.get("amount_accepted"),
                r.get("quarter"),
                r.get("payment_date"),
                r.get("amount_paid"),
                r.get("tds_deducted") or r.get("tds"),
                r.get("tds_deposited"),
                r.get("status"),
                r.get("raw_line"),
            )
        )

    cur.executemany(
        """
        INSERT INTO AISTISImportRecord(
            import_id, record_type,
            information_code, information_description, information_source,
            source_tan,
            bucket, count, amount,
            amount_reported, amount_processed, amount_accepted,
            quarter, payment_date, amount_paid,
            tds_deducted, tds_deposited, status,
            raw_line
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    conn.close()


def get_ais_tis_records(import_id: int) -> list[dict]:
    """Get structured records for an import."""
    create_ais_tis_detail_tables()
    conn = get_connection()
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT * FROM AISTISImportRecord WHERE import_id = ? ORDER BY record_id ASC",
        (import_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_ais_tis_data(person_id: int, financial_year: str):
    """Get AIS/TIS data for person and FY."""
    create_ais_tis_table()
    conn = get_connection()
    cur = conn.cursor()
    
    row = cur.execute("""
        SELECT * FROM AISTISImport
        WHERE person_id = ? AND financial_year = ?
        ORDER BY import_date DESC LIMIT 1
    """, (person_id, financial_year)).fetchone()
    
    conn.close()
    return dict(row) if row else None


def get_all_ais_tis_imports(person_id: int = None):
    """Get all AIS/TIS imports."""
    create_ais_tis_table()
    conn = get_connection()
    cur = conn.cursor()
    
    if person_id:
        rows = cur.execute("""
            SELECT a.*, p.full_name as person_name
            FROM AISTISImport a
            JOIN Person p ON a.person_id = p.person_id
            WHERE a.person_id = ?
            ORDER BY a.import_date DESC
        """, (person_id,)).fetchall()
    else:
        rows = cur.execute("""
            SELECT a.*, p.full_name as person_name
            FROM AISTISImport a
            JOIN Person p ON a.person_id = p.person_id
            ORDER BY a.import_date DESC
        """).fetchall()
    
    conn.close()
    return [dict(r) for r in rows]
