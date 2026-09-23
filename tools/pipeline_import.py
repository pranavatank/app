#!/usr/bin/env python
"""
tools/pipeline_import.py — Statement parsing and transaction import pipeline.

Parses bank statements using the modern parser and imports transactions into the database.
"""

import sys
import os
import inspect
from pathlib import Path

# Add app root to path
app_root = Path(__file__).parent.parent
sys.path.insert(0, str(app_root))

from engines.statement import parse_statement_pdf, LowConfidenceParse
from models import transaction as transaction_model
from core.database import get_connection

# Configuration
STATEMENTS = {
    38: ("Jana - Pranav.pdf", None),
    39: ("IDFC.pdf", None),
    40: ("Ujjivan - Pranav.pdf", None),
    41: ("Equitas.pdf", None),  # Password resolved at runtime
}

STATEMENT_DIR = app_root / "data" / "PersonalData" / "Pranav" / "Statement"
PERSON_ID = 1
PASSWORD_FILE = app_root / "data" / "PersonalData" / "Pranav" / "password.txt"


def read_equitas_password() -> str | None:
    """Read Equitas statement password from password file.

    Scans lines for one whose lowercased text contains "equitas"
    and a ":", returns the text after the last ":", stripped.
    Returns None if file is absent or no line matches.
    """
    if not PASSWORD_FILE.exists():
        return None

    try:
        with open(PASSWORD_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line_lower = line.lower()
                if "equitas" in line_lower and ":" in line:
                    # Return text after last colon
                    return line.split(":")[-1].strip()
    except Exception:
        pass

    return None


def get_fd_count():
    """Get current count of FixedDeposit rows."""
    conn = get_connection()
    row = conn.execute("SELECT COUNT(*) AS cnt FROM FixedDeposit").fetchone()
    conn.close()
    return row["cnt"] if row else 0


def get_account_name(account_id):
    """Get bank_name for an account_id."""
    conn = get_connection()
    row = conn.execute(
        "SELECT bank_name FROM BankAccount WHERE account_id = ?",
        (account_id,)
    ).fetchone()
    conn.close()
    return row["bank_name"] if row else "Unknown"


def clear_account_transactions(account_id):
    """Delete all transactions for an account (for idempotency)."""
    conn = get_connection()
    conn.execute("DELETE FROM Transactions WHERE account_id = ?", (account_id,))
    conn.commit()
    conn.close()


def import_transactions(account_id, transactions_list):
    """
    Import a list of transactions into an account.
    Uses add_transactions_batch from the transaction model.
    """
    if not transactions_list:
        return []

    # Prepare transactions for insert: add_transactions_batch expects specific keys
    prepared = []
    for txn in transactions_list:
        prepared.append({
            "transaction_date": txn.get("transaction_date"),
            "transaction_type": txn.get("transaction_type", "Expense"),
            "amount": float(txn.get("amount", 0)),
            "category": txn.get("category"),
            "mode": txn.get("mode"),
            "description": txn.get("description"),
            "reference_no": txn.get("reference_no"),
            "deposit_account_no": txn.get("deposit_account_no"),
            "balance_after": txn.get("balance_after"),
        })

    # Use the model's batch insert function
    inserted_ids = transaction_model.add_transactions_batch(
        account_id, PERSON_ID, prepared, source="Statement Import"
    )

    transaction_model.reprocess_internal_transfers(person_id=PERSON_ID)

    return inserted_ids


def print_account_summary():
    """Print per-account summary: account_id, bank_name, count, sum Income, sum Expense."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT
            ba.account_id,
            ba.bank_name,
            COUNT(CASE WHEN t.transaction_type = 'Income' THEN 1 END) AS income_count,
            COUNT(CASE WHEN t.transaction_type = 'Expense' THEN 1 END) AS expense_count,
            SUM(CASE WHEN t.transaction_type = 'Income' THEN t.amount ELSE 0 END) AS income_sum,
            SUM(CASE WHEN t.transaction_type = 'Expense' THEN t.amount ELSE 0 END) AS expense_sum
        FROM BankAccount ba
        LEFT JOIN Transactions t ON ba.account_id = t.account_id
        WHERE ba.account_id IN (38, 39, 40, 41)
        GROUP BY ba.account_id, ba.bank_name
        ORDER BY ba.account_id
    """).fetchall()
    conn.close()

    print("\n=== PER-ACCOUNT SUMMARY ===")
    print(f"{'Account ID':<12} {'Bank Name':<30} {'Income Count':<14} {'Expense Count':<14} {'Income Sum':<15} {'Expense Sum':<15}")
    print("-" * 100)
    for row in rows:
        account_id = row["account_id"]
        bank_name = row["bank_name"]
        income_count = row["income_count"] or 0
        expense_count = row["expense_count"] or 0
        income_sum = row["income_sum"] or 0
        expense_sum = row["expense_sum"] or 0
        print(f"{account_id:<12} {bank_name:<30} {income_count:<14} {expense_count:<14} {income_sum:<15.2f} {expense_sum:<15.2f}")


def print_fd_summary(before_count, after_count):
    """Print FixedDeposit row counts before and after."""
    print("\n=== FIXEDDEPOSIT ROW COUNT ===")
    print(f"Before: {before_count}")
    print(f"After:  {after_count}")
    print(f"New FDs created: {after_count - before_count}")


def print_interest_transactions():
    """Print all transactions with 'INTEREST' in description."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT
            transaction_date,
            amount,
            transaction_type,
            category,
            description
        FROM Transactions
        WHERE LOWER(description) LIKE '%interest%'
        ORDER BY transaction_date
    """).fetchall()
    conn.close()

    print("\n=== INTEREST TRANSACTIONS ===")
    if not rows:
        print("(No interest transactions found)")
    else:
        print(f"{'Date':<12} {'Amount':<12} {'Type':<10} {'Category':<20} {'Description':<40}")
        print("-" * 94)
        for row in rows:
            date_str = row["transaction_date"][:10] if row["transaction_date"] else "N/A"
            amount = row["amount"] or 0
            txn_type = row["transaction_type"] or ""
            category = row["category"] or ""
            description = (row["description"] or "")[:40]
            print(f"{date_str:<12} {amount:<12.2f} {txn_type:<10} {category:<20} {description:<40}")


def print_total_transactions():
    """Print total Transactions count."""
    conn = get_connection()
    row = conn.execute("SELECT COUNT(*) AS cnt FROM Transactions").fetchone()
    conn.close()
    total = row["cnt"] if row else 0
    print(f"\n=== TOTAL TRANSACTIONS ===")
    print(f"Total: {total}")


def main():
    print("=== STATEMENT IMPORT PIPELINE ===\n")

    # Check if statement files exist
    statement_dir = STATEMENT_DIR
    if not statement_dir.exists():
        print(f"ERROR: Statement directory does not exist: {statement_dir}")
        return

    fd_before = get_fd_count()
    print(f"FixedDeposit count before import: {fd_before}")

    # Import each statement
    for account_id, (filename, password) in STATEMENTS.items():
        filepath = statement_dir / filename
        bank_name = get_account_name(account_id)

        print(f"\n--- Processing {bank_name} (account_id {account_id}, file: {filename}) ---")

        if not filepath.exists():
            print(f"  WARNING: File not found: {filepath}")
            continue

        # Resolve password at runtime for documents that need it
        resolved_password = password
        if filename == "Equitas.pdf":
            resolved_password = read_equitas_password()
            if not resolved_password:
                print(f"  ERROR: Equitas password not found in {PASSWORD_FILE}")
                print(f"  SKIPPING: {filename}")
                continue

        try:
            # Parse the statement
            transactions = parse_statement_pdf(str(filepath), password=resolved_password)
            print(f"  Parsed {len(transactions)} transactions")

            if transactions:
                # Clear existing transactions for this account (for idempotency)
                clear_account_transactions(account_id)
                print(f"  Cleared previous transactions for account {account_id}")

                # Import transactions
                imported_ids = import_transactions(account_id, transactions)
                print(f"  Imported {len(imported_ids)} transactions (IDs: {imported_ids[:3]}...)" if len(imported_ids) > 3 else f"  Imported {len(imported_ids)} transactions")

        except LowConfidenceParse as e:
            print(f"  ERROR: Low confidence parse (score: {e.confidence})")
            print(f"    Failing rows: {len(e.failing_rows)}")
        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}")

    # Print summaries
    fd_after = get_fd_count()
    print_account_summary()
    print_fd_summary(fd_before, fd_after)
    print_interest_transactions()
    print_total_transactions()

    print("\n=== IMPORT COMPLETE ===")


if __name__ == "__main__":
    main()
