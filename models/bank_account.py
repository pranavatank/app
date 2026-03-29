"""
models/bank_account.py — CRUD operations for the BankAccount table.
"""

from core.database import get_connection
from typing import Optional


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
            (person_id, bank_name, account_holder_name, account_type, account_number_masked, account_number_full,
             ifsc_code, micr_code, customer_id, ckyc_id, branch_name, branch_address,
             communication_address, email_id, phone_no, account_opening_date,
             account_status, currency, nomination_status, nominee_name,
             debit_card_enabled, debit_card_charges, debit_card_effective_from,
             opening_balance, current_balance, interest_rate)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (person_id, bank_name, account_holder_name, account_type, account_number_masked, account_number_full,
          ifsc_code, micr_code, customer_id, ckyc_id, branch_name, branch_address,
          communication_address, email_id, phone_no, account_opening_date,
          account_status, currency, nomination_status, nominee_name,
          debit_card_enabled, debit_card_charges, debit_card_effective_from,
          opening_balance, opening_balance, interest_rate))
    conn.commit()
    account_id = cur.lastrowid
    conn.close()
    return account_id


def get_accounts_for_person(person_id: int) -> list[dict]:
    """Return all accounts belonging to a person."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM BankAccount
        WHERE person_id = ?
        ORDER BY bank_name
    """, (person_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_accounts() -> list[dict]:
    """Return all accounts across all persons."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT ba.*, p.full_name AS person_name
        FROM BankAccount ba
        JOIN Person p ON ba.person_id = p.person_id
        ORDER BY p.full_name, ba.bank_name
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_account(account_id: int) -> dict | None:
    """Return a single account by ID."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM BankAccount WHERE account_id = ?", (account_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_account(account_id: int, **kwargs) -> None:
    """Update account details with any provided fields."""
    conn = get_connection()
    
    allowed_fields = [
        "person_id", "bank_name", "account_holder_name", "account_type", "account_number_masked", "account_number_full",
        "ifsc_code", "micr_code", "customer_id", "ckyc_id", "branch_name", "branch_address",
        "communication_address", "email_id", "phone_no", "account_opening_date",
        "account_status", "currency", "nomination_status", "nominee_name",
        "debit_card_enabled", "debit_card_charges", "debit_card_effective_from",
        "opening_balance", "interest_rate"
    ]
    
    updates = []
    params = []
    
    for field in allowed_fields:
        if field in kwargs and kwargs[field] is not None:
            updates.append(f"{field} = ?")
            params.append(kwargs[field])
    
    if updates:
        params.append(account_id)
        query = f"UPDATE BankAccount SET {', '.join(updates)} WHERE account_id = ?"
        conn.execute(query, params)
        conn.commit()
    
    conn.close()


def update_account_balance(account_id: int, new_balance: float) -> None:
    """Update the current balance of an account."""
    conn = get_connection()
    conn.execute(
        "UPDATE BankAccount SET current_balance = ? WHERE account_id = ?",
        (new_balance, account_id)
    )
    conn.commit()
    conn.close()


def delete_account(account_id: int) -> None:
    """Delete an account and all associated records."""
    conn = get_connection()
    
    # Delete associated records first (due to foreign key constraints)
    # Delete transactions
    conn.execute("DELETE FROM Transactions WHERE account_id = ?", (account_id,))
    
    # Delete fixed deposits
    conn.execute("DELETE FROM FDInterestRecord WHERE fd_id IN (SELECT fd_id FROM FixedDeposit WHERE account_id = ?)", (account_id,))
    conn.execute("DELETE FROM FixedDeposit WHERE account_id = ?", (account_id,))
    
    # Delete savings interest records
    conn.execute("DELETE FROM SavingsInterestRecord WHERE account_id = ?", (account_id,))
    
    # Delete statement import logs
    conn.execute("DELETE FROM StatementImportLog WHERE account_id = ?", (account_id,))
    
    # Finally delete the account
    conn.execute("DELETE FROM BankAccount WHERE account_id = ?", (account_id,))
    
    conn.commit()
    conn.close()


def get_total_balance(person_id: int = None) -> float:
    """Return total balance across all accounts, optionally filtered by person."""
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
