"""
engines/interest_engine.py — FD compounding, savings interest, FY allocation
"""

from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from config import get_assessment_year, fy_date_range
from models.fixed_deposit import get_fd
from models.fd_interest_record import upsert_fd_interest
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
    total_interest = fd["maturity_amount"] - fd["principal_amount"]
    
    fy_interest = (total_interest * days_in_fy) / total_days
    return round(fy_interest, 2)


def allocate_fd_interest_to_fy(fd_id: int) -> None:
    """Allocate FD interest across all relevant FYs and store in DB."""
    fd = get_fd(fd_id)
    if not fd:
        return
    
    fd_start = date.fromisoformat(fd["start_date"])
    fd_end = date.fromisoformat(fd["maturity_date"])
    
    # Generate all FYs that overlap with FD tenure
    current_date = fd_start
    while current_date <= fd_end:
        if current_date.month >= 4:
            fy = f"{current_date.year}-{str(current_date.year + 1)[2:]}"
        else:
            fy = f"{current_date.year - 1}-{str(current_date.year)[2:]}"
        
        interest = calculate_fd_interest_for_fy(fd_id, fy)
        if interest > 0:
            ay = get_assessment_year(fy)
            upsert_fd_interest(fd_id, fy, interest, ay)
        
        # Move to next FY
        current_date = date(current_date.year + 1, 4, 1) if current_date.month >= 4 else date(current_date.year, 4, 1)


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
    
    # Calculate average monthly balance
    monthly_balances = {}
    for txn in transactions:
        txn_date = date.fromisoformat(txn["transaction_date"])
        month_key = (txn_date.year, txn_date.month)
        if month_key not in monthly_balances:
            monthly_balances[month_key] = []
        monthly_balances[month_key].append(txn["balance_after"])
    
    # Average balance per month
    avg_balance = 0
    if monthly_balances:
        month_avgs = [sum(balances) / len(balances) for balances in monthly_balances.values()]
        avg_balance = sum(month_avgs) / len(month_avgs)
    
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
    
    # Calculate average monthly balance
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
    
    interest = (avg_balance * interest_rate * 1) / 100
    
    upsert_savings_interest(
        account_id, financial_year, avg_balance, interest_rate, round(interest, 2)
    )


def project_fd_interest_next_fy(fd_id: int, current_fy: str) -> float:
    """Project FD interest for next FY."""
    next_fy_year = int(current_fy.split("-")[0]) + 1
    next_fy = f"{next_fy_year}-{str(next_fy_year + 1)[2:]}"
    return calculate_fd_interest_for_fy(fd_id, next_fy)
