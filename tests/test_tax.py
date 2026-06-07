from engines.tax_engine import calculate_old_regime_tax, calculate_new_regime_tax


def test_old_regime_basic():
    res = calculate_old_regime_tax(600000, deductions_80c=50000, deductions_80d=0)
    assert "total_tax" in res
    assert res["taxable_income"] >= 0


def test_new_regime_basic():
    res = calculate_new_regime_tax(600000)
    assert "total_tax" in res
    assert res["taxable_income"] >= 0
