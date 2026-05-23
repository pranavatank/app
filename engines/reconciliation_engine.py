"""
engines/reconciliation_engine.py — Form 26AS vs AIS TDS reconciliation engine.

Compares TDS records from two sources and identifies mismatches.
"""

from dataclasses import dataclass
from typing import Literal


@dataclass
class ReconciliationItem:
    """Single reconciliation row comparing 26AS and AIS."""
    deductor_name: str
    deductor_tan: str
    section: str
    form26as_amount: float
    ais_amount: float
    difference: float
    status: Literal["Match", "Minor Diff", "Mismatch", "26AS Only", "AIS Only"]
    form26as_record_id: int | None = None
    ais_record_id: int | None = None


def reconcile_tds(
    form26as_records: list[dict],
    ais_records: list[dict],
    tolerance: float = 1.0,
) -> list[ReconciliationItem]:
    """
    Reconcile TDS records from Form 26AS and AIS.
    
    Parameters
    ----------
    form26as_records : list of dicts with keys: record_id, deductor_tan, deductor_name, section, tds_deducted
    ais_records      : list of dicts with keys: record_id, source_tan, information_source, information_code, tds_deducted
    tolerance        : difference threshold for "Minor Diff" vs "Mismatch"
    
    Returns
    -------
    List of ReconciliationItem objects sorted by status severity.
    """
    results: list[ReconciliationItem] = []
    
    # Build lookup maps by TAN
    form26as_by_tan: dict[str, list[dict]] = {}
    for rec in form26as_records:
        tan = (rec.get("deductor_tan") or "").strip().upper()
        if tan:
            form26as_by_tan.setdefault(tan, []).append(rec)
    
    ais_by_tan: dict[str, list[dict]] = {}
    for rec in ais_records:
        tan = (rec.get("source_tan") or "").strip().upper()
        if tan:
            ais_by_tan.setdefault(tan, []).append(rec)
    
    # Track matched records
    matched_26as = set()
    matched_ais = set()
    
    # Match by TAN
    all_tans = set(form26as_by_tan.keys()) | set(ais_by_tan.keys())
    
    for tan in all_tans:
        f26_list = form26as_by_tan.get(tan, [])
        ais_list = ais_by_tan.get(tan, [])
        
        if not f26_list and ais_list:
            # AIS only
            for ais_rec in ais_list:
                results.append(ReconciliationItem(
                    deductor_name=ais_rec.get("information_source", "Unknown"),
                    deductor_tan=tan,
                    section=ais_rec.get("information_code", "—"),
                    form26as_amount=0.0,
                    ais_amount=ais_rec.get("tds_deducted", 0.0),
                    difference=ais_rec.get("tds_deducted", 0.0),
                    status="AIS Only",
                    ais_record_id=ais_rec.get("record_id"),
                ))
                matched_ais.add(ais_rec.get("record_id"))
        
        elif f26_list and not ais_list:
            # 26AS only
            for f26_rec in f26_list:
                results.append(ReconciliationItem(
                    deductor_name=f26_rec.get("deductor_name", "Unknown"),
                    deductor_tan=tan,
                    section=f26_rec.get("section", "—"),
                    form26as_amount=f26_rec.get("tds_deducted", 0.0),
                    ais_amount=0.0,
                    difference=f26_rec.get("tds_deducted", 0.0),
                    status="26AS Only",
                    form26as_record_id=f26_rec.get("record_id"),
                ))
                matched_26as.add(f26_rec.get("record_id"))
        
        else:
            # Both exist - aggregate by TAN
            f26_total = sum(r.get("tds_deducted", 0.0) for r in f26_list)
            ais_total = sum(r.get("tds_deducted", 0.0) for r in ais_list)
            diff = abs(f26_total - ais_total)
            
            if diff <= tolerance:
                status = "Match"
            elif diff <= tolerance * 10:
                status = "Minor Diff"
            else:
                status = "Mismatch"
            
            results.append(ReconciliationItem(
                deductor_name=f26_list[0].get("deductor_name", "Unknown"),
                deductor_tan=tan,
                section=f26_list[0].get("section", "—"),
                form26as_amount=f26_total,
                ais_amount=ais_total,
                difference=diff,
                status=status,
                form26as_record_id=f26_list[0].get("record_id") if len(f26_list) == 1 else None,
                ais_record_id=ais_list[0].get("record_id") if len(ais_list) == 1 else None,
            ))
            
            for r in f26_list:
                matched_26as.add(r.get("record_id"))
            for r in ais_list:
                matched_ais.add(r.get("record_id"))
    
    # Sort by severity: Mismatch > 26AS Only > AIS Only > Minor Diff > Match
    severity_order = {"Mismatch": 0, "26AS Only": 1, "AIS Only": 2, "Minor Diff": 3, "Match": 4}
    results.sort(key=lambda x: (severity_order.get(x.status, 5), x.deductor_name))
    
    return results


def get_reconciliation_summary(items: list[ReconciliationItem]) -> dict:
    """Generate summary statistics for reconciliation results."""
    total = len(items)
    match = sum(1 for i in items if i.status == "Match")
    minor = sum(1 for i in items if i.status == "Minor Diff")
    mismatch = sum(1 for i in items if i.status == "Mismatch")
    only_26as = sum(1 for i in items if i.status == "26AS Only")
    only_ais = sum(1 for i in items if i.status == "AIS Only")
    
    total_26as = sum(i.form26as_amount for i in items)
    total_ais = sum(i.ais_amount for i in items)
    total_diff = abs(total_26as - total_ais)
    
    return {
        "total_records": total,
        "match_count": match,
        "minor_diff_count": minor,
        "mismatch_count": mismatch,
        "only_26as_count": only_26as,
        "only_ais_count": only_ais,
        "total_26as_tds": total_26as,
        "total_ais_tds": total_ais,
        "total_difference": total_diff,
        "reconciliation_rate": (match / total * 100) if total > 0 else 100.0,
    }
