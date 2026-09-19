"""
engines/prediction_engine.py — Income prediction engine for FY planning

Forecasts the owner's current financial-year income from HIS OWN data
(transactions, FDs, income expectations) so he can act early to stay under
the 12,00,000 rebate limit and avoid TDS.

This engine works ONLY with real data — transactions are already classified
by category, and FDs with missing details are synthesised with defaults.
No speculative optimisation; all figures carry an is_estimated flag.
"""

from datetime import date
from dateutil.relativedelta import relativedelta
from config import fy_date_range, get_current_financial_year
from models.transaction import get_transactions
from models.fixed_deposit import get_all_fds
from models.bank_account import get_accounts_for_person
from engines.interest_engine import fd_interest_accrued_to
from engines.tax_engine import _get_tax_params
from core.database import get_connection


# Module Constants
DEFAULT_FD_RATE = 7.5
DEFAULT_FD_TENURE_MONTHS = 12
TAXABLE_INCOME_CATEGORIES = {"FD Interest", "Savings Interest"}
NON_TAXABLE_INCOME_CATEGORIES = {"FD Maturity", "Other Income"}


def _current_fy_or_default(financial_year: str | None) -> str:
    """Return financial_year if provided, else current FY."""
    if financial_year:
        return financial_year
    return get_current_financial_year()


def _as_of_date(as_of: date | None) -> date:
    """Return as_of date or today."""
    return as_of if as_of else date.today()


def _synthesise_fd(fd: dict) -> dict:
    """
    Return a COPY of fd with interest_rate and maturity_date filled in from
    defaults when missing. Include an is_estimated flag: True when either
    field needed to be filled, else False.
    """
    copy = dict(fd)
    is_estimated = False

    if not copy.get("interest_rate"):
        copy["interest_rate"] = DEFAULT_FD_RATE
        is_estimated = True

    if not copy.get("maturity_date"):
        fd_start = date.fromisoformat(copy["start_date"])
        copy["maturity_date"] = (
            fd_start + relativedelta(months=DEFAULT_FD_TENURE_MONTHS)
        ).isoformat()
        is_estimated = True

    copy["is_estimated"] = is_estimated
    return copy


def project_fd_interest(
    person_id: int,
    financial_year: str,
    as_of: date | None = None
) -> dict:
    """
    Per-FD and total projected interest for the FY, using synthesised FDs.

    Returns:
        {
          "total": float,
          "known_total": float (from FDs with actual rate/maturity),
          "estimated_total": float,
          "estimated_fd_count": int,
          "known_fd_count": int,
          "per_bank": {
            "bank_name": {
              "total": float,
              "known_total": float,
              "estimated_total": float,
              "is_estimated": bool
            }
          },
          "is_estimated": bool (True if any FD is estimated)
        }
    """
    as_of = _as_of_date(as_of)
    fds = get_all_fds(person_id=person_id)

    total_interest = 0.0
    known_total = 0.0
    estimated_total = 0.0
    estimated_count = 0
    known_count = 0
    per_bank = {}
    any_estimated = False

    for fd in fds:
        try:
            synth_fd = _synthesise_fd(fd)
            interest = fd_interest_accrued_to(synth_fd, as_of)

            if interest <= 0:
                continue

            total_interest += interest
            bank_name = fd.get("bank_name") or "Unknown"

            if bank_name not in per_bank:
                per_bank[bank_name] = {
                    "total": 0.0,
                    "known_total": 0.0,
                    "estimated_total": 0.0,
                    "is_estimated": False,
                }

            per_bank[bank_name]["total"] += interest

            if synth_fd["is_estimated"]:
                estimated_total += interest
                estimated_count += 1
                per_bank[bank_name]["estimated_total"] += interest
                per_bank[bank_name]["is_estimated"] = True
                any_estimated = True
            else:
                known_total += interest
                known_count += 1
                per_bank[bank_name]["known_total"] += interest
        except Exception:
            # Skip FDs that crash (e.g., NULL maturity_date before synthesis)
            pass

    return {
        "total": round(total_interest, 2),
        "known_total": round(known_total, 2),
        "estimated_total": round(estimated_total, 2),
        "estimated_fd_count": estimated_count,
        "known_fd_count": known_count,
        "per_bank": {k: {kk: round(vv, 2) if isinstance(vv, float) else vv for kk, vv in v.items()} for k, v in per_bank.items()},
        "is_estimated": any_estimated,
    }


def project_savings_interest(
    person_id: int,
    financial_year: str
) -> dict:
    """
    Project savings interest for the FY.
    Currently returns 0 (no savings interest calculation engine exists).
    Marked as estimated.

    Returns:
        {
          "total": float,
          "is_estimated": bool
        }
    """
    return {
        "total": 0.0,
        "is_estimated": True,
    }


def realised_income_to_date(
    person_id: int,
    financial_year: str,
    as_of: date | None = None
) -> dict:
    """
    Realised (already-received) income to the as_of date from transactions.

    CRITICAL: classify by category column. Only categories in TAXABLE_INCOME_CATEGORIES
    or NON_TAXABLE_INCOME_CATEGORIES are counted. All others are marked unclassified.

    Returns:
        {
          "taxable": float,
          "non_taxable": float,
          "unclassified": float,
          "by_category": {
            "category_name": float,
            ...
          }
        }
    """
    txns = get_transactions(person_id=person_id, financial_year=financial_year, transaction_type="Income")

    taxable = 0.0
    non_taxable = 0.0
    unclassified = 0.0
    by_category = {}

    for txn in txns:
        amount = float(txn.get("amount") or 0)
        category = txn.get("category") or "Unclassified"

        if category not in by_category:
            by_category[category] = 0.0

        by_category[category] += amount

        if category in TAXABLE_INCOME_CATEGORIES:
            taxable += amount
        elif category in NON_TAXABLE_INCOME_CATEGORIES:
            non_taxable += amount
        else:
            unclassified += amount

    return {
        "taxable": round(taxable, 2),
        "non_taxable": round(non_taxable, 2),
        "unclassified": round(unclassified, 2),
        "by_category": {k: round(v, 2) for k, v in sorted(by_category.items())},
    }


def expected_income(
    person_id: int,
    financial_year: str
) -> dict:
    """
    Sum expected income from IncomeExpectation table for the FY.

    Returns:
        {
          "total": float,
          "count": int,
          "is_empty": bool
        }
    """
    conn = get_connection()
    row = conn.execute(
        """
        SELECT COUNT(*) AS cnt, COALESCE(SUM(expected_amount), 0.0) AS total
        FROM IncomeExpectation
        WHERE person_id = ? AND financial_year = ?
        """,
        (person_id, financial_year),
    ).fetchone()
    conn.close()

    count = int(row["cnt"]) if row else 0
    total = float(row["total"]) if row else 0.0

    return {
        "total": round(total, 2),
        "count": count,
        "is_empty": count == 0,
    }


def project_fy_income(
    person_id: int,
    financial_year: str | None = None,
    as_of: date | None = None,
) -> dict:
    """
    Project total taxable income for the FY and headroom to rebate limit.

    Taxable income = realised taxable + projected FD interest + projected savings interest.

    Returns:
        {
          "financial_year": str,
          "as_of": str (ISO date),
          "projected_total": float,
          "limit": float (from TaxParams.rebate_87a_limit),
          "headroom": float (limit - projected_total, can be negative),
          "is_over_limit": bool,
          "is_estimated": bool
        }
    """
    financial_year = _current_fy_or_default(financial_year)
    as_of = _as_of_date(as_of)

    realised = realised_income_to_date(person_id, financial_year, as_of)
    fd_interest = project_fd_interest(person_id, financial_year, as_of)
    savings_interest = project_savings_interest(person_id, financial_year)

    # Tax parameters: use private helper with a brief comment
    params = _get_tax_params(financial_year)  # Private helper used to load tax config from DB
    limit = float(params.get("rebate_87a_limit") or 1200000.0)

    projected_total = (
        realised["taxable"]
        + fd_interest["total"]
        + savings_interest["total"]
    )

    headroom = limit - projected_total

    return {
        "financial_year": financial_year,
        "as_of": as_of.isoformat(),
        "projected_total": round(projected_total, 2),
        "limit": round(limit, 2),
        "headroom": round(headroom, 2),
        "is_over_limit": projected_total > limit,
        "is_estimated": fd_interest["is_estimated"] or savings_interest["is_estimated"],
    }


def project_bank_tds_risk(
    person_id: int,
    financial_year: str,
    as_of: date | None = None,
) -> dict:
    """
    Per-bank projected interest vs fd_tds_threshold from TaxParams.

    For each bank with FDs: projected interest, threshold, will_cross (bool),
    amount_over, is_estimated.

    Returns:
        {
          "threshold": float (from TaxParams.fd_tds_threshold),
          "by_bank": [
            {
              "bank_name": str,
              "projected_interest": float,
              "threshold": float,
              "will_cross": bool,
              "amount_over": float (0 if won't cross),
              "is_estimated": bool
            },
            ...
          ]
        }
    """
    as_of = _as_of_date(as_of)
    params = _get_tax_params(financial_year)  # Private helper used to load tax config from DB
    threshold = float(params.get("fd_tds_threshold") or 50000.0)

    fd_result = project_fd_interest(person_id, financial_year, as_of)
    per_bank = fd_result.get("per_bank") or {}

    by_bank = []
    for bank_name, bank_data in per_bank.items():
        interest = bank_data["total"]
        will_cross = interest >= threshold
        amount_over = max(0.0, interest - threshold)

        by_bank.append({
            "bank_name": bank_name,
            "projected_interest": round(interest, 2),
            "threshold": round(threshold, 2),
            "will_cross": will_cross,
            "amount_over": round(amount_over, 2),
            "is_estimated": bank_data["is_estimated"],
        })

    by_bank.sort(key=lambda x: x["projected_interest"], reverse=True)

    return {
        "threshold": round(threshold, 2),
        "by_bank": by_bank,
    }


def income_timeline(
    person_id: int,
    financial_year: str,
    as_of: date | None = None,
) -> dict:
    """
    12 month buckets for the FY with monthly and cumulative projected taxable income.

    Returns:
        {
          "financial_year": str,
          "months": [
            {
              "month": int (1–12, Apr=1),
              "month_name": str,
              "monthly_projected": float,
              "cumulative_projected": float,
              "is_estimated": bool
            },
            ...
          ]
        }
    """
    as_of = _as_of_date(as_of)
    fy_start, fy_end = fy_date_range(financial_year)
    start_year = int(financial_year.split("-")[0])

    # Calculate total projected income to date
    total_projected = 0.0
    realised = realised_income_to_date(person_id, financial_year, as_of)
    fd_interest = project_fd_interest(person_id, financial_year, as_of)
    savings_interest = project_savings_interest(person_id, financial_year)

    total_projected = (
        realised["taxable"]
        + fd_interest["total"]
        + savings_interest["total"]
    )

    months = []
    month_num = 1

    for m in range(4, 16):
        if m <= 12:
            month = m
            year = start_year
        else:
            month = m - 12
            year = start_year + 1

        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year + 1, 1, 1) - relativedelta(days=1)
        else:
            month_end = date(year, month + 1, 1) - relativedelta(days=1)

        # Clamp to FY range
        month_start = max(month_start, fy_start)
        month_end = min(month_end, fy_end)

        if month_start > month_end:
            break

        # Approximate monthly share (simple: total projected / 12)
        # A more accurate approach would re-query transactions per month
        monthly_projected = round(total_projected / 12, 2)

        months.append({
            "month": month_num,
            "month_name": date(2000, month, 1).strftime("%B"),
            "monthly_projected": monthly_projected,
            "cumulative_projected": round(monthly_projected * month_num, 2),
            "is_estimated": fd_interest["is_estimated"] or savings_interest["is_estimated"],
        })

        month_num += 1

    # Adjust last cumulative to match total
    if months:
        months[-1]["cumulative_projected"] = round(total_projected, 2)

    return {
        "financial_year": financial_year,
        "months": months,
    }


def build_advisory(
    person_id: int,
    financial_year: str | None = None,
    as_of: date | None = None,
) -> dict:
    """
    Rules-based advisory with severity, title, detail, category, amount, is_estimated.

    Covers:
      - Over/under the 12L limit and by how much
      - Per-bank projected TDS threshold crossing
      - Estimated FD rate count
      - Empty IncomeExpectation note
      - Disclaimer that these are estimates, not tax advice

    Returns:
        {
          "warnings": [
            {
              "severity": "info" | "warning" | "alert",
              "title": str,
              "detail": str,
              "category": str,
              "amount": float,
              "is_estimated": bool
            },
            ...
          ],
          "disclaimer": str
        }
    """
    financial_year = _current_fy_or_default(financial_year)
    as_of = _as_of_date(as_of)

    warnings = []

    # Projected income vs 12L limit
    income = project_fy_income(person_id, financial_year, as_of)
    if income["is_over_limit"]:
        warnings.append({
            "severity": "alert",
            "title": "Income above rebate limit",
            "detail": f"Projected taxable income ₹{income['projected_total']:,.0f} exceeds ₹{income['limit']:,.0f} rebate limit by ₹{abs(income['headroom']):,.0f}.",
            "category": "income_limit",
            "amount": abs(income["headroom"]),
            "is_estimated": income["is_estimated"],
        })
    elif income["headroom"] > 0 and income["headroom"] < 50000:
        warnings.append({
            "severity": "warning",
            "title": "Low headroom to rebate limit",
            "detail": f"Only ₹{income['headroom']:,.0f} headroom remaining before exceeding the ₹{income['limit']:,.0f} rebate limit.",
            "category": "income_limit",
            "amount": income["headroom"],
            "is_estimated": income["is_estimated"],
        })

    # Per-bank TDS threshold crossing
    tds_risk = project_bank_tds_risk(person_id, financial_year, as_of)
    for bank in tds_risk["by_bank"]:
        if bank["will_cross"]:
            warnings.append({
                "severity": "warning",
                "title": f"{bank['bank_name']}: TDS threshold at risk",
                "detail": f"Projected FD interest ₹{bank['projected_interest']:,.0f} exceeds ₹{bank['threshold']:,.0f} threshold by ₹{bank['amount_over']:,.0f}. File Form 15G to avoid TDS.",
                "category": "tds_threshold",
                "amount": bank["amount_over"],
                "is_estimated": bank["is_estimated"],
            })

    # FD estimated count
    fd_interest = project_fd_interest(person_id, financial_year, as_of)
    if fd_interest["estimated_fd_count"] > 0:
        warnings.append({
            "severity": "info",
            "title": f"{fd_interest['estimated_fd_count']} FDs use estimated 7.5% rate",
            "detail": f"{fd_interest['estimated_fd_count']} FD(s) lack interest rate or maturity date. Actual interest may differ. Update FD details to refine projections.",
            "category": "estimated_rates",
            "amount": fd_interest["estimated_total"],
            "is_estimated": True,
        })

    # Empty IncomeExpectation
    expectations = expected_income(person_id, financial_year)
    if expectations["is_empty"]:
        warnings.append({
            "severity": "info",
            "title": "No income expectations set",
            "detail": "IncomeExpectation table is empty for this FY. Projections use only realised transactions and FD interest.",
            "category": "data_completeness",
            "amount": 0.0,
            "is_estimated": True,
        })

    disclaimer = (
        "DISCLAIMER: These projections are based on current data and estimates only. "
        "They are NOT tax advice. Consult a qualified tax professional before making decisions."
    )

    return {
        "warnings": warnings,
        "disclaimer": disclaimer,
    }


def get_prediction_summary(
    person_id: int,
    financial_year: str | None = None,
    as_of: date | None = None,
) -> dict:
    """
    Single entry point for the UI: all prediction data in one call.

    Returns:
        {
          "financial_year": str,
          "as_of": str (ISO date),
          "realised_income": {taxable, non_taxable, unclassified, by_category},
          "projected_fd_interest": {total, known_total, estimated_total, ...},
          "projected_savings_interest": {total, is_estimated},
          "expected_income": {total, count, is_empty},
          "fy_income": {projected_total, limit, headroom, is_over_limit, is_estimated},
          "tds_risk": {threshold, by_bank},
          "timeline": {months},
          "advisory": {warnings, disclaimer}
        }
    """
    financial_year = _current_fy_or_default(financial_year)
    as_of = _as_of_date(as_of)

    return {
        "financial_year": financial_year,
        "as_of": as_of.isoformat(),
        "realised_income": realised_income_to_date(person_id, financial_year, as_of),
        "projected_fd_interest": project_fd_interest(person_id, financial_year, as_of),
        "projected_savings_interest": project_savings_interest(person_id, financial_year),
        "expected_income": expected_income(person_id, financial_year),
        "fy_income": project_fy_income(person_id, financial_year, as_of),
        "tds_risk": project_bank_tds_risk(person_id, financial_year, as_of),
        "timeline": income_timeline(person_id, financial_year, as_of),
        "advisory": build_advisory(person_id, financial_year, as_of),
    }
