r"""tools/backfill_transactions.py — Backfill transaction categorization and internal transfers.

Recategorizes misclassified "Other Income" rows using _guess_fd_category and explicit
rules for known taxable income sources (ENLIGHTVISION, LOTUS INVESTMENT, KEVISION, PRASAD M).
Detects and marks internal transfers. Dry-run safe; can write to database if not --dry-run.

Usage:
  .venv\Scripts\python.exe tools/backfill_transactions.py [--dry-run] [--person-id 1]
"""

import sys
import os
import argparse
from pathlib import Path
from datetime import date
import re

# UTF-8 stdout header FIRST, before any other import
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DB_PATH, BACKUP_DIR
from core.database import get_connection, backup_database
from engines.parser_utils import _guess_fd_category
from engines.prediction_engine import realised_income_to_date
from models.transaction import _load_transfer_rows, find_internal_transfers, reprocess_internal_transfers


def _mask_description(desc: str, min_digits: int = 6) -> str:
    """Mask runs of 6+ digits with <N>."""
    return re.sub(rf"\d{{{min_digits},}}", "<N>", desc or "")


def _find_phase1_changes(conn, person_id: int) -> list[dict]:
    """Phase 1: Find all "Other Income" rows that should be recategorized.

    Returns list of dicts: {
        transaction_id, account_id, transaction_date, amount,
        old_category, new_category, description
    }
    """
    rows = conn.execute("""
        SELECT transaction_id, account_id, transaction_date, amount, category, description
        FROM Transactions
        WHERE person_id = ? AND transaction_type = 'Income' AND category = 'Other Income'
        ORDER BY transaction_date, transaction_id
    """, (person_id,)).fetchall()

    changes = []

    for row in rows:
        txn_id = row["transaction_id"]
        account_id = row["account_id"]
        txn_date = row["transaction_date"]
        amount = row["amount"]
        old_cat = row["category"]
        desc = row["description"] or ""
        desc_upper = desc.upper()
        desc_nospace = re.sub(r"\s+", "", desc_upper)

        new_cat = None

        # Try _guess_fd_category first (FD Maturity, FD Interest, Savings Interest)
        guessed = _guess_fd_category(desc_upper, "Income")
        if guessed and guessed != old_cat:
            new_cat = guessed

        # Explicit rules for known taxable income sources
        if not new_cat:
            if "ENLIGHTVISION" in desc_upper:
                new_cat = "Professional Fees"
            elif "LOTUSINVESTMENT" in desc_nospace and \
                 ("INCENTIVE" in desc_upper or "COMMISSION" in desc_upper):
                new_cat = "Commission Income"
            elif "KEVISION" in desc_upper:
                new_cat = "Commission Income"
            elif "PRASAD M" in desc_upper and \
                 ("SALARY" in desc_upper or "INCENTIVE" in desc_upper):
                new_cat = "Salary"

        if new_cat and new_cat != old_cat:
            changes.append({
                "transaction_id": txn_id,
                "account_id": account_id,
                "transaction_date": txn_date,
                "amount": amount,
                "old_category": old_cat,
                "new_category": new_cat,
                "description": desc,
            })

    return changes


def _print_changes(changes: list[dict]) -> None:
    """Print planned changes (one per line, masked)."""
    for ch in changes:
        masked_desc = _mask_description(ch["description"])
        print(
            f"  ID {ch['transaction_id']:5d} | "
            f"{ch['transaction_date']} | "
            f"₹{ch['amount']:12.2f} | "
            f"{ch['old_category']:20s} → {ch['new_category']:20s} | "
            f"{masked_desc[:50]}"
        )


def _mask_transfer_txn(txn: dict) -> str:
    """Mask a transaction for display (id, date, amount, masked description)."""
    desc = txn.get("description") or ""
    masked = _mask_description(desc, min_digits=6)[:40]
    return f"ID {txn['transaction_id']} ({txn['transaction_date']}) ₹{txn['amount']:.2f} {masked}"


def run_backfill(person_id: int, dry_run: bool) -> int:
    """Run the backfill process. Returns 0 on success, 1 on failure."""

    # Connect to database
    conn = get_connection()

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 1: Find planned category changes
    # ─────────────────────────────────────────────────────────────────────────

    print("\n=== PHASE 1: Category Changes ===")
    changes = _find_phase1_changes(conn, person_id)

    if changes:
        print(f"\nPlanned changes: {len(changes)}")
        _print_changes(changes)
    else:
        print("\nNo category changes planned.")

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 2: Internal transfer detection
    # ─────────────────────────────────────────────────────────────────────────

    print("\n=== PHASE 2: Internal Transfers ===")

    # Load rows and owner names
    txns, owner_names = _load_transfer_rows(conn, person_id=person_id)

    # Apply phase-1 changes IN MEMORY ONLY (don't mutate DB yet)
    change_map = {ch["transaction_id"]: ch["new_category"] for ch in changes}
    for txn in txns:
        if txn["transaction_id"] in change_map:
            txn["category"] = change_map[txn["transaction_id"]]

    # Detect internal transfers
    pairs, self_credit_ids = find_internal_transfers(txns, owner_names)

    if pairs:
        print(f"\nInternal transfer pairs: {len(pairs)}")
        for debit_id, credit_id in pairs:
            debit_txn = next((t for t in txns if t["transaction_id"] == debit_id), None)
            credit_txn = next((t for t in txns if t["transaction_id"] == credit_id), None)
            if debit_txn and credit_txn:
                print(f"  Debit  {_mask_transfer_txn(debit_txn)}")
                print(f"  Credit {_mask_transfer_txn(credit_txn)}")
    else:
        print("\nNo internal transfer pairs found.")

    if self_credit_ids:
        print(f"\nSelf-credit rows: {len(self_credit_ids)}")
        for txn_id in self_credit_ids:
            txn = next((t for t in txns if t["transaction_id"] == txn_id), None)
            if txn:
                print(f"  {_mask_transfer_txn(txn)}")
    else:
        print("\nNo self-credit rows found.")

    # ─────────────────────────────────────────────────────────────────────────
    # Print before-figures (informational, always)
    # ─────────────────────────────────────────────────────────────────────────

    print("\n=== BEFORE: Income figures ===")
    before = realised_income_to_date(person_id, "2025-26", date(2026, 3, 31))
    print(f"Taxable income:      ₹{before['taxable']:12.2f}")
    print(f"Non-taxable income:  ₹{before['non_taxable']:12.2f}")
    print(f"Unclassified income: ₹{before['unclassified']:12.2f}")
    print(f"Total income:        ₹{before['taxable'] + before['non_taxable'] + before['unclassified']:12.2f}")
    if before.get("by_category"):
        print("\nBy category:")
        for cat in sorted(before["by_category"].keys()):
            amt = before["by_category"][cat]
            print(f"  {cat:30s}: ₹{amt:12.2f}")

    # ─────────────────────────────────────────────────────────────────────────
    # If dry-run, stop here
    # ─────────────────────────────────────────────────────────────────────────

    if dry_run:
        print("\n=== DRY-RUN: No database changes ===")
        conn.close()
        return 0

    # ─────────────────────────────────────────────────────────────────────────
    # Real run: backup, apply changes, validate, print after-figures
    # ─────────────────────────────────────────────────────────────────────────

    print("\n=== REAL RUN: Backing up database ===")
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"{timestamp}-before-backfill-financial.db")
    try:
        backup_database(backup_path)
        print(f"Backup saved: {backup_path}")
    except Exception as e:
        print(f"Backup FAILED: {e}")
        conn.close()
        return 1

    # Apply phase-1 category updates
    print("\n=== Applying category changes ===")
    try:
        for ch in changes:
            conn.execute("""
                UPDATE Transactions
                SET category = ?
                WHERE transaction_id = ?
            """, (ch["new_category"], ch["transaction_id"]))
        conn.commit()
        print(f"Applied {len(changes)} category changes.")
    except Exception as e:
        print(f"Category update FAILED: {e}")
        conn.rollback()
        conn.close()
        return 1

    # Reprocess internal transfers (on the now-updated DB)
    print("\n=== Reprocessing internal transfers ===")
    try:
        pairs_linked, txns_marked = reprocess_internal_transfers(person_id=person_id)
        print(f"Pairs linked: {pairs_linked}, Transactions marked: {txns_marked}")

        # Validate counts match
        if pairs_linked != len(pairs):
            print(f"WARNING: Phase-2 found {len(pairs)} pairs, but reprocess linked {pairs_linked}")
        if txns_marked != len(pairs) * 2 + len(self_credit_ids):
            expected = len(pairs) * 2 + len(self_credit_ids)
            print(f"WARNING: Expected {expected} txns marked, but got {txns_marked}")
    except Exception as e:
        print(f"Reprocess internal transfers FAILED: {e}")
        conn.close()
        return 1

    # Validate: no internal_transfer=1 row should have taxable category
    print("\n=== Validating internal transfer categories ===")
    try:
        bad_rows = conn.execute("""
            SELECT transaction_id, category, amount
            FROM Transactions
            WHERE is_internal_transfer = 1 AND category IN ('FD Interest', 'Savings Interest')
        """).fetchall()

        if bad_rows:
            print(f"FAIL: {len(bad_rows)} internal transfer rows have taxable categories:")
            for row in bad_rows:
                print(f"  ID {row['transaction_id']}: {row['category']} ₹{row['amount']:.2f}")
            conn.close()
            return 1
        else:
            print("PASS: No internal transfer rows have taxable categories.")
    except Exception as e:
        print(f"Validation FAILED: {e}")
        conn.close()
        return 1

    # Print after-figures
    print("\n=== AFTER: Income figures ===")
    after = realised_income_to_date(person_id, "2025-26", date(2026, 3, 31))
    print(f"Taxable income:      ₹{after['taxable']:12.2f}")
    print(f"Non-taxable income:  ₹{after['non_taxable']:12.2f}")
    print(f"Unclassified income: ₹{after['unclassified']:12.2f}")
    print(f"Total income:        ₹{after['taxable'] + after['non_taxable'] + after['unclassified']:12.2f}")
    if after.get("by_category"):
        print("\nBy category:")
        for cat in sorted(after["by_category"].keys()):
            amt = after["by_category"][cat]
            print(f"  {cat:30s}: ₹{amt:12.2f}")

    conn.close()
    print("\n=== Success ===")
    return 0


def main() -> int:
    """Parse command-line arguments and run backfill."""
    parser = argparse.ArgumentParser(
        description="Backfill transaction categorization and internal transfers."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and detect without writing to database",
    )
    parser.add_argument(
        "--person-id",
        type=int,
        default=1,
        help="Person ID to backfill for (default: 1)",
    )

    args = parser.parse_args()

    return run_backfill(person_id=args.person_id, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
