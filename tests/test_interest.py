from engines.interest_engine import calculate_fd_maturity, calculate_fd_maturity_bank_style
from datetime import date


def test_fd_maturity_formula_monthly():
    m = calculate_fd_maturity(10000, 6.0, 12, "Monthly")
    assert isinstance(m, float)
    assert m > 10000


def test_fd_maturity_bank_style_simple():
    start = date(2024, 1, 1)
    end = date(2025, 1, 1)
    m = calculate_fd_maturity_bank_style(50000, 7.0, start, end, "Quarterly")
    assert isinstance(m, float)
    assert m >= 50000
