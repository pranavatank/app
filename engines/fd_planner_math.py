"""Shared financial-year, ordinary-income tax and existing-FD estimate helpers."""
from datetime import date,timedelta
from dateutil.relativedelta import relativedelta


def fy_start(day: date) -> int:
    return day.year if day.month >= 4 else day.year - 1


def fy_label(year: int) -> str:
    return f"{year}-{str(year + 1)[2:]}"


def normal_tax(income: float) -> float:
    """Resident, new regime, normal income only; no surcharge (<= Rs 50L).

    FY 2025-26/2026-27 parameters. Future years explicitly assume continuity.
    Income is already taxable, after eligible deductions. TDS is not a cost.
    """
    if not 0 <= income <= 5_000_000:
        raise ValueError("Planner tax model supports taxable income up to ₹50 lakh only.")
    if income <= 1_200_000:
        return 0.0
    tax = sum(max(0, min(income, hi) - lo) * rate for lo, hi, rate in (
        (400_000, 800_000, .05), (800_000, 1_200_000, .10),
        (1_200_000, 1_600_000, .15), (1_600_000, 2_000_000, .20),
        (2_000_000, 2_400_000, .25), (2_400_000, 5_000_000, .30)))
    return min(tax, income - 1_200_000) * 1.04


def interest_schedule(start: date, days: int, rate: float,
                      compounding: int = 4, day_basis: str = "actual") -> dict[int, float]:
    """FY accrual per rupee: calendar compounding + simple broken period.

    Start inclusive, maturity exclusive. Accrues daily at coupon / day basis;
    capitalization occurs on calendar anniversaries. This is an estimate,
    rather than a substitute for a bank's FD advice/rounding convention.
    """
    return interest_curve(start, days, rate, compounding, day_basis)[days]


def interest_curve(start: date, days: int, rate: float,
                   compounding: int = 4, day_basis: str = "actual") -> dict[int, dict[int, float]]:
    """Build every maturity coefficient in one pass over the horizon."""
    if days <= 0 or not 0 <= rate <= 20 or compounding not in (1, 2, 4, 12):
        raise ValueError("Invalid tenure, rate or compounding frequency.")
    if day_basis not in ("actual", "365"):
        raise ValueError("Unknown interest day basis.")
    end = start + timedelta(days=days)
    boundary = start + relativedelta(months=12 // compounding)
    balance, accrued = 1.0, 0.0
    result: dict[int, float] = {}
    day = start
    curve = {}
    period = 1
    while day < end:
        denominator = (date(day.year + 1, 1, 1) - date(day.year, 1, 1)).days if day_basis == "actual" else 365
        interest = balance * rate / 100 / denominator
        year = fy_start(day)
        result[year] = result.get(year, 0) + interest
        accrued += interest
        day += timedelta(days=1)
        curve[(day - start).days] = dict(result)
        if day == boundary:
            balance += accrued
            accrued = 0
            period += 1
            boundary = start + relativedelta(months=period * (12 // compounding))
    return curve
