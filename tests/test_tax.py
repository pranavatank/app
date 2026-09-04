from engines.tax_engine import calculate_new_regime_tax


def test_new_regime_basic():
    res = calculate_new_regime_tax(600000)
    assert "total_tax" in res
    assert res["taxable_income"] >= 0
