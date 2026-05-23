"""
engines/advance_tax_engine.py — Quarterly Advance Tax calculation engine (India).

Indian advance tax rules (non-senior citizens):
  By 15 Jun  → 15% of estimated annual tax
  By 15 Sep  → 45% of estimated annual tax (cumulative)
  By 15 Dec  → 75% of estimated annual tax (cumulative)
  By 15 Mar  → 100% of estimated annual tax (cumulative)

Senior citizens (≥ 60 yrs, no business income) are exempt.

Interest u/s 234B and 234C is calculated on shortfall.
"""

from __future__ import annotations
from datetime import date, timedelta
from dataclasses import dataclass, field


# ── Installment schedule ──────────────────────────────────────────────────────

INSTALLMENTS = [
    {"name": "1st Installment",  "due_month": 6,  "due_day": 15, "cum_pct": 0.15, "quarter": "Q1"},
    {"name": "2nd Installment",  "due_month": 9,  "due_day": 15, "cum_pct": 0.45, "quarter": "Q2"},
    {"name": "3rd Installment",  "due_month": 12, "due_day": 15, "cum_pct": 0.75, "quarter": "Q3"},
    {"name": "4th Installment",  "due_month": 3,  "due_day": 15, "cum_pct": 1.00, "quarter": "Q4"},
]


@dataclass
class InstallmentStatus:
    name: str
    quarter: str
    due_date: date
    cumulative_pct: float        # e.g. 0.15 = 15%
    annual_tax: float
    amount_due: float            # cumulative amount expected by this date
    amount_paid: float           # already paid (TDS + advance tax paid so far)
    shortfall: float             # max(0, amount_due - amount_paid)
    status: str                  # "Upcoming" | "Due Soon" | "Overdue" | "Paid" | "Partial"
    days_remaining: int          # negative if overdue
    interest_234c: float = 0.0   # 1% per month for 3 months on shortfall


@dataclass
class AdvanceTaxResult:
    financial_year: str
    assessment_year: str
    estimated_gross_income: float
    estimated_annual_tax: float   # total tax after TDS/TCS
    tds_deducted: float
    advance_tax_paid: float
    net_tax_payable: float
    installments: list[InstallmentStatus] = field(default_factory=list)
    banner_message: str = ""
    banner_level: str = "info"    # "info" | "warning" | "danger" | "success"
    next_due: InstallmentStatus | None = None


# ── Due date helpers ──────────────────────────────────────────────────────────

def _due_date(fy_start_year: int, month: int, day: int) -> date:
    """Convert installment month/day to an absolute date given FY start year."""
    year = fy_start_year if month >= 4 else fy_start_year + 1
    return date(year, month, day)


def _days_to(due: date, today: date | None = None) -> int:
    t = today or date.today()
    return (due - t).days


# ── Section 234C interest ─────────────────────────────────────────────────────

def _interest_234c(shortfall: float) -> float:
    """Simple estimate: 1% per month × 3 months on shortfall."""
    if shortfall <= 0:
        return 0.0
    return round(shortfall * 0.01 * 3, 2)


# ── Main calculation ──────────────────────────────────────────────────────────

def calculate_advance_tax(
    financial_year: str,
    gross_income: float,
    annual_tax: float,
    tds_deducted: float = 0.0,
    advance_tax_paid: float = 0.0,
    today: date | None = None,
) -> AdvanceTaxResult:
    """
    Calculate advance tax installments and produce reminder/banner data.

    Parameters
    ----------
    financial_year  : e.g. "2024-25"
    gross_income    : estimated gross total income for the year
    annual_tax      : estimated total tax liability (old or new regime)
    tds_deducted    : TDS already deducted / expected to be deducted
    advance_tax_paid: advance tax already paid so far
    today           : override today's date (for testing)
    """
    today = today or date.today()
    fy_start_year = int(financial_year.split("-")[0])
    ay_start = fy_start_year + 1
    assessment_year = f"{ay_start}-{str(ay_start + 1)[2:]}"

    # Net tax after TDS
    net_tax = max(0.0, annual_tax - tds_deducted)
    total_paid = advance_tax_paid  # running total of advance tax paid

    # If liability < ₹10,000 → no advance tax required
    if net_tax < 10_000:
        result = AdvanceTaxResult(
            financial_year=financial_year,
            assessment_year=assessment_year,
            estimated_gross_income=gross_income,
            estimated_annual_tax=annual_tax,
            tds_deducted=tds_deducted,
            advance_tax_paid=advance_tax_paid,
            net_tax_payable=net_tax,
            banner_message=(
                f"No advance tax required — estimated tax liability "
                f"₹ {net_tax:,.2f} is below the ₹10,000 threshold."
            ),
            banner_level="success",
        )
        return result

    installments: list[InstallmentStatus] = []
    next_due: InstallmentStatus | None = None

    for inst in INSTALLMENTS:
        due = _due_date(fy_start_year, inst["due_month"], inst["due_day"])
        cum_amount = round(net_tax * inst["cum_pct"], 2)
        days_rem = _days_to(due, today)

        # How much should have been paid cumulatively by this date
        if today > due:
            # Quarter already passed
            shortfall = max(0.0, cum_amount - total_paid)
            if shortfall < 1.0:
                status = "Paid"
            elif shortfall < cum_amount * 0.10:
                status = "Partial"
            else:
                status = "Overdue"
        elif days_rem <= 7:
            shortfall = max(0.0, cum_amount - total_paid)
            status = "Due Soon"
        else:
            shortfall = max(0.0, cum_amount - total_paid)
            status = "Upcoming"

        interest = _interest_234c(shortfall) if status in ("Overdue", "Partial") else 0.0

        s = InstallmentStatus(
            name=inst["name"],
            quarter=inst["quarter"],
            due_date=due,
            cumulative_pct=inst["cum_pct"],
            annual_tax=net_tax,
            amount_due=cum_amount,
            amount_paid=total_paid,
            shortfall=shortfall,
            status=status,
            days_remaining=days_rem,
            interest_234c=interest,
        )
        installments.append(s)

        # Track next upcoming installment
        if next_due is None and status in ("Upcoming", "Due Soon"):
            next_due = s

    # Banner for the most urgent situation
    overdue = [i for i in installments if i.status == "Overdue"]
    due_soon = [i for i in installments if i.status == "Due Soon"]

    if overdue:
        total_shortfall = sum(i.shortfall for i in overdue)
        total_interest  = sum(i.interest_234c for i in overdue)
        banner_message = (
            f"⚠  {len(overdue)} advance tax installment(s) overdue! "
            f"Shortfall: ₹ {total_shortfall:,.2f}  |  "
            f"Estimated 234C interest: ₹ {total_interest:,.2f}"
        )
        banner_level = "danger"
    elif due_soon:
        nxt = due_soon[0]
        banner_message = (
            f"🔔  {nxt.name} ({nxt.quarter}) due on {nxt.due_date.strftime('%d %b %Y')} "
            f"({nxt.days_remaining} day{'s' if nxt.days_remaining != 1 else ''} left) — "
            f"Pay ₹ {nxt.shortfall:,.2f} by due date."
        )
        banner_level = "warning"
    elif next_due:
        banner_message = (
            f"📅  Next installment: {next_due.name} ({next_due.quarter}) — "
            f"₹ {next_due.shortfall:,.2f} due by {next_due.due_date.strftime('%d %b %Y')} "
            f"({next_due.days_remaining} days away)."
        )
        banner_level = "info"
    else:
        # All quarters done
        remaining = max(0.0, net_tax - advance_tax_paid)
        if remaining < 1.0:
            banner_message = "✅  All advance tax installments have been covered."
            banner_level = "success"
        else:
            banner_message = (
                f"🔔  Final self-assessment tax of ₹ {remaining:,.2f} "
                f"due before 31 July {ay_start}."
            )
            banner_level = "warning"

    return AdvanceTaxResult(
        financial_year=financial_year,
        assessment_year=assessment_year,
        estimated_gross_income=gross_income,
        estimated_annual_tax=annual_tax,
        tds_deducted=tds_deducted,
        advance_tax_paid=advance_tax_paid,
        net_tax_payable=net_tax,
        installments=installments,
        banner_message=banner_message,
        banner_level=banner_level,
        next_due=next_due,
    )


# ── Projection helpers ────────────────────────────────────────────────────────

def project_annual_tax_from_ytd(
    fy: str,
    ytd_income: float,
    ytd_tax: float,
    today: date | None = None,
) -> tuple[float, float]:
    """
    Simple linear projection: annualise year-to-date income/tax.
    Returns (projected_gross_income, projected_annual_tax).
    """
    from config import fy_date_range
    today = today or date.today()
    fy_start, fy_end = fy_date_range(fy)
    total_days  = (fy_end - fy_start).days + 1
    elapsed     = (today - fy_start).days + 1
    if elapsed <= 0:
        return ytd_income, ytd_tax
    factor = total_days / elapsed
    return round(ytd_income * factor, 2), round(ytd_tax * factor, 2)
