"""engines/fd_allocation_engine.py — Split savings across bank FDs for the best return within the DICGC insurance limit."""

import math
import re

from config import DICGC_INSURANCE_LIMIT, FD_TDS_THRESHOLD, FD_TDS_THRESHOLD_SENIOR
from engines.fd_rate_source import SMALL_FINANCE_BANK
from engines.interest_engine import calculate_fd_maturity
from models.bank_account import get_accounts_for_person
from models.fixed_deposit import get_all_fds

TENURE_MONTHS = {"rate_1y": 12, "rate_3y": 36, "rate_5y": 60}
TENURE_LABELS = {"rate_1y": "1 year", "rate_3y": "3 years", "rate_5y": "5 years"}
_ALLOCATION_STEP = 1000
_ACTIVE_FD_STATUSES = ("Active", "Pending Details")
_DEPOSIT_ACCOUNT_TYPES = ("Savings", "Current", "Salary")
_NAME_STOPWORDS = {"bank", "ltd", "limited", "the", "of", "co"}
_NAME_ALIASES = {"sbi": "state india", "bob": "baroda", "pnb": "punjab national", "boi": "india", "induslnd": "indusind"}
COVERAGE_OVER = "Over limit"
COVERAGE_NEAR = "Near limit"
COVERAGE_OK = "Within limit"
_NEAR_LIMIT_SHARE = 0.9


def normalize_bank_key(bank_name: str) -> str:
    """Reduce a bank name to a comparable key, e.g. 'HDFC Bank Ltd' -> 'hdfc'."""
    key = re.sub(r"[^a-z0-9]+", " ", bank_name.lower().replace("&", " and "))
    tokens = []
    for token in key.split():
        if token == "sfb":
            tokens.extend(["small", "finance"])
        elif token not in _NAME_STOPWORDS:
            tokens.append(token)
    key = " ".join(tokens)
    return _NAME_ALIASES.get(key, key)


def _exposure_entry(exposure: dict[str, dict], bank_name: str) -> dict | None:
    key = normalize_bank_key(bank_name or "")
    if not key:
        return None
    return exposure.setdefault(key, {
        "bank_name": bank_name, "fd_amount": 0.0, "savings_amount": 0.0,
        "annual_fd_interest": 0.0, "total": 0.0,
    })


def get_existing_exposure(person_id: int) -> dict[str, dict]:
    """Insured amount already held per bank by a person (FDs including interest, plus savings balances)."""
    exposure: dict[str, dict] = {}

    for fd in get_all_fds(person_id=person_id):
        if fd.get("status") not in _ACTIVE_FD_STATUSES:
            continue
        entry = _exposure_entry(exposure, fd.get("bank_name"))
        if entry is None:
            continue
        principal = float(fd.get("principal_amount") or 0)
        insured = float(fd.get("maturity_amount") or 0) or principal
        entry["fd_amount"] += insured
        entry["annual_fd_interest"] += principal * float(fd.get("interest_rate") or 0) / 100

    for acct in get_accounts_for_person(person_id):
        if acct.get("account_type") not in _DEPOSIT_ACCOUNT_TYPES:
            continue
        if (acct.get("account_status") or "Active") == "Closed":
            continue
        entry = _exposure_entry(exposure, acct.get("bank_name"))
        if entry is None:
            continue
        entry["savings_amount"] += max(float(acct.get("current_balance") or 0), 0)

    for entry in exposure.values():
        entry["total"] = entry["fd_amount"] + entry["savings_amount"]
        for field in ("fd_amount", "savings_amount", "annual_fd_interest", "total"):
            entry[field] = round(entry[field], 2)
    return exposure


def max_principal_within_limit(headroom: float, rate: float, tenure_months: int,
                               count_interest: bool = True) -> float:
    """Largest principal whose maturity value (or principal, if count_interest is False) fits in the headroom."""
    if headroom <= 0:
        return 0.0
    if not count_interest:
        return float(headroom)
    factor = calculate_fd_maturity(100000.0, rate, tenure_months, "Quarterly") / 100000.0
    return headroom / factor


def _eligible_candidates(banks: list[dict], tenure_key: str, is_senior: bool,
                         excluded: set, include_small_finance: bool) -> list[tuple[float, dict]]:
    candidates = []
    for bank in banks:
        base_rate = bank.get(tenure_key)
        if base_rate is None or bank["bank_name"] in excluded:
            continue
        if not include_small_finance and bank.get("bank_type") == SMALL_FINANCE_BANK:
            continue
        if is_senior and bank.get("senior_extra") is None:
            continue  # A premium range cannot establish an exact senior quote.
        senior_extra = (bank.get("senior_extra") or 0) if is_senior else 0
        candidates.append((round(base_rate + senior_extra, 2), bank))
    unique = {}
    for rate, bank in candidates:
        key = normalize_bank_key(bank["bank_name"])
        if key not in unique or rate > unique[key][0]:
            unique[key] = (rate, bank)
    return sorted(unique.values(), key=lambda candidate: (-candidate[0], candidate[1]["bank_name"]))


def suggest_household_allocation(amount: float, banks: list[dict], tenure_key: str, depositors: list[dict], *,
                                 per_bank_limit: float = DICGC_INSURANCE_LIMIT, max_banks: int = 5,
                                 min_per_bank: float = 10_000, include_small_finance: bool = True,
                                 count_interest_in_limit: bool = True, excluded_banks=()) -> dict:
    """Optimize a fixed-tenure simulation with minimum tickets and a bank-count limit."""
    months = TENURE_MONTHS[tenure_key]
    excluded = set(excluded_banks)
    candidates = []
    for d_index, depositor in enumerate(depositors):
        for rate, bank in _eligible_candidates(banks, tenure_key, depositor["is_senior"], excluded, include_small_finance):
            candidates.append((rate, d_index, bank))
    candidates.sort(key=lambda candidate: (-candidate[0], candidate[1], candidate[2]["bank_name"]))

    from engines.fd_allocation_solver import solve_fixed_allocation
    caps = []
    skipped_full = []
    for rate, d_index, bank in candidates:
        existing = depositors[d_index]["exposure"].get(normalize_bank_key(bank["bank_name"]), {})
        cap = max_principal_within_limit(per_bank_limit - existing.get("total", 0), rate, months, count_interest_in_limit)
        cap = math.floor(cap / _ALLOCATION_STEP) * _ALLOCATION_STEP
        caps.append(cap)
        if cap < min_per_bank:
            name = bank["bank_name"]
            skipped_full.append(name if len(depositors) == 1 else f"{name} ({depositors[d_index]['name']})")
    investments = solve_fixed_allocation(amount, candidates, caps, min_per_bank, max_banks,
                                         depositors, months, _ALLOCATION_STEP, calculate_fd_maturity, normalize_bank_key)
    rows = []
    for (rate, d_index, bank), invest in zip(candidates, investments):
        if invest <= 0:
            continue
        depositor = depositors[d_index]
        existing = depositor["exposure"].get(normalize_bank_key(bank["bank_name"]), {})
        existing_total = existing.get("total", 0.0)
        maturity = calculate_fd_maturity(invest, rate, months, "Quarterly")
        insured_after = existing_total + (maturity if count_interest_in_limit else invest)
        tds_threshold = FD_TDS_THRESHOLD_SENIOR if depositor["is_senior"] else FD_TDS_THRESHOLD
        tds_risk = invest * rate / 100 + existing.get("annual_fd_interest", 0.0) > tds_threshold
        rows.append({
            "bank_name": bank["bank_name"], "bank_type": bank.get("bank_type"), "rate": rate,
            "amount": round(invest, 2), "interest": round(maturity-invest, 2), "maturity_value": maturity,
            "existing_amount": round(existing_total, 2), "insured_total_after": round(insured_after, 2),
            "fully_insured": insured_after <= per_bank_limit + .01, "tds_risk": tds_risk,
            "person_name": depositor["name"],
        })
    remaining = max(0, amount - sum(row["amount"] for row in rows))

    allocated = sum(row["amount"] for row in rows)
    total_interest = sum(row["interest"] for row in rows)
    total_maturity = sum(row["maturity_value"] for row in rows)
    weighted_rate = round(sum(row["rate"] * row["amount"] for row in rows) / allocated, 2) if allocated else 0.0
    average_rate = round(sum(rate for rate, _, _ in candidates) / len(candidates), 2) if candidates else 0.0
    baseline_interest = calculate_fd_maturity(allocated, average_rate, months, "Quarterly") - allocated if allocated else 0.0

    return {
        "rows": rows,
        "tenure_key": tenure_key,
        "tenure_months": months,
        "allocated": round(allocated, 2),
        "unallocated": round(remaining, 2),
        "total_interest": round(total_interest, 2),
        "total_maturity": round(total_maturity, 2),
        "weighted_rate": weighted_rate,
        "average_rate": average_rate,
        "extra_vs_average": round(total_interest - baseline_interest, 2),
        "skipped_full": skipped_full,
        "per_bank_limit": per_bank_limit,
    }


def suggest_fd_allocation(amount: float, banks: list[dict], tenure_key: str, *,
                          is_senior: bool = False, exposure: dict | None = None,
                          per_bank_limit: float = DICGC_INSURANCE_LIMIT, max_banks: int = 5,
                          min_per_bank: float = 10_000, include_small_finance: bool = True,
                          count_interest_in_limit: bool = True, excluded_banks=()) -> dict:
    """Optimize the fixed-tenure comparison within the insurance limit."""
    return suggest_household_allocation(
        amount, banks, tenure_key, [{"name": "", "is_senior": is_senior, "exposure": exposure or {}}],
        per_bank_limit=per_bank_limit, max_banks=max_banks, min_per_bank=min_per_bank,
        include_small_finance=include_small_finance, count_interest_in_limit=count_interest_in_limit,
        excluded_banks=excluded_banks)


def get_savings_total(person_ids: list[int]) -> float:
    """Sum of deposit account balances across persons, counting joint accounts once."""
    seen = set()
    total = 0.0
    for person_id in person_ids:
        for acct in get_accounts_for_person(person_id):
            if acct.get("account_type") not in _DEPOSIT_ACCOUNT_TYPES:
                continue
            if (acct.get("account_status") or "Active") == "Closed":
                continue
            if acct.get("account_id") in seen:
                continue
            seen.add(acct.get("account_id"))
            total += max(float(acct.get("current_balance") or 0), 0)
    return round(total, 2)


def get_coverage_report(persons: list[dict], per_bank_limit: float = DICGC_INSURANCE_LIMIT) -> list[dict]:
    """Insured amount per person and bank against the limit, with headroom and status."""
    rows = []
    for person in persons:
        for entry in get_existing_exposure(person["person_id"]).values():
            total = entry["total"]
            if total == 0:
                continue
            status = (COVERAGE_OVER if total > per_bank_limit
                      else COVERAGE_NEAR if total >= _NEAR_LIMIT_SHARE * per_bank_limit
                      else COVERAGE_OK)
            rows.append({
                "person_name": person["full_name"],
                "bank_name": entry["bank_name"],
                "savings_amount": entry["savings_amount"],
                "fd_amount": entry["fd_amount"],
                "total": total,
                "headroom": round(max(per_bank_limit - total, 0), 2),
                "used_pct": round(total / per_bank_limit * 100, 1) if per_bank_limit else 0.0,
                "status": status,
            })
    return sorted(rows, key=lambda row: (row["person_name"], -row["total"]))
