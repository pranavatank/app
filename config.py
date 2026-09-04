"""
config.py — App-wide constants and path configuration
"""

import os
from datetime import date

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DATA_DIR    = os.path.join(BASE_DIR, "data")
BACKUP_DIR  = os.path.join(BASE_DIR, "backups")
DB_PATH     = os.path.join(DATA_DIR, "financial.db")

# ── App Meta ─────────────────────────────────────────────────────────────────
APP_NAME    = "Personal Financial Manager"
APP_VERSION = "1.0.0"

# ── Security ──────────────────────────────────────────────────────────────────
PBKDF2_ITERATIONS = 100_000
SALT_SIZE         = 32    # bytes
AES_KEY_SIZE      = 32    # bytes (256-bit)

# ── FD TDS (tax deducted at source on Fixed Deposit interest) ─────────────────
# Banks deduct TDS once a depositor's FD interest crosses the threshold in a
# financial year. To avoid deduction, file Form 15G (non-senior) or Form 15H
# (senior citizen, 60+) when total income is below the taxable limit.
FD_TDS_THRESHOLD         = 50_000
FD_TDS_FORM_NAME         = "Form 15G"
FD_TDS_FORM_NAME_SENIOR  = "Form 15H"
FD_TDS_THRESHOLD_SENIOR  = 100_000

# ── Financial Year Helpers ────────────────────────────────────────────────────
def get_current_financial_year() -> str:
    """Returns e.g. '2024-25' based on today's date."""
    today = date.today()
    if today.month >= 4:
        return f"{today.year}-{str(today.year + 1)[2:]}"
    else:
        return f"{today.year - 1}-{str(today.year)[2:]}"

def get_assessment_year(financial_year: str) -> str:
    """Returns AY string for a given FY. e.g. '2024-25' → '2025-26'."""
    start = int(financial_year.split("-")[0])
    ay_start = start + 1
    return f"{ay_start}-{str(ay_start + 1)[2:]}"

def fy_date_range(financial_year: str):
    """Returns (start_date, end_date) for a financial year string."""
    start_year = int(financial_year.split("-")[0])
    start = date(start_year, 4, 1)
    end   = date(start_year + 1, 3, 31)
    return start, end

def get_all_financial_years(since_year: int = 2020) -> list:
    """Returns list of FY strings from since_year to current FY."""
    current = get_current_financial_year()
    current_start = int(current.split("-")[0])
    return [
        f"{y}-{str(y + 1)[2:]}"
        for y in range(since_year, current_start + 1)
    ]

# ── Transaction Categories ────────────────────────────────────────────────────
INCOME_CATEGORIES = [
    "Salary", "Pension", "FD Interest", "Savings Interest",
    "FD Maturity", "Rental Income", "Business Income", "Dividend", "Other Income",
]

EXPENSE_CATEGORIES = [
    "Food & Dining", "Groceries", "Travel", "Fuel",
    "EMI / Loan", "Utilities", "Medical", "Education",
    "Shopping", "Entertainment", "Insurance", "Investment",
    "Fixed Deposit", "FD Principal",
    "Tax Payment", "Other Expense",
]

TRANSACTION_MODES = ["Bank Transfer", "Cash", "UPI", "Credit Card", "Debit Card", "Cheque"]

ACCOUNT_TYPES = ["Savings", "Current", "Salary", "FD-linked"]

COMPOUNDING_TYPES = ["Monthly", "Quarterly", "Annual"]
