"""
models/auth_security.py — Helper queries for AuthSecurity table.
Most auth logic lives in core/auth.py; this module provides direct DB helpers.
"""

from core.database import get_connection


def get_auth_record() -> dict | None:
    conn = get_connection()
    row  = conn.execute(
        "SELECT * FROM AuthSecurity ORDER BY auth_id LIMIT 1"
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def set_privacy_mode(enabled: bool) -> None:
    record = get_auth_record()
    if not record:
        return
    conn = get_connection()
    conn.execute(
        "UPDATE AuthSecurity SET privacy_mode_enabled = ? WHERE auth_id = ?",
        (1 if enabled else 0, record["auth_id"])
    )
    conn.commit()
    conn.close()


def get_privacy_mode() -> bool:
    record = get_auth_record()
    return bool(record["privacy_mode_enabled"]) if record else False
