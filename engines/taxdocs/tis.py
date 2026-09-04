"""
engines/taxdocs/tis.py — Parse TIS PDF using pdfplumber table extraction
"""

import re
from typing import Dict, Any


def _parse_inr_amount(value: str) -> float:
    """Parse Indian-formatted amount, stripping commas (which are used for thousands grouping)."""
    s = (value or "").strip()
    s = s.replace("₹", "").replace(",", "")
    if not s:
        return 0.0
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", s):
        return 0.0
    try:
        return float(s)
    except Exception:
        return 0.0


def parse_tis_pdf(pdf_path: str, password: str = None) -> Dict[str, Any]:
    """
    Parse TIS PDF using pdfplumber.

    Reads the summary table from page 1 only, extracting values from the
    ACCEPTED BY TAXPAYER column.

    Returns a dict with keys:
    - dividend
    - savings_interest
    - fd_interest
    - business_receipts
    - non_income (dict with purchase_of_time_deposits)
    """
    import pdfplumber

    with pdfplumber.open(pdf_path, password=password) as pdf:
        # Page 1 only (index 0)
        page = pdf.pages[0]
        table = page.extract_table()

    result = {
        'dividend': 0.0,
        'savings_interest': 0.0,
        'fd_interest': 0.0,
        'business_receipts': 0.0,
        'non_income': {
            'purchase_of_time_deposits': 0.0
        }
    }

    if not table or len(table) < 2:
        return result

    # Find the ACCEPTED BY TAXPAYER column index by looking at the header
    header = table[0]
    accepted_col_idx = None
    for idx, cell in enumerate(header):
        cell_lower = (cell or "").lower()
        if "accepted" in cell_lower:
            accepted_col_idx = idx
            break

    # If not found, assume it's the last column (common case)
    if accepted_col_idx is None:
        accepted_col_idx = len(header) - 1

    # Parse data rows (skip header, which is row 0)
    for row_idx in range(1, len(table)):
        row = table[row_idx]
        if not row or len(row) <= accepted_col_idx:
            continue

        # Get category and amount
        category = None
        amount_str = None

        # Category is typically in column 1 (index 1)
        if len(row) > 1:
            category = (row[1] or "").strip()

        # Amount is in the ACCEPTED BY TAXPAYER column
        if len(row) > accepted_col_idx:
            amount_str = (row[accepted_col_idx] or "").strip()

        if not category or not amount_str:
            continue

        amount = _parse_inr_amount(amount_str)
        category_lower = category.lower()

        # Map categories to fields
        if "dividend" in category_lower:
            result['dividend'] += amount
        elif "savings bank" in category_lower:
            result['savings_interest'] += amount
        elif "interest from deposit" in category_lower:
            result['fd_interest'] += amount
        elif "business receipt" in category_lower:
            result['business_receipts'] += amount
        elif "purchase of time deposit" in category_lower:
            result['non_income']['purchase_of_time_deposits'] += amount

    return result
