"""
engines/tax_engine.py — Indian income tax calculation (2024-25)
"""

from config import get_assessment_year
from models.tax_profile import upsert_tax_profile


# ── Tax Slabs 2024-25 ─────────────────────────────────────────────────────────

OLD_REGIME_SLABS = [
    (250000, 0),      # Up to 2.5L: 0%
    (500000, 5),      # 2.5L - 5L: 5%
    (1000000, 20),    # 5L - 10L: 20%
    (float('inf'), 30) # Above 10L: 30%
]

NEW_REGIME_SLABS = [
    (300000, 0),      # Up to 3L: 0%
    (600000, 5),      # 3L - 6L: 5%
    (900000, 10),     # 6L - 9L: 10%
    (1200000, 15),    # 9L - 12L: 15%
    (1500000, 20),    # 12L - 15L: 20%
    (float('inf'), 30) # Above 15L: 30%
]

CESS_RATE = 4  # 4% cess on total tax


def calculate_tax_by_slabs(taxable_income: float, slabs: list) -> float:
    """Calculate tax based on slab structure."""
    if taxable_income <= 0:
        return 0.0
    
    tax = 0.0
    prev_limit = 0
    
    for limit, rate in slabs:
        if taxable_income <= prev_limit:
            break

        taxable_in_slab = min(taxable_income, limit) - prev_limit
        tax += taxable_in_slab * rate / 100
        prev_limit = limit

    return round(tax, 2)


def slab_position(taxable_income: float, slabs: list) -> dict:
    """
    Locate a taxable income within a slab table: which marginal rate applies,
    the current slab's floor/ceiling, and how far (in ₹) until the income
    crosses into the next-higher slab. Used to answer "how close am I to the
    next tax bracket / the top slab".
    """
    prev_limit = 0
    for i, (limit, rate) in enumerate(slabs):
        if taxable_income <= limit:
            is_top = limit == float("inf")
            next_rate = slabs[i + 1][1] if (not is_top and i + 1 < len(slabs)) else None
            return {
                "current_rate": rate,
                "slab_floor": prev_limit,
                "slab_ceiling": None if is_top else limit,
                "amount_to_next_slab": None if is_top else round(limit - taxable_income, 2),
                "next_rate": next_rate,
                "is_top_slab": is_top,
            }
        prev_limit = limit
    # Unreachable when the last slab is (inf, rate), but stay safe.
    top_rate = slabs[-1][1] if slabs else 0
    return {
        "current_rate": top_rate,
        "slab_floor": prev_limit,
        "slab_ceiling": None,
        "amount_to_next_slab": None,
        "next_rate": None,
        "is_top_slab": True,
    }


def calculate_old_regime_tax(gross_income: float, deductions_80c: float = 0,
                              deductions_80d: float = 0, home_loan_interest: float = 0,
                              hra_exemption: float = 0, standard_deduction: float = 50000) -> dict:
    """Calculate tax under old regime with deductions."""
    total_deductions = (
        min(deductions_80c, 150000) +  # 80C capped at 1.5L
        min(deductions_80d, 25000) +   # 80D capped at 25K (50K for senior citizens)
        home_loan_interest +            # 80EE/80EEA
        hra_exemption +
        standard_deduction
    )

    taxable_income = max(0, gross_income - total_deductions)
    base_tax = calculate_tax_by_slabs(taxable_income, OLD_REGIME_SLABS)
    cess_base = base_tax

    # Rebate under section 87A for taxable income up to 5L (old regime)
    rebate_87a = 0.0
    if taxable_income <= 500000:
        rebate_87a = min(base_tax, 12500)
        cess_base = max(0, base_tax - rebate_87a)

    cess = round(cess_base * CESS_RATE / 100, 2)
    total_tax = cess_base + cess

    return {
        "taxable_income": round(taxable_income, 2),
        "base_tax": base_tax,
        "cess": cess,
        "total_tax": round(total_tax, 2),
        "total_deductions": round(total_deductions, 2),
        "rebate_87a": rebate_87a
    }


def calculate_new_regime_tax(gross_income: float, standard_deduction: float = 75000) -> dict:
    """Calculate tax under new regime (no deductions except standard)."""
    taxable_income = max(0, gross_income - standard_deduction)
    base_tax = calculate_tax_by_slabs(taxable_income, NEW_REGIME_SLABS)
    cess_base = base_tax

    # Rebate under section 87A for income up to 7L
    rebate_87a = 0.0
    if taxable_income <= 700000:
        rebate_87a = min(base_tax, 25000)
        cess_base = max(0, base_tax - rebate_87a)

    cess = round(cess_base * CESS_RATE / 100, 2)
    total_tax = cess_base + cess

    return {
        "taxable_income": round(taxable_income, 2),
        "base_tax": base_tax,
        "cess": cess,
        "total_tax": round(total_tax, 2),
        "rebate_87a": rebate_87a
    }


def calculate_and_save_tax(person_id: int, financial_year: str,
                           salary_income: float = 0,
                           fd_interest: float = 0,
                           savings_interest: float = 0,
                           other_income: float = 0,
                           deductions_80c: float = 0,
                           deductions_80d: float = 0,
                           home_loan_interest: float = 0,
                           hra_exemption: float = 0,
                           tds_deducted: float = 0,
                           tcs_collected: float = 0,
                           advance_tax_paid: float = 0,
                           self_assessment_tax: float = 0) -> dict:
    """
    Calculate tax for both regimes and save to database.
    Returns dict with both regime calculations, plus net payable/refund
    for each regime after subtracting taxes already paid (TDS/TCS/advance/
    self-assessment).
    """
    gross_total_income = salary_income + fd_interest + savings_interest + other_income
    taxes_paid = tds_deducted + tcs_collected + advance_tax_paid + self_assessment_tax

    # Old regime
    old = calculate_old_regime_tax(
        gross_total_income,
        deductions_80c,
        deductions_80d,
        home_loan_interest,
        hra_exemption
    )
    old["net_payable"] = round(old["total_tax"] - taxes_paid, 2)

    # New regime
    new = calculate_new_regime_tax(gross_total_income)
    new["net_payable"] = round(new["total_tax"] - taxes_paid, 2)

    # Assessment year
    assessment_year = get_assessment_year(financial_year)

    # Save to database
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
        standard_deduction=50000,
        taxable_income_old_regime=old["taxable_income"],
        taxable_income_new_regime=new["taxable_income"],
        tax_old_regime=old["base_tax"],
        tax_new_regime=new["base_tax"],
        cess_amount=old["cess"],
        total_tax_old=old["total_tax"],
        total_tax_new=new["total_tax"],
        rebate_87a_old=old["rebate_87a"],
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
        "old_regime": old,
        "new_regime": new,
        "recommended": "Old Regime" if old["total_tax"] < new["total_tax"] else "New Regime"
    }


def get_tax_summary(person_id: int, financial_year: str) -> dict:
    """Get tax summary for a person and FY."""
    from models.tax_profile import get_tax_profile

    profile = get_tax_profile(person_id, financial_year)
    if not profile:
        return None

    old_total = profile.get("total_tax_old", 0)
    new_total = profile.get("total_tax_new", 0)
    taxes_paid = (
        profile.get("tds_deducted", 0) + profile.get("tcs_collected", 0)
        + profile.get("advance_tax_paid", 0) + profile.get("self_assessment_tax", 0)
    )

    return {
        "gross_income": profile.get("gross_total_income", 0),
        "old_regime_tax": old_total,
        "new_regime_tax": new_total,
        "recommended": "Old Regime" if old_total < new_total else "New Regime",
        "savings": abs(old_total - new_total),
        "taxes_paid": round(taxes_paid, 2),
        "net_payable_old": round(old_total - taxes_paid, 2),
        "net_payable_new": round(new_total - taxes_paid, 2),
    }


def project_next_year_income(person_id: int, current_fy: str) -> dict:
    """
    Project next financial year's gross income and where it lands in the New
    Regime slabs. Composition (honest about what is real vs assumed):

      • salary / other income  — summed from next-FY recurring income
        expectations (each expectation row is one occurrence, so summing
        expected_amount gives the annual total); if none exist, carried
        forward from this year's saved tax profile.
      • FD interest             — REAL: next-FY interest already allocated to
        FDInterestRecord for deposits that run into next year.
      • savings interest        — carried forward from this year's estimate.

    Returns a dict with the breakdown, projected New-Regime tax, and the slab
    position (marginal rate + ₹ headroom to the next bracket). `income_source`
    is "expectations" or "carry_forward" so the UI can label the assumption.
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
    new = calculate_new_regime_tax(gross)
    slab = slab_position(new["taxable_income"], NEW_REGIME_SLABS)

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
