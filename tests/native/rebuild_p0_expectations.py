r"""tests/native/rebuild_p0_expectations.py — Phase 0.3 headless expectations.

Read-only. Imports parsers only, never core.database. Records what a fresh
import SHOULD produce, from the real documents, independent of the app / DB.
Writes artifacts/native/rebuild/P0_expectations.json (no secrets,
PAN masked).
"""
import sys
import argparse
import re
import json
import hashlib
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tests.support.repo_paths import artifact_path

try:
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
except Exception:
    pass

from engines.statement import parse_statement_pdf
from engines.statement_parser import extract_statement_text
from engines.statement_metadata_extractor import extract_account_metadata, mask_account_number
from engines.taxdocs.form26as import parse_form26as_pdf
from engines.taxdocs.ais import parse_ais_pdf
from engines.taxdocs.tis import parse_tis_pdf
from tools.private_sources import get_personal_data_dir
from tests.native.rebuild_preflight import (
    matching_document_year_fields, normalize_assessment_year,
    require_master_credential, validate_person_seed, validate_statement_rows,
)
from tests.native.rebuild_common import read_secret, run_logged


BASE = Path(__file__).resolve().parents[2]
PDATA = get_personal_data_dir()
OUT_DIR = artifact_path("rebuild")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def mask_pan(pan):
    if not pan:
        return None
    return "XXXXX9999X" if re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]$", pan) else "***"


def is_fd_opening(txn):
    """Call _TransactionImportWorker._is_fd_opening_transaction from
    ui/statement_import_screen_modern.py."""
    from ui.statement_import_screen_modern import _TransactionImportWorker
    worker = _TransactionImportWorker(None, None, [], [], '', '', '', [])
    return worker._is_fd_opening_transaction(txn)


def statement_expectations(name, filename, password=None):
    path = str(PDATA / "Statement" / filename)
    debug = {}
    txns = parse_statement_pdf(path, password=password, debug=debug)
    income_sum = sum(t["amount"] for t in txns if t["transaction_type"] == "Income")
    expense_sum = sum(t["amount"] for t in txns if t["transaction_type"] == "Expense")
    dates = [t["transaction_date"] for t in txns]
    cat_hist = {}
    for t in txns:
        cat_hist[t["category"]] = cat_hist.get(t["category"], 0) + 1
    balance_audit = {}
    opening_balance = validate_statement_rows(txns, balance_audit)
    first = txns[0]
    fd_openings = [(t["transaction_date"], t["amount"]) for t in txns if is_fd_opening(t)]
    redemption_candidates = [t for t in txns if t["transaction_type"] == "Income"]

    file_type = "pdf"
    text = extract_statement_text(path, file_type, password=password)
    meta = extract_account_metadata(text)
    masked_acct = mask_account_number(meta["account_number_full"]) if meta.get("account_number_full") else None

    return {
        "bank": name,
        "file": filename,
        "count": len(txns),
        "min_date": min(dates) if dates else None,
        "max_date": max(dates) if dates else None,
        "income_sum": round(income_sum, 2),
        "expense_sum": round(expense_sum, 2),
        "first_balance_after": first["balance_after"],
        "last_balance_after": txns[-1]["balance_after"],
        "opening_balance": opening_balance,
        "balance_audit": balance_audit,
        "category_histogram": cat_hist,
        "fd_opening_count": len(fd_openings),
        "fd_openings": fd_openings,
        "redemption_candidate_count": len(redemption_candidates),
        "masked_account_number": masked_acct,
        "ifsc": meta.get("ifsc_code"),
        "confidence_debug_keys": list(debug.keys()),
    }


def document_assessment_year(path, password, expected_assessment_year):
    """Read AY/FY only from an explicit header label in the source PDF text."""
    import pdfplumber
    with pdfplumber.open(str(path), password=password) as pdf:
        text = pdf.pages[0].extract_text() or ""
    return matching_document_year_fields(text, expected_assessment_year)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--defer-unity",
        action="store_true",
        help="explicitly defer the present Unity PDF from this rebuild; record it as deferred, without importing it",
    )
    args = parser.parse_args()

    # A failed preflight must never leave a prior run's seed available to P2.
    for stale_path in (
        OUT_DIR / "P0_expectations.json",
        OUT_DIR / "P0_person_seed.json",
        OUT_DIR / "P0_personaldata_hashes.json",
    ):
        stale_path.unlink(missing_ok=True)

    result = {}
    failures = []
    if not PDATA.is_dir():
        raise FileNotFoundError(f"personal data directory not found: {PDATA}")
    equitas_pw = read_secret("equitas")
    ais_tis_pw = read_secret("ais_tis")
    print(f"equitas_password_loaded={bool(equitas_pw)}")
    print(f"ais_tis_password_loaded={bool(ais_tis_pw)}")
    try:
        master_present = bool(read_secret("master"))
    except RuntimeError:
        master_present = False
    print(f"master_credential_present={master_present}")
    try:
        require_master_credential(master_present)
    except ValueError as exc:
        failures.append(str(exc))

    statements = [
        ("Jana", "Jana - Pranav.pdf", None),
        ("IDFC FIRST", "IDFC.pdf", None),
        ("Ujjivan", "Ujjivan - Pranav.pdf", None),
        ("Equitas", "Equitas.pdf", equitas_pw),
    ]
    result["statements"] = {}
    for name, filename, pw in statements:
        try:
            result["statements"][name] = statement_expectations(name, filename, pw)
            print(f"OK statement {name}: count={result['statements'][name]['count']}")
        except Exception as e:
            result["statements"][name] = {"error": type(e).__name__}
            print(f"FAIL statement {name}: {type(e).__name__}")
            failures.append(f"statement {name} parse failed ({type(e).__name__})")

    unity_path = PDATA / "Statement" / "Unity - Pranav.pdf"
    if args.defer_unity and unity_path.is_file():
        result["deferred_sources"] = [{
            "file": str(unity_path.relative_to(BASE)),
            "reason": "explicitly deferred by operator using --defer-unity",
        }]
        unity_status = "deferred by explicit --defer-unity option; not imported"
        print("DEFERRED statement Unity: explicit --defer-unity option")
    elif unity_path.is_file():
        try:
            result["statements"]["Unity"] = statement_expectations("Unity", unity_path.name)
            print(f"OK statement Unity: count={result['statements']['Unity']['count']}")
            unity_status = "parsed and ready for import"
        except Exception as e:
            result["statements"]["Unity"] = {"error": type(e).__name__}
            print(f"FAIL statement Unity: {type(e).__name__}")
            failures.append(f"Unity statement parse failed ({type(e).__name__})")
            unity_status = f"not ready; parser failed ({type(e).__name__})"
    else:
        unity_status = "not imported; source PDF is absent"

    # 26AS
    try:
        f26 = parse_form26as_pdf(str(PDATA / "26AS.pdf"), debug={})
        parsed_assessment_year = normalize_assessment_year(f26.get("assessment_year"))
        part_i = f26.get("records") or []
        part_ii = f26.get("part_ii") or []
        all_records = part_i + part_ii
        per_deductor = {}
        for r in all_records:
            ded = (r.get("deductor_name") or "").strip()
            if ded:
                per_deductor.setdefault(ded, {"gross": 0.0, "tds": 0.0, "tan": r.get("deductor_tan")})
                per_deductor[ded]["gross"] += r.get("amount_paid", 0) or 0
                per_deductor[ded]["tds"] += r.get("tds_deducted", 0) or 0
        result["form26as"] = {
            "assessment_year": parsed_assessment_year,
            "part_i_count": len(part_i),
            "part_ii_count": len(part_ii),
            "record_count": len(all_records),
            "reported_total_tds": f26.get("total_tds"),
            "per_deductor": per_deductor,
            "name": f26.get("name"),
            "pan_masked": mask_pan(f26.get("pan")),
            "top_level_keys": list(f26.keys()),
        }
        # Keep raw name/pan only in-memory for later phases; not written unmasked.
        result["_person_name_raw"] = f26.get("name")
        result["_person_pan_raw"] = f26.get("pan")
        try:
            validate_person_seed(f26.get("name"), f26.get("pan"))
        except ValueError as exc:
            failures.append(str(exc))
        if not all_records:
            failures.append("26AS parser returned no records")
        print(f"OK 26AS: part_i={len(part_i)} part_ii={len(part_ii)} total={len(all_records)} total_tds={f26.get('total_tds')}")
    except Exception as e:
        result["form26as"] = {"error": type(e).__name__}
        print(f"FAIL 26AS: {type(e).__name__}")
        failures.append(f"26AS parse failed ({type(e).__name__})")

    # AIS / TIS
    expected_ay = (result.get("form26as") or {}).get("assessment_year")
    for label, fn, filename in [("ais", parse_ais_pdf, "AIS.pdf"), ("tis", parse_tis_pdf, "TIS.pdf")]:
        try:
            doc_path = PDATA / filename
            data = fn(str(doc_path), password=ais_tis_pw)
            year_fields = document_assessment_year(doc_path, ais_tis_pw, expected_ay)
            result[label] = {
                k: v for k, v in data.items()
                if k in (
                    "fd_interest", "savings_interest", "dividend", "business_receipts",
                    "total_interest", "tds",
                )
            }
            result[label].update(year_fields)
            sft = data.get("sft_016_td") or data.get("sft016") or []
            result[label]["sft_016_td_account_count"] = len(sft) if isinstance(sft, list) else None
            result[label]["top_level_keys"] = list(data.keys())
            print(f"OK {label.upper()}: {result[label]}")
        except Exception as e:
            result[label] = {"error": type(e).__name__}
            print(f"FAIL {label.upper()}: {type(e).__name__}")
            failures.append(f"{label.upper()} parse failed ({type(e).__name__})")

    # Keep a truthful inventory: these files are available beside the import
    # sources but are not consumed by the existing PDF import workflow.
    result["source_manifest"] = {
        "workbook": {"file": "Data 26-27.xlsx", "status": "read-only FD Planner input; not imported"},
        "ais_json": {"file": "AIS-JSON.json", "status": "not imported by existing tax PDF flow"},
        "form16a": {
            "files": ["PRANAV Q3_AY202627_16A.pdf", "PRANAV Q4_AY202627_16A.pdf"],
            "status": "not imported by existing tax PDF flow",
        },
        "unity_statement": {"status": unity_status},
    }

    if failures:
        for failure in failures:
            print(f"FAIL readiness: {failure}")
        raise RuntimeError(f"P0 readiness failed ({len(failures)} issue(s)); no seed files written")

    missing_files = []
    required_files = [*(PDATA / "Statement" / spec[1] for spec in statements),
                      PDATA / "26AS.pdf", PDATA / "AIS.pdf", PDATA / "TIS.pdf"]
    missing_files = [str(p) for p in required_files if not p.is_file()]
    if missing_files:
        raise FileNotFoundError("required source document(s) missing: " + ", ".join(missing_files))

    # Private-source hashes exclude the password file by case-insensitive name.
    hashes = {}
    for p in sorted(PDATA.rglob("*")):
        if p.is_file() and p.name.casefold() != "password.txt":
            h = hashlib.sha256(p.read_bytes()).hexdigest()
            hashes[str(p.relative_to(BASE))] = h
    (OUT_DIR / "P0_personaldata_hashes.json").write_text(
        json.dumps(hashes, indent=2), encoding="utf-8"
    )
    print(f"wrote private-source hashes for {len(hashes)} files")

    # Write expectations without secrets/PAN
    to_write = {k: v for k, v in result.items() if not k.startswith("_")}
    (OUT_DIR / "P0_expectations.json").write_text(
        json.dumps(to_write, indent=2, default=str), encoding="utf-8"
    )
    print("wrote P0_expectations.json")

    # Keep the raw name/pan in a separate, still-gitignored-dir file for P2.1 to consume
    # (artifacts/native/rebuild is gitignored; PAN is real user data needed for data entry).
    person_seed = {
        "full_name": result.get("_person_name_raw"),
        "pan": result.get("_person_pan_raw"),
    }
    (OUT_DIR / "P0_person_seed.json").write_text(json.dumps(person_seed), encoding="utf-8")
    print("wrote P0_person_seed.json (contains PAN - gitignored dir only)")


if __name__ == "__main__":
    run_logged(main, "P0_expectations_crash")
