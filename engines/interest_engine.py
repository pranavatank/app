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


def calculate_fd_maturity_flexible(principal: float, rate: float,
                                   start_date: date, maturity_date: date,
                                   compounding: str,
                                   tenure_years: int = 0,
                                   tenure_months: int = 0,
                                   tenure_days: int = 0) -> float:
    """Formula-style maturity for flexible tenure input."""
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
                                     tenure_days: int = 0) -> float:
    """
    Bank-style maturity: actual-day interest with leap-year denominator,
    compounding at each completed compounding period.
    """
    if principal <= 0 or rate <= 0 or maturity_date < start_date:
        return round(principal, 2)

    # For pure day-tenure FDs, many bank sheets align more closely with
    # formula-based fractional tenure than period-posting simulation.
    if tenure_days > 0 and tenure_years == 0 and tenure_months == 0:
        return calculate_fd_maturity_flexible(
            principal,
            rate,
            start_date,
            maturity_date,
            compounding,
            tenure_years,
            tenure_months,
            tenure_days,
        )

    period_months = _period_months_for_compounding(compounding)
    current_principal = principal
    total_interest = 0.0
    period_start = start_date
    annual_rate = rate / 100

    while period_start <= maturity_date:
        period_end = min(
            period_start + relativedelta(months=period_months) - timedelta(days=1),
            maturity_date,
        )

        period_interest = _accrue_period_interest(current_principal, annual_rate, period_start, period_end)
        total_interest += period_interest

        # Compound only when the period is fully completed before maturity.
        if period_end < maturity_date:
            current_principal += period_interest

        period_start = period_end + timedelta(days=1)

    return round(principal + total_interest, 2)


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


def calculate_fd_interest_for_fy(fd_id: int, financial_year: str) -> float:
    """Calculate FD interest earned in a specific FY."""
    fd = get_fd(fd_id)
    if not fd:
        return 0.0
    
    fy_start, fy_end = fy_date_range(financial_year)
    fd_start = date.fromisoformat(fd["start_date"])
    fd_end = date.fromisoformat(fd["maturity_date"])
    
    # Overlap period
    overlap_start = max(fd_start, fy_start)
    overlap_end = min(fd_end, fy_end)
    
    if overlap_start > overlap_end:
        return 0.0
    
    # Calculate interest for overlap period
    days_in_fy = (overlap_end - overlap_start).days + 1
    total_days = (fd_end - fd_start).days + 1
    total_interest = _effective_maturity_amount(fd) - float(fd["principal_amount"])
    
    fy_interest = (total_interest * days_in_fy) / total_days
    return round(fy_interest, 2)


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


def calculate_fd_interest_quarterly_for_fy(fd_id: int, financial_year: str) -> list[dict]:
    """Allocate selected FD interest amount into FY quarters by overlap days."""
    fd = get_fd(fd_id)
    if not fd:
        return []

    fd_start = date.fromisoformat(fd["start_date"])
    fd_end = date.fromisoformat(fd["maturity_date"])
    total_days = (fd_end - fd_start).days + 1
    if total_days <= 0:
        return []

    total_interest = _effective_maturity_amount(fd) - float(fd["principal_amount"])
    rows = []
    for quarter, q_start, q_end in _fy_quarters(financial_year):
        overlap_start = max(fd_start, q_start)
        overlap_end = min(fd_end, q_end)
        if overlap_start > overlap_end:
            continue
        days = (overlap_end - overlap_start).days + 1
        interest = round((total_interest * days) / total_days, 2)
        rows.append({
            "quarter": quarter,
            "period_start": overlap_start.isoformat(),
            "period_end": overlap_end.isoformat(),
            "days": days,
            "interest": interest,
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


def project_fd_interest_next_fy(fd_id: int, current_fy: str) -> float:
    """Project FD interest for next FY."""
    next_fy_year = int(current_fy.split("-")[0]) + 1
    next_fy = f"{next_fy_year}-{str(next_fy_year + 1)[2:]}"
    return calculate_fd_interest_for_fy(fd_id, next_fy)


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
