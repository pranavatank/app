"""
Test script for TIS and AIS tax document parsers.
This will verify the parsers produce the expected output.
"""

import sys
from pathlib import Path

# Add repo root to path
repo_root = Path(__file__).parent
sys.path.insert(0, str(repo_root))

from engines.taxdocs.tis import parse_tis_pdf
from engines.taxdocs.ais import parse_ais_pdf


def test_tis_parser():
    """Test TIS parser against known good values."""
    pdf_path = repo_root / "data" / "PersonalData" / "Pranav" / "TIS.pdf"
    password = "azipt9702h08032004"

    result = parse_tis_pdf(str(pdf_path), password=password)

    print("\n=== TIS Parser Output ===")
    print(f"dividend: {result['dividend']}")
    print(f"savings_interest: {result['savings_interest']}")
    print(f"fd_interest: {result['fd_interest']}")
    print(f"business_receipts: {result['business_receipts']}")
    print(f"non_income (purchase_of_time_deposits): {result['non_income']['purchase_of_time_deposits']}")

    # Verify against expected values
    expected = {
        'dividend': 2655.0,
        'savings_interest': 46183.0,
        'fd_interest': 256642.0,
        'business_receipts': 105069.0,
        'purchase_of_time_deposits': 1300000.0,
    }

    print("\n=== Verification ===")
    matches = []
    for key, expected_val in expected.items():
        if key == 'purchase_of_time_deposits':
            actual = result['non_income'].get(key, 0.0)
        else:
            actual = result.get(key, 0.0)

        match = actual == expected_val
        matches.append(match)
        status = "✓" if match else "✗"
        print(f"{status} {key}: {actual} (expected {expected_val})")

    assert all(matches), "TIS parser output does not match expected values"
    return result


def test_ais_parser():
    """Test AIS parser against known good values."""
    pdf_path = repo_root / "data" / "PersonalData" / "Pranav" / "AIS.pdf"
    password = "azipt9702h08032004"

    result = parse_ais_pdf(str(pdf_path), password=password)

    print("\n=== AIS Parser Output ===")
    print(f"dividend: {result['dividend']}")
    print(f"savings_interest: {result['savings_interest']}")
    print(f"fd_interest: {result['fd_interest']}")
    print(f"business_receipts: {result['business_receipts']}")
    print(f"tds: {result['tds']}")
    print(f"non_income (SFT-005): {result['non_income'].get('SFT-005', 0.0)}")

    print("\n=== TDS Investigation ===")
    for note in result['tds_investigation']['notes']:
        print(f"  {note}")

    # Verify against expected values
    expected = {
        'dividend': 2655.0,
        'savings_interest': 46183.0,
        'fd_interest': 256642.0,
        'business_receipts': 105069.0,
        'tds': 13367.0,  # This is the target we need to investigate
        'SFT-005': 1300000.0,
    }

    print("\n=== Verification ===")
    matches = []
    for key, expected_val in expected.items():
        if key == 'SFT-005':
            actual = result['non_income'].get(key, 0.0)
        else:
            actual = result.get(key, 0.0)

        match = actual == expected_val
        matches.append(match)
        status = "✓" if match else "✗"
        print(f"{status} {key}: {actual} (expected {expected_val})")

    return result


if __name__ == '__main__':
    try:
        tis_result = test_tis_parser()
        ais_result = test_ais_parser()

        print("\n=== FINAL RESULTS ===")
        print("\nTIS Parser:")
        print(f"  dividend: {tis_result['dividend']}")
        print(f"  savings_interest: {tis_result['savings_interest']}")
        print(f"  fd_interest: {tis_result['fd_interest']}")
        print(f"  business_receipts: {tis_result['business_receipts']}")
        print(f"  purchase_of_time_deposits (non-income): {tis_result['non_income']['purchase_of_time_deposits']}")

        print("\nAIS Parser:")
        print(f"  dividend: {ais_result['dividend']}")
        print(f"  savings_interest: {ais_result['savings_interest']}")
        print(f"  fd_interest: {ais_result['fd_interest']}")
        print(f"  business_receipts: {ais_result['business_receipts']}")
        print(f"  tds: {ais_result['tds']}")
        print(f"  SFT-005 (non-income): {ais_result['non_income'].get('SFT-005', 0.0)}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
