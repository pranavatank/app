#!/usr/bin/env python3
"""
tools/tax_reconcile.py — Reconcile tax documents (26AS, AIS, TIS) against bank transactions.

HEADLESS ONLY: no GUI window, no QT_QPA_PLATFORM.
"""

import sys
import os
import sqlite3
from pathlib import Path

# Ensure we can import from the project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from engines.taxdocs.form26as import parse_form26as_pdf
from engines.taxdocs.ais import parse_ais_pdf
from engines.taxdocs.tis import parse_tis_pdf
from config import DB_PATH, DATA_DIR


def get_db_connection():
    """Open read-only connection to the database."""
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)


def fetch_26as_data():
    """Parse 26AS and return structured data."""
    pdf_path = Path(DATA_DIR) / "PersonalData" / "Pranav" / "26AS.pdf"
    if not pdf_path.exists():
        print(f"ERROR: 26AS file not found at {pdf_path}")
        return None

    try:
        result = parse_form26as_pdf(str(pdf_path), password=None, debug={})
        return result
    except Exception as e:
        print(f"ERROR parsing 26AS: {e}")
        return None


def fetch_ais_data():
    """Parse AIS with password and return data."""
    pdf_path = Path(DATA_DIR) / "PersonalData" / "Pranav" / "AIS.pdf"
    if not pdf_path.exists():
        return None, "File not found"

    try:
        result = parse_ais_pdf(str(pdf_path), password="azipt9702h08032004")
        return result, None
    except Exception as e:
        return None, str(e)


def fetch_tis_data():
    """Parse TIS with password and return data."""
    pdf_path = Path(DATA_DIR) / "PersonalData" / "Pranav" / "TIS.pdf"
    if not pdf_path.exists():
        return None, "File not found"

    try:
        result = parse_tis_pdf(str(pdf_path), password="azipt9702h08032004")
        return result, None
    except Exception as e:
        return None, str(e)


def get_bank_accounts():
    """Fetch all bank accounts for person_id=1."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT account_id, bank_name FROM BankAccount WHERE person_id = 1 ORDER BY account_id"
    )
    accounts = {row[0]: row[1] for row in cur.fetchall()}
    conn.close()
    return accounts


def get_transactions_by_account():
    """Fetch all transactions grouped by account_id."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT account_id, transaction_type, category, description, amount FROM Transactions WHERE person_id = 1"
    )
    txns = cur.fetchall()
    conn.close()
    return txns


def print_section(title):
    """Print a section header."""
    print(f"\n{'='*80}")
    print(f"{title}")
    print(f"{'='*80}")


def print_26as_summary(data):
    """Print 26AS data grouped by deductor (Part-I and Part-II separately)."""
    if not data or not data.get("records"):
        print("No 26AS records found.")
        return

    # Group by deductor_name and part
    deductors = {}
    for rec in data.get("records", []):
        deductor = rec.get("deductor_name", "Unknown")
        part = rec.get("part", "")

        key = (deductor, part)
        if key not in deductors:
            deductors[key] = {"count": 0, "amount_paid": 0.0, "tds_deducted": 0.0}

        deductors[key]["count"] += 1
        deductors[key]["amount_paid"] += rec.get("amount_paid", 0.0)
        deductors[key]["tds_deducted"] += rec.get("tds_deducted", 0.0)

    print("\n26AS RECORDS GROUPED BY DEDUCTOR:")
    print(f"{'Deductor':<40} {'Part':<8} {'Count':<6} {'Amount Paid':<15} {'TDS Deducted':<15}")
    print("-" * 90)

    for (deductor, part), values in sorted(deductors.items()):
        print(f"{deductor:<40} {part:<8} {values['count']:<6} {values['amount_paid']:>13,.2f} {values['tds_deducted']:>13,.2f}")


def get_interest_by_account(accounts, txns):
    """Extract interest income by account."""
    interest_by_account = {}

    for account_id, bank_name in accounts.items():
        interest_by_account[account_id] = {
            "bank_name": bank_name,
            "count": 0,
            "total": 0.0
        }

    for txn_account_id, txn_type, category, description, amount in txns:
        if txn_account_id not in interest_by_account:
            continue

        # Match: Income + category like Interest OR description contains INTEREST
        if txn_type.upper() == "INCOME":
            is_interest = False
            if category and "interest" in category.lower():
                is_interest = True
            elif description and "interest" in description.upper():
                is_interest = True

            if is_interest:
                interest_by_account[txn_account_id]["count"] += 1
                interest_by_account[txn_account_id]["total"] += amount

    return interest_by_account


def match_26as_to_db(data, interest_by_account, accounts):
    """Match 26AS deductors to bank accounts and compare interest amounts."""
    # Build a mapping from deductor name (first word) to account_id
    deductor_to_account = {}

    for account_id, bank_name in accounts.items():
        first_word = bank_name.split()[0].upper()
        deductor_to_account[first_word] = account_id

    # Group 26AS records by section 194A (interest from banks)
    interest_194a = {}
    for rec in data.get("records", []):
        if rec.get("section") == "194A":
            deductor = rec.get("deductor_name", "Unknown")
            first_word = deductor.split()[0].upper()

            if first_word not in interest_194a:
                interest_194a[first_word] = {"amount_paid": 0.0, "tds_deducted": 0.0}

            interest_194a[first_word]["amount_paid"] += rec.get("amount_paid", 0.0)
            interest_194a[first_word]["tds_deducted"] += rec.get("tds_deducted", 0.0)

    print("\n26AS vs DB INTEREST RECONCILIATION:")
    print(f"{'Bank':<35} {'26AS (194A)':<18} {'DB Income':<18} {'Difference':<18}")
    print("-" * 90)

    total_26as = 0.0
    total_db = 0.0

    for first_word in sorted(deductor_to_account.keys()):
        account_id = deductor_to_account[first_word]
        bank_name = accounts[account_id]

        db_amount = interest_by_account[account_id]["total"]

        if first_word in interest_194a:
            amount_26as = interest_194a[first_word]["amount_paid"]
        else:
            amount_26as = 0.0

        diff = amount_26as - db_amount
        total_26as += amount_26as
        total_db += db_amount

        print(f"{bank_name:<35} {amount_26as:>16,.2f} {db_amount:>16,.2f} {diff:>16,.2f}")

    print("-" * 90)
    total_diff = total_26as - total_db
    print(f"{'TOTAL':<35} {total_26as:>16,.2f} {total_db:>16,.2f} {total_diff:>16,.2f}")


def print_tds_summary(data, txns):
    """Print TDS from 26AS and search for TDS in transactions."""
    # Sum TDS from 26AS
    total_tds_26as = data.get("total_tds", 0.0) if data else 0.0

    print("\nTDS SUMMARY:")
    print(f"26AS Total TDS (all parts): {total_tds_26as:,.2f}")

    # Search for TDS in transaction descriptions
    tds_count = 0
    tds_total = 0.0
    for txn_account_id, txn_type, category, description, amount in txns:
        if description and ("TDS" in description.upper() or "TAX DEDUCT" in description.upper()):
            tds_count += 1
            tds_total += amount

    if tds_count > 0:
        print(f"DB TDS transactions found: {tds_count} rows, total {tds_total:,.2f}")
    else:
        print("DB TDS transactions found: None (no TDS entries in transaction descriptions)")


def print_ais_tis_summary():
    """Fetch and print AIS/TIS data."""
    print("\nAIS PARSING:")
    ais_data, ais_error = fetch_ais_data()
    if ais_error:
        print(f"  Error: {ais_error}")
    elif ais_data:
        # AIS returns: dividend, savings_interest, fd_interest, business_receipts, tds, details
        dividend = ais_data.get("dividend", 0.0)
        savings_interest = ais_data.get("savings_interest", 0.0)
        fd_interest = ais_data.get("fd_interest", 0.0)
        business_receipts = ais_data.get("business_receipts", 0.0)
        tds = ais_data.get("tds", 0.0)
        details = ais_data.get("details", [])

        total_interest = savings_interest + fd_interest
        print(f"  Detail rows: {len(details)}")
        print(f"  Dividend: {dividend:,.2f}")
        print(f"  Savings Interest: {savings_interest:,.2f}")
        print(f"  FD Interest: {fd_interest:,.2f}")
        print(f"  Total Interest: {total_interest:,.2f}")
        print(f"  Business Receipts: {business_receipts:,.2f}")
        print(f"  TDS: {tds:,.2f}")
    else:
        print("  AIS file not found or parsing returned None")

    print("\nTIS PARSING:")
    tis_data, tis_error = fetch_tis_data()
    if tis_error:
        print(f"  Error: {tis_error}")
    elif tis_data:
        # TIS typically has savings_interest and fd_interest
        savings_interest = tis_data.get("savings_interest", 0.0)
        fd_interest = tis_data.get("fd_interest", 0.0)
        dividend = tis_data.get("dividend", 0.0)
        business_receipts = tis_data.get("business_receipts", 0.0)
        total_interest = savings_interest + fd_interest
        print(f"  Dividend: {dividend:,.2f}")
        print(f"  Savings Interest: {savings_interest:,.2f}")
        print(f"  FD Interest: {fd_interest:,.2f}")
        print(f"  Total Interest: {total_interest:,.2f}")
        print(f"  Business Receipts: {business_receipts:,.2f}")
    else:
        print("  TIS file not found or parsing returned None")


def main():
    """Main reconciliation logic."""
    print_section("TAX RECONCILIATION REPORT")

    # Fetch 26AS
    data_26as = fetch_26as_data()

    # Fetch database data
    accounts = get_bank_accounts()
    txns = get_transactions_by_account()

    # Print 26AS summary
    print_section("1. 26AS RECORDS BY DEDUCTOR")
    print_26as_summary(data_26as)

    # Print DB interest by account
    print_section("2. DB INTEREST INCOME BY ACCOUNT")
    interest_by_account = get_interest_by_account(accounts, txns)
    print(f"{'Account ID':<12} {'Bank Name':<35} {'Row Count':<10} {'Total Interest':<15}")
    print("-" * 75)
    for account_id, bank_name in sorted(accounts.items()):
        data = interest_by_account[account_id]
        print(f"{account_id:<12} {bank_name:<35} {data['count']:<10} {data['total']:>13,.2f}")

    # Match 26AS to DB
    print_section("3. 26AS vs DB RECONCILIATION (SECTION 194A - INTEREST)")
    if data_26as:
        match_26as_to_db(data_26as, interest_by_account, accounts)
    else:
        print("ERROR: Could not load 26AS data for reconciliation.")

    # TDS summary
    print_section("4. TDS ANALYSIS")
    if data_26as:
        print_tds_summary(data_26as, txns)

    # AIS/TIS
    print_section("5. AIS AND TIS PARSING")
    print_ais_tis_summary()

    print_section("END OF REPORT")


if __name__ == "__main__":
    main()
