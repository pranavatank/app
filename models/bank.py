"""
models/bank.py — Bank master table for managing unique banks
"""

from core.database import get_connection


def create_bank_table():
    """Create Bank table if not exists."""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS Bank (
            bank_id INTEGER PRIMARY KEY AUTOINCREMENT,
            bank_name TEXT NOT NULL UNIQUE,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()


def add_bank(bank_name: str) -> int:
    """Add a new bank. Returns bank_id."""
    conn = get_connection()
    try:
        cur = conn.execute("INSERT INTO Bank (bank_name) VALUES (?)", (bank_name,))
        conn.commit()
        return cur.lastrowid
    except Exception:
        # Bank already exists, get its ID
        row = conn.execute("SELECT bank_id FROM Bank WHERE bank_name = ?", (bank_name,)).fetchone()
        return row["bank_id"] if row else None


def get_all_banks() -> list[dict]:
    """Get all banks ordered by name."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM Bank ORDER BY bank_name").fetchall()
    return [dict(r) for r in rows]


def get_bank(bank_id: int) -> dict | None:
    """Get a single bank by ID."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM Bank WHERE bank_id = ?", (bank_id,)).fetchone()
    return dict(row) if row else None


def get_or_create_bank(bank_name: str) -> int:
    """Get existing bank ID or create new bank. Returns bank_id."""
    conn = get_connection()
    row = conn.execute("SELECT bank_id FROM Bank WHERE bank_name = ?", (bank_name,)).fetchone()
    if row:
        return row["bank_id"]
    return add_bank(bank_name)
