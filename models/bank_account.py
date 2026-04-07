"""
models/bank_account.py — CRUD operations for the BankAccount table.
FIX: update_account now allows setting fields to None (clearing optional fields).
FIX: update_account_balance alias added for balance_engine compatibility.
"""

from core.database import get_connection


def add_account(person_id: int, bank_name: str, account_type: str,
                account_holder_name: str = None,
                account_number_masked: str = None, account_number_full: str = None,
                ifsc_code: str = None, micr_code: str = None,
                customer_id: str = None, ckyc_id: str = None,
                branch_name: str = None, branch_address: str = None,
                communication_address: str = None, email_id: str = None,
                phone_no: str = None, account_opening_date: str = None,
                account_status: str = "Active", currency: str = "INR",
                nomination_status: str = None, nominee_name: str = None,
                debit_card_enabled: int = 0, debit_card_charges: float = 0.0,
                debit_card_effective_from: str = None,
                opening_balance: float = 0.0, interest_rate: float = 0.0) -> int:
    """Insert a new bank account. Returns new account_id."""
    conn = get_connection()
    cur = conn.execute("""
        INSERT INTO BankAccount
            (person_id, bank_name, account_holder_name, account_type,
             account_number_masked, account_number_full,
             ifsc_code, micr_code, customer_id, ckyc_id,
             branch_name, branch_address, communication_address,
             email_id, phone_no, account_opening_date,
             account_status, currency, nomination_status, nominee_name,
             debit_card_enabled, debit_card_charges, debit_card_effective_from,
             opening_balance, current_balance, interest_rate)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (person_id, bank_name, account_holder_name, account_type,
          account_number_masked, account_number_full,
          ifsc_code, micr_code, customer_id, ckyc_id,
          branch_name, branch_address, communication_address,
          email_id, phone_no, account_opening_date,
          account_status, currency, nomination_status, nominee_name,
          debit_card_enabled, debit_card_charges, debit_card_effective_from,
          opening_balance, opening_balance, interest_rate))
    conn.commit()
    account_id = cur.lastrowid
    conn.close()
    return account_id


def get_accounts_for_person(person_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT ba.*, b.tan_code, b.nickname AS bank_nickname,
               COALESCE(NULLIF(b.nickname, ''), ba.bank_name) AS bank_display_name
        FROM BankAccount ba
        LEFT JOIN Bank b ON lower(b.bank_name) = lower(ba.bank_name)
        WHERE ba.person_id = ?
        ORDER BY lower(COALESCE(NULLIF(b.nickname, ''), ba.bank_name)), lower(ba.bank_name)
    """, (person_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_accounts() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT ba.*, p.full_name AS person_name, b.tan_code,
               b.nickname AS bank_nickname,
               COALESCE(NULLIF(b.nickname, ''), ba.bank_name) AS bank_display_name
        FROM BankAccount ba
        JOIN Person p ON ba.person_id = p.person_id
        LEFT JOIN Bank b ON lower(b.bank_name) = lower(ba.bank_name)
        ORDER BY p.full_name, lower(COALESCE(NULLIF(b.nickname, ''), ba.bank_name)), lower(ba.bank_name)
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_account(account_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute("""
        SELECT ba.*, b.tan_code, b.nickname AS bank_nickname,
               COALESCE(NULLIF(b.nickname, ''), ba.bank_name) AS bank_display_name
        FROM BankAccount ba
        LEFT JOIN Bank b ON lower(b.bank_name) = lower(ba.bank_name)
        WHERE ba.account_id = ?
    """, (account_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


_UPDATABLE_FIELDS = [
    "person_id", "bank_name", "account_holder_name", "account_type",
    "account_number_masked", "account_number_full",
    "ifsc_code", "micr_code", "customer_id", "ckyc_id",
    "branch_name", "branch_address", "communication_address",
    "email_id", "phone_no", "account_opening_date",
    "account_status", "currency", "nomination_status", "nominee_name",
    "debit_card_enabled", "debit_card_charges", "debit_card_effective_from",
    "opening_balance", "interest_rate",
]


def update_account(account_id: int, **kwargs) -> None:
    """
    Update account fields. Explicitly includes fields in kwargs even when None,
    so optional fields can be cleared.
    """
    conn = get_connection()
    updates = []
    params  = []
    for field in _UPDATABLE_FIELDS:
        if field in kwargs:
            updates.append(f"{field} = ?")
            params.append(kwargs[field])
    if updates:
        params.append(account_id)
        conn.execute(
            f"UPDATE BankAccount SET {', '.join(updates)} WHERE account_id = ?",
            params
        )
        conn.commit()
    conn.close()


def update_balance(account_id: int, new_balance: float) -> None:
    """Update current_balance (simple alias used by some screens)."""
    _set_balance(account_id, new_balance)


def update_account_balance(account_id: int, new_balance: float) -> None:
    """Update current_balance — used by balance_engine."""
    _set_balance(account_id, new_balance)


def _set_balance(account_id: int, new_balance: float) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE BankAccount SET current_balance = ? WHERE account_id = ?",
        (new_balance, account_id)
    )
    conn.commit()
    conn.close()


def delete_account(account_id: int) -> None:
    """Delete account and all associated data."""
    conn = get_connection()
    conn.execute("DELETE FROM Transactions WHERE account_id = ?", (account_id,))
    conn.execute("""
        DELETE FROM FDInterestRecord
        WHERE fd_id IN (SELECT fd_id FROM FixedDeposit WHERE account_id = ?)
    """, (account_id,))
    conn.execute("DELETE FROM FixedDeposit WHERE account_id = ?", (account_id,))
    conn.execute("DELETE FROM SavingsInterestRecord WHERE account_id = ?", (account_id,))
    conn.execute("DELETE FROM StatementImportLog WHERE account_id = ?", (account_id,))
    conn.execute("DELETE FROM BankAccount WHERE account_id = ?", (account_id,))
    conn.commit()
    conn.close()


def get_total_balance(person_id: int = None) -> float:
    conn = get_connection()
    if person_id:
        row = conn.execute(
            "SELECT SUM(current_balance) AS total FROM BankAccount WHERE person_id = ?",
            (person_id,)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT SUM(current_balance) AS total FROM BankAccount"
        ).fetchone()
    conn.close()
    return row["total"] or 0.0
