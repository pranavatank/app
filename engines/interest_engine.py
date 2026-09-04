"""
engines/interest_engine.py — FD compounding, savings interest, FY allocation
"""

from datetime import date, timedelta
import calendar
from dateutil.relativedelta import relativedelta
from config import get_assessment_year, fy_date_range, FD_TDS_THRESHOLD
from models.fixed_deposit import get_fd
from models.fd_interest_record import (
    upsert_fd_interest, delete_fd_interest_records, get_fd_interest_by_fy,
)
from models.savings_interest import upsert_savings_interest
from models.transaction import get_transactions_by_account


def calculate_fd_maturity(principal: float, rate: float, tenure_months: int,
                          compounding: str) -> float:
    """Calculate FD maturity amount with compounding."""
    r = rate / 100
    if compounding == "Monthly":
        n = 12
    elif compounding == "Quarterly":
        n = 4
    else:  # Annual
        n = 1
    
    t = tenure_months / 12
    maturity = principal * ((1 + r / n) ** (n * t))
    return round(maturity, 2)




def calculate_fd_maturity_date(start_date: date,
                               tenure_years: int = 0,
                               tenure_months: int = 0,
                               tenure_days: int = 0) -> date:
    return start_date + relativedelta(
        years=tenure_years,
        months=tenure_months,
        days=tenure_days,
    )


def _year_days(d: date) -> int:
    return 366 if calendar.isleap(d.year) else 365


def _period_months_for_compounding(compounding: str) -> int:
    if compounding == "Monthly":
        return 1
    if compounding == "Quarterly":
        return 3
    return 12


def _accrue_period_interest(principal: float, annual_rate: float,
                            period_start: date, period_end: date) -> float:
    """
    Calculate interest accrued over a period using actual day count with
    leap-year awareness. Splits calculation across calendar years for precision.
    Returns accumulated interest amount (not rounded).
    """
    chunk_start = period_start
    period_interest = 0.0
    while chunk_start <= period_end:
        year_end = date(chunk_start.year, 12, 31)
        chunk_end = min(period_end, year_end)
        days = (chunk_end - chunk_start).days + 1
        period_interest += principal * annual_rate * days / _year_days(chunk_start)
        chunk_start = chunk_end + timedelta(days=1)
    return period_interest


def _average_monthly_balance(transactions: list) -> float:
    """
    Compute average balance across months from a list of transactions.
    Each transaction dict must have "transaction_date" and "balance_after" fields.
    Returns the average of monthly averages.
    """
    monthly_balances = {}
    for txn in transactions:
        txn_date = date.fromisoformat(txn["transaction_date"])
        month_key = (txn_date.year, txn_date.month)
        if month_key not in monthly_balances:
            monthly_balances[month_key] = []
        monthly_balances[month_key].append(txn["balance_after"])

    avg_balance = 0
    if monthly_balances:
        month_avgs = [sum(balances) / len(balances) for balances in monthly_balances.values()]
        avg_balance = sum(month_avgs) / len(month_avgs)

    return avg_balance


def calculate_fd_maturity_bank_style(principal: float, rate: float,
                                     start_date: date, maturity_date: date,
                                     compounding: str,
                                     tenure_years: int = 0,
                                     tenure_months: int = 0,
                                     tenure_days: int = 0,
                                     rounding_adjustment: float = 0) -> float:
    """
    Bank-style maturity using the U/V/W/X/Y/Z method from the spec:
    U = completed quarters
    V = broken-period days (from calendar date U quarters after start)
    W = compounded part: (1 + rate/400)^U * principal - principal
    X = simple interest on broken period: ((1 + rate/400)^U * principal) * (V/365 * rate/100)
    Y = W + X
    Z = ROUND(Y, 0)
    """
    if principal <= 0 or rate <= 0 or maturity_date < start_date:
        return round(principal, 2)

    # Calculate number of days
    total_days = (maturity_date - start_date).days

    # U = completed quarters (INT((E - C) / 30.433 / 3))
    # Using 30.433 days/month average
    u = int(total_days / 30.433 / 3)

    # V = broken-period days
    # Advance start date by 3*U months (calendar date arithmetic)
    quarter_date = start_date + relativedelta(months=3 * u)
    v = (maturity_date - quarter_date).days

    # W = (1 + rate/400)^U * principal - principal
    rate_factor = 1 + rate / 400
    principal_after_compounding = principal * (rate_factor ** u)
    w = principal_after_compounding - principal

    # X = principal_after_compounding * (V/365 * rate/100)
    x = principal_after_compounding * (v / 365 * rate / 100)

    # Y = W + X
    y = w + x

    # Z = ROUND(Y, 0)
    return round(principal + y, 2)


def calculate_fd_maturity_flexible(principal: float, rate: float,
                                   start_date: date, maturity_date: date,
                                   compounding: str,
                                   tenure_years: int = 0,
                                   tenure_months: int = 0,
                                   tenure_days: int = 0,
                                   rounding_adjustment: float = 4) -> float:
    """Formula-style maturity for flexible tenure input.
    H = ROUNDUP(F * (1 + G/100/4)^(4*(E - C)/365), 0) - F - rounding_adjustment
    """
    if principal <= 0 or rate <= 0 or maturity_date <= start_date:
        return round(principal, 2)

    # Keep backward compatibility for month-only tenure entry.
    if tenure_days == 0 and tenure_years == 0 and tenure_months > 0:
        return calculate_fd_maturity(principal, rate, tenure_months, compounding)

    r = rate / 100
    if compounding == "Monthly":
        n = 12
    elif compounding == "Quarterly":
        n = 4
    else:
        n = 1

    total_days = (maturity_date - start_date).days
    t = total_days / 365
    maturity = principal * ((1 + r / n) ** (n * t))

    # Apply the rounding adjustment (default 4, per spec's column H)
    interest = round(maturity - principal, 0) - rounding_adjustment
    return round(principal + interest, 2)


def _effective_maturity_amount(fd: dict) -> float:
    selected = fd.get("maturity_amount")
    if selected is not None:
        return float(selected)

    method = fd.get("maturity_calc_method") or "Formula"
    if method == "BankStyle" and fd.get("maturity_amount_bank") is not None:
        return float(fd["maturity_amount_bank"])
    if method == "Formula" and fd.get("maturity_amount_formula") is not None:
        return float(fd["maturity_amount_formula"])

    fallback = fd.get("maturity_amount_formula")
    if fallback is None:
        fallback = fd.get("maturity_amount_bank")
    if fallback is None:
        fallback = fd.get("principal_amount", 0)
    return float(fallback)


def fd_interest_accrued_to(fd: dict, as_of: date) -> float:
    """
    Calculate interest accrued to a specific date using the spec's three-branch rule.

    Let M = plain day count from start_date to as_of (boundary - start, not inclusive).
        M <= 183           ->  INT(F * G/100 * M / 365)
        183 < M <= 365     ->  INT(F * (1 + G/400)^4 - F)
        M > 365            ->  INT(F * (1 + G/400)^(4*M/365) - F)

    Day count is a plain date difference (no +1). For start 2026-02-24 and target 2026-03-31,
    the count is 35 days, not 36.
    """
    fd_start = date.fromisoformat(fd["start_date"])
    if as_of < fd_start:
        return 0.0

    principal = float(fd["principal_amount"])
    rate = float(fd.get("interest_rate") or 0)

    if principal <= 0 or rate <= 0:
        return 0.0

    # Plain day count: from start_date to as_of
    m = (as_of - fd_start).days
    g = rate  # G is the rate as a whole number (8 means 8%)
    f = principal

    if m <= 183:
        # Simple interest for first 183 days
        accrued = int(f * g / 100 * m / 365)
    elif m <= 365:
        # Quarterly compounding for full year
        accrued = int(f * ((1 + g / 400) ** 4) - f)
    else:
        # Quarterly compounding for M days
        accrued = int(f * ((1 + g / 400) ** (4 * m / 365)) - f)

    return float(accrued)


def fd_interest_for_fy(fd: dict, financial_year: str) -> float:
    """
    Calculate FD interest earned in a specific FY using the accrual method.

    The FINAL financial year takes the remainder: total_interest - sum(earlier years),
    so the parts always add back to the maturity total exactly.
    """
    fd_start = date.fromisoformat(fd["start_date"])
    fd_end = date.fromisoformat(fd["maturity_date"])
    fy_start, fy_end = fy_date_range(financial_year)

    # Clamp the FD's date range to the FY's date range
    accrual_start = max(fd_start, fy_start)
    accrual_end = min(fd_end, fy_end)

    if accrual_start > accrual_end:
        return 0.0

    # Check if this is the final FY (FD matures during or before this FY)
    is_final_fy = accrual_end >= fd_end

    if not is_final_fy:
        # Not final FY: use direct accrual calculation
        interest_at_end = fd_interest_accrued_to(fd, accrual_end)
        interest_at_start = 0.0
        if accrual_start > fd_start:
            interest_at_start = fd_interest_accrued_to(fd, accrual_start - timedelta(days=1))
        return round(interest_at_end - interest_at_start, 2)
    else:
        # Final FY: take the remainder to ensure exact re-addition
        total_interest = _effective_maturity_amount(fd) - float(fd["principal_amount"])

        # Sum all previous FYs' interest
        previous_total = 0.0
        fd_fy = _fy_of_date(fd_start)
        fd_fy_year = int(fd_fy.split("-")[0])
        current_fy_year = int(financial_year.split("-")[0])

        # Iterate through all FYs from FD start to the one before the current FY
        for offset in range(current_fy_year - fd_fy_year):
            check_fy_year = fd_fy_year + offset
            check_fy = f"{check_fy_year}-{str(check_fy_year + 1)[2:]}"
            check_fy_start, check_fy_end = fy_date_range(check_fy)

            check_start = max(fd_start, check_fy_start)
            check_end = min(fd_end, check_fy_end)

            if check_start <= check_end:
                interest_at_end = fd_interest_accrued_to(fd, check_end)
                interest_at_start = 0.0
                if check_start > fd_start:
                    interest_at_start = fd_interest_accrued_to(fd, check_start - timedelta(days=1))
                previous_total += interest_at_end - interest_at_start

        return round(total_interest - previous_total, 2)


def _fy_quarters(financial_year: str) -> list[tuple[str, date, date]]:
    start_year = int(financial_year.split("-")[0])
    return [
        ("Q1", date(start_year, 4, 1), date(start_year, 6, 30)),
        ("Q2", date(start_year, 7, 1), date(start_year, 9, 30)),
        ("Q3", date(start_year, 10, 1), date(start_year, 12, 31)),
        ("Q4", date(start_year + 1, 1, 1), date(start_year + 1, 3, 31)),
    ]


def _fy_of_date(d: date) -> str:
    if d.month >= 4:
        return f"{d.year}-{str(d.year + 1)[2:]}"
    return f"{d.year - 1}-{str(d.year)[2:]}"


def _quarter_of_date(d: date) -> str:
    if d.month in (4, 5, 6):
        return "Q1"
    if d.month in (7, 8, 9):
        return "Q2"
    if d.month in (10, 11, 12):
        return "Q3"
    return "Q4"


def _simulate_compounding_events(principal: float, rate: float,
                                 start_date: date, maturity_date: date,
                                 compounding: str) -> list[dict]:
    """Generate interest credit events at compounding period ends."""
    if principal <= 0 or rate <= 0 or maturity_date < start_date:
        return []

    period_months = _period_months_for_compounding(compounding)
    current_principal = principal
    annual_rate = rate / 100
    events = []
    period_start = start_date

    while period_start <= maturity_date:
        period_end = min(
            period_start + relativedelta(months=period_months) - timedelta(days=1),
            maturity_date,
        )

        period_interest = _accrue_period_interest(current_principal, annual_rate, period_start, period_end)

        events.append({
            "period_start": period_start,
            "period_end": period_end,
            "event_date": period_end,
            "days": (period_end - period_start).days + 1,
            "interest": period_interest,
        })

        if period_end < maturity_date:
            current_principal += period_interest

        period_start = period_end + timedelta(days=1)

    return events


def _scale_events_to_interest(events: list[dict], total_interest: float) -> list[dict]:
    if not events:
        return []
    raw_total = sum(e["interest"] for e in events)
    if raw_total <= 0:
        return []

    factor = total_interest / raw_total
    scaled = []
    running = 0.0
    for i, e in enumerate(events):
        if i == len(events) - 1:
            amt = round(total_interest - running, 2)
        else:
            amt = round(e["interest"] * factor, 2)
            running += amt
        scaled.append({**e, "interest": amt})
    return scaled


def calculate_fd_quarterly_credit_breakdown(principal: float, rate: float,
                                            start_date: date, maturity_date: date,
                                            compounding: str,
                                            total_interest: float) -> list[dict]:
    """Quarter-wise interest based on credit events (AIS-comparable)."""
    events = _simulate_compounding_events(principal, rate, start_date, maturity_date, compounding)
    if not events:
        if total_interest > 0:
            d = maturity_date
            fy = _fy_of_date(d)
            return [{
                "fy": fy,
                "ay": get_assessment_year(fy),
                "quarter": _quarter_of_date(d),
                "period_start": start_date.isoformat(),
                "period_end": maturity_date.isoformat(),
                "interest": round(total_interest, 2),
                "days": (maturity_date - start_date).days + 1,
            }]
        return []

    events = _scale_events_to_interest(events, total_interest)
    agg = {}
    for e in events:
        d = e["event_date"]
        fy = _fy_of_date(d)
        q = _quarter_of_date(d)
        key = (fy, q)
        if key not in agg:
            agg[key] = {
                "fy": fy,
                "ay": get_assessment_year(fy),
                "quarter": q,
                "period_start": e["period_start"],
                "period_end": e["period_end"],
                "interest": 0.0,
                "days": 0,
            }
        agg[key]["period_start"] = min(agg[key]["period_start"], e["period_start"])
        agg[key]["period_end"] = max(agg[key]["period_end"], e["period_end"])
        agg[key]["interest"] += e["interest"]
        agg[key]["days"] += e["days"]

    rows = []
    for _, v in sorted(agg.items(), key=lambda kv: (kv[1]["fy"], kv[1]["quarter"])):
        rows.append({
            "fy": v["fy"],
            "ay": v["ay"],
            "quarter": v["quarter"],
            "period_start": v["period_start"].isoformat(),
            "period_end": v["period_end"].isoformat(),
            "interest": round(v["interest"], 2),
            "days": v["days"],
        })
    return rows


def allocate_fd_interest_to_fy(fd_id: int) -> None:
    """Allocate FD interest across all relevant FYs and store in DB."""
    fd = get_fd(fd_id)
    if not fd:
        return
    if not fd.get("maturity_date") or fd.get("maturity_amount") is None:
        # Pending-details FDs cannot be allocated until maturity details are available.
        return

    # Rebuild FY allocations for this FD to avoid stale/duplicate records.
    delete_fd_interest_records(fd_id)
    
    fd_start = date.fromisoformat(fd["start_date"])
    fd_end = date.fromisoformat(fd["maturity_date"])
    total_interest = _effective_maturity_amount(fd) - float(fd["principal_amount"])

    rows = calculate_fd_quarterly_credit_breakdown(
        principal=float(fd["principal_amount"]),
        rate=float(fd.get("interest_rate") or 0),
        start_date=fd_start,
        maturity_date=fd_end,
        compounding=fd.get("compounding_type") or "Quarterly",
        total_interest=total_interest,
    )

    for row in rows:
        if row["interest"] <= 0:
            continue
        upsert_fd_interest(
            fd_id,
            row["fy"],
            row["interest"],
            row["ay"],
            quarter=row["quarter"],
            period_start=row["period_start"],
            period_end=row["period_end"],
        )


def calculate_savings_interest_for_fy(account_id: int, financial_year: str,
                                      interest_rate: float) -> float:
    """Estimate savings interest based on average monthly balance."""
    fy_start, fy_end = fy_date_range(financial_year)

    transactions = get_transactions_by_account(
        account_id,
        start_date=fy_start.isoformat(),
        end_date=fy_end.isoformat()
    )

    if not transactions:
        return 0.0

    avg_balance = _average_monthly_balance(transactions)

    # Simple interest calculation
    interest = (avg_balance * interest_rate * 1) / 100
    return round(interest, 2)


def allocate_savings_interest_to_fy(account_id: int, financial_year: str,
                                    interest_rate: float) -> None:
    """Calculate and store savings interest for a FY."""
    fy_start, fy_end = fy_date_range(financial_year)

    transactions = get_transactions_by_account(
        account_id,
        start_date=fy_start.isoformat(),
        end_date=fy_end.isoformat()
    )

    if not transactions:
        return

    avg_balance = _average_monthly_balance(transactions)

    interest = (avg_balance * interest_rate * 1) / 100

    upsert_savings_interest(
        account_id, financial_year, avg_balance, interest_rate, round(interest, 2)
    )


_TDS_QUARTERS = ["Q1", "Q2", "Q3", "Q4"]


def fd_tds_threshold_status(person_id: int, financial_year: str,
                            threshold: float = FD_TDS_THRESHOLD) -> dict:
    """
    Per-bank check of whether a person's FD interest crosses the TDS threshold
    in a financial year, and in which quarter the running total crosses it.

    Banks that credit FD interest quarterly deduct TDS in the quarter their
    cumulative interest for the year first crosses the limit — so the check is
    per-bank (each bank/deductor applies the limit to its own interest) and
    quarter-cumulative. Interest with no quarter label is folded in before Q1
    so the crossing is flagged at the earliest (safe) point.

    Returns:
        {
          "threshold": float,
          "any_exceeds": bool,
          "banks": [
            {"bank_name", "total_interest", "exceeds", "crossing_quarter",
             "breakdown": [{"quarter", "interest", "cumulative"}, ...]},
            ...
          ]
        }
    """
    records = get_fd_interest_by_fy(financial_year, person_id=person_id)

    by_bank: dict[str, dict] = {}
    for r in records:
        bank = r.get("bank_name") or "Unknown Bank"
        entry = by_bank.setdefault(
            bank, {"total": 0.0, "quarters": {q: 0.0 for q in _TDS_QUARTERS}, "misc": 0.0})
        amount = float(r.get("interest_earned") or 0)
        entry["total"] += amount
        quarter = r.get("quarter")
        if quarter in entry["quarters"]:
            entry["quarters"][quarter] += amount
        else:
            entry["misc"] += amount

    banks = []
    for bank, e in by_bank.items():
        cumulative = e["misc"]
        crossing_quarter = None
        breakdown = []
        for q in _TDS_QUARTERS:
            cumulative += e["quarters"][q]
            breakdown.append({
                "quarter": q,
                "interest": round(e["quarters"][q], 2),
                "cumulative": round(cumulative, 2),
            })
            if crossing_quarter is None and cumulative >= threshold:
                crossing_quarter = q
        banks.append({
            "bank_name": bank,
            "total_interest": round(e["total"], 2),
            "exceeds": e["total"] >= threshold,
            "crossing_quarter": crossing_quarter,
            "breakdown": breakdown,
        })

    banks.sort(key=lambda b: b["total_interest"], reverse=True)
    return {
        "threshold": threshold,
        "any_exceeds": any(b["exceeds"] for b in banks),
        "banks": banks,
    }
