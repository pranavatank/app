"""
models/income_source.py — Income sources / TDS deductors model.

Stores companies, employers, banks, and other entities that pay income or deduct TDS.
"""

from core.database import get_connection


def create_income_source_table():
    """Create income source table if not exists."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS IncomeSource (
            source_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL,
            source_name TEXT NOT NULL,
            tan TEXT,
            pan TEXT,
            address TEXT,
            contact_person TEXT,
            phone TEXT,
            email TEXT,
            notes TEXT,
            created_date TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(tan)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_IncomeSource_tan ON IncomeSource(tan)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_IncomeSource_type ON IncomeSource(source_type)")
    conn.commit()
    conn.close()


def save_income_source(
    source_type: str,
    source_name: str,
    tan: str = None,
    pan: str = None,
    address: str = None,
    contact_person: str = None,
    phone: str = None,
    email: str = None,
    notes: str = None,
) -> int:
    """Save or update income source. Returns source_id."""
    create_income_source_table()
    conn = get_connection()
    cur = conn.cursor()
    
    # Check if TAN exists
    if tan:
        existing = cur.execute(
            "SELECT source_id FROM IncomeSource WHERE tan = ?", (tan,)
        ).fetchone()
        if existing:
            # Update existing
            cur.execute("""
                UPDATE IncomeSource
                SET source_type = ?, source_name = ?, pan = ?, address = ?,
                    contact_person = ?, phone = ?, email = ?, notes = ?
                WHERE source_id = ?
            """, (source_type, source_name, pan, address, contact_person, 
                  phone, email, notes, existing["source_id"]))
            conn.commit()
            conn.close()
            return existing["source_id"]
    
    # Insert new
    cur.execute("""
        INSERT INTO IncomeSource
        (source_type, source_name, tan, pan, address, contact_person, phone, email, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (source_type, source_name, tan, pan, address, contact_person, phone, email, notes))
    
    source_id = cur.lastrowid
    conn.commit()
    conn.close()
    return source_id


def get_income_source_by_tan(tan: str) -> dict | None:
    """Get income source by TAN."""
    if not tan:
        return None
    create_income_source_table()
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM IncomeSource WHERE tan = ?", (tan.strip().upper(),)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_income_source(source_id: int) -> dict | None:
    """Get income source by ID."""
    create_income_source_table()
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM IncomeSource WHERE source_id = ?", (source_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_income_sources(source_type: str = None) -> list[dict]:
    """Get all income sources, optionally filtered by type."""
    create_income_source_table()
    conn = get_connection()
    if source_type:
        rows = conn.execute(
            "SELECT * FROM IncomeSource WHERE source_type = ? ORDER BY source_name",
            (source_type,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM IncomeSource ORDER BY source_name"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_income_source(source_id: int):
    """Delete income source."""
    create_income_source_table()
    conn = get_connection()
    conn.execute("DELETE FROM IncomeSource WHERE source_id = ?", (source_id,))
    conn.commit()
    conn.close()


def search_income_sources(query: str) -> list[dict]:
    """Search income sources by name or TAN."""
    create_income_source_table()
    conn = get_connection()
    pattern = f"%{query}%"
    rows = conn.execute("""
        SELECT * FROM IncomeSource
        WHERE source_name LIKE ? OR tan LIKE ? OR pan LIKE ?
        ORDER BY source_name
    """, (pattern, pattern, pattern)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# Source type constants
SOURCE_TYPE_EMPLOYER = "Employer"
SOURCE_TYPE_BANK = "Bank"
SOURCE_TYPE_COMPANY = "Company"
SOURCE_TYPE_BROKER = "Broker"
SOURCE_TYPE_MUTUAL_FUND = "Mutual Fund"
SOURCE_TYPE_TENANT = "Tenant"
SOURCE_TYPE_OTHER = "Other"

SOURCE_TYPES = [
    SOURCE_TYPE_EMPLOYER,
    SOURCE_TYPE_BANK,
    SOURCE_TYPE_COMPANY,
    SOURCE_TYPE_BROKER,
    SOURCE_TYPE_MUTUAL_FUND,
    SOURCE_TYPE_TENANT,
    SOURCE_TYPE_OTHER,
]
