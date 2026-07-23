"""
engines/balance_engine.py — Running balance calculations (Phase 7)
"""

from models.transaction import (
    get_account_transactions_for_balance,
    set_transaction_balances,
    get_balance_points,
)
from models.bank_account import get_account, update_account_balance


def recalculate_account_balance(account_id: int) -> float:
    """
    Recalculate running balance for all transactions in an account.
    Updates balance_after for each transaction and account current_balance.

    Returns final balance.
    """
    account = get_account(account_id)
    if not account:
        return 0.0

    opening_balance = account["opening_balance"]

    # Get all transactions for this account, ordered by date
    transactions = get_account_transactions_for_balance(account_id)

    running_balance = opening_balance
    balance_updates = []

    for txn in transactions:
        txn_id = txn["transaction_id"]
        txn_type = txn["transaction_type"]
        amount = txn["amount"]

        # Update running balance
        if txn_type == "Income":
            running_balance += amount
        elif txn_type == "Expense":
            running_balance -= amount
        # Transfer doesn't change balance (handled separately)

        # Collect balance update for batch processing
        balance_updates.append((running_balance, txn_id))

    # Batch update all transaction balances
    set_transaction_balances(balance_updates)

    # Update account current balance
    update_account_balance(account_id, running_balance)

    return running_balance


def recalculate_all_balances(person_id: int = None) -> dict:
    """
    Recalculate balances for all accounts (optionally filtered by person).
    
    Returns dict with account_id -> final_balance mapping.
    """
    from models.bank_account import get_accounts_for_person, get_all_accounts
    
    if person_id:
        accounts = get_accounts_for_person(person_id)
    else:
        accounts = get_all_accounts()
    
    results = {}
    for acc in accounts:
        final_balance = recalculate_account_balance(acc["account_id"])
        results[acc["account_id"]] = final_balance
    
    return results


def get_balance_history(account_id: int, start_date: str = None,
                        end_date: str = None) -> list[dict]:
    """
    Get balance history for an account over time.

    Returns list of {date, balance} dicts.
    """
    return get_balance_points(account_id, start_date, end_date)
