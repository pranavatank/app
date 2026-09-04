"""
tests/test_tax_baseline.py — Tax engine regression tests (no fixtures).

These tests validate the tax calculation engine against known ground-truth values.

Specification:
  - calculate_tax_by_slabs(1_500_000) should == 105000.0 (FY2026-27 slabs)
  - calculate_new_regime_tax(1_275_000)["total_tax"] should == 0.0
    Note: 12,75,000 is the headline tax-free salary figure (standard deduction at 75K).
"""

import pytest
from engines.tax_engine import calculate_tax_by_slabs, calculate_new_regime_tax, _get_tax_slabs


class TestTaxEngine:
    """Tax engine regression tests."""

    def test_calculate_tax_by_slabs_new_regime(self):
        """Tax calculation on 1.5M under current slabs should be 105000."""
        slabs = _get_tax_slabs("2026-27")
        result = calculate_tax_by_slabs(1_500_000, slabs)
        assert result == 105000.0

    def test_calculate_new_regime_tax_threshold(self):
        """Tax on 1,275,000 (tax-free threshold with standard deduction) should be 0.0 under new regime."""
        result = calculate_new_regime_tax(1_275_000, salary_income=1_275_000, financial_year="2026-27")
        assert result["total_tax"] == 0.0

    def test_special_rate_income_s111a_12lakh_base_case(self):
        """
        12,00,000 with 2,00,000 s.111A income should yield total_tax 31,200.

        Breakdown:
        - Normal income: 12,00,000 - 2,00,000 = 10,00,000
        - Slab tax on normal: 0 (0-4L) + 20,000 (4-8L @5%) + 20,000 (8-10L @10%) = 40,000
        - Special-rate tax: 2,00,000 @ 15% = 30,000
        - 87A rebate: min(40,000, 60,000) = 40,000 (only on normal tax, normal income <= 12L limit)
        - Tax after rebate: (40,000 - 40,000) + 30,000 = 30,000
        - Cess 4%: 30,000 * 4% = 1,200
        - Total: 30,000 + 1,200 = 31,200
        """
        result = calculate_new_regime_tax(
            gross_income=1_200_000,
            special_rate_income=200_000,
            financial_year="2026-27"
        )
        assert result["total_tax"] == 31_200.0, f"Expected 31,200 but got {result['total_tax']}"
        assert result["rebate_87a"] == 40_000.0, f"Expected rebate_87a=40,000 but got {result['rebate_87a']}"

    def test_special_rate_income_zero_no_regression(self):
        """
        12,00,000 with 0 special income should yield total_tax 0.
        This ensures the split logic doesn't break the ordinary (no special income) path.
        """
        result = calculate_new_regime_tax(
            gross_income=1_200_000,
            special_rate_income=0,
            financial_year="2026-27"
        )
        assert result["total_tax"] == 0.0, f"Expected 0 but got {result['total_tax']}"

    def test_special_rate_income_exceeds_rebate_limit(self):
        """
        When special-rate income alone exceeds the rebate limit (12,00,000),
        no rebate should be granted against it and tax is paid on the full amount.

        Example: 15,00,000 with 13,00,000 s.111A
        - Normal income: 15,00,000 - 13,00,000 = 2,00,000
        - Slab tax on normal: 0 (0-4L) = 0 (normal income 2L < 4L threshold)
        - Special-rate tax: 13,00,000 @ 15% = 1,95,000
        - 87A rebate: 0 (no slab tax on normal portion to rebate)
        - Tax after rebate: 1,95,000
        - Cess 4%: 1,95,000 * 4% = 7,800
        - Total: 1,95,000 + 7,800 = 2,02,800
        """
        result = calculate_new_regime_tax(
            gross_income=1_500_000,
            special_rate_income=1_300_000,
            financial_year="2026-27"
        )
        assert result["rebate_87a"] == 0.0, f"No rebate expected but got {result['rebate_87a']}"
        expected_total = 195_000 + 7_800  # 1,95,000 special-rate tax + 4% cess
        assert result["total_tax"] == expected_total, f"Expected {expected_total} but got {result['total_tax']}"
