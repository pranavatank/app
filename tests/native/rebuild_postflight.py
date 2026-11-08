"""Bounded, read-only audit of the fresh rebuild against P0 source expectations.

This script does not initialize the application database or launch a GUI. It
re-parses the four statement PDFs, validates their balance walks, then compares
each parsed row as a multiset with the persisted statement-import rows.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path


BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE))

from tests.support.repo_paths import artifact_path

from tools.private_sources import get_personal_data_dir
from tests.native.rebuild_preflight import validate_statement_rows
from models.transaction import normalize_transaction_type

DB_PATH = BASE / "data" / "financial.db"
DEFAULT_OUT = artifact_path("rebuild") / "postflight.json"
EXPECTED_STATEMENTS = {
    "Jana": ("Jana - Pranav.pdf", 65),
    "IDFC FIRST": ("IDFC.pdf", 376),
    "Ujjivan": ("Ujjivan - Pranav.pdf", 27),
    "Equitas": ("Equitas.pdf", 39),
}
CENT = Decimal("0.01")


def money(v):
    try:
        number = Decimal(str(v))
        if not number.is_finite():
            raise ValueError("invalid monetary value")
        return number.quantize(CENT)
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("invalid monetary value") from None


def row_key(row):
    return (row[0], normalize_transaction_type(row[1]), money(row[2]), row[3] or "", row[4] or "", money(row[5]) if row[5] is not None else None)


def safe_diff(expected, actual):
    missing = expected - actual
    extra = actual - expected
    return {"expected_rows": sum(expected.values()), "actual_rows": sum(actual.values()),
            "missing_rows": sum(missing.values()), "extra_rows": sum(extra.values())}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    seed_path = DEFAULT_OUT.parent / "P0_expectations.json"
    if not seed_path.is_file():
        raise RuntimeError("P0_expectations.json is missing")
    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    if not DB_PATH.is_file():
        raise RuntimeError("fresh database is missing")

    # Parser-only Qt support, matching P0; no windows are constructed.
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from engines.statement import parse_statement_pdf
    from engines.taxdocs.form26as import parse_form26as_pdf
    from engines.taxdocs.ais import parse_ais_pdf
    from engines.taxdocs.tis import parse_tis_pdf
    from tests.native.rebuild_common import read_secret

    pdata = get_personal_data_dir(BASE)
    equitas_pw = read_secret("equitas")
    ais_pw = read_secret("ais_tis")
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    report = {"created_utc": datetime.now(timezone.utc).isoformat(), "status": "PASS", "checks": {}, "limitations": [
        "FD provenance is delegated to rebuild_p2_8_fd_origin.py; this audit reports ledger/tax rows and FD opening counts only.",
        "26AS verification compares imported row count and headline TDS total; it does not compare every Form26ASRecord field.",
        "No UI behavior was exercised. This tool performs no schema initialization or database writes.",
    ]}
    failures = []
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        fk_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
        report["checks"]["sqlite_integrity"] = integrity
        report["checks"]["foreign_key_violations"] = len(fk_errors)
        if integrity != "ok" or fk_errors:
            failures.append("SQLite integrity or foreign-key check failed")

        people = conn.execute("SELECT person_id, full_name, first_name, middle_name, last_name, date_of_birth, pan_number FROM Person").fetchall()
        if len(people) != 1:
            failures.append("person count differs from fresh seed")
            person_id = people[0]["person_id"] if people else None
        else:
            person_id = people[0]["person_id"]
            pseed = json.loads((DEFAULT_OUT.parent / "P0_person_seed.json").read_text(encoding="utf-8"))
            legal_tokens = (pseed.get("full_name") or "").split()
            expected_first = legal_tokens[0] if legal_tokens else None
            expected_last = legal_tokens[-1] if len(legal_tokens) > 1 else None
            expected_middle = " ".join(legal_tokens[1:-1]) if len(legal_tokens) > 2 else None
            person = people[0]
            if (person["full_name"] != "Pranav" or person["first_name"] != expected_first or
                    person["middle_name"] != expected_middle or person["last_name"] != expected_last or
                    person["pan_number"] != pseed.get("pan") or person["date_of_birth"] != "2004-03-08"):
                failures.append("person fields differ from P0 seed")
        n_accounts = conn.execute("SELECT COUNT(*) FROM BankAccount").fetchone()[0]
        n_bank_conventions = conn.execute("SELECT COUNT(*) FROM BankFDConvention").fetchone()[0]
        if n_accounts != 4:
            failures.append("total account count differs from fresh four-account seed")
        if n_bank_conventions != 4:
            failures.append("bank FD convention count differs from fresh four-bank seed")
        account_report = {}
        account_by_bank = {}
        for bank, (filename, count_expected) in EXPECTED_STATEMENTS.items():
            statement_seed = seed.get("statements", {}).get(bank, {})
            expected_count = int(statement_seed.get("count", count_expected))
            if expected_count != count_expected:
                failures.append(f"{bank}: P0 statement count differs from required source count")
            pw = equitas_pw if bank == "Equitas" else None
            parsed = parse_statement_pdf(str(pdata / "Statement" / filename), password=pw, debug={})
            audit = {}
            opening = validate_statement_rows(parsed, audit)
            if len(parsed) != expected_count:
                failures.append(f"{bank}: source parser row count mismatch")
            expected_legal_bank_name = {"Jana": "Jana Small Finance Bank", "IDFC FIRST": "IDFC FIRST Bank",
                                        "Ujjivan": "Ujjivan Small Finance Bank", "Equitas": "Equitas Small Finance Bank"}[bank]
            accounts = conn.execute("SELECT a.*, b.bank_name AS legal_bank_name, b.nickname AS bank_nickname FROM BankAccount a JOIN Bank b ON lower(b.bank_name)=lower(a.bank_name) WHERE a.person_id=? AND b.nickname=?", (person_id, bank)).fetchall()
            if len(accounts) != 1:
                failures.append(f"{bank}: expected one account")
                continue
            account = accounts[0]
            if account["legal_bank_name"] != expected_legal_bank_name:
                failures.append(f"{bank}: legal bank name mismatch")
            account_id = account["account_id"]
            account_by_bank[bank] = account_id
            holder_count = conn.execute("SELECT COUNT(*) FROM AccountHolder WHERE account_id=? AND person_id=?", (account_id, person_id)).fetchone()[0]
            all_holder_count = conn.execute("SELECT COUNT(*) FROM AccountHolder WHERE account_id=?", (account_id,)).fetchone()[0]
            if holder_count != 1 or all_holder_count != 1:
                failures.append(f"{bank}: account holder link count mismatch")
            expected_rows = []
            derived = {r["index"]: Decimal(str(r["derived_balance_after"])) for r in audit.get("derived_internal_balances", [])}
            for i, txn in enumerate(parsed):
                balance = txn.get("balance_after")
                if balance is None:
                    balance = derived.get(i)
                expected_rows.append((txn["transaction_date"], txn["transaction_type"], txn["amount"], txn.get("category"), txn.get("description"), balance))
            actual_rows = conn.execute("SELECT transaction_date, transaction_type, amount, category, description, balance_after FROM Transactions WHERE account_id=? AND source='Statement Import' ORDER BY transaction_date, transaction_id", (account_id,)).fetchall()
            ec = Counter(row_key(r) for r in expected_rows)
            ac = Counter(row_key(tuple(r)) for r in actual_rows)
            diff = safe_diff(ec, ac)
            if diff["missing_rows"] or diff["extra_rows"]:
                failures.append(f"{bank}: transaction multiset differs")
            import_logs = conn.execute("SELECT COUNT(*) AS n, SUM(CASE WHEN status='Success' AND records_imported=? THEN 1 ELSE 0 END) AS ok FROM StatementImportLog WHERE account_id=? AND file_name=?", (expected_count, account_id, filename)).fetchone()
            if import_logs["n"] != 1 or import_logs["ok"] != 1:
                failures.append(f"{bank}: successful import log mismatch")
            closing_matches = bool(actual_rows) and actual_rows[-1]["balance_after"] is not None and abs(money(actual_rows[-1]["balance_after"]) - money(parsed[-1].get("balance_after"))) == 0
            account_report[bank] = {"transaction_rows": diff, "opening_balance_matches": abs(money(account["opening_balance"]) - money(opening)) == 0,
                                    "opening_balance": float(opening), "closing_balance_matches": closing_matches,
                                    "current_balance_matches": abs(money(account["current_balance"]) - money(parsed[-1].get("balance_after"))) == 0,
                                    "holder_links": holder_count, "import_log_rows": import_logs["n"]}
            if not account_report[bank]["opening_balance_matches"]:
                failures.append(f"{bank}: account opening balance mismatch")
            if not account_report[bank]["closing_balance_matches"]:
                failures.append(f"{bank}: closing balance mismatch")
            if not account_report[bank]["current_balance_matches"]:
                failures.append(f"{bank}: current account balance mismatch")
            if import_logs["n"] != 1:
                failures.append(f"{bank}: import log row count mismatch")
        report["checks"]["accounts"] = account_report
        total_transactions = conn.execute("SELECT COUNT(*) FROM Transactions").fetchone()[0]
        statement_transactions = conn.execute("SELECT COUNT(*) FROM Transactions WHERE source='Statement Import'").fetchone()[0]
        report["checks"]["transaction_totals"] = {"all": total_transactions, "statement_import": statement_transactions}
        if total_transactions != 507 or statement_transactions != 507:
            failures.append("transaction table contains missing or extra rows")

        # Verify imported tax document rows and headline totals against P0 parser outputs.
        f26 = parse_form26as_pdf(str(pdata / "26AS.pdf"), debug={})
        ais = parse_ais_pdf(str(pdata / "AIS.pdf"), password=ais_pw)
        tis = parse_tis_pdf(str(pdata / "TIS.pdf"), password=ais_pw)
        form_rows = conn.execute("SELECT i.financial_year, i.total_tds, COUNT(r.record_id) AS n FROM Form26ASImport i LEFT JOIN Form26ASRecord r ON r.import_id=i.import_id GROUP BY i.import_id").fetchall()
        tax = {"26as_imports": len(form_rows), "26as_records": sum(r["n"] for r in form_rows), "26as_fy": form_rows[0]["financial_year"] if len(form_rows)==1 else None,
               "26as_total_tds": form_rows[0]["total_tds"] if len(form_rows)==1 else None,
               "ais_tis_imports": conn.execute("SELECT COUNT(*) FROM AISTISImport").fetchone()[0]}
        parsed_26as_count = len(f26.get("records",[]) or []) + len(f26.get("part_ii",[]) or [])
        if parsed_26as_count != 158 or len(form_rows) != 1 or sum(r["n"] for r in form_rows) != parsed_26as_count:
            failures.append("26AS imported record count differs from parsed PDF")
        if len(form_rows) != 1 or form_rows[0]["financial_year"] != "2025-26" or abs(money(form_rows[0]["total_tds"]) - money(f26.get("total_tds"))) > CENT or abs(money(form_rows[0]["total_tds"]) - Decimal("13367.00")) > CENT:
            failures.append("26AS import year or total differs from parsed PDF")
        ais_rows = conn.execute("SELECT source_type, financial_year, fd_interest, savings_interest, dividend_income, tds_deducted FROM AISTISImport ORDER BY source_type").fetchall()
        tax["ais_tis"] = {r["source_type"]: {"financial_year": r["financial_year"], "fd_interest": r["fd_interest"], "savings_interest": r["savings_interest"], "dividend_income": r["dividend_income"], "tds_deducted": r["tds_deducted"]} for r in ais_rows}
        if len(ais_rows) != 2 or {r["source_type"] for r in ais_rows} != {"AIS", "TIS"}:
            failures.append("AIS/TIS import rows are incomplete")
        # P0 aggregates are authoritative for this FY; account for the model's documented
        # AIS/TIS field mapping while avoiding any classification or tax re-computation.
        for label, parsed_tax in (("AIS", ais), ("TIS", tis)):
            dbrow = next((r for r in ais_rows if r["source_type"] == label), None)
            if dbrow is None:
                continue
            expected = seed.get(label.lower(), {})
            if dbrow["financial_year"] != expected.get("financial_year"):
                failures.append(f"{label}: financial year differs from P0")
            for dbfield, p0field in (("fd_interest", "fd_interest"), ("savings_interest", "savings_interest"), ("dividend_income", "dividend"), ("tds_deducted", "tds")):
                if p0field not in expected:
                    continue
                source_total = parsed_tax.get(p0field)
                if source_total is None:
                    failures.append(f"{label}: parser did not return {p0field}")
                    continue
                if abs(money(source_total or 0) - money(expected[p0field] or 0)) > CENT:
                    failures.append(f"{label}: current PDF total differs from P0")
                if abs(money(dbrow[dbfield] or 0) - money(source_total or 0)) > CENT:
                    failures.append(f"{label}: imported {dbfield} differs from current PDF total")
        report["checks"]["tax_documents"] = tax
        if person_id is not None:
            holder_total = conn.execute("SELECT COUNT(*) FROM AccountHolder h JOIN BankAccount a ON a.account_id=h.account_id WHERE a.person_id=?", (person_id,)).fetchone()[0]
            report["checks"]["account_holder_links"] = holder_total
            if holder_total != 4:
                failures.append("expected four account-holder links")
    finally:
        conn.close()
    if failures:
        report["status"] = "FAIL"
        report["failure_count"] = len(failures)
        report["failures"] = failures
    else:
        report["failure_count"] = 0
        report["failures"] = []
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"status": report["status"], "failure_count": report["failure_count"], "out": str(args.out),
                      "statement_counts": {k: v["transaction_rows"]["actual_rows"] for k,v in report["checks"].get("accounts",{}).items()},
                      "tax_counts": {k: report["checks"].get("tax_documents",{}).get(k) for k in ("26as_records", "ais_tis_imports")}}, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
