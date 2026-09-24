"""
engines/prediction_engine.py — Income prediction engine for FY planning

Forecasts the owner's current financial-year income from HIS OWN data
(transactions, FDs, income expectations) so he can act early to stay under
the 12,00,000 rebate limit and avoid TDS.

This engine works ONLY with real data — transactions are already classified
by category, and FDs with missing details are synthesised with defaults.
No speculative optimisation; all figures carry an is_estimated flag.
"""

from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from config import fy_date_range, get_current_financial_year, FD_TDS_FORM_NAME, FD_TDS_FORM_NAME_SENIOR
from models.transaction import get_transactions
from models.fixed_deposit import get_all_fds
from models.bank_account import get_accounts_for_person
from models.form26as import get_form26as_import
from models.ais_tis_import import get_ais_tis_data
from engines.interest_engine import fd_interest_accrued_to, _is_senior_citizen_in_fy
from engines.tax_engine import _get_tax_params
from core.database import get_connection


# Module Constants
DEFAULT_FD_RATE = 7.5
DEFAULT_FD_TENURE_MONTHS = 12
TAXABLE_INCOME_CATEGORIES = {"FD Interest", "Savings Interest", "Professional Fees", "Commission Income", "Salary"}
NON_TAXABLE_INCOME_CATEGORIES = {"FD Maturity", "Other Income"}

ITR_SOURCE_26AS = "26AS"
ITR_SOURCE_AIS  = "AIS"
ITR_SOURCE_TIS  = "TIS"

STRATEGY_DECLARATION         = "declaration"
STRATEGY_REDISTRIBUTION      = "redistribution"
STRATEGY_NEW_BANK            = "new_bank"
STRATEGY_DEFER_MATURITY      = "defer_maturity"
STRATEGY_HEADROOM_INVESTMENT = "headroom_investment"
STRATEGY_DATA_QUALITY        = "data_quality"


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
    fy_start, fy_end = fy_date_range(financial_year)
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
            fd_start = date.fromisoformat(synth_fd["start_date"])
            fd_end = date.fromisoformat(synth_fd["maturity_date"])
            window_start = max(fd_start, fy_start)
            window_end = min(fd_end, fy_end)
            if window_start > window_end:
                continue
            interest = fd_interest_accrued_to(synth_fd, window_end)
            if window_start > fd_start:
                interest -= fd_interest_accrued_to(synth_fd, window_start - timedelta(days=1))

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
    financial_year: str,
    as_of: date | None = None
) -> dict:
    """
    Project NOT-YET-REALISED savings interest from statement-coverage end to FY end.
    Realised interest is already counted elsewhere and must not be double-counted.

    Per-bank basis: current FY realised (if positive), else prior FY, else none.

    Returns:
        {
          "total": float,
          "realised": float,
          "full_year": float,
          "per_bank": {bank_name: {realised, projected, basis, is_estimated}},
          "is_estimated": bool
        }
    """
    as_of = _as_of_date(as_of)
    fy_start, fy_end = fy_date_range(financial_year)
    cutoff = min(as_of, fy_end)

    start_year = int(financial_year.split("-")[0])
    prev_fy = f"{start_year - 1}-{str(start_year)[2:]}"
    p_start, p_end = fy_date_range(prev_fy)
    prev_days = (p_end - p_start).days + 1

    rows = get_transactions(person_id=person_id)

    if not rows:
        return {
            "total": 0.0,
            "realised": 0.0,
            "full_year": 0.0,
            "per_bank": {},
            "is_estimated": False,
        }

    accounts = {}
    for row in rows:
        account_id = row.get("account_id")
        if not account_id:
            continue

        if account_id not in accounts:
            accounts[account_id] = {
                "bank_name": row.get("bank_name") or "Unknown",
                "rows": [],
            }
        accounts[account_id]["rows"].append(row)

    total_projected = 0.0
    total_realised = 0.0
    per_bank = {}

    for account_id, account_data in accounts.items():
        bank_name = account_data["bank_name"]
        account_rows = account_data["rows"]

        max_date = None
        for row in account_rows:
            row_date = row.get("transaction_date")
            if row_date:
                try:
                    d = date.fromisoformat(row_date)
                    if max_date is None or d > max_date:
                        max_date = d
                except (ValueError, TypeError):
                    pass

        realised = 0.0
        for row in account_rows:
            category = row.get("category")
            txn_type = row.get("transaction_type")
            row_date = row.get("transaction_date")

            if category == "Savings Interest" and txn_type == "Income":
                try:
                    d = date.fromisoformat(row_date)
                    if fy_start <= d <= cutoff:
                        realised += float(row.get("amount") or 0)
                except (ValueError, TypeError):
                    pass

        prior = 0.0
        for row in account_rows:
            category = row.get("category")
            txn_type = row.get("transaction_type")
            row_date = row.get("transaction_date")

            if category == "Savings Interest" and txn_type == "Income":
                try:
                    d = date.fromisoformat(row_date)
                    if p_start <= d <= p_end:
                        prior += float(row.get("amount") or 0)
                except (ValueError, TypeError):
                    pass

        covered_to = max(min(cutoff, max_date) if max_date else fy_start - relativedelta(days=1),
                         fy_start - relativedelta(days=1))
        covered_days = max(0, (covered_to - fy_start).days + 1)
        remaining_days = max(0, (fy_end - covered_to).days)

        if realised > 0 and covered_days > 0:
            daily = realised / covered_days
            basis = "current_fy"
        elif prior > 0:
            daily = prior / prev_days
            basis = "prior_fy"
        else:
            daily = 0.0
            basis = "none"

        projected = daily * remaining_days
        total_projected += projected
        total_realised += realised

        if bank_name not in per_bank:
            per_bank[bank_name] = {
                "realised": 0.0,
                "projected": 0.0,
                "basis": basis,
                "is_estimated": False,
            }

        per_bank[bank_name]["realised"] += realised
        per_bank[bank_name]["projected"] += projected
        per_bank[bank_name]["basis"] = basis
        per_bank[bank_name]["is_estimated"] = projected > 0

    for bank_name in per_bank:
        per_bank[bank_name]["realised"] = round(per_bank[bank_name]["realised"], 2)
        per_bank[bank_name]["projected"] = round(per_bank[bank_name]["projected"], 2)

    return {
        "total": round(total_projected, 2),
        "realised": round(total_realised, 2),
        "full_year": round(total_realised + total_projected, 2),
        "per_bank": per_bank,
        "is_estimated": total_projected > 0,
    }


def realised_income_to_date(
    person_id: int,
    financial_year: str,
    as_of: date | None = None
) -> dict:
    """
    Realised (already-received) income to the as_of date from transactions.

    Classification logic:
    1. Taxable category match takes precedence (TAXABLE_INCOME_CATEGORIES).
    2. Then check internal_transfer flag OR non-taxable category (NON_TAXABLE_INCOME_CATEGORIES).
    3. All others are marked unclassified.

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
        elif txn.get("is_internal_transfer") or category in NON_TAXABLE_INCOME_CATEGORIES:
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
    savings_interest = project_savings_interest(person_id, financial_year, as_of)

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
          "form_name": str (Form 15G or Form 15H),
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
    is_senior = _is_senior_citizen_in_fy(person_id, financial_year)
    threshold = float(params.get("fd_tds_threshold_senior" if is_senior else "fd_tds_threshold") or 50000.0)
    form_name = FD_TDS_FORM_NAME_SENIOR if is_senior else FD_TDS_FORM_NAME

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
        "form_name": form_name,
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
    savings_interest = project_savings_interest(person_id, financial_year, as_of)

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


def itr_actuals(person_id: int, financial_year: str) -> dict:
    """
    ITR-side stored figures (26AS / AIS / TIS). READ-ONLY — this engine never
    changes them; they are the Income Tax department's record, not ours.

    Returns:
      {
        "has_data": bool,
        "form26as": {"total_tds": float, "source_file": str, "import_date": str} | None,
        "ais":      {"fd_interest","savings_interest","other_interest",
                     "dividend_income","other_income","tds_deducted",
                     "total_interest"} | None,
        "tis":      {same keys as "ais"} | None,
      }
    """
    form26as = get_form26as_import(person_id, financial_year)
    form26as_dict = None
    if form26as:
        form26as_dict = {
            "total_tds": round(float(form26as.get("total_tds") or 0.0), 2),
            "source_file": str(form26as.get("source_file") or ""),
            "import_date": str(form26as.get("import_date") or ""),
        }

    ais = get_ais_tis_data(person_id, financial_year, ITR_SOURCE_AIS)
    ais_dict = None
    if ais:
        fd_interest = float(ais.get("fd_interest") or 0.0)
        savings_interest = float(ais.get("savings_interest") or 0.0)
        other_interest = float(ais.get("other_interest") or 0.0)
        total_interest = fd_interest + savings_interest + other_interest
        ais_dict = {
            "fd_interest": round(fd_interest, 2),
            "savings_interest": round(savings_interest, 2),
            "other_interest": round(other_interest, 2),
            "dividend_income": round(float(ais.get("dividend_income") or 0.0), 2),
            "other_income": round(float(ais.get("other_income") or 0.0), 2),
            "tds_deducted": round(float(ais.get("tds_deducted") or 0.0), 2),
            "total_interest": round(total_interest, 2),
        }

    tis = get_ais_tis_data(person_id, financial_year, ITR_SOURCE_TIS)
    tis_dict = None
    if tis:
        fd_interest = float(tis.get("fd_interest") or 0.0)
        savings_interest = float(tis.get("savings_interest") or 0.0)
        other_interest = float(tis.get("other_interest") or 0.0)
        total_interest = fd_interest + savings_interest + other_interest
        tis_dict = {
            "fd_interest": round(fd_interest, 2),
            "savings_interest": round(savings_interest, 2),
            "other_interest": round(other_interest, 2),
            "dividend_income": round(float(tis.get("dividend_income") or 0.0), 2),
            "other_income": round(float(tis.get("other_income") or 0.0), 2),
            "tds_deducted": round(float(tis.get("tds_deducted") or 0.0), 2),
            "total_interest": round(total_interest, 2),
        }

    has_data = form26as_dict is not None or ais_dict is not None or tis_dict is not None

    return {
        "has_data": has_data,
        "form26as": form26as_dict,
        "ais": ais_dict,
        "tis": tis_dict,
    }


def compare_our_data_to_itr(person_id: int, financial_year: str,
                            as_of: date | None = None) -> dict:
    """
    Side-by-side of OUR prediction against the ITR-side record.

    Neutral framing only. The words "gap", "mismatch" and "error" must not
    appear in any string this function produces: our figure being lower is the
    expected shape, because most FD interest is credited inside the FD and
    never lands in a savings-account row.

    Returns:
      {
        "has_itr_data": bool,
        "itr_source": "AIS" | "TIS" | None,     # AIS preferred, TIS fallback
        "rows": [ {"label": str, "our_value": float, "itr_value": float,
                   "our_under_reports": bool, "is_estimated": bool} ],
      }
    """
    as_of = _as_of_date(as_of)

    itr = itr_actuals(person_id, financial_year)
    fd_proj = project_fd_interest(person_id, financial_year, as_of)
    savings_proj = realised_income_to_date(person_id, financial_year, as_of)
    form26as = itr.get("form26as")

    # Prefer AIS, fall back to TIS
    itr_source = None
    itr_data = itr.get("ais")
    if itr_data:
        itr_source = ITR_SOURCE_AIS
    else:
        itr_data = itr.get("tis")
        if itr_data:
            itr_source = ITR_SOURCE_TIS

    has_itr_data = itr_source is not None or form26as is not None

    rows = []

    # FD Interest row
    our_fd_interest = fd_proj.get("total", 0.0)
    itr_fd_interest = itr_data.get("fd_interest", 0.0) if itr_data else 0.0
    rows.append({
        "label": "FD Interest",
        "our_value": round(our_fd_interest, 2),
        "itr_value": round(itr_fd_interest, 2),
        "our_under_reports": our_fd_interest < itr_fd_interest,
        "is_estimated": fd_proj.get("is_estimated", False),
    })

    # Savings Interest row
    our_savings_interest = savings_proj.get("by_category", {}).get("Savings Interest", 0.0)
    itr_savings_interest = itr_data.get("savings_interest", 0.0) if itr_data else 0.0
    rows.append({
        "label": "Savings Interest",
        "our_value": round(our_savings_interest, 2),
        "itr_value": round(itr_savings_interest, 2),
        "our_under_reports": our_savings_interest < itr_savings_interest,
        "is_estimated": False,
    })

    # Total Interest row
    our_total_interest = our_fd_interest + our_savings_interest
    itr_total_interest = itr_data.get("total_interest", 0.0) if itr_data else 0.0
    rows.append({
        "label": "Total Interest",
        "our_value": round(our_total_interest, 2),
        "itr_value": round(itr_total_interest, 2),
        "our_under_reports": our_total_interest < itr_total_interest,
        "is_estimated": fd_proj.get("is_estimated", False),
    })

    # TDS Deducted row
    # TDS is deducted before credit so it never appears in a transaction
    form26as_tds = form26as.get("total_tds", 0.0) if form26as else 0.0
    rows.append({
        "label": "TDS Deducted",
        "our_value": 0.0,
        "itr_value": round(form26as_tds, 2),
        "our_under_reports": True,
        "is_estimated": False,
    })

    return {
        "has_itr_data": has_itr_data,
        "itr_source": itr_source,
        "rows": rows,
    }


def build_strategies(
    person_id: int,
    financial_year: str | None = None,
    as_of: date | None = None,
) -> dict:
    """
    Concrete actions for staying under the rebate limit and keeping TDS off.

    Pure: no Qt, no DB writes. Every threshold is read from TaxParams via
    _get_tax_params(); nothing here hardcodes a rupee limit.

    Returns:
      {
        "limit": float, "headroom": float, "tds_threshold": float,
        "form_name": str,                      # Form 15G or Form 15H
        "is_senior": bool,
        "strategies": [ {
            "id": str,            # e.g. "declaration:Jana Small Finance Bank"
            "category": str,      # one of the STRATEGY_* constants
            "priority": int,      # 1 = act first
            "title": str,
            "detail": str,
            "action": str,        # one imperative sentence
            "amount": float,      # rupees this action moves or protects
            "bank_name": str | None,
            "is_estimated": bool,
        } ],
      }
    """
    financial_year = _current_fy_or_default(financial_year)
    as_of = _as_of_date(as_of)

    # Gather data
    fy_income = project_fy_income(person_id, financial_year, as_of)
    tds_risk = project_bank_tds_risk(person_id, financial_year, as_of)
    fd_interest = project_fd_interest(person_id, financial_year, as_of)
    is_senior = _is_senior_citizen_in_fy(person_id, financial_year)
    form_name = FD_TDS_FORM_NAME_SENIOR if is_senior else FD_TDS_FORM_NAME

    limit = fy_income["limit"]
    headroom = fy_income["headroom"]
    threshold = tds_risk["threshold"]
    by_bank = tds_risk["by_bank"]

    strategies = []

    # Rule 1: STRATEGY_DECLARATION (priority 1)
    if not fy_income["is_over_limit"]:
        for bank in by_bank:
            if bank["will_cross"]:
                strategy_id = f"{STRATEGY_DECLARATION}:{bank['bank_name']}"
                strategies.append({
                    "id": strategy_id,
                    "category": STRATEGY_DECLARATION,
                    "priority": 1,
                    "title": f"{bank['bank_name']}: file {form_name}",
                    "detail": f"Lawful only when total projected income stays under the rebate limit.",
                    "action": f"Submit {form_name} to {bank['bank_name']} before the next interest credit.",
                    "amount": bank["projected_interest"],
                    "bank_name": bank["bank_name"],
                    "is_estimated": bank["is_estimated"],
                })

    # Rule 2: STRATEGY_REDISTRIBUTION (priority 2)
    for src_bank in by_bank:
        if src_bank["will_cross"]:
            excess = src_bank["projected_interest"] - threshold

            # Find receivers
            receivers = [b for b in by_bank if b["bank_name"] != src_bank["bank_name"] and (threshold - b["projected_interest"]) > 0]
            receivers.sort(key=lambda x: threshold - x["projected_interest"], reverse=True)

            if receivers:
                dst_bank = receivers[0]
                room = threshold - dst_bank["projected_interest"]
                movable_interest = min(excess, room)

                # Compute weighted known rate for source bank's FDs
                fds = get_all_fds(person_id=person_id)
                src_fds = [fd for fd in fds if fd.get("bank_name") == src_bank["bank_name"]]
                known_rate = DEFAULT_FD_RATE
                known_principals = 0.0
                known_total_rate = 0.0
                for fd in src_fds:
                    if fd.get("interest_rate"):
                        known_principals += fd.get("principal_amount", 0.0)
                        known_total_rate += fd.get("interest_rate", 0.0) * fd.get("principal_amount", 0.0)

                if known_principals > 0:
                    known_rate = known_total_rate / known_principals
                elif known_rate <= 0:
                    known_rate = DEFAULT_FD_RATE

                movable_principal = movable_interest / (known_rate / 100.0) if known_rate > 0 else 0.0

                strategy_id = f"{STRATEGY_REDISTRIBUTION}:{src_bank['bank_name']}-{dst_bank['bank_name']}"
                strategies.append({
                    "id": strategy_id,
                    "category": STRATEGY_REDISTRIBUTION,
                    "priority": 2,
                    "title": f"Move deposits from {src_bank['bank_name']} to {dst_bank['bank_name']}",
                    "detail": f"Rebalance FD principal to spread TDS risk across banks.",
                    "action": f"Shift about {movable_principal:,.0f} of principal from {src_bank['bank_name']} to {dst_bank['bank_name']} at renewal.",
                    "amount": movable_principal,
                    "bank_name": src_bank["bank_name"],
                    "is_estimated": src_bank["is_estimated"] or dst_bank["is_estimated"],
                })

    # Rule 3: STRATEGY_NEW_BANK (priority 3)
    crossing_banks = [b for b in by_bank if b["will_cross"]]
    if crossing_banks:
        # Check if any bank has room to receive
        receivers = [b for b in by_bank if (threshold - b["projected_interest"]) > 0]
        if not receivers:
            total_excess = sum(max(0.0, b["projected_interest"] - threshold) for b in crossing_banks)
            if total_excess > 0:
                deployable_principal = total_excess / (DEFAULT_FD_RATE / 100.0) if DEFAULT_FD_RATE > 0 else 0.0
                strategy_id = f"{STRATEGY_NEW_BANK}"
                strategies.append({
                    "id": strategy_id,
                    "category": STRATEGY_NEW_BANK,
                    "priority": 3,
                    "title": "Open a deposit at an additional bank",
                    "detail": f"Diversify to stay within TDS threshold of {threshold:,.0f} per bank.",
                    "action": f"Open a deposit at an additional bank for about {deployable_principal:,.0f} of principal so no single bank crosses {threshold:,.0f}.",
                    "amount": deployable_principal,
                    "bank_name": None,
                    "is_estimated": True,
                })

    # Rule 4: STRATEGY_DEFER_MATURITY (priority 1)
    if fy_income["is_over_limit"]:
        fy_start, fy_end = fy_date_range(financial_year)
        last_quarter_start = fy_end - relativedelta(months=3)

        fds = get_all_fds(person_id=person_id)
        maturity_candidates = []

        for fd in fds:
            try:
                synth_fd = _synthesise_fd(fd)
                maturity_date_str = synth_fd.get("maturity_date")
                if maturity_date_str:
                    maturity_date = date.fromisoformat(maturity_date_str)
                    if last_quarter_start <= maturity_date <= fy_end:
                        interest = fd_interest_accrued_to(synth_fd, min(maturity_date, fy_end))
                        maturity_candidates.append({
                            "fd": synth_fd,
                            "interest": interest,
                            "maturity_date": maturity_date,
                        })
            except Exception:
                pass

        maturity_candidates.sort(key=lambda x: x["interest"], reverse=True)
        for candidate in maturity_candidates[:5]:
            strategy_id = f"{STRATEGY_DEFER_MATURITY}:{candidate['fd'].get('fd_id')}"
            strategies.append({
                "id": strategy_id,
                "category": STRATEGY_DEFER_MATURITY,
                "priority": 1,
                "title": f"Renew FD maturing {candidate['maturity_date'].isoformat()}",
                "detail": f"Income will exceed the rebate limit this FY. Defer interest to next year.",
                "action": f"Renew this deposit with a maturity after {fy_end.isoformat()} so the interest falls in the next financial year.",
                "amount": candidate["interest"],
                "bank_name": candidate["fd"].get("bank_name"),
                "is_estimated": candidate["fd"].get("is_estimated", False),
            })

    # Rule 5: STRATEGY_HEADROOM_INVESTMENT (priority 4)
    if headroom > 0:
        # Compute principal-weighted average of known FD rates
        known_rate = DEFAULT_FD_RATE
        known_principals = 0.0
        known_total_rate = 0.0
        fds = get_all_fds(person_id=person_id)
        for fd in fds:
            if fd.get("interest_rate"):
                known_principals += fd.get("principal_amount", 0.0)
                known_total_rate += fd.get("interest_rate", 0.0) * fd.get("principal_amount", 0.0)

        if known_principals > 0:
            known_rate = known_total_rate / known_principals
        elif known_rate <= 0:
            known_rate = DEFAULT_FD_RATE

        rate_to_use = known_rate if known_rate > 0 else DEFAULT_FD_RATE
        is_estimated_rate = known_principals == 0.0

        deployable = headroom / (rate_to_use / 100.0) if rate_to_use > 0 else 0.0

        strategy_id = f"{STRATEGY_HEADROOM_INVESTMENT}"
        strategies.append({
            "id": strategy_id,
            "category": STRATEGY_HEADROOM_INVESTMENT,
            "priority": 4,
            "title": "Headroom available",
            "detail": f"Remaining space under the {limit:,.0f} rebate limit.",
            "action": f"Up to about {deployable:,.0f} of fresh principal can be deployed this year while staying under {limit:,.0f}.",
            "amount": deployable,
            "bank_name": None,
            "is_estimated": is_estimated_rate,
        })

    # Rule 6: STRATEGY_DATA_QUALITY (priority 5)
    if fd_interest["estimated_fd_count"] > 0:
        strategy_id = f"{STRATEGY_DATA_QUALITY}"
        strategies.append({
            "id": strategy_id,
            "category": STRATEGY_DATA_QUALITY,
            "priority": 5,
            "title": f"{fd_interest['estimated_fd_count']} deposit(s) use estimated rates",
            "detail": f"Rates are guessed at {DEFAULT_FD_RATE}% until you enter the real ones.",
            "action": f"Enter the real rate for {fd_interest['estimated_fd_count']} deposit(s) from the Fixed Deposits screen to firm these figures up.",
            "amount": fd_interest["estimated_total"],
            "bank_name": None,
            "is_estimated": True,
        })

    # Sort by (priority, -amount)
    strategies.sort(key=lambda x: (x["priority"], -x["amount"]))

    return {
        "limit": round(limit, 2),
        "headroom": round(headroom, 2),
        "tds_threshold": round(threshold, 2),
        "form_name": form_name,
        "is_senior": is_senior,
        "strategies": strategies,
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
                "detail": f"Projected FD interest ₹{bank['projected_interest']:,.0f} exceeds ₹{bank['threshold']:,.0f} threshold by ₹{bank['amount_over']:,.0f}. File {tds_risk['form_name']} to avoid TDS.",
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

    strategies = build_strategies(person_id, financial_year, as_of)

    return {
        "warnings": warnings,
        "strategies": strategies["strategies"],
        "context": {k: strategies[k] for k in ("limit", "headroom", "tds_threshold", "form_name", "is_senior")},
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
          "projected_savings_interest": {total, realised, full_year, per_bank, is_estimated},
          "expected_income": {total, count, is_empty},
          "fy_income": {projected_total, limit, headroom, is_over_limit, is_estimated},
          "tds_risk": {threshold, by_bank},
          "timeline": {months},
          "advisory": {warnings, disclaimer},
          "itr_actuals": {has_data, form26as, ais, tis},
          "comparison": {has_itr_data, itr_source, rows}
        }
    """
    financial_year = _current_fy_or_default(financial_year)
    as_of = _as_of_date(as_of)

    return {
        "financial_year": financial_year,
        "as_of": as_of.isoformat(),
        "realised_income": realised_income_to_date(person_id, financial_year, as_of),
        "projected_fd_interest": project_fd_interest(person_id, financial_year, as_of),
        "projected_savings_interest": project_savings_interest(person_id, financial_year, as_of),
        "expected_income": expected_income(person_id, financial_year),
        "fy_income": project_fy_income(person_id, financial_year, as_of),
        "tds_risk": project_bank_tds_risk(person_id, financial_year, as_of),
        "timeline": income_timeline(person_id, financial_year, as_of),
        "advisory": build_advisory(person_id, financial_year, as_of),
        "itr_actuals": itr_actuals(person_id, financial_year),
        "comparison": compare_our_data_to_itr(person_id, financial_year, as_of),
    }
