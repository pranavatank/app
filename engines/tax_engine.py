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
    cess = round(base_tax * CESS_RATE / 100, 2)
    total_tax = base_tax + cess
    
    return {
        "taxable_income": round(taxable_income, 2),
        "base_tax": base_tax,
        "cess": cess,
        "total_tax": round(total_tax, 2),
        "total_deductions": round(total_deductions, 2)
    }


def calculate_new_regime_tax(gross_income: float, standard_deduction: float = 50000) -> dict:
    """Calculate tax under new regime (no deductions except standard)."""
    taxable_income = max(0, gross_income - standard_deduction)
    base_tax = calculate_tax_by_slabs(taxable_income, NEW_REGIME_SLABS)
    cess = round(base_tax * CESS_RATE / 100, 2)
    total_tax = base_tax + cess
    
    # Rebate under section 87A for income up to 7L
    if taxable_income <= 700000:
        rebate = min(base_tax, 25000)
        total_tax = max(0, total_tax - rebate)
    
    return {
        "taxable_income": round(taxable_income, 2),
        "base_tax": base_tax,
        "cess": cess,
        "total_tax": round(total_tax, 2),
        "rebate_87a": rebate if taxable_income <= 700000 else 0
    }


def calculate_and_save_tax(person_id: int, financial_year: str,
                           salary_income: float = 0,
                           fd_interest: float = 0,
                           savings_interest: float = 0,
                           other_income: float = 0,
                           deductions_80c: float = 0,
                           deductions_80d: float = 0,
                           home_loan_interest: float = 0,
                           hra_exemption: float = 0) -> dict:
    """
    Calculate tax for both regimes and save to database.
    Returns dict with both regime calculations.
    """
    gross_total_income = salary_income + fd_interest + savings_interest + other_income
    
    # Old regime
    old = calculate_old_regime_tax(
        gross_total_income,
        deductions_80c,
        deductions_80d,
        home_loan_interest,
        hra_exemption
    )
    
    # New regime
    new = calculate_new_regime_tax(gross_total_income)
    
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
        total_tax_new=new["total_tax"]
    )
    
    return {
        "gross_total_income": gross_total_income,
        "assessment_year": assessment_year,
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
    
    return {
        "gross_income": profile.get("gross_total_income", 0),
        "old_regime_tax": old_total,
        "new_regime_tax": new_total,
        "recommended": "Old Regime" if old_total < new_total else "New Regime",
        "savings": abs(old_total - new_total)
    }
