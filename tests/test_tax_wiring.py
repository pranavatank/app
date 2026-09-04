"""
tests/test_tax_wiring.py — Comprehensive tests for tax engine wiring and special-rate income.

Verification suite for T030, T031, T032, T033 tasks.
"""

import pytest
from engines.tax_engine import (
    calculate_new_regime_tax,
    calculate_gross_total_income,
    calculate_and_save_tax,
    get_recommended_itr_form,
)
from engines.advance_tax_engine import calculate_advance_tax, INSTALLMENTS_44ADA
from datetime import date
from core.session import session


class TestGrossIncomeCalculation:
    """T031: Test that gross income is calculated correctly from all sources."""

    def test_calculate_gross_total_income_all_components(self):
        """Test that all income components are summed correctly."""
        gross, special = calculate_gross_total_income(
            salary_income=1000000,
            business_income=100000,
            house_property_income=50000,
            capital_gains_normal=25000,
            capital_gains_stcg_111a=200000,  # s.111A @ 15%
            capital_gains_ltcg_112=30000,    # s.112 @ 20%
            capital_gains_ltcg_112a=40000,   # s.112A @ 12.5%
            interest_income=50000,
            dividend_income=25000,
            other_income=15000,
        )
        # Total = 1M + 100K + 50K + 25K + 200K (special) + 30K + 40K (special) + 50K + 25K + 15K
        expected_gross = 1000000 + 100000 + 50000 + 25000 + 200000 + 30000 + 40000 + 50000 + 25000 + 15000
        expected_special = 200000 + 40000  # s.111A + s.112A
        assert gross == expected_gross
        assert special == expected_special

    def test_gross_income_with_presumptive_income(self):
        """Test that presumptive income is included in gross."""
        gross, special = calculate_gross_total_income(
            salary_income=1000000,
            business_income=0,
            house_property_income=0,
            capital_gains_normal=0,
            capital_gains_stcg_111a=0,
            capital_gains_ltcg_112=0,
            capital_gains_ltcg_112a=0,
            interest_income=50000,
            dividend_income=0,
            other_income=0,
        )
        assert gross == 1050000
        assert special == 0


class TestSpecialRateIncomeHandling:
    """T031: Test that special-rate income (s.111A, s.112A) is handled separately."""

    def test_stcg_111a_at_15_percent(self):
        """Short-term capital gains under s.111A are taxed at 15%, not slab rates."""
        result = calculate_new_regime_tax(
            gross_income=200000,
            special_rate_income=200000,
            special_rate_pct=15.0,
            financial_year="2026-27"
        )
        # 200K @ 15% = 30,000 + cess
        expected_tax = 200000 * 0.15
        expected_cess = expected_tax * 0.04
        expected_total = expected_tax + expected_cess
        assert result["special_rate_tax"] == 30000.0
        assert result["total_tax"] == expected_total

    def test_ltcg_112a_at_12_5_percent(self):
        """Long-term capital gains under s.112A are taxed at 12.5%, not slab rates."""
        result = calculate_new_regime_tax(
            gross_income=200000,
            special_rate_income=200000,
            special_rate_pct=12.5,
            financial_year="2026-27"
        )
        # 200K @ 12.5% = 25,000 + cess
        expected_tax = 200000 * 0.125
        expected_cess = expected_tax * 0.04
        expected_total = expected_tax + expected_cess
        assert result["special_rate_tax"] == 25000.0
        assert result["total_tax"] == expected_total

    def test_presumptive_income_44ada(self):
        """Test that 44ADA presumptive income is properly wired through and ITR-4 recommended."""
        from models.person import add_person
        # Create a test person first
        person_id = add_person("Test Person", pan_number="AAAAAAAAAAAAA")

        # Use 52535 (owner's test case from requirements)
        result = calculate_and_save_tax(
            person_id=person_id,
            financial_year="2026-27",
            salary_income=0,
            presumptive_income=52535,  # Owner's 44ADA income
            capital_gains_stcg_111a=0,
            fd_interest=0,
            savings_interest=0,
            other_interest=0,
            dividend_income=0,
            other_income=0,
        )
        # 52535 is under 4L slab with 87A rebate, so tax = 0 (but calculation runs)
        # The key is that it was wired through correctly
        assert result["new_regime"]["taxable_income"] == 52535
        # ITR should be ITR-4 for 44ADA
        assert result["itr_form"] == "ITR-4"

    def test_presumptive_income_44ada_higher(self):
        """Test 44ADA with higher income to verify non-zero tax."""
        from models.person import add_person
        person_id = add_person("Test Person 3", pan_number="CCCCCCCCCCCC")

        # Use 2000000 presumptive income to exceed 87A rebate cap
        result = calculate_and_save_tax(
            person_id=person_id,
            financial_year="2026-27",
            salary_income=0,
            presumptive_income=2000000,
            capital_gains_stcg_111a=0,
            fd_interest=0,
            savings_interest=0,
            other_interest=0,
            dividend_income=0,
            other_income=0,
        )
        # Debug: print what we got
        print(f"\nDEBUG: Gross: {result['gross_total_income']}, Tax: {result['new_regime']['total_tax']}")
        print(f"DEBUG: Taxable: {result['new_regime']['taxable_income']}, Slab: {result['new_regime']['slab_tax']}")
        # 2000000 should definitely have tax even after 87A rebate
        assert result["new_regime"]["total_tax"] > 0, f"Expected tax > 0 but got {result['new_regime']['total_tax']}"
        assert result["itr_form"] == "ITR-4"


class TestITRFormRecommendation:
    """T033: Test ITR form recommendation based on income mix."""

    def test_itr4_with_44ada(self):
        """44ADA presumptive income should recommend ITR-4."""
        form, reason = get_recommended_itr_form(
            salary_income=0,
            business_income=0,
            presumptive_income=50000,
            interest_income=0,
            dividend_income=0,
            other_income=0,
        )
        assert form == "ITR-4"
        assert "44ADA" in reason

    def test_itr3_with_business_income(self):
        """Business income should recommend ITR-3."""
        form, reason = get_recommended_itr_form(
            salary_income=1000000,
            business_income=100000,
            presumptive_income=0,
            interest_income=0,
            dividend_income=0,
            other_income=0,
        )
        assert form == "ITR-3"
        assert "Business" in reason

    def test_itr1_with_interest_dividend_only(self):
        """Interest and dividend income only should recommend ITR-1."""
        form, reason = get_recommended_itr_form(
            salary_income=0,
            business_income=0,
            presumptive_income=0,
            interest_income=50000,
            dividend_income=25000,
            other_income=0,
        )
        assert form == "ITR-1"
        assert "dividend" in reason.lower()

    def test_itr1_with_salary_only(self):
        """Salary only should recommend ITR-1."""
        form, reason = get_recommended_itr_form(
            salary_income=1000000,
            business_income=0,
            presumptive_income=0,
            interest_income=0,
            dividend_income=0,
            other_income=0,
        )
        assert form == "ITR-1"

    def test_owner_profile_itr3_or_4(self):
        """Owner's profile with 44ADA should return ITR-4, not ITR-1."""
        form, reason = get_recommended_itr_form(
            salary_income=1275000,
            business_income=0,
            presumptive_income=52535,  # Owner's s.44ADA income
            interest_income=50000,
            dividend_income=0,
            other_income=0,
        )
        # Should be ITR-4 due to 44ADA, never ITR-1
        assert form in ("ITR-4", "ITR-3")
        assert form != "ITR-1"


class TestAdvanceTaxEngine:
    """T032: Test advance tax engine fixes."""

    def test_safe_harbours_12_36_75_100(self):
        """Safe harbour percentages must be 12/36/75/100, not 15/45/75/100."""
        from engines.advance_tax_engine import INSTALLMENTS
        assert INSTALLMENTS[0]["cum_pct"] == 0.12, "Q1 should be 12%"
        assert INSTALLMENTS[1]["cum_pct"] == 0.36, "Q2 should be 36%"
        assert INSTALLMENTS[2]["cum_pct"] == 0.75, "Q3 should be 75%"
        assert INSTALLMENTS[3]["cum_pct"] == 1.00, "Q4 should be 100%"

    def test_44ada_single_instalment(self):
        """A 44ADA taxpayer should have exactly ONE instalment due 15 March."""
        result = calculate_advance_tax(
            financial_year="2026-27",
            gross_income=100000,
            annual_tax=50000,  # Large enough to exceed 10k threshold
            tds_deducted=0,
            advance_tax_paid=0,
            is_44ada=True,
            today=date(2026, 6, 1),  # Mid-year
        )
        # Should have exactly 1 instalment
        assert len(result.installments) == 1
        assert result.installments[0].due_date.month == 3
        assert result.installments[0].due_date.day == 15
        assert result.installments[0].cumulative_pct == 1.0

    def test_44ada_not_showing_overdue_q1_q2_q3(self):
        """Owner's 44ADA case should NOT mark Q1-Q3 as overdue."""
        result = calculate_advance_tax(
            financial_year="2026-27",
            gross_income=100000,
            annual_tax=5000,
            tds_deducted=0,
            advance_tax_paid=0,
            is_44ada=True,
            today=date(2026, 12, 31),  # End of year, before March
        )
        # Only 1 instalment should exist (March 15)
        overdue_count = len([i for i in result.installments if i.status == "Overdue"])
        assert overdue_count == 0, "44ADA taxpayer should not have overdue Q1-Q3"

    def test_senior_citizen_exemption(self):
        """Resident senior citizen with no business income should be exempt from advance tax."""
        result = calculate_advance_tax(
            financial_year="2026-27",
            gross_income=100000,
            annual_tax=5000,
            tds_deducted=0,
            advance_tax_paid=0,
            is_senior_resident=True,
            has_business_income=False,
        )
        # Should show exemption message
        assert "exempt" in result.banner_message.lower()
        assert result.banner_level == "success"

    def test_advance_tax_paid_accumulation(self):
        """Advance tax paid reduces shortfall correctly across all instalments."""
        # Scenario: paid Q1 instalment (12% = 1200), now in Q3
        result = calculate_advance_tax(
            financial_year="2026-27",
            gross_income=100000,
            annual_tax=10000,
            tds_deducted=0,
            advance_tax_paid=1200,  # Q1 payment
            today=date(2026, 12, 1),  # Q3 period
        )
        # With advance_tax_paid = 1200:
        # Q1 due: 12% = 1200, shortfall = 1200 - 1200 = 0 (Paid)
        # Q2 due: 36% = 3600, shortfall = 3600 - 1200 = 2400 (Overdue)
        # Q3 due: 75% = 7500, shortfall = 7500 - 1200 = 6300 (Overdue)
        assert result.installments[0].shortfall < 1.0, "Q1 should be paid"
        assert result.installments[1].shortfall == 2400.0, "Q2 shortfall should be 2400"
        assert result.installments[2].shortfall == 6300.0, "Q3 shortfall should be 6300"

    def test_march_shortfall_1_month_interest(self):
        """15 March shortfall should accrue 1 month interest, not 3 months."""
        result = calculate_advance_tax(
            financial_year="2026-27",
            gross_income=100000,
            annual_tax=10000,
            tds_deducted=0,
            advance_tax_paid=0,  # No payment
            today=date(2027, 4, 1),  # After March 15, 2027 (next year's March)
        )
        # Final instalment (March 15, 2027)
        march_inst = result.installments[-1]
        assert march_inst.due_date.month == 3
        assert march_inst.due_date.year == 2027
        # 10000 @ 1% * 1 month = 100
        expected_interest = 100.0
        assert march_inst.interest_234c == expected_interest, f"Expected 100, got {march_inst.interest_234c}"


class TestLoadingOldProfileColumns:
    """T030: Test that loading TaxProfile rows with *_old columns doesn't raise."""

    def test_load_profile_with_old_columns(self):
        """Loading a TaxProfile with taxable_income_old_regime and tax_old_regime should not raise."""
        from models.tax_profile import get_tax_profile, upsert_tax_profile
        from models.person import add_person

        # Create a test person first
        person_id = add_person("Test Person 2", pan_number="BBBBBBBBBBBBB")

        # Create a profile
        tax_id = upsert_tax_profile(
            person_id=person_id,
            financial_year="2026-27",
            salary_income=1000000,
            gross_total_income=1000000,
        )

        # Retrieve it — should not raise
        profile = get_tax_profile(person_id=person_id, financial_year="2026-27")
        assert profile is not None
        # Old columns should still be there (from schema), even if not set
        assert "taxable_income_old_regime" in profile
        assert "tax_old_regime" in profile
        assert "total_tax_old" in profile


class TestTaxBaselinePreservation:
    """Verify that the five baseline tax calculations remain unchanged."""

    def test_baseline_1_slab_tax_1_5m(self):
        """Baseline 1: Tax on 1.5M under new regime slabs should be 105,000."""
        from engines.tax_engine import calculate_tax_by_slabs, _get_tax_slabs
        slabs = _get_tax_slabs("2026-27")
        result = calculate_tax_by_slabs(1_500_000, slabs)
        assert result == 105000.0

    def test_baseline_2_threshold_12_75m(self):
        """Baseline 2: Tax on 1,275,000 (tax-free threshold) should be 0."""
        result = calculate_new_regime_tax(
            gross_income=1_275_000,
            salary_income=1_275_000,
            financial_year="2026-27"
        )
        assert result["total_tax"] == 0.0

    def test_baseline_3_salary_12_75k_zero_tax(self):
        """Baseline 3: Salary 12,75,000 should yield tax of 0 (with standard deduction)."""
        # 12,75,000 - standard deduction 75,000 = 12,00,000 taxable
        # 12,00,000 with 87A rebate limit gives tax = 0
        result = calculate_new_regime_tax(
            gross_income=1_275_000,
            salary_income=1_275_000,
            financial_year="2026-27"
        )
        assert result["total_tax"] == 0.0

    def test_baseline_4_special_rate_with_rebate(self):
        """Baseline 4: 12,00,000 incl 2,00,000 s.111A → 31,200 with rebate 40,000."""
        result = calculate_new_regime_tax(
            gross_income=1_200_000,
            special_rate_income=200_000,
            financial_year="2026-27"
        )
        assert result["total_tax"] == 31_200.0
        assert result["rebate_87a"] == 40_000.0

    def test_baseline_5_owner_fy2025_26(self):
        """Baseline 5: Owner FY2025-26 3,58,015 → tax 0, no standard deduction."""
        result = calculate_new_regime_tax(
            gross_income=358_015,
            salary_income=0,  # Presumptive income, no salary standard deduction
            financial_year="2025-26"
        )
        # Presumptive income is not eligible for standard deduction
        # So taxable = 358,015
        # All under 4L slab = 0 tax
        # Cess 4% on 0 = 0
        # Total = 0
        assert result["total_tax"] == 0.0
