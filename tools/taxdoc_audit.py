#!/usr/bin/env python3
"""
taxdoc_audit.py — Audit extracted tax documents (26AS, AIS, TIS)

Validates extraction quality by comparing extracted data against expected totals.
Reports record counts, per-deductor summaries, and reconciliation status.

Usage:
    python tools/taxdoc_audit.py <path/to/26AS.pdf> [--show-errors]
"""

import sys
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
import argparse
from pathlib import Path

def audit_26as(pdf_path, show_errors=False):
    """Audit Form 26AS extraction."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from engines.taxdocs.form26as import parse_form26as_pdf

    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        print(f"Error: File not found: {pdf_path}")
        return False

    print(f"\n=== Form 26AS Audit ===")
    print(f"File: {pdf_file.name}")
    print()

    result = parse_form26as_pdf(str(pdf_file), password=None, debug={})

    # Header info
    print(f"PAN: {result['pan']}")
    print(f"Name: {result['name']}")
    print(f"Assessment Year: {result['assessment_year']}")
    print()

    # Totals
    print(f"Total TDS (from deductor summaries): ₹{result['total_tds']:,.2f}")
    print(f"Part-I detail records: {len(result['records'])}")
    print(f"Part-II detail records: {len(result['part_ii'])}")
    total_records = len(result['records']) + len(result['part_ii'])
    print(f"Total records extracted: {total_records}")
    print()

    # Part-I breakdown by deductor
    print("Part-I Records by Deductor:")
    print("-" * 70)
    part_i_deductors = {}
    for rec in result['records']:
        key = (rec.get('deductor_name', 'UNKNOWN'), rec.get('deductor_tan', ''))
        if key not in part_i_deductors:
            part_i_deductors[key] = {'count': 0, 'gross': 0.0, 'tds': 0.0}
        part_i_deductors[key]['count'] += 1
        part_i_deductors[key]['gross'] += rec.get('amount_paid', 0.0)
        part_i_deductors[key]['tds'] += rec.get('tds_deducted', 0.0)

    for (name, tan), stats in sorted(part_i_deductors.items()):
        print(f"  {name[:40]:40s} | {tan:12s} | {stats['count']:3d} rows | Gross: ₹{stats['gross']:12,.2f} | TDS: ₹{stats['tds']:12,.2f}")

    print()
    print("Part-II Records (15G/15H) by Deductor:")
    print("-" * 70)
    part_ii_deductors = {}
    for rec in result['part_ii']:
        key = (rec.get('deductor_name', 'UNKNOWN'), rec.get('deductor_tan', ''))
        if key not in part_ii_deductors:
            part_ii_deductors[key] = {'count': 0, 'amount': 0.0}
        part_ii_deductors[key]['count'] += 1
        part_ii_deductors[key]['amount'] += rec.get('amount_paid', 0.0)

    for (name, tan), stats in sorted(part_ii_deductors.items()):
        print(f"  {name[:40]:40s} | {tan:12s} | {stats['count']:3d} rows | Amount: ₹{stats['amount']:12,.2f}")

    print()
    print("Reconciliation:")
    print("-" * 70)

    # Verify TDS total
    calculated_tds = sum(rec.get('tds_deducted', 0.0) for rec in result['records'])
    expected_tds = result['total_tds']
    tds_match = abs(calculated_tds - expected_tds) < 0.01
    status = "✓ PASS" if tds_match else "✗ FAIL"
    print(f"  TDS Reconciliation: {status}")
    print(f"    Deductor summaries: ₹{expected_tds:,.2f}")
    print(f"    Sum of detail rows: ₹{calculated_tds:,.2f}")
    print(f"    Match: {tds_match}")

    # Calculate net gross
    net_gross_i = sum(rec.get('amount_paid', 0.0) for rec in result['records'])
    net_gross_ii = sum(rec.get('amount_paid', 0.0) for rec in result['part_ii'])
    print(f"\n  Gross Amounts:")
    print(f"    Part-I net: ₹{net_gross_i:,.2f}")
    print(f"    Part-II net: ₹{net_gross_ii:,.2f}")
    print(f"    Combined: ₹{net_gross_i + net_gross_ii:,.2f}")

    return tds_match


def main():
    parser = argparse.ArgumentParser(description='Audit extracted tax documents')
    parser.add_argument('pdf', help='Path to Form 26AS PDF')
    parser.add_argument('--show-errors', action='store_true', help='Show detailed error rows')

    args = parser.parse_args()

    success = audit_26as(args.pdf, show_errors=args.show_errors)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
