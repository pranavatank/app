import sys
import os
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

os.environ["QT_QPA_PLATFORM"]="offscreen"

import argparse
import json
import hashlib
import sqlite3
import tempfile
from pathlib import Path
from datetime import date, datetime, timedelta, timedelta as td
from dateutil.relativedelta import relativedelta

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

REAL_DB = BASE / "data" / "financial.db"
REBUILD_DIR = BASE / "tools" / "real_ui_tests" / "screenshots" / "rebuild"
REBUILD_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_FD_RATE = 7.5


def fingerprint_real_db():
    conn = sqlite3.connect(f"file:{REAL_DB}?mode=ro", uri=True)
    result = {}

    # Get all tables from sqlite_master (excludes sqlite_* internal tables)
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()]

    for tbl in tables:
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM [{tbl}]").fetchone()[0]
            rows = conn.execute(f"SELECT * FROM [{tbl}] ORDER BY rowid").fetchall()
            sha = hashlib.sha256(repr(rows).encode("utf-8", errors="replace")).hexdigest()
            result[tbl] = {"count": count, "sha256": sha}
        except sqlite3.OperationalError:
            result[tbl] = {"count": 0, "sha256": ""}

    conn.close()
    return result


def test_fingerprint(output_name=None):
    fp = fingerprint_real_db()
    if output_name:
        output_file = REBUILD_DIR / f"FP_{output_name}.json"
    else:
        output_file = REBUILD_DIR / "P4_verify_fingerprint.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(fp, f, indent=2)
    print(f"PASS fingerprint observed=captured expected=baseline output={output_file}")
    return True


def diff_fingerprints(before, after, allowed=()):
    """Compare two fingerprints and return list of changed tables."""
    changed = []
    for table in before.keys():
        if table not in after:
            continue
        if before[table]["count"] != after[table]["count"] or before[table]["sha256"] != after[table]["sha256"]:
            if table not in allowed:
                changed.append(table)
    changed += [t for t in set(before) ^ set(after) if t not in allowed]
    return changed


def compare_fingerprints(name_a, name_b, allowed_tables=None):
    """Load two fingerprint files and compare them."""
    if allowed_tables is None:
        allowed_tables = ()

    fp_a_file = REBUILD_DIR / f"FP_{name_a}.json"
    fp_b_file = REBUILD_DIR / f"FP_{name_b}.json"

    if not fp_a_file.exists():
        print(f"ERROR: {fp_a_file} not found")
        return 1
    if not fp_b_file.exists():
        print(f"ERROR: {fp_b_file} not found")
        return 1

    with open(fp_a_file, "r", encoding="utf-8") as f:
        fp_a = json.load(f)
    with open(fp_b_file, "r", encoding="utf-8") as f:
        fp_b = json.load(f)

    changed = diff_fingerprints(fp_a, fp_b, allowed=allowed_tables)

    if changed:
        print(f"FAIL fingerprints differ in tables: {changed}")
        for table in changed:
            print(f"  {table}: a_count={fp_a[table]['count']} b_count={fp_b[table]['count']}")
        return 1
    else:
        print("PASS fingerprints match (no non-allowed tables changed)")
        return 0


def test_engines():
    from config import fy_date_range, FD_TDS_FORM_NAME, FD_TDS_FORM_NAME_SENIOR
    from engines.prediction_engine import (
        realised_income_to_date, project_fd_interest, project_bank_tds_risk,
        get_prediction_summary, TAXABLE_INCOME_CATEGORIES, _synthesise_fd, DEFAULT_FD_RATE
    )
    from engines.tax_engine import calculate_new_regime_tax
    from engines.advance_tax_engine import calculate_advance_tax
    from engines.interest_engine import fd_interest_accrued_to, _is_senior_citizen_in_fy
    from models.person import get_person
    from models.fixed_deposit import get_all_fds
    from models.transaction import get_transactions
    from core.database import get_connection
    from ui.widgets.money_label import format_inr
    from ui.dashboard_screen import _format_indian_number

    person_id = 1
    fy = "2025-26"
    as_of = date(2026, 3, 31)

    conn = sqlite3.connect(f"file:{REAL_DB}?mode=ro", uri=True)
    failures = []
    findings = []

    try:
        cur = conn.cursor()
        fy_start, fy_end = fy_date_range(fy)

        realised = realised_income_to_date(person_id, fy, as_of)
        taxable = realised["taxable"]
        non_taxable = realised["non_taxable"]

        sql_taxable = 0.0
        sql_non_taxable = 0.0
        sql_unclassified = 0.0

        rows = cur.execute("""
            SELECT amount, category, is_internal_transfer
            FROM Transactions
            WHERE person_id=? AND transaction_type='Income'
            AND transaction_date BETWEEN ? AND ?
            ORDER BY transaction_date
        """, (person_id, fy_start.isoformat(), fy_end.isoformat())).fetchall()

        for amount, category, is_internal_transfer in rows:
            amount = float(amount or 0)
            category = category or "Unclassified"
            if category in TAXABLE_INCOME_CATEGORIES:
                sql_taxable += amount
            elif (is_internal_transfer or category in {"FD Maturity", "Other Income"}):
                sql_non_taxable += amount
            else:
                sql_unclassified += amount

        if abs(taxable - sql_taxable) > 0.01:
            failures.append(f"realised_income taxable: observed={taxable} expected={sql_taxable}")
        else:
            print(f"PASS realised_income_to_date.taxable observed={taxable} expected={sql_taxable}")

        if abs(non_taxable - sql_non_taxable) > 0.01:
            failures.append(f"realised_income non_taxable: observed={non_taxable} expected={sql_non_taxable}")
        else:
            print(f"PASS realised_income_to_date.non_taxable observed={non_taxable} expected={sql_non_taxable}")

        fd_result = project_fd_interest(person_id, fy, as_of)
        fd_total = fd_result["total"]
        fd_est_count = fd_result["estimated_fd_count"]
        fd_known_count = fd_result["known_fd_count"]

        fds = get_all_fds(person_id=person_id)
        dated_fds_with_principal = [f for f in fds if f.get("principal_amount", 0) > 0 and f.get("start_date")]

        if not dated_fds_with_principal:
            findings.append(f"No FDs with principal > 0 and start_date found")
        else:
            dated_count = len(dated_fds_with_principal)
            expected_count = fd_est_count + fd_known_count

            if expected_count != dated_count:
                failures.append(f"project_fd_interest count mismatch: estimated+known={expected_count} expected={dated_count}")
            else:
                print(f"PASS project_fd_interest.count observed={expected_count} expected={dated_count}")

            total_computed = 0.0
            for fd in dated_fds_with_principal:
                fd_start = date.fromisoformat(fd["start_date"])
                if fd_start > fy_end:
                    continue

                synth_fd = _synthesise_fd(fd)
                fd_end = date.fromisoformat(synth_fd["maturity_date"])
                window_start = max(fd_start, fy_start)
                window_end = min(fd_end, fy_end)

                if window_start > window_end:
                    continue

                interest = fd_interest_accrued_to(synth_fd, window_end)
                if window_start > fd_start:
                    interest -= fd_interest_accrued_to(synth_fd, window_start - td(days=1))

                if interest > 0:
                    total_computed += interest

            if abs(total_computed - fd_total) > 1.0:
                failures.append(f"project_fd_interest.total: observed={fd_total} expected={total_computed}")
            else:
                print(f"PASS project_fd_interest.total observed={fd_total} expected={total_computed}")

        tds_risk = project_bank_tds_risk(person_id, fy, as_of)
        threshold = tds_risk["threshold"]
        form_name = tds_risk["form_name"]

        dob_row = cur.execute("SELECT date_of_birth FROM Person WHERE person_id=?", (person_id,)).fetchone()
        if dob_row and dob_row[0]:
            dob = date.fromisoformat(dob_row[0])
            sixty_date = dob + relativedelta(years=60)
            is_senior_expected = sixty_date <= fy_end
        else:
            is_senior_expected = False

        expected_form = FD_TDS_FORM_NAME_SENIOR if is_senior_expected else FD_TDS_FORM_NAME
        expected_threshold = 100000 if is_senior_expected else 50000

        if abs(threshold - expected_threshold) > 0.01:
            failures.append(f"tds_risk threshold: observed={threshold} expected={expected_threshold}")
        else:
            print(f"PASS project_bank_tds_risk.threshold observed={threshold} expected={expected_threshold}")

        if form_name != expected_form:
            failures.append(f"tds_risk form_name: observed={form_name} expected={expected_form}")
        else:
            print(f"PASS project_bank_tds_risk.form_name observed={form_name} expected={expected_form}")

        for bank in tds_risk["by_bank"]:
            interest = bank["projected_interest"]
            will_cross = bank["will_cross"]
            expected_cross = interest >= threshold
            if will_cross != expected_cross:
                failures.append(f"{bank['bank_name']} will_cross: {will_cross} expected {expected_cross}")

        summary = get_prediction_summary(person_id, fy, as_of)
        itr = summary.get("itr_actuals", {})
        ais = itr.get("ais")

        if not ais:
            failures.append(f"itr_actuals.ais missing")
        else:
            fd_interest_ais = ais.get("fd_interest", 0)
            savings_interest_ais = ais.get("savings_interest", 0)

            if abs(fd_interest_ais - 256642) > 1:
                failures.append(f"itr_actuals.ais.fd_interest: observed={fd_interest_ais} expected=256642")
            else:
                print(f"PASS itr_actuals.ais.fd_interest observed={fd_interest_ais} expected=256642")

            if abs(savings_interest_ais - 46183) > 1:
                failures.append(f"itr_actuals.ais.savings_interest: observed={savings_interest_ais} expected=46183")
            else:
                print(f"PASS itr_actuals.ais.savings_interest observed={savings_interest_ais} expected=46183")

        form26as = itr.get("form26as")
        if not form26as:
            failures.append(f"itr_actuals.form26as missing")
        else:
            total_tds = form26as.get("total_tds", 0)
            if abs(total_tds - 13367) > 1:
                failures.append(f"itr_actuals.form26as.total_tds: observed={total_tds} expected=13367")
            else:
                print(f"PASS itr_actuals.form26as.total_tds observed={total_tds} expected=13367")

        test_cases = [
            (1200000, 0, 0),
            (1210000, 0, 10400),
            (1300000, 0, 78000),
            (1275000, 1275000, 0),
            (350458, 0, 0),
            (6000000, 0, 1578720),
        ]

        for gross, salary, expected_tax in test_cases:
            result = calculate_new_regime_tax(gross, salary_income=salary, financial_year="2025-26")
            total_tax = result["total_tax"]
            if abs(total_tax - expected_tax) > 1:
                failures.append(f"tax({gross}, salary={salary}): observed={total_tax} expected={expected_tax}")
            else:
                print(f"PASS calculate_new_regime_tax({gross},{salary}) observed={total_tax} expected={expected_tax}")

        result = calculate_advance_tax(
            financial_year="2025-26",
            gross_income=100000,
            annual_tax=100000,
            is_senior_resident=False,
            has_business_income=False
        )
        installments = result.installments
        expected_cumulatives = [15000, 45000, 75000, 100000]

        if len(installments) >= 4:
            for i in range(min(4, len(installments))):
                amt_due = installments[i].amount_due
                expected = expected_cumulatives[i]
                if abs(amt_due - expected) > 1:
                    failures.append(f"advance_tax Q{i+1}: observed={amt_due} expected={expected}")
                else:
                    print(f"PASS advance_tax installment_{i+1} observed={amt_due} expected={expected}")

        test_formats = [
            (0.005, "₹0.01"),
            (1234567.899, "₹12,34,567.90"),
            (-100000.10, "-₹1,00,000.10"),
            (99.999, "₹100"),
            (256642, "₹2,56,642"),
            (-0.004, "₹0"),
        ]

        for value, expected_str in test_formats:
            result = format_inr(value)
            if result != expected_str:
                failures.append(f"format_inr({value}): observed={result} expected={expected_str}")
            else:
                print(f"PASS format_inr({value}) observed={result} expected={expected_str}")

        test_dash = [(0.005, "₹0.01"), (256642, "₹2,56,642"), (-0.004, "₹0")]
        for value, expected in test_dash:
            result = _format_indian_number(value)
            if result != expected:
                failures.append(f"_format_indian_number({value}): observed={result} expected={expected}")
            else:
                print(f"PASS _format_indian_number({value}) observed={result} expected={expected}")

    finally:
        conn.close()

    output_file = REBUILD_DIR / "P4_verify_engines.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({"failures": failures, "findings": findings}, f, indent=2)

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return False
    return True


def test_tempdb():
    tmpdir = tempfile.mkdtemp(prefix="finmgr_verify_")
    test_db = Path(tmpdir) / "verify.db"

    failures = []
    findings = []

    try:
        import config
        from core.database import initialise_database
        from models.person import add_person
        from models.bank_account import add_account
        from models.transaction import add_transaction
        from config import fy_date_range

        config.DB_PATH = str(test_db)

        from core import database
        from core import backup_manager
        database.DB_PATH = str(test_db)
        backup_manager.DB_PATH = str(test_db)

        assert str(test_db) != str(REAL_DB), "Test DB must not be real DB"

        initialise_database()

        person_id = add_person("Tmp Person", "2004-03-08", "XXXXX9999X")
        account_id = add_account(person_id, "Tmp Bank", "Savings", opening_balance=0.0, interest_rate=4.0)

        add_transaction(
            account_id=account_id, person_id=person_id, transaction_date="2025-03-10",
            transaction_type="Income", amount=500.0,
            category="Savings Interest", description="Opening", balance_after=10000.0,
            source="Test"
        )
        add_transaction(
            account_id=account_id, person_id=person_id, transaction_date="2025-06-01",
            transaction_type="Income", amount=100.0,
            category="Savings Interest", description="Mid", balance_after=10100.0,
            source="Test"
        )

        from engines.interest_engine import calculate_savings_interest_for_fy

        result = calculate_savings_interest_for_fy(account_id, "2025-26", 4.0, opening_balance=0.0)
        breakdown = result.get("breakdown", [])

        q1 = next((q for q in breakdown if q["quarter"] == "Q1"), None)
        if not q1:
            failures.append(f"Q1 breakdown missing from savings interest calculation")
        else:
            days = q1.get("days", 0)
            daily_product = q1.get("daily_product_sum", 0)

            if days != 91:
                failures.append(f"tempdb.opening_balance_setup Q1 days: observed={days} expected=91")
            else:
                print(f"PASS tempdb.opening_balance_setup.q1_days observed={days} expected=91")

            if daily_product != 913000:
                failures.append(f"tempdb.opening_balance_setup Q1 daily_product: observed={daily_product} expected=913000")
            else:
                print(f"PASS tempdb.opening_balance_setup.q1_daily_product observed={daily_product} expected=913000")

        from core.auth import setup_master_password, verify_login, change_password
        from models.bank_account import set_statement_password, get_statement_password
        from models.person import set_ais_tis_password, get_ais_tis_password

        setup_master_password("Tmp#Pass123")
        ok, _, key = verify_login("Tmp#Pass123")
        if not ok:
            failures.append("setup_master_password failed")
        else:
            print("PASS tempdb.setup_master_password observed=ok expected=ok")

            set_statement_password(account_id, "stmt-secret-1", key)
            set_ais_tis_password(person_id, "ais-secret-1", key)

            change_password("Tmp#Pass123", "Tmp#Pass456")

            ok_new, _, key_new = verify_login("Tmp#Pass456")
            ok_old, _, key_old = verify_login("Tmp#Pass123")

            if ok_new and not ok_old:
                print("PASS tempdb.change_password observed=ok expected=ok")
            else:
                failures.append(f"change_password: ok_new={ok_new} ok_old={ok_old}")

            ais_pwd = get_ais_tis_password(person_id, key_new)
            if ais_pwd == "ais-secret-1":
                print("PASS tempdb.get_ais_tis_password_with_new_key observed=ok expected=ok")
            else:
                failures.append(f"get_ais_tis_password with new key: {ais_pwd}")

            ais_pwd_old = get_ais_tis_password(person_id, key_old)
            if ais_pwd_old is None:
                print("PASS tempdb.get_ais_tis_password_with_old_key_fails observed=ok expected=ok")
            else:
                failures.append(f"get_ais_tis_password with old key should be None: {ais_pwd_old}")

            stmt_pwd = get_statement_password(account_id, key_new)
            if stmt_pwd == "stmt-secret-1":
                print("PASS tempdb.get_statement_password_with_new_key observed=ok expected=ok")
            else:
                failures.append(f"get_statement_password with new key: {stmt_pwd}")

            stmt_pwd_old = get_statement_password(account_id, key_old)
            if stmt_pwd_old is None:
                print("PASS tempdb.get_statement_password_with_old_key_fails observed=ok expected=ok")
            else:
                failures.append(f"get_statement_password with old key should be None: {stmt_pwd_old}")

            conn = sqlite3.connect(str(test_db))
            cur = conn.cursor()
            enc_before = cur.execute(
                "SELECT statement_password_enc FROM BankAccount WHERE account_id=?",
                (account_id,)
            ).fetchone()
            if enc_before:
                enc_before = enc_before[0]
                if isinstance(enc_before, str):
                    enc_before = enc_before.encode()

                corrupt_bytes = bytearray(enc_before)
                corrupt_bytes[0] = (corrupt_bytes[0] + 1) % 256
                cur.execute(
                    "UPDATE BankAccount SET statement_password_enc=? WHERE account_id=?",
                    (bytes(corrupt_bytes), account_id)
                )
                conn.commit()

                change_password("Tmp#Pass456", "Tmp#Pass789")

                enc_after = cur.execute(
                    "SELECT statement_password_enc FROM BankAccount WHERE account_id=?",
                    (account_id,)
                ).fetchone()

                if enc_after:
                    enc_after = enc_after[0]
                    if isinstance(enc_after, str):
                        enc_after = enc_after.encode()
                    if enc_after == enc_before:
                        findings.append(f"H12: corrupt ciphertext silently skipped (unchanged)")
                    else:
                        findings.append(f"H12: corrupt ciphertext was re-encrypted (changed)")

            conn.close()

            set_statement_password(account_id, "test-value", key_new)
            test_pwd = get_statement_password(account_id, key_new)
            if test_pwd == "test-value":
                print("PASS tempdb.password_persist observed=ok expected=ok")
            else:
                failures.append(f"password persist failed: {test_pwd}")

    except Exception as e:
        import traceback
        failures.append(f"tempdb exception: {str(e)}\n{traceback.format_exc()}")

    finally:
        import shutil
        try:
            shutil.rmtree(tmpdir)
        except:
            pass

    output_file = REBUILD_DIR / "P4_verify_tempdb.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({"failures": failures, "findings": findings}, f, indent=2)

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return False

    return True


def main():
    parser = argparse.ArgumentParser(description="Rebuild verification tool")
    parser.add_argument("--fingerprint", action="store_true", help="Fingerprint real DB")
    parser.add_argument("--out", type=str, help="Output name for fingerprint (writes to FP_NAME.json)")
    parser.add_argument("--compare", nargs=2, metavar=("A", "B"), help="Compare two fingerprints (A and B are names)")
    parser.add_argument("--allow", type=str, help="Comma-separated list of tables allowed to change in comparison")
    parser.add_argument("--engines", action="store_true", help="Test engine functions")
    parser.add_argument("--tempdb", action="store_true", help="Test with temporary DB")

    args = parser.parse_args()

    if not args.fingerprint and not args.engines and not args.tempdb and not args.compare:
        parser.print_help()
        return 1

    exit_code = 0

    if args.fingerprint:
        if not test_fingerprint(output_name=args.out):
            exit_code = 1

    if args.compare:
        allowed = ()
        if args.allow:
            allowed = tuple(t.strip() for t in args.allow.split(","))
        exit_code = compare_fingerprints(args.compare[0], args.compare[1], allowed_tables=allowed)

    if args.engines:
        if not test_engines():
            exit_code = 1

    if args.tempdb:
        if not test_tempdb():
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
