r"""tools/taxdoc_import.py — Headless CLI for importing tax documents into the DB.

Parses 26AS/AIS/TIS PDFs from a directory and persists them to the database,
then reads back and verifies the stored data.

Usage:
  .venv\Scripts\python.exe tools/taxdoc_import.py [--person-id 1]
      [--dir data/PersonalData/Pranav] [--financial-year 2025-26]
      [--password-file data/PersonalData/Pranav/password.txt] [--dry-run]
"""

import sys
import os
import argparse
from pathlib import Path

# UTF-8 stdout header FIRST, before any other import
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from engines.taxdocs.form26as import parse_form26as_pdf
from engines.taxdocs.ais import parse_ais_pdf
from engines.taxdocs.tis import parse_tis_pdf
from engines.taxdocs.persist import (
    persist_form26as,
    persist_ais_tis,
    financial_year_from_assessment_year,
    SOURCE_TYPE_AIS,
    SOURCE_TYPE_TIS,
)
from models.form26as import get_form26as_import, get_form26as_records
from models.ais_tis_import import get_ais_tis_data
from core.backup_manager import create_backup
from config import get_current_financial_year


EXPECTED = {
    "form26as_total_tds": 13367.0,
    "form26as_record_count": 158,
    "ais_fd_interest": 256642.0,
    "ais_savings_interest": 46183.0,
    "ais_dividend": 2655.0,
    "ais_total_interest": 302825.0,
    "ais_tds": 12073.0,
}


def read_ais_tis_password(password_file: str) -> str | None:
    """Read AIS/TIS password from a file.

    Scans lines for one whose lowercased text contains both "ais" and "tis"
    and a ":", returns the text after the last ":", stripped.
    Returns None if file is absent or no line matches.
    """
    if not os.path.exists(password_file):
        return None

    try:
        with open(password_file, "r", encoding="utf-8") as f:
            for line in f:
                line_lower = line.lower()
                if "ais" in line_lower and "tis" in line_lower and ":" in line:
                    # Return text after last colon
                    return line.split(":")[-1].strip()
    except Exception:
        pass

    return None


def read_equitas_password(password_file: str) -> str | None:
    """Read Equitas statement password from a file.

    Scans lines for one whose lowercased text contains "equitas"
    and a ":", returns the text after the last ":", stripped.
    Returns None if file is absent or no line matches.
    """
    if not os.path.exists(password_file):
        return None

    try:
        with open(password_file, "r", encoding="utf-8") as f:
            for line in f:
                line_lower = line.lower()
                if "equitas" in line_lower and ":" in line:
                    # Return text after last colon
                    return line.split(":")[-1].strip()
    except Exception:
        pass

    return None


def import_all(
    person_id: int,
    doc_dir: str,
    financial_year: str | None,
    password: str | None,
    password_file: str | None,
    dry_run: bool,
) -> int:
    """Import all tax documents from a directory.

    Returns 0 on success (all VERIFY checks passed), 1 otherwise.
    """
    # Resolve password in order: arg -> env var -> file -> None
    resolved_password = password
    if not resolved_password:
        resolved_password = os.environ.get("AIS_TIS_PASSWORD")

    if not resolved_password and password_file:
        resolved_password = read_ais_tis_password(password_file)

    # Report password status (never print the actual password)
    if resolved_password:
        print("password: loaded from file")
    else:
        print("password: not supplied")

    # Back up first (unless dry-run)
    if not dry_run:
        backup_path = create_backup()
        if backup_path:
            print(f"backup: {backup_path}")
        else:
            print("backup: FAILED")
            return 1

    # Parse 26AS (not encrypted, no password needed)
    path_26as = os.path.join(doc_dir, "26AS.pdf")
    parsed_26as = None
    if os.path.exists(path_26as):
        try:
            parsed_26as = parse_form26as_pdf(path_26as, password=None, debug={})
            ay = parsed_26as.get("assessment_year", "")
            fy = financial_year or financial_year_from_assessment_year(ay) or get_current_financial_year()
            records = parsed_26as.get("records", [])
            part_ii = parsed_26as.get("part_ii", [])
            total_tds = parsed_26as.get("total_tds", 0.0)
            print(f"26AS: ay={ay} fy={fy} records={len(records)} part_ii={len(part_ii)} total_tds={total_tds}")
        except Exception as e:
            print(f"26AS: error parsing: {e}")
            parsed_26as = None
    else:
        print("26AS: file not found, skipped")

    # Determine FY for AIS/TIS
    if parsed_26as:
        fy = financial_year or financial_year_from_assessment_year(parsed_26as.get("assessment_year")) or get_current_financial_year()
    else:
        fy = financial_year or get_current_financial_year()

    # Parse AIS
    path_ais = os.path.join(doc_dir, "AIS.pdf")
    parsed_ais = None
    if os.path.exists(path_ais):
        try:
            parsed_ais = parse_ais_pdf(path_ais, password=resolved_password)
            fd_interest = parsed_ais.get("fd_interest", 0.0)
            savings_interest = parsed_ais.get("savings_interest", 0.0)
            dividend = parsed_ais.get("dividend", 0.0)
            tds = parsed_ais.get("tds", 0.0)
            details = parsed_ais.get("details", [])
            print(f"AIS: fd_interest={fd_interest} savings_interest={savings_interest} dividend={dividend} tds={tds} details={len(details)}")
        except Exception as e:
            # Check if it's an encryption error
            if "password" in str(e).lower() or "encrypted" in str(e).lower():
                if not resolved_password:
                    print("AIS: skipped (password required)")
                    parsed_ais = None
                else:
                    print(f"AIS: error parsing: {e}")
                    parsed_ais = None
            else:
                print(f"AIS: error parsing: {e}")
                parsed_ais = None
    else:
        print("AIS: file not found, skipped")

    # Parse TIS
    path_tis = os.path.join(doc_dir, "TIS.pdf")
    parsed_tis = None
    if os.path.exists(path_tis):
        try:
            parsed_tis = parse_tis_pdf(path_tis, password=resolved_password)
            fd_interest = parsed_tis.get("fd_interest", 0.0)
            savings_interest = parsed_tis.get("savings_interest", 0.0)
            dividend = parsed_tis.get("dividend", 0.0)
            details = parsed_tis.get("details", [])
            print(f"TIS: fd_interest={fd_interest} savings_interest={savings_interest} dividend={dividend} details={len(details)}")
        except Exception as e:
            # Check if it's an encryption error
            if "password" in str(e).lower() or "encrypted" in str(e).lower():
                if not resolved_password:
                    print("TIS: skipped (password required)")
                    parsed_tis = None
                else:
                    print(f"TIS: error parsing: {e}")
                    parsed_tis = None
            else:
                print(f"TIS: error parsing: {e}")
                parsed_tis = None
    else:
        print("TIS: file not found, skipped")

    # Persist to database (unless dry-run)
    if not dry_run:
        if parsed_26as:
            persist_form26as(person_id, parsed_26as, source_file="26AS.pdf")
        if parsed_ais:
            persist_ais_tis(person_id, parsed_ais, SOURCE_TYPE_AIS, fy, source_file="AIS.pdf")
        if parsed_tis:
            persist_ais_tis(person_id, parsed_tis, SOURCE_TYPE_TIS, fy, source_file="TIS.pdf")

    # Skip VERIFY in dry-run mode
    if dry_run:
        return 0

    # Read back and verify
    print("\nVERIFY:")
    all_passed = True

    # Check Form 26AS
    import_26as = get_form26as_import(person_id, fy)
    if import_26as:
        total_tds = import_26as.get("total_tds", 0.0)
        records = get_form26as_records(import_26as.get("import_id"))
        record_count = len(records)

        # Check total_tds
        if abs(total_tds - EXPECTED["form26as_total_tds"]) < 0.01:
            print(f"PASS: form26as_total_tds == {total_tds}")
        else:
            print(f"FAIL: form26as_total_tds expected {EXPECTED['form26as_total_tds']}, got {total_tds}")
            all_passed = False

        # Check record_count
        if record_count == EXPECTED["form26as_record_count"]:
            print(f"PASS: form26as_record_count == {record_count}")
        else:
            print(f"FAIL: form26as_record_count expected {EXPECTED['form26as_record_count']}, got {record_count}")
            all_passed = False
    else:
        print(f"FAIL: form26as_total_tds expected {EXPECTED['form26as_total_tds']}, got None")
        print(f"FAIL: form26as_record_count expected {EXPECTED['form26as_record_count']}, got None")
        all_passed = False

    # Check AIS
    ais_data = get_ais_tis_data(person_id, fy, SOURCE_TYPE_AIS)
    if ais_data:
        fd_interest = ais_data.get("fd_interest", 0.0)
        savings_interest = ais_data.get("savings_interest", 0.0)
        dividend = ais_data.get("dividend_income", 0.0)
        tds = ais_data.get("tds_deducted", 0.0)
        total_interest = fd_interest + savings_interest + ais_data.get("other_interest", 0.0)

        # Check fd_interest
        if abs(fd_interest - EXPECTED["ais_fd_interest"]) < 0.01:
            print(f"PASS: ais_fd_interest == {fd_interest}")
        else:
            print(f"FAIL: ais_fd_interest expected {EXPECTED['ais_fd_interest']}, got {fd_interest}")
            all_passed = False

        # Check savings_interest
        if abs(savings_interest - EXPECTED["ais_savings_interest"]) < 0.01:
            print(f"PASS: ais_savings_interest == {savings_interest}")
        else:
            print(f"FAIL: ais_savings_interest expected {EXPECTED['ais_savings_interest']}, got {savings_interest}")
            all_passed = False

        # Check dividend
        if abs(dividend - EXPECTED["ais_dividend"]) < 0.01:
            print(f"PASS: ais_dividend == {dividend}")
        else:
            print(f"FAIL: ais_dividend expected {EXPECTED['ais_dividend']}, got {dividend}")
            all_passed = False

        # Check total_interest
        if abs(total_interest - EXPECTED["ais_total_interest"]) < 0.01:
            print(f"PASS: ais_total_interest == {total_interest}")
        else:
            print(f"FAIL: ais_total_interest expected {EXPECTED['ais_total_interest']}, got {total_interest}")
            all_passed = False

        # Check tds
        if abs(tds - EXPECTED["ais_tds"]) < 0.01:
            print(f"PASS: ais_tds == {tds}")
        else:
            print(f"FAIL: ais_tds expected {EXPECTED['ais_tds']}, got {tds}")
            all_passed = False
    else:
        print(f"FAIL: ais_fd_interest expected {EXPECTED['ais_fd_interest']}, got None")
        print(f"FAIL: ais_savings_interest expected {EXPECTED['ais_savings_interest']}, got None")
        print(f"FAIL: ais_dividend expected {EXPECTED['ais_dividend']}, got None")
        print(f"FAIL: ais_total_interest expected {EXPECTED['ais_total_interest']}, got None")
        print(f"FAIL: ais_tds expected {EXPECTED['ais_tds']}, got None")
        all_passed = False

    return 0 if all_passed else 1


def main() -> int:
    """Parse command-line arguments and run import."""
    parser = argparse.ArgumentParser(
        description="Import tax documents (26AS/AIS/TIS) from a directory."
    )
    parser.add_argument(
        "--person-id",
        type=int,
        default=1,
        help="Person ID to import for (default: 1)",
    )
    parser.add_argument(
        "--dir",
        type=str,
        default="data/PersonalData/Pranav",
        help="Directory containing PDF files (default: data/PersonalData/Pranav)",
    )
    parser.add_argument(
        "--financial-year",
        type=str,
        default=None,
        help="Financial year (e.g. 2025-26), overrides assessment year",
    )
    parser.add_argument(
        "--password-file",
        type=str,
        default="data/PersonalData/Pranav/password.txt",
        help="Path to file containing AIS/TIS password",
    )
    parser.add_argument(
        "--password",
        type=str,
        default=None,
        help="AIS/TIS password (if not provided, looks in env var and file)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and verify without writing to database",
    )

    args = parser.parse_args()

    return import_all(
        person_id=args.person_id,
        doc_dir=args.dir,
        financial_year=args.financial_year,
        password=args.password,
        password_file=args.password_file,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    sys.exit(main())
