"""
models/person.py — CRUD operations for the Person table.
"""

from core.database import get_connection


def add_person(full_name: str, first_name: str = None, middle_name: str = None,
               last_name: str = None, date_of_birth: str = None,
               pan_number: str = None, contact_notes: str = None) -> int:
    """Insert a new person. Returns the new person_id."""
    conn = get_connection()
    cur = conn.execute("""
        INSERT INTO Person (
            full_name, first_name, middle_name, last_name,
            date_of_birth, pan_number, contact_notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (full_name, first_name, middle_name, last_name,
           date_of_birth, pan_number, contact_notes))
    conn.commit()
    person_id = cur.lastrowid
    conn.close()
    return person_id


def get_all_persons() -> list[dict]:
    """Return all persons ordered by name."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM Person ORDER BY full_name"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_person(person_id: int) -> dict | None:
    """Return a single person by ID."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM Person WHERE person_id = ?", (person_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_person(person_id: int, full_name: str, first_name: str = None,
                  middle_name: str = None, last_name: str = None,
                  date_of_birth: str = None, pan_number: str = None,
                  contact_notes: str = None) -> None:
    """Update person details."""
    conn = get_connection()
    conn.execute("""
        UPDATE Person
        SET full_name = ?, first_name = ?, middle_name = ?, last_name = ?,
            date_of_birth = ?, pan_number = ?, contact_notes = ?
        WHERE person_id = ?
    """, (full_name, first_name, middle_name, last_name,
           date_of_birth, pan_number, contact_notes, person_id))
    conn.commit()
    conn.close()


def delete_person(person_id: int) -> None:
    """Delete a person and all linked data (cascade via FK)."""
    conn = get_connection()
    conn.execute("DELETE FROM Person WHERE person_id = ?", (person_id,))
    conn.commit()
    conn.close()
