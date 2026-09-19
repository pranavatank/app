#!/usr/bin/env python
"""
tools/extraction_audit.py - Extraction quality audit for modern vs legacy parsers.

Compares both parsers on three real statements and prints a table with:
- Row count
- Confidence score
- Balance-walk failure count
- Field non-null counts: reference_no, mode, category, balance_after
- Transaction type split (Income vs Expense)

Usage:
    .venv\Scripts\python.exe tools/extraction_audit.py
"""

import sys
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
import os
from pathlib import Path

# Ensure we can import from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from engines.statement import parse_statement_pdf
from engines.statement.validate import confidence, balance_walk, normalise_order
from engines.statement_parser import parse_statement_with_debug


STATEMENTS = [
    ("Jana - Pranav.pdf", "Jana"),
    ("IDFC.pdf", "IDFC"),
    ("Ujjivan - Pranav.pdf", "Ujjivan"),
]

STATEMENT_DIR = "data/PersonalData/Pranav/Statement"


def count_non_null(transactions, field):
    """Count non-null values for a field."""
    return sum(1 for t in transactions if t.get(field))


def count_transaction_types(transactions):
    """Count Income vs Expense transactions."""
    income = sum(1 for t in transactions if t.get("transaction_type") == "Income")
    expense = sum(1 for t in transactions if t.get("transaction_type") == "Expense")
    return income, expense


def anonymize_description(desc):
    """Remove account numbers and sensitive info from description."""
    if not desc:
        return desc
    # Remove account numbers (e.g., 4522030015435122/1 or FD300014105382)
    import re
    desc = re.sub(r'\b\d{16}(/\d+)?\b', 'XXXX', desc)
    desc = re.sub(r'\bFD\d{12,}\b', 'FDXXXX', desc)
    return desc


def audit_modern(file_path):
    """Audit modern parser."""
    try:
        txns = parse_statement_pdf(file_path)
        # Normalize order BEFORE validation (as the modern engine does)
        txns = normalise_order(txns)
        conf = confidence(txns)
        failing = balance_walk(txns)
        income, expense = count_transaction_types(txns)
        return {
            "rows": len(txns),
            "confidence": conf,
            "failures": len(failing),
            "refs": count_non_null(txns, "reference_no"),
            "modes": count_non_null(txns, "mode"),
            "categories": count_non_null(txns, "category"),
            "balances": count_non_null(txns, "balance_after"),
            "income": income,
            "expense": expense,
            "transactions": txns,
        }
    except Exception as e:
        return {"error": str(e)}


def audit_legacy(file_path):
    """Audit legacy parser."""
    try:
        txns, debug_info = parse_statement_with_debug(file_path, "pdf")
        # Legacy parser does NOT normalize order; confidence/balance_walk will be evaluated
        # on potentially descending order
        conf = confidence(txns)
        failing = balance_walk(txns)
        income, expense = count_transaction_types(txns)
        return {
            "rows": len(txns),
            "confidence": conf,
            "failures": len(failing),
            "refs": count_non_null(txns, "reference_no"),
            "modes": count_non_null(txns, "mode"),
            "categories": count_non_null(txns, "category"),
            "balances": count_non_null(txns, "balance_after"),
            "income": income,
            "expense": expense,
            "transactions": txns,
        }
    except Exception as e:
        return {"error": str(e)}


def main():
    """Run audit and print comparison table."""
    print("\n" + "=" * 100)
    print("STATEMENT EXTRACTION AUDIT - Modern vs Legacy Parser")
    print("=" * 100 + "\n")

    for filename, label in STATEMENTS:
        file_path = os.path.join(STATEMENT_DIR, filename)
        if not os.path.exists(file_path):
            print(f"SKIP {label}: File not found\n")
            continue

        print(f"Statement: {label}")
        print("-" * 100)

        modern = audit_modern(file_path)
        legacy = audit_legacy(file_path)

        if "error" in modern:
            print(f"  Modern parser FAILED: {modern['error']}\n")
            continue

        if "error" in legacy:
            print(f"  Legacy parser FAILED: {legacy['error']}\n")
            continue

        # Print side-by-side comparison
        print(f"{'Metric':<25} {'Modern':<20} {'Legacy':<20} {'D':<10}")
        print("-" * 75)

        # Rows
        delta = modern["rows"] - legacy["rows"]
        delta_str = f"{delta:+d}" if delta != 0 else "-"
        print(f"{'Row count':<25} {modern['rows']:<20} {legacy['rows']:<20} {delta_str:<10}")

        # Confidence
        delta = modern["confidence"] - legacy["confidence"]
        delta_str = f"{delta:+.1%}" if delta != 0 else "-"
        print(f"{'Confidence':<25} {modern['confidence']:.1%}{'':<14} {legacy['confidence']:.1%}{'':<14} {delta_str:<10}")

        # Failures
        delta = modern["failures"] - legacy["failures"]
        delta_str = f"{delta:+d}" if delta != 0 else "-"
        print(f"{'Balance failures':<25} {modern['failures']:<20} {legacy['failures']:<20} {delta_str:<10}")

        # Reference_no non-null count
        delta = modern["refs"] - legacy["refs"]
        delta_str = f"{delta:+d}" if delta != 0 else "-"
        ref_pct_modern = f"{modern['refs']}/{modern['rows']}" if modern['rows'] > 0 else "0"
        ref_pct_legacy = f"{legacy['refs']}/{legacy['rows']}" if legacy['rows'] > 0 else "0"
        print(f"{'Reference_no (non-null)':<25} {ref_pct_modern:<20} {ref_pct_legacy:<20} {delta_str:<10}")

        # Mode non-null count
        delta = modern["modes"] - legacy["modes"]
        delta_str = f"{delta:+d}" if delta != 0 else "-"
        print(f"{'Mode (non-null)':<25} {modern['modes']:<20} {legacy['modes']:<20} {delta_str:<10}")

        # Category non-null count
        delta = modern["categories"] - legacy["categories"]
        delta_str = f"{delta:+d}" if delta != 0 else "-"
        print(f"{'Category (non-null)':<25} {modern['categories']:<20} {legacy['categories']:<20} {delta_str:<10}")

        # Balance_after non-null count
        delta = modern["balances"] - legacy["balances"]
        delta_str = f"{delta:+d}" if delta != 0 else "-"
        print(f"{'Balance_after (non-null)':<25} {modern['balances']:<20} {legacy['balances']:<20} {delta_str:<10}")

        # Transaction type split
        print(f"{'Income count':<25} {modern['income']:<20} {legacy['income']:<20} {modern['income'] - legacy['income']:+d}")
        print(f"{'Expense count':<25} {modern['expense']:<20} {legacy['expense']:<20} {modern['expense'] - legacy['expense']:+d}")

        print()


if __name__ == "__main__":
    main()
