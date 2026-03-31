"""
models/bank.py — Bank master table for managing unique banks
"""

import re

from core.database import get_connection


_TAN_RE = re.compile(r"\(([A-Z0-9]{10})\)")


def create_bank_table():
    """Create Bank table if not exists."""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS Bank (
            bank_id INTEGER PRIMARY KEY AUTOINCREMENT,
            bank_name TEXT NOT NULL UNIQUE,
            tan_code TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    cols = {row[1] for row in conn.execute("PRAGMA table_info(Bank)").fetchall()}
    if "tan_code" not in cols:
        conn.execute("ALTER TABLE Bank ADD COLUMN tan_code TEXT")

    # Unique TAN (ignore NULL/empty)
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_Bank_tan_code_unique "
        "ON Bank(tan_code) WHERE tan_code IS NOT NULL AND tan_code <> ''"
    )
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


def extract_bank_name_and_tan(source_text: str) -> tuple[str, str]:
    """Extract bank/deductor name and TAN from 'NAME (TAN)' strings."""
    s = (source_text or "").strip()
    if not s:
        return "", ""
    m = _TAN_RE.search(s.upper())
    tan = m.group(1).strip() if m else ""
    name = s
    if tan:
        # Remove the last '(TAN)' part.
        name = re.sub(r"\s*\([A-Z0-9]{10}\)\s*$", "", s, flags=re.IGNORECASE).strip()
    return name, tan


def update_bank_tan_code_if_exists(bank_name: str, tan_code: str) -> bool:
    """Update an existing bank's TAN code.

    Returns True if a row was updated. Does not create new banks.
    """
    name = (bank_name or "").strip()
    tan = (tan_code or "").strip().upper()
    if not name or not tan:
        return False

    create_bank_table()
    conn = get_connection()
    cur = conn.execute(
        "UPDATE Bank SET tan_code = ? WHERE bank_name = ?",
        (tan, name),
    )
    conn.commit()
    return (cur.rowcount or 0) > 0


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
