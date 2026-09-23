r"""tools/delete_account.py — CLI tool to safely delete a bank account and all dependent data.

Usage:
  .venv\Scripts\python.exe tools/delete_account.py --account-id 1 --expect-name "Test Bank" [--dry-run]
"""

import sys
import os
import argparse
from datetime import datetime
from pathlib import Path

# UTF-8 stdout header FIRST, before any other import
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_connection, backup_database
from models.bank_account import get_account, delete_account


def get_dependent_counts(conn, account_id: int) -> dict:
    """Query count of dependent rows for an account."""
    counts = {}

    counts["Transactions"] = conn.execute(
        "SELECT COUNT(*) FROM Transactions WHERE account_id = ?", (account_id,)
    ).fetchone()[0]

    counts["FixedDeposit"] = conn.execute(
        "SELECT COUNT(*) FROM FixedDeposit WHERE account_id = ?", (account_id,)
    ).fetchone()[0]

    counts["FDInterestRecord"] = conn.execute(
        "SELECT COUNT(*) FROM FDInterestRecord WHERE fd_id IN (SELECT fd_id FROM FixedDeposit WHERE account_id = ?)",
        (account_id,)
    ).fetchone()[0]

    counts["SavingsInterestRecord"] = conn.execute(
        "SELECT COUNT(*) FROM SavingsInterestRecord WHERE account_id = ?", (account_id,)
    ).fetchone()[0]

    counts["StatementImportLog"] = conn.execute(
        "SELECT COUNT(*) FROM StatementImportLog WHERE account_id = ?", (account_id,)
    ).fetchone()[0]

    counts["IncomeExpectation"] = conn.execute(
        "SELECT COUNT(*) FROM IncomeExpectation WHERE account_id = ?", (account_id,)
    ).fetchone()[0]

    counts["AccountHolder"] = conn.execute(
        "SELECT COUNT(*) FROM AccountHolder WHERE account_id = ?", (account_id,)
    ).fetchone()[0]

    return counts


def get_summary_counts(conn) -> dict:
    """Query overall summary counts."""
    counts = {}
    counts["BankAccount"] = conn.execute("SELECT COUNT(*) FROM BankAccount").fetchone()[0]
    counts["Person"] = conn.execute("SELECT COUNT(*) FROM Person").fetchone()[0]
    return counts


def main() -> int:
    """Parse arguments and delete account."""
    parser = argparse.ArgumentParser(
        description="Delete a bank account and all dependent data."
    )
    parser.add_argument(
        "--account-id",
        type=int,
        required=True,
        help="Account ID to delete",
    )
    parser.add_argument(
        "--expect-name",
        type=str,
        required=True,
        help="Expected bank name (safety check)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without modifying database",
    )

    args = parser.parse_args()

    # Look up account
    account = get_account(args.account_id)
    if not account:
        print(f"ERROR: Account {args.account_id} not found")
        return 1

    # Verify bank_name matches
    bank_name = account.get("bank_name", "")
    if bank_name != args.expect_name:
        print(f"ERROR: bank_name mismatch")
        print(f"  expected: {args.expect_name}")
        print(f"  actual: {bank_name}")
        return 1

    print(f"Account: id={args.account_id} bank_name={bank_name}")

    # Get before counts
    conn = get_connection()
    before_counts = get_dependent_counts(conn, args.account_id)
    before_summary = get_summary_counts(conn)
    conn.close()

    print("\nBEFORE deletion:")
    for table, count in before_counts.items():
        print(f"  {table}: {count}")
    print(f"  BankAccount (total): {before_summary['BankAccount']}")
    print(f"  Person (total): {before_summary['Person']}")

    # If dry-run, stop here
    if args.dry_run:
        print("\n[DRY-RUN] No changes made")
        return 0

    # Back up database
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"{timestamp}-before-delete-account-{args.account_id}-financial.db"
    backup_path = os.path.join("backups", backup_filename)

    print(f"\nBacking up to: {backup_path}")
    try:
        backup_database(backup_path)
        print(f"Backup: OK")
    except Exception as e:
        print(f"Backup: FAILED - {e}")
        return 1

    # Delete account
    print(f"\nDeleting account {args.account_id}...")
    try:
        delete_account(args.account_id)
        print("Deletion: OK")
    except Exception as e:
        print(f"Deletion: FAILED - {e}")
        return 1

    # Get after counts
    conn = get_connection()
    after_counts = get_dependent_counts(conn, args.account_id)
    after_summary = get_summary_counts(conn)
    conn.close()

    print("\nAFTER deletion:")
    for table, count in after_counts.items():
        print(f"  {table}: {count}")
    print(f"  BankAccount (total): {after_summary['BankAccount']}")
    print(f"  Person (total): {after_summary['Person']}")

    # Verify all dependent counts are now 0
    all_zero = all(count == 0 for count in after_counts.values())
    if not all_zero:
        print("\nERROR: Some dependent rows still exist after deletion")
        for table, count in after_counts.items():
            if count > 0:
                print(f"  {table}: {count} (expected 0)")
        return 1

    # Verify Person count is unchanged
    if after_summary["Person"] != before_summary["Person"]:
        print("\nERROR: Person count changed (expected to remain the same)")
        print(f"  before: {before_summary['Person']}")
        print(f"  after: {after_summary['Person']}")
        return 1

    print("\nAll checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
