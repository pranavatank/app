"""engines/investment_options.py — Government-backed alternatives to bank FDs with projected returns."""

from datetime import date

from engines.interest_engine import calculate_fd_maturity

SCHEMES_PERIOD = "Oct–Dec 2026"
SCHEMES_VALID_UNTIL = "2026-12-31"
INDIA_POST_RATES_URL = "https://www.indiapost.gov.in/banking-services/savings"
RBI_FRSB_URL = "https://www.rbi.org.in/scripts/NotificationUser.aspx?Id=11924"
ELIGIBLE_ALL = "Everyone"
ELIGIBLE_SENIOR = "Senior citizens (60+)"
ELIGIBLE_GIRL_CHILD = "Girl child under 10"


def _option(name: str, rate: float, tenure_months: int, compounding: str | None, payout: bool,
            max_amount: float | None, eligibility: str, tax: str, notes: str,
            source_url: str = INDIA_POST_RATES_URL) -> dict:
    return {
        "name": name,
        "rate": rate,
        "tenure_months": tenure_months,
        "compounding": compounding,
        "payout": payout,
        "max_amount": max_amount,
        "eligibility": eligibility,
        "tax": tax,
        "notes": notes,
        "source_url": source_url,
    }


INVESTMENT_OPTIONS = [
    _option("Post Office Time Deposit – 1 year", 6.9, 12, "Quarterly", False, None,
            ELIGIBLE_ALL, "Taxable", "Interest paid yearly; no upper limit."),
    _option("Post Office Time Deposit – 2 years", 7.0, 24, "Quarterly", False, None,
            ELIGIBLE_ALL, "Taxable", "Interest paid yearly; no upper limit."),
    _option("Post Office Time Deposit – 3 years", 7.1, 36, "Quarterly", False, None,
            ELIGIBLE_ALL, "Taxable", "Interest paid yearly; no upper limit."),
    _option("Post Office Time Deposit – 5 years", 7.5, 60, "Quarterly", False, None,
            ELIGIBLE_ALL, "Taxable; 80C deduction", "Interest paid yearly; no upper limit."),
    _option("National Savings Certificate (NSC)", 7.7, 60, "Annual", False, None,
            ELIGIBLE_ALL, "Taxable; 80C deduction", "Interest compounds yearly and is paid at maturity."),
    _option("Kisan Vikas Patra (KVP)", 7.5, 115, "Annual", False, None,
            ELIGIBLE_ALL, "Taxable", "Money doubles in 115 months."),
    _option("Post Office Monthly Income Scheme", 7.4, 60, None, True, 900000,
            ELIGIBLE_ALL, "Taxable", "Monthly payout; up to ₹9 lakh single or ₹15 lakh joint."),
    _option("Senior Citizens Savings Scheme (SCSS)", 8.2, 60, None, True, 3000000,
            ELIGIBLE_SENIOR, "Taxable; 80C deduction", "Quarterly payout; up to ₹30 lakh per person."),
    _option("Public Provident Fund (PPF)", 7.1, 180, "Annual", False, 150000,
            ELIGIBLE_ALL, "Tax-free; 80C deduction", "Up to ₹1.5 lakh per year; 15-year lock-in."),
    _option("Sukanya Samriddhi Yojana (SSY)", 8.2, 252, "Annual", False, 150000,
            ELIGIBLE_GIRL_CHILD, "Tax-free; 80C deduction", "Up to ₹1.5 lakh per year, in a daughter's name."),
    _option("RBI Floating Rate Savings Bond", 8.05, 84, None, True, None,
            ELIGIBLE_ALL, "Taxable",
            "Rate resets every 6 months (NSC + 0.35%); interest paid half-yearly; 7-year lock-in.",
            source_url=RBI_FRSB_URL),
]


def _pluralize(count: int, unit: str) -> str:
    return f"{count} {unit}" if count == 1 else f"{count} {unit}s"


def format_lock_in(tenure_months: int) -> str:
    years, months = divmod(tenure_months, 12)
    parts = []
    if years:
        parts.append(_pluralize(years, "year"))
    if months:
        parts.append(_pluralize(months, "month"))
    return " ".join(parts)


def project_option(option: dict, amount: float) -> dict:
    amount = max(amount, 0)
    max_amount = option["max_amount"]
    invested = min(amount, max_amount) if max_amount is not None else amount

    if option["name"].startswith("Post Office Time Deposit"):
        # Interest is compounded quarterly within each year and paid annually;
        # paid-out interest does not continue compounding in the TD account.
        annual_payout = calculate_fd_maturity(invested, option["rate"], 12, "Quarterly") - invested
        interest = annual_payout * option["tenure_months"] / 12
        maturity_value = invested + interest  # Total receipts, including annual payouts
    elif option["name"] == "Kisan Vikas Patra (KVP)":
        maturity_value = invested * 2
        interest = invested
    elif option["payout"]:
        interest = invested * option["rate"] / 100 * option["tenure_months"] / 12
        maturity_value = invested + interest
    else:
        maturity_value = calculate_fd_maturity(invested, option["rate"], option["tenure_months"],
                                               option["compounding"])
        interest = maturity_value - invested

    return {
        "invested": round(invested, 2),
        "interest": round(interest, 2),
        "maturity_value": round(maturity_value, 2),
        "capped": max_amount is not None and amount > max_amount,
        "variable_rate_scenario": option["name"] in ("Public Provident Fund (PPF)", "Sukanya Samriddhi Yojana (SSY)", "RBI Floating Rate Savings Bond"),
    }


def eligible_options(is_senior: bool) -> list[dict]:
    return [
        option for option in INVESTMENT_OPTIONS
        if is_senior or option["eligibility"] != ELIGIBLE_SENIOR
    ]


def best_overflow_option(tenure_months: int, is_senior: bool, amount: float) -> dict | None:
    candidates = [
        option for option in eligible_options(is_senior)
        if option["eligibility"] != ELIGIBLE_GIRL_CHILD
        and (option["max_amount"] is None or option["max_amount"] >= amount)
        and option["tenure_months"] <= tenure_months
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda option: (option["rate"], -option["tenure_months"]))


def schemes_outdated(today: date | None = None) -> bool:
    return (today or date.today()) > date.fromisoformat(SCHEMES_VALID_UNTIL)
