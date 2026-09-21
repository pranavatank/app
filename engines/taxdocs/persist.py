"""engines/taxdocs/persist.py — map parsed tax-document dicts onto the storage models.

ITR-side data is READ-ONLY truth: this module stores it verbatim and never
adjusts a figure. Nothing here opens a database connection; all writes go
through models/form26as.py and models/ais_tis_import.py.
"""

import json
from config import get_current_financial_year
from models.form26as import save_form26as_import
from models.ais_tis_import import save_ais_tis_data, save_ais_tis_records


SOURCE_TYPE_26AS = "26AS"
SOURCE_TYPE_AIS = "AIS"
SOURCE_TYPE_TIS = "TIS"

PART_II_STATUS = "15G/15H"


def financial_year_from_assessment_year(assessment_year: str | None) -> str | None:
    """Convert assessment year (e.g. '2026-27') to financial year (e.g. '2025-26')."""
    if not assessment_year:
        return None
    try:
        y = int(assessment_year.split("-")[0])
        return f"{y-1}-{str(y)[2:]}"
    except (ValueError, IndexError):
        return None


def form26as_records_for_storage(parsed: dict) -> list[dict]:
    """Transform parsed Form 26AS records into storage format."""
    records = parsed.get("records", [])
    part_ii = parsed.get("part_ii", [])

    result = []

    for r in records:
        tds_deposited = r.get("tds_deposited")
        if tds_deposited is None:
            tds_deposited = r.get("tds_deducted") or 0

        raw_parts = []
        for key in ["part", "section", "deductor_name", "deductor_tan", "transaction_date", "booking_date", "amount_paid", "tds_deducted"]:
            val = r.get(key)
            if val:
                raw_parts.append(str(val))

        raw_line = " | ".join(raw_parts)[:500]

        result.append({
            "section": r.get("section"),
            "deductor_name": r.get("deductor_name"),
            "deductor_tan": r.get("deductor_tan"),
            "transaction_date": r.get("transaction_date"),
            "amount_paid": r.get("amount_paid"),
            "tds_deducted": r.get("tds_deducted"),
            "tds_deposited": tds_deposited,
            "status": r.get("booking_status"),
            "certificate_no": None,
            "remarks": r.get("remarks"),
            "raw_line": raw_line,
        })

    for r in part_ii:
        tds_deposited = 0

        raw_parts = []
        for key in ["part", "section", "deductor_name", "deductor_tan", "transaction_date", "booking_date", "amount_paid", "tds_deducted"]:
            if key == "part":
                raw_parts.append("II")
            else:
                val = r.get(key)
                if val:
                    raw_parts.append(str(val))

        raw_line = " | ".join(raw_parts)[:500]

        result.append({
            "section": r.get("section"),
            "deductor_name": r.get("deductor_name"),
            "deductor_tan": r.get("deductor_tan"),
            "transaction_date": r.get("transaction_date"),
            "amount_paid": r.get("amount_paid"),
            "tds_deducted": r.get("tds_deducted"),
            "tds_deposited": tds_deposited,
            "status": PART_II_STATUS,
            "certificate_no": None,
            "remarks": r.get("remarks"),
            "raw_line": raw_line,
        })

    return result


def persist_form26as(person_id: int, parsed: dict, source_file: str = "",
                     financial_year: str | None = None) -> dict:
    """Store parsed Form 26AS data."""
    fy = financial_year or financial_year_from_assessment_year(parsed.get("assessment_year")) or get_current_financial_year()

    records = form26as_records_for_storage(parsed)

    import_id = save_form26as_import(person_id, fy, records, source_file=source_file, raw_text="")

    stored_total_tds = sum(r.get("tds_deducted") or 0 for r in records)
    parsed_total_tds = float(parsed.get("total_tds") or 0.0)

    return {
        "import_id": import_id,
        "financial_year": fy,
        "record_count": len(records),
        "stored_total_tds": stored_total_tds,
        "parsed_total_tds": parsed_total_tds,
    }


def ais_tis_payload(parsed: dict) -> dict:
    """Extract the summary data dict for save_ais_tis_data."""
    return {
        "salary_income": 0.0,
        "fd_interest": parsed.get("fd_interest", 0.0),
        "savings_interest": parsed.get("savings_interest", 0.0),
        "other_interest": 0.0,
        "dividend_income": parsed.get("dividend", 0.0),
        "rental_income": 0.0,
        "other_income": parsed.get("business_receipts", 0.0),
        "tds_deducted": parsed.get("tds", 0.0),
    }


def ais_tis_records_for_storage(parsed: dict) -> list[dict]:
    """Transform parsed AIS/TIS details into storage format."""
    details = parsed.get("details", [])
    if not details:
        return []

    result = []
    for d in details:
        result.append({
            "record_type": d.get("type") or "unknown",
            "information_code": d.get("code"),
            "information_description": d.get("description"),
            "information_source": d.get("source"),
            "amount": d.get("amount"),
            "raw_line": str(d.get("raw_row"))[:500] if d.get("raw_row") else "",
        })

    return result


def persist_ais_tis(person_id: int, parsed: dict, source_type: str,
                    financial_year: str, source_file: str = "") -> dict:
    """Store parsed AIS/TIS data."""
    if source_type not in (SOURCE_TYPE_AIS, SOURCE_TYPE_TIS):
        raise ValueError(f"source_type must be one of {SOURCE_TYPE_AIS}, {SOURCE_TYPE_TIS}")

    raw_json = json.dumps(parsed, default=str)
    payload = ais_tis_payload(parsed)

    import_id = save_ais_tis_data(person_id, financial_year, source_type, raw_json, payload)

    records = ais_tis_records_for_storage(parsed)
    save_ais_tis_records(import_id, records)

    return {
        "import_id": import_id,
        "financial_year": financial_year,
        "source_type": source_type,
        "record_count": len(records),
    }
