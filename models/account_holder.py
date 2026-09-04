"""
models/account_holder.py — CRUD operations for the AccountHolder table.
Manages multiple holders per account, where exactly one is marked as primary.
"""

from core.database import get_connection


def add_account_holder(account_id: int, person_id: int, is_primary: int = 0) -> None:
    """Add a holder to an account."""
    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO AccountHolder (account_id, person_id, is_primary)
        VALUES (?, ?, ?)
    """, (account_id, person_id, is_primary))
    conn.commit()
    conn.close()


def get_account_holders(account_id: int) -> list[dict]:
    """Get all holders for an account, ordered by primary first."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT ah.account_id, ah.person_id, ah.is_primary,
               p.full_name, p.entity_type, p.date_of_birth
        FROM AccountHolder ah
        JOIN Person p ON ah.person_id = p.person_id
        WHERE ah.account_id = ?
        ORDER BY ah.is_primary DESC, ah.person_id
    """, (account_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_primary_holder(account_id: int) -> dict | None:
    """Get the primary (tax-declaring) holder for an account."""
    conn = get_connection()
    row = conn.execute("""
        SELECT ah.account_id, ah.person_id, ah.is_primary,
               p.full_name, p.entity_type, p.date_of_birth
        FROM AccountHolder ah
        JOIN Person p ON ah.person_id = p.person_id
        WHERE ah.account_id = ? AND ah.is_primary = 1
    """, (account_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def set_primary_holder(account_id: int, person_id: int) -> None:
    """Set person_id as the primary holder for account_id (unsets previous primary)."""
    conn = get_connection()
    # First unset all primaries for this account
    conn.execute("""
        UPDATE AccountHolder SET is_primary = 0 WHERE account_id = ?
    """, (account_id,))

    # Then set the new primary
    conn.execute("""
        UPDATE AccountHolder SET is_primary = 1
        WHERE account_id = ? AND person_id = ?
    """, (account_id, person_id))

    conn.commit()
    conn.close()


def remove_account_holder(account_id: int, person_id: int) -> None:
    """Remove a holder from an account."""
    conn = get_connection()
    conn.execute("""
        DELETE FROM AccountHolder
        WHERE account_id = ? AND person_id = ?
    """, (account_id, person_id))
    conn.commit()
    conn.close()


def holder_exists(account_id: int, person_id: int) -> bool:
    """Check if person is a holder of the account."""
    conn = get_connection()
    row = conn.execute("""
        SELECT COUNT(*) AS cnt FROM AccountHolder
        WHERE account_id = ? AND person_id = ?
    """, (account_id, person_id)).fetchone()
    conn.close()
    return row["cnt"] > 0 if row else False
