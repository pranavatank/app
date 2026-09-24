r"""tools/real_ui_tests/rebuild_p0_expectations.py — Phase 0.3 headless expectations.

Read-only. Imports parsers only, never core.database. Records what a fresh
import SHOULD produce, from the real documents, independent of the app / DB.
Writes tools/real_ui_tests/screenshots/rebuild/P0_expectations.json (no secrets,
PAN masked).
"""
import sys
import os
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

from engines.statement import parse_statement_pdf
from engines.statement_parser import extract_statement_text
from engines.statement_metadata_extractor import extract_account_metadata, mask_account_number
from engines.taxdocs.form26as import parse_form26as_pdf
from engines.taxdocs.ais import parse_ais_pdf
from engines.taxdocs.tis import parse_tis_pdf
from tools.taxdoc_import import read_ais_tis_password, read_equitas_password

BASE = Path(__file__).resolve().parent.parent.parent
PDATA = BASE / "data" / "PersonalData" / "Pranav"
PWFILE = PDATA / "password.txt"
OUT_DIR = BASE / "tools" / "real_ui_tests" / "screenshots" / "rebuild"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def mask_pan(pan):
    if not pan:
        return None
    return "XXXXX9999X" if re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]$", pan) else "***"


def is_fd_opening(txn):
    """Mirrors _TransactionImportWorker._is_fd_opening_transaction exactly
    (ui/statement_import_screen_modern.py:247-250) — substring rule."""
    desc = (txn.get("description") or "").lower()
    return any(p in desc for p in ["fd accepted", "opening", "fixed deposit"])


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
    first = txns[0]
    signed_first = first["amount"] if first["transaction_type"] == "Income" else -first["amount"]
    opening_balance = (first["balance_after"] - signed_first) if first["balance_after"] is not None else None
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
        "category_histogram": cat_hist,
        "fd_opening_count": len(fd_openings),
        "fd_openings": fd_openings,
        "redemption_candidate_count": len(redemption_candidates),
        "masked_account_number": masked_acct,
        "ifsc": meta.get("ifsc_code"),
        "confidence_debug_keys": list(debug.keys()),
    }


def main():
    result = {}
    equitas_pw = read_equitas_password(str(PWFILE))
    ais_tis_pw = read_ais_tis_password(str(PWFILE))
    print(f"equitas_password_loaded={bool(equitas_pw)}")
    print(f"ais_tis_password_loaded={bool(ais_tis_pw)}")

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
            result["statements"][name] = {"error": repr(e)}
            print(f"FAIL statement {name}: {e!r}")

    # 26AS
    try:
        f26 = parse_form26as_pdf(str(PDATA / "26AS.pdf"), debug={})
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
        print(f"OK 26AS: part_i={len(part_i)} part_ii={len(part_ii)} total={len(all_records)} total_tds={f26.get('total_tds')}")
    except Exception as e:
        result["form26as"] = {"error": repr(e)}
        print(f"FAIL 26AS: {e!r}")

    # AIS / TIS
    for label, fn, filename in [("ais", parse_ais_pdf, "AIS.pdf"), ("tis", parse_tis_pdf, "TIS.pdf")]:
        try:
            data = fn(str(PDATA / filename), password=ais_tis_pw)
            result[label] = {
                k: v for k, v in data.items()
                if k in (
                    "fd_interest", "savings_interest", "dividend", "business_receipts",
                    "total_interest", "tds", "financial_year", "assessment_year",
                )
            }
            sft = data.get("sft_016_td") or data.get("sft016") or []
            result[label]["sft_016_td_account_count"] = len(sft) if isinstance(sft, list) else None
            result[label]["top_level_keys"] = list(data.keys())
            print(f"OK {label.upper()}: {result[label]}")
        except Exception as e:
            result[label] = {"error": repr(e)}
            print(f"FAIL {label.upper()}: {e!r}")

    # PersonalData hashes
    hashes = {}
    for p in sorted(PDATA.rglob("*")):
        if p.is_file() and p.name != "password.txt":
            h = hashlib.sha256(p.read_bytes()).hexdigest()
            hashes[str(p.relative_to(BASE))] = h
    (OUT_DIR / "P0_personaldata_hashes.json").write_text(
        json.dumps(hashes, indent=2), encoding="utf-8"
    )
    print(f"wrote hashes for {len(hashes)} files")

    # Write expectations without secrets/PAN
    to_write = {k: v for k, v in result.items() if not k.startswith("_")}
    (OUT_DIR / "P0_expectations.json").write_text(
        json.dumps(to_write, indent=2, default=str), encoding="utf-8"
    )
    print("wrote P0_expectations.json")

    # Keep the raw name/pan in a separate, still-gitignored-dir file for P2.1 to consume
    # (screenshots/rebuild is gitignored; PAN is real user data needed for data entry).
    person_seed = {
        "full_name": result.get("_person_name_raw"),
        "pan": result.get("_person_pan_raw"),
    }
    (OUT_DIR / "P0_person_seed.json").write_text(json.dumps(person_seed), encoding="utf-8")
    print("wrote P0_person_seed.json (contains PAN - gitignored dir only)")


if __name__ == "__main__":
    main()
