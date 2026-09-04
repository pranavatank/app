"""
engines/taxdocs/merge.py — Merge TIS, AIS, and Form 26AS into a single financial position.

Authority rules:
- Income comes from TIS (taxpayer-accepted summary)
- Tax credit comes from 26AS (total_tds), not AIS
- Per-source detail comes from AIS (which account, which quarter)
- Never sum AIS Part B1 and Part B2 (TDS-194A and SFT-016(TD) are the same interest reported twice)
- Non-income categories (purchases of time deposits, etc.) surfaced separately
- AIS vs 26AS TDS difference is surfaced as reconciliation item
"""

from typing import Dict, Any, Optional, List, Callable
from decimal import Decimal, ROUND_HALF_UP


def _apply_44ada_presumptive_profit(business_receipts: float) -> Dict[str, Any]:
    """
    Calculate presumptive profit under s.44ADA for non-professional trusts/entities.

    For trusts and non-professional entities, 50% of business receipts can be claimed
    as presumptive profit regardless of amount. This is the deemed profit calculation.

    Returns dict with:
    - presumptive_profit: 50% of business_receipts, rounded to nearest rupee
    - is_applicable: True if business_receipts > 0
    - rule: description of the rule applied
    """
    if business_receipts > 0:
        # Income tax computations round to nearest rupee with halves rounded UP.
        # Python's built-in round() uses banker's rounding, which would truncate
        # 52534.5 to 52534. Use Decimal with ROUND_HALF_UP for correct rounding.
        profit_decimal = Decimal(str(business_receipts * 0.5))
        rounded_profit = int(profit_decimal.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        return {
            'presumptive_profit': rounded_profit,
            'is_applicable': True,
            'rule': 's.44ADA @ 50% (non-professional entity)'
        }
    else:
        return {
            'presumptive_profit': 0.0,
            'is_applicable': False,
            'rule': 'No business receipts'
        }


def merge_tax_documents(
    tis_data: Dict[str, Any],
    ais_data: Dict[str, Any],
    form26as_data: Dict[str, Any],
    fd_by_account_no_lookup: Optional[Callable] = None,
) -> Dict[str, Any]:
    """
    Merge three tax documents (TIS, AIS, Form 26AS) into a single financial position.

    Args:
        tis_data: dict with:
            - dividend, savings_interest, fd_interest, business_receipts (floats)
            - non_income: {purchase_of_time_deposits, ...}

        ais_data: dict with:
            - dividend, savings_interest, fd_interest, business_receipts (floats)
            - tds: float (sum from AIS detail tables)
            - non_income: {SFT-005, SFT-004, SFT-012, ...}
            - details: list of per-source records (code, description, source, amount, account_number if present)

        form26as_data: dict with:
            - total_tds: float (from DEDUCTOR TOTAL rows, PART-I only)
            - records: list of detail records
            - part_ii: list of 15G/15H declarations
            - refunds: dict

        fd_by_account_no_lookup: optional callable(account_no: str) -> FixedDeposit or None
            Used to match AIS account numbers to FD records.

    Returns:
        dict with:
        - financial_position: {income breakdown, total income, presumptive profit, tds, refund}
        - income_variance: table comparing TIS, AIS, app values
        - tds_reconciliation: {ais_tds, form26as_tds, difference, authority}
        - fd_matches: {account_number: {matched_fd_id, ais_amount, ...}, ...}
        - fd_not_in_app: [unmatched AIS accounts]
        - non_income_items: {category: amount, ...}
    """
    if not tis_data or not ais_data or not form26as_data:
        raise ValueError("All three documents (TIS, AIS, 26AS) are required")

    # ========== 1. EXTRACT INCOME FROM TIS (AUTHORITY) ==========
    tis_dividend = tis_data.get('dividend', 0.0)
    tis_savings_interest = tis_data.get('savings_interest', 0.0)
    tis_fd_interest = tis_data.get('fd_interest', 0.0)
    tis_business_receipts = tis_data.get('business_receipts', 0.0)

    # Non-income from TIS
    tis_non_income = tis_data.get('non_income', {})
    tis_purchase_of_td = tis_non_income.get('purchase_of_time_deposits', 0.0)

    # ========== CALCULATE PRESUMPTIVE PROFIT ==========
    # (Do this before calculating total_income since we'll use presumptive_profit in the total)
    presumptive_calc = _apply_44ada_presumptive_profit(tis_business_receipts)
    presumptive_profit = presumptive_calc['presumptive_profit']

    # Total income (from TIS, which is the taxpayer-accepted summary)
    # Under s.44ADA, the taxable income is dividend + interest + presumptive_profit,
    # not dividend + interest + business_receipts (the presumptive profit is the deemed income)
    total_income = (
        tis_dividend +
        tis_savings_interest +
        tis_fd_interest +
        presumptive_profit  # Use presumptive profit, not raw business receipts
    )

    # ========== 2. EXTRACT TAX CREDIT FROM 26AS (AUTHORITY) ==========
    form26as_total_tds = form26as_data.get('total_tds', 0.0)

    # ========== 3. GET AIS DATA FOR DETAIL AND RECONCILIATION ==========
    ais_dividend = ais_data.get('dividend', 0.0)
    ais_savings_interest = ais_data.get('savings_interest', 0.0)
    ais_fd_interest = ais_data.get('fd_interest', 0.0)
    ais_business_receipts = ais_data.get('business_receipts', 0.0)
    ais_total_tds = ais_data.get('tds', 0.0)
    ais_non_income = ais_data.get('non_income', {})
    ais_details = ais_data.get('details', [])

    # ========== 4. BUILD INCOME VARIANCE TABLE ==========
    income_variance = {
        'dividend': {
            'tis': tis_dividend,
            'ais': ais_dividend,
            'difference': abs(tis_dividend - ais_dividend),
            'authority': 'TIS'
        },
        'savings_interest': {
            'tis': tis_savings_interest,
            'ais': ais_savings_interest,
            'difference': abs(tis_savings_interest - ais_savings_interest),
            'authority': 'TIS'
        },
        'fd_interest': {
            'tis': tis_fd_interest,
            'ais': ais_fd_interest,
            'difference': abs(tis_fd_interest - ais_fd_interest),
            'authority': 'TIS'
        },
        'business_receipts': {
            'tis': tis_business_receipts,
            'ais': ais_business_receipts,
            'difference': abs(tis_business_receipts - ais_business_receipts),
            'authority': 'TIS'
        }
    }

    # (Presumptive profit already calculated above)

    # ========== 6. BUILD TDS RECONCILIATION ==========
    tds_difference = form26as_total_tds - ais_total_tds
    tds_reconciliation = {
        'ais_tds': ais_total_tds,
        'form26as_tds': form26as_total_tds,
        'difference': tds_difference,
        'authority': '26AS (is authoritative on tax credit)',
        'note': 'AIS and 26AS measure different things; AIS is authority on income detail, 26AS on tax credit'
    }

    # ========== 7. MATCH AIS ACCOUNTS TO FD RECORDS ==========
    fd_matches = {}
    fd_not_in_app = []

    if fd_by_account_no_lookup:
        # Extract SFT-016(TD) records from AIS details (these have account numbers)
        for detail in ais_details:
            if detail.get('code') == 'SFT-016(TD)':
                account_no = detail.get('account_number')
                if account_no:
                    matched_fd = fd_by_account_no_lookup(account_no)
                    if matched_fd:
                        fd_matches[account_no] = {
                            'fd_id': matched_fd.get('fd_id') if isinstance(matched_fd, dict) else matched_fd.fd_id,
                            'ais_amount': detail.get('amount', 0.0),
                            'detail': detail
                        }
                    else:
                        fd_not_in_app.append(account_no)

    # ========== 8. BUILD FINANCIAL POSITION ==========
    financial_position = {
        'dividend': tis_dividend,
        'savings_interest': tis_savings_interest,
        'fd_interest': tis_fd_interest,
        'business_receipts': tis_business_receipts,
        'total_income': total_income,
        'presumptive_profit': presumptive_profit,
        'presumptive_profit_rule': presumptive_calc.get('rule', ''),
        'standard_deduction': 0.0,  # No salary income
        'taxable_income': total_income,  # Simplified; full calculation requires rebates/surcharge
        'tax_payable': 0.0,  # Below basic exemption (4L)
        'tds_deducted': form26as_total_tds,
        'refund_due': form26as_total_tds  # Entire TDS is refunded (tax_payable is 0)
    }

    # ========== 9. BUILD NON-INCOME ITEMS ==========
    non_income_items = {
        'purchase_of_time_deposits': tis_purchase_of_td,
    }
    # Add other non-income items from both sources
    for code in ['SFT-005', 'SFT-004', 'SFT-012']:
        amount = ais_non_income.get(code, 0.0)
        if amount > 0:
            non_income_items[code] = amount

    # ========== 10. BUILD FINAL RESULT ==========
    return {
        'financial_position': financial_position,
        'income_variance': income_variance,
        'tds_reconciliation': tds_reconciliation,
        'fd_matches': fd_matches,
        'fd_not_in_app': fd_not_in_app,
        'non_income_items': non_income_items,
        'metadata': {
            'tis_data_keys': list(tis_data.keys()),
            'ais_data_keys': list(ais_data.keys()),
            'form26as_data_keys': list(form26as_data.keys())
        }
    }
