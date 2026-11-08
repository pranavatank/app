from datetime import date
import pytest
from engines.fd_planner_math import normal_tax,interest_schedule,fy_start,fy_label


@pytest.mark.parametrize('income,expected',[(1200000,0),(1201000,1040),(1600000,124800),(2400000,312000)])
def test_tax_rebate_marginal_relief_and_cess(income,expected):
    assert normal_tax(income)==pytest.approx(expected)


def test_interest_splits_at_april_and_handles_leap_year():
    schedule=interest_schedule(date(2027,3,31),2,10)
    assert schedule[2026]==pytest.approx(.1/365)
    assert schedule[2027]==pytest.approx(.1/365)
    assert sum(interest_schedule(date(2028,2,29),1,10).values())==pytest.approx(.1/366)


def test_financial_year_boundary_and_label():
    assert fy_start(date(2026,3,31))==2025
    assert fy_start(date(2026,4,1))==2026
    assert fy_label(2026)=='2026-27'
