"""
engines/tax_engine.py — Indian income tax calculation (FY2025-26 onwards)
Implements correct tax calculation with 87A rebate, marginal relief, surcharge, cess.
"""

from config import get_assessment_year
from models.tax_profile import upsert_tax_profile
from core.database import get_connection


def _get_tax_slabs(financial_year: str) -> list:
    """
    Load New Regime tax slabs from database by financial year.
    Returns list of (upper_limit, rate) tuples, ordered by sort_order.
    Falls back to latest seeded year if the requested year is missing.
    """
    conn = get_connection()
    cur = conn.cursor()

    # Try to get slabs for the requested year
    rows = cur.execute("""
        SELECT upper_limit, rate FROM TaxSlabConfig
        WHERE financial_year = ? AND regime = 'new'
        ORDER BY sort_order
    """, (financial_year,)).fetchall()

    # If not found, get the latest year's slabs
    if not rows:
        rows = cur.execute("""
            SELECT upper_limit, rate FROM TaxSlabConfig
            WHERE regime = 'new'
            ORDER BY financial_year DESC, sort_order
            LIMIT 7
        """).fetchall()

    conn.close()
    return [(row[0], row[1]) for row in rows]


def _get_tax_params(financial_year: str) -> dict:
    """
    Load tax parameters (rebate limits, deduction, cess) from database.
    Falls back to latest seeded year if missing.
    """
    conn = get_connection()
    cur = conn.cursor()

    row = cur.execute(
        "SELECT rebate_87a_limit, rebate_87a_max, standard_deduction, cess_rate, fd_tds_threshold, fd_tds_threshold_senior FROM TaxParams WHERE financial_year = ?",
        (financial_year,)
    ).fetchone()

    # If not found, get the latest year's params
    if not row:
        row = cur.execute("""
            SELECT rebate_87a_limit, rebate_87a_max, standard_deduction, cess_rate, fd_tds_threshold, fd_tds_threshold_senior FROM TaxParams
            ORDER BY financial_year DESC
            LIMIT 1
        """).fetchone()

    conn.close()

    if row:
        return {
            "rebate_87a_limit": row[0],
            "rebate_87a_max": row[1],
            "standard_deduction": row[2],
            "cess_rate": row[3],
            "fd_tds_threshold": row[4],
            "fd_tds_threshold_senior": row[5],
        }

    # Hardcoded fallback if no params found
    return {
        "rebate_87a_limit": 1200000,
        "rebate_87a_max": 60000,
        "standard_deduction": 75000,
        "cess_rate": 4,
        "fd_tds_threshold": 50000,
        "fd_tds_threshold_senior": 100000,
    }


def calculate_tax_by_slabs(taxable_income: float, slabs: list) -> float:
    """Calculate tax based on slab structure."""
    if taxable_income <= 0:
        return 0.0

    tax = 0.0
    prev_limit = 0

    for limit, rate in slabs:
        if taxable_income <= prev_limit:
            break

        upper = limit if limit is not None else float('inf')
        taxable_in_slab = min(taxable_income, upper) - prev_limit
        tax += taxable_in_slab * rate / 100
        prev_limit = upper if limit is not None else limit

    return round(tax, 2)


def slab_position(taxable_income: float, slabs: list) -> dict:
    """
    Locate a taxable income within a slab table: which marginal rate applies,
    the current slab's floor/ceiling, and how far (in ₹) until the income
    crosses into the next-higher slab.
    """
    prev_limit = 0
    for i, (limit, rate) in enumerate(slabs):
        upper = limit if limit is not None else float('inf')
        if taxable_income <= upper:
            is_top = limit is None
            next_rate = slabs[i + 1][1] if (not is_top and i + 1 < len(slabs)) else None
            return {
                "current_rate": rate,
                "slab_floor": prev_limit,
                "slab_ceiling": limit,
                "amount_to_next_slab": None if is_top else round(limit - taxable_income, 2),
                "next_rate": next_rate,
                "is_top_slab": is_top,
            }
        prev_limit = upper if limit is not None else limit

    # Unreachable when the last slab is (None, rate), but stay safe.
    top_rate = slabs[-1][1] if slabs else 0
    return {
        "current_rate": top_rate,
        "slab_floor": prev_limit,
        "slab_ceiling": None,
        "amount_to_next_slab": None,
        "next_rate": None,
        "is_top_slab": True,
    }


def calculate_gross_total_income(
    salary_income: float = 0,
    pension_income: float = 0,
    business_income: float = 0,
    house_property_income: float = 0,
    capital_gains_normal: float = 0,
    capital_gains_stcg_111a: float = 0,
    capital_gains_ltcg_112: float = 0,
    capital_gains_ltcg_112a: float = 0,
    interest_income: float = 0,
    dividend_income: float = 0,
    other_income: float = 0,
) -> tuple[float, float]:
    """
    Calculate gross total income and identify special-rate capital gains.

    Returns (gross_total_income, special_rate_income) where special_rate_income
    is the sum of s.111A and s.112A gains that will be taxed at fixed rates
    (not slab rates).
    """
    # Sum all normal-slab income
    normal_gross = (
        salary_income + pension_income + business_income + house_property_income +
        capital_gains_normal + interest_income + dividend_income + other_income
    )

    # Special-rate income (taxed at 15% for s.111A, 12.5% for s.112/112A)
    special_rate_income = capital_gains_stcg_111a + capital_gains_ltcg_112a

    gross_total_income = normal_gross + capital_gains_ltcg_112 + special_rate_income

    return gross_total_income, special_rate_income


def calculate_new_regime_tax(
    gross_income: float,
    salary_income: float = 0,
    pension_income: float = 0,
    special_rate_income: float = 0,
    special_rate_pct: float = 15.0,
    financial_year: str = "2026-27"
) -> dict:
    """
    Calculate tax under new regime with correct order of operations:
    1. Split income into normal and special-rate portions
    2. Apply slab tax to normal income only
    3. Tax special-rate income at its own rate
    4. 87A rebate (applies to normal-income tax only, not special-rate tax)
    5. Marginal relief on rebate threshold (12,00,000)
    6. Surcharge (10/15/25%)
    7. Cess (4%)

    Parameters:
    -----------
    gross_income : float
        Total income before standard deduction
    salary_income, pension_income : float
        Used to calculate standard deduction only
    special_rate_income : float
        Income taxed under s.111A (STCG), s.112, or s.112A (LTCG).
        This income is NOT eligible for 87A rebate and is taxed at its own rate.
    special_rate_pct : float
        Tax rate for special-rate income. Default 15.0 for s.111A (STCG).
        Pass 12.5 for s.112/112A (LTCG).
    financial_year : str
        Financial year for tax parameters
    """
    params = _get_tax_params(financial_year)
    slabs = _get_tax_slabs(financial_year)

    # Guard against special_rate_income exceeding gross_income
    special_rate_income = min(special_rate_income, gross_income)

    # Standard deduction applies only to salary + pension income (not to special-rate income)
    standard_deduction = min(params["standard_deduction"], salary_income + pension_income)

    # Split income into normal and special-rate portions
    normal_gross_income = gross_income - special_rate_income
    normal_taxable_income = max(0, normal_gross_income - standard_deduction)
    special_rate_taxable_income = special_rate_income  # No standard deduction on special-rate income

    # 1. Calculate slab tax on normal income only
    slab_tax = calculate_tax_by_slabs(normal_taxable_income, slabs)

    # 2. Calculate tax on special-rate income at its own rate
    special_rate_tax = round(special_rate_taxable_income * special_rate_pct / 100, 2)

    # 3. Calculate 87A rebate: applies ONLY to normal income tax
    #    Available only if normal taxable income (after standard deduction) <= 12,00,000
    rebate_87a = 0.0
    if normal_taxable_income <= params["rebate_87a_limit"]:
        rebate_87a = min(slab_tax, params["rebate_87a_max"])

    # Tax after rebate (rebate applies only to normal tax, not special-rate tax)
    tax_after_rebate = slab_tax - rebate_87a + special_rate_tax

    # Total income (used for rebate threshold and surcharge calculations)
    total_income = gross_income

    # 4. Marginal relief on rebate threshold: above 12,00,000 total income,
    #    tax must not exceed the income earned above the threshold
    tax_before_surcharge = tax_after_rebate
    if total_income > params["rebate_87a_limit"]:
        income_above_threshold = total_income - params["rebate_87a_limit"]
        tax_before_surcharge = min(tax_after_rebate, income_above_threshold)

    # 5. Surcharge
    surcharge = 0.0
    if special_rate_income > 0:
        # Special-rate income (s.111A/112A) has 15% surcharge cap
        if total_income > 5000000:
            surcharge_rate = min(15, 10 if total_income <= 10000000 else 15 if total_income <= 20000000 else 25)
        else:
            surcharge_rate = 0
    else:
        # Normal income surcharge rates
        if total_income > 50000000:
            surcharge_rate = 25
        elif total_income > 20000000:
            surcharge_rate = 15
        elif total_income > 10000000:
            surcharge_rate = 15
        elif total_income > 5000000:
            surcharge_rate = 10
        else:
            surcharge_rate = 0

    surcharge = round(tax_before_surcharge * surcharge_rate / 100, 2)

    # Marginal relief on surcharge: increase in surcharge must not exceed increase in income
    if total_income > 0 and surcharge_rate > 0:
        prev_income_threshold = {10000000: 5000000, 20000000: 10000000, 50000000: 20000000}.get(total_income if total_income in [10000000, 20000000, 50000000] else None)
        if prev_income_threshold:
            surcharge_base_income = max(0, total_income - prev_income_threshold)
            surcharge_capped = min(surcharge, surcharge_base_income * surcharge_rate / 100)
            surcharge = surcharge_capped

    # 6. Cess: 4% on (tax - rebate + surcharge)
    cess_base = tax_before_surcharge + surcharge
    cess = round(cess_base * params["cess_rate"] / 100, 2)

    total_tax = tax_before_surcharge + surcharge + cess

    return {
        "normal_income": round(normal_taxable_income, 2),
        "special_rate_income": round(special_rate_taxable_income, 2),
        "taxable_income": round(normal_taxable_income + special_rate_taxable_income, 2),
        "slab_tax": slab_tax,
        "special_rate_tax": special_rate_tax,
        "base_tax": slab_tax + special_rate_tax,  # Keep for backward compatibility
        "rebate_87a": rebate_87a,
        "surcharge": surcharge,
        "cess": cess,
        "total_tax": round(total_tax, 2),
    }


def get_recommended_itr_form(
    salary_income: float,
    business_income: float,
    presumptive_income: float,
    interest_income: float,
    dividend_income: float,
    other_income: float,
) -> tuple[str, str]:
    """
    Recommend ITR form based on income composition per current tax law.

    Returns (form, reason) tuple.
    - ITR-4 (Sugam) if 44ADA presumptive income is the main/only business income
    - ITR-3 if there is any business or professional income (not under 44ADA)
    - ITR-1 if interest/dividend only (no business/salary)
    - ITR-1 as fallback if salary only

    Note: 44ADA (now renamed s.44AE for individuals) is a one-time election per owner's case
    that determines this taxpayer's form choice permanently (Form 10-IEA binding).
    For a purely salaried person, the choice is annual.
    """
    has_business = business_income > 0
    has_presumptive = presumptive_income > 0
    has_salary = salary_income > 0
    has_interest = interest_income > 0
    has_dividend = dividend_income > 0
    has_other = other_income > 0

    if has_presumptive and presumptive_income >= (business_income or 0):
        return "ITR-4", "44ADA presumptive income (Sugam)"

    if has_business or has_presumptive:
        return "ITR-3", "Business or professional income"

    if has_interest or has_dividend:
        return "ITR-1", "Interest and dividend income only"

    if has_salary or has_other:
        return "ITR-1", "Salaried person"

    return "ITR-1", "Not applicable (no income)"


def calculate_and_save_tax(
    person_id: int,
    financial_year: str,
    salary_income: float = 0,
    pension_income: float = 0,
    business_income: float = 0,
    presumptive_income: float = 0,
    house_property_income: float = 0,
    capital_gains_normal: float = 0,
    capital_gains_stcg_111a: float = 0,
    capital_gains_ltcg_112: float = 0,
    capital_gains_ltcg_112a: float = 0,
    fd_interest: float = 0,
    savings_interest: float = 0,
    other_interest: float = 0,
    dividend_income: float = 0,
    other_income: float = 0,
    deductions_80c: float = 0,
    deductions_80d: float = 0,
    home_loan_interest: float = 0,
    hra_exemption: float = 0,
    tds_deducted: float = 0,
    tcs_collected: float = 0,
    advance_tax_paid: float = 0,
    self_assessment_tax: float = 0,
) -> dict:
    """
    Calculate tax for New Regime and save to database.
    Returns dict with calculation details, net payable/refund, and ITR recommendation.

    All income categories must be passed separately so the engine can handle
    special-rate income (s.111A at 15%, s.112A at 12.5%) correctly.

    REGIME CHOICE REMOVED (T030):
    The old-vs-new regime choice has been deleted from this application because
    the owner has professional income under s.194J, which triggers Form 10-IEA —
    a one-time, binding switch between regimes per financial year. Once elected,
    it stands for that FY. The database columns (taxable_income_old_regime,
    tax_old_regime, total_tax_old, rebate_87a_old) are preserved to load existing
    profiles without error.

    For a purely salaried person without such professional income, the regime
    choice IS annual under current law, and a future maintainer should restore
    this if the user's circumstances change or multi-user logic is added.
    """
    # Calculate gross income and identify special-rate components
    # Presumptive income is part of business income
    total_business_income = business_income + presumptive_income
    gross_total_income, special_rate_income = calculate_gross_total_income(
        salary_income=salary_income,
        pension_income=pension_income,
        business_income=total_business_income,
        house_property_income=house_property_income,
        capital_gains_normal=capital_gains_normal,
        capital_gains_stcg_111a=capital_gains_stcg_111a,
        capital_gains_ltcg_112=capital_gains_ltcg_112,
        capital_gains_ltcg_112a=capital_gains_ltcg_112a,
        interest_income=fd_interest + savings_interest + other_interest,
        dividend_income=dividend_income,
        other_income=other_income,
    )

    total_interest = fd_interest + savings_interest + other_interest
    taxes_paid = tds_deducted + tcs_collected + advance_tax_paid + self_assessment_tax

    # Calculate tax using New Regime
    new = calculate_new_regime_tax(
        gross_income=gross_total_income,
        salary_income=salary_income,
        pension_income=pension_income,
        special_rate_income=special_rate_income,
        financial_year=financial_year
    )
    new["net_payable"] = round(new["total_tax"] - taxes_paid, 2)

    # Assessment year
    assessment_year = get_assessment_year(financial_year)

    # Get ITR recommendation
    itr_form, itr_reason = get_recommended_itr_form(
        salary_income=salary_income,
        business_income=business_income,
        presumptive_income=presumptive_income,
        interest_income=total_interest,
        dividend_income=dividend_income,
        other_income=other_income,
    )

    # Save to database (only New Regime now)
    upsert_tax_profile(
        person_id=person_id,
        financial_year=financial_year,
        salary_income=salary_income,
        fd_interest_income=fd_interest,
        savings_interest_income=savings_interest,
        other_income=other_income,
        gross_total_income=gross_total_income,
        deductions_80c=deductions_80c,
        deductions_80d=deductions_80d,
        home_loan_interest=home_loan_interest,
        hra_exemption=hra_exemption,
        standard_deduction=min(75000, salary_income + pension_income),
        taxable_income_new_regime=new["taxable_income"],
        tax_new_regime=new["base_tax"],
        cess_amount=new["cess"],
        total_tax_new=new["total_tax"],
        rebate_87a_new=new["rebate_87a"],
        tds_deducted=tds_deducted,
        tcs_collected=tcs_collected,
        advance_tax_paid=advance_tax_paid,
        self_assessment_tax=self_assessment_tax,
    )

    return {
        "gross_total_income": gross_total_income,
        "assessment_year": assessment_year,
        "taxes_paid": round(taxes_paid, 2),
        "new_regime": new,
        "itr_form": itr_form,
        "itr_reason": itr_reason,
    }


def get_tax_summary(person_id: int, financial_year: str) -> dict:
    """Get tax summary for a person and FY."""
    from models.tax_profile import get_tax_profile

    profile = get_tax_profile(person_id, financial_year)
    if not profile:
        return None

    new_total = profile.get("total_tax_new", 0)
    taxes_paid = (
        profile.get("tds_deducted", 0) + profile.get("tcs_collected", 0)
        + profile.get("advance_tax_paid", 0) + profile.get("self_assessment_tax", 0)
    )

    return {
        "gross_income": profile.get("gross_total_income", 0),
        "new_regime_tax": new_total,
        "taxes_paid": round(taxes_paid, 2),
        "net_payable_new": round(new_total - taxes_paid, 2),
    }


def project_next_year_income(person_id: int, current_fy: str) -> dict:
    """
    Project next financial year's gross income and where it lands in the New
    Regime slabs. Composition:
      • salary / other income  — summed from next-FY recurring income
        expectations; if none exist, carried forward from this year's saved profile.
      • FD interest            — REAL: next-FY interest already allocated.
      • savings interest       — carried forward from this year's estimate.

    Returns a dict with the breakdown, projected New-Regime tax, and slab position.
    """
    from models.income_expectation import get_income_expectations
    from models.fd_interest_record import get_total_fd_interest
    from models.savings_interest import get_total_savings_interest
    from models.tax_profile import get_tax_profile

    start = int(current_fy.split("-")[0])
    next_fy = f"{start + 1}-{str(start + 2)[2:]}"

    expectations = get_income_expectations(person_id=person_id, financial_year=next_fy)
    expected_income = sum(float(e.get("expected_amount") or 0) for e in expectations)
    income_source = "expectations"

    if expected_income <= 0:
        profile = get_tax_profile(person_id, current_fy)
        if profile:
            expected_income = (
                float(profile.get("salary_income", 0)) + float(profile.get("other_income", 0))
            )
        income_source = "carry_forward"

    fd_interest = get_total_fd_interest(next_fy, person_id=person_id)
    savings_interest = get_total_savings_interest(current_fy, person_id=person_id)

    gross = expected_income + fd_interest + savings_interest
    new = calculate_new_regime_tax(gross, salary_income=expected_income, financial_year=next_fy)
    slabs = _get_tax_slabs(next_fy)
    slab = slab_position(new["taxable_income"], slabs)

    return {
        "next_fy": next_fy,
        "assessment_year": get_assessment_year(next_fy),
        "expected_income": round(expected_income, 2),
        "income_source": income_source,
        "fd_interest": round(fd_interest, 2),
        "savings_interest": round(savings_interest, 2),
        "gross_total_income": round(gross, 2),
        "taxable_income": new["taxable_income"],
        "projected_tax": new["total_tax"],
        "slab": slab,
    }
