"""
engines/taxdocs/ais.py — Parse AIS PDF using pdfplumber table extraction

IMPORTANT: TDS calculation rule needs investigation. The simple "sum Active rows only"
produces incorrect totals. The target (13,367) appears to be composed of deductor-level totals:
- Enlightvision (194J): 10,508
- Jana (194A): 2,859
This suggests either:
1. A header-level total above each detail block is authoritative
2. Different columns (TDS DEPOSITED vs DEDUCTED) should be summed
3. Some detail blocks are missing due to page break spanning
4. A mix of the above

Investigation and rule will be captured in parse_ais_pdf() docstring after verification.
"""

import re
from typing import Dict, Any, List, Optional


def _parse_inr_amount(value: str) -> float:
    """Parse Indian-formatted amount, stripping commas."""
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


def _find_column_index(header: List[str], keyword: str) -> Optional[int]:
    """
    Find column index by matching header cells by substring.
    Returns first index where keyword is found in any cell, case-insensitive.
    """
    keyword_lower = keyword.lower()
    for idx, cell in enumerate(header):
        cell_lower = (cell or "").lower()
        if keyword_lower in cell_lower:
            return idx
    return None


def parse_ais_pdf(pdf_path: str, password: str = None) -> Dict[str, Any]:
    """
    Parse AIS PDF using pdfplumber, extracting all 6 pages.

    Returns a dict with keys:
    - dividend
    - savings_interest
    - fd_interest
    - business_receipts
    - tds (sum of TDS DEDUCTED from detail tables, filtered by rule)
    - non_income (dict with SFT-005, SFT-004, SFT-012 amounts)
    - details (list of per-row records for drilling down)

    TDS rule: UNDER INVESTIGATION
    ==============================
    Known facts:
    - Target: 13,367
    - Composition: Enlightvision (194J) 10,508 + Jana (194A) 2,859
    - Naive approach (sum Active rows): 6,246 (too low)
    - Alternative (sum all rows): 12,073 (close but wrong)

    This suggests:
    - Deductor-level header totals may exist above detail blocks (authoritative)
    - OR TDS DEPOSITED column should be used instead of TDS DEDUCTED
    - OR detail blocks span page breaks and some are missed
    - OR a combination of the above

    Will investigate during PDF processing and update this docstring with findings.
    """
    import pdfplumber

    with pdfplumber.open(pdf_path, password=password) as pdf:
        all_tables = []
        for page_num in range(len(pdf.pages)):
            page = pdf.pages[page_num]
            tables = page.extract_tables()
            for table in (tables or []):
                all_tables.append({
                    'page': page_num,
                    'table': table
                })

    result = {
        'dividend': 0.0,
        'savings_interest': 0.0,
        'fd_interest': 0.0,
        'business_receipts': 0.0,
        'tds': 0.0,
        'non_income': {
            'SFT-005': 0.0,  # Purchase of time deposits
            'SFT-004': 0.0,
            'SFT-012': 0.0,
        },
        'details': [],
        'tds_investigation': {
            'active_rows_sum': 0.0,
            'inactive_rows_sum': 0.0,
            'all_rows_sum': 0.0,
            'deductor_totals': {},
            'notes': []
        }
    }

    # Track which codes are income vs non-income
    non_income_codes = {'SFT-005', 'SFT-004', 'SFT-012'}
    # Track which codes are duplicates (TDS-194A is duplicate of SFT-016(TD))
    duplicate_tds_codes = {'TDS-194A'}

    current_section = None
    current_code = None
    code_amounts = {}  # For aggregating by code across all pages
    deductor_tds_totals = {}  # For tracking TDS by deductor name

    # Parse summary tables first
    for table_info in all_tables:
        table = table_info['table']
        if not table or len(table) < 2:
            continue

        header = table[0]
        header_text = ' '.join([str(h or '') for h in header]).lower()

        # Detect if this is a summary table (has COUNT and AMOUNT columns)
        is_summary = 'count' in header_text and 'amount' in header_text

        if is_summary:
            # Summary table: SR. NO. | CODE | DESCRIPTION | SOURCE | COUNT | AMOUNT
            sr_idx = _find_column_index(header, 'SR')
            code_idx = _find_column_index(header, 'CODE')
            desc_idx = _find_column_index(header, 'DESCRIPTION')
            source_idx = _find_column_index(header, 'SOURCE')
            amount_idx = _find_column_index(header, 'AMOUNT')

            # Default to reasonable positions if not found
            if code_idx is None:
                code_idx = 1
            if amount_idx is None:
                amount_idx = len(header) - 1

            for row_idx in range(1, len(table)):
                row = table[row_idx]
                if not row or len(row) < 2:
                    continue

                code = None
                desc = None
                source = None
                amount_str = None

                if code_idx is not None and len(row) > code_idx:
                    code = (row[code_idx] or "").strip()
                if desc_idx is not None and len(row) > desc_idx:
                    desc = (row[desc_idx] or "").strip()
                if source_idx is not None and len(row) > source_idx:
                    source = (row[source_idx] or "").strip()
                if len(row) > amount_idx:
                    amount_str = (row[amount_idx] or "").strip()

                if not code or not amount_str:
                    continue

                amount = _parse_inr_amount(amount_str)
                if amount == 0.0:
                    continue

                # Aggregate by code
                if code not in code_amounts:
                    code_amounts[code] = {'amount': 0.0, 'desc': desc, 'source': source}
                code_amounts[code]['amount'] += amount

                # Track detail
                result['details'].append({
                    'type': 'summary',
                    'page': table_info['page'],
                    'code': code,
                    'description': desc,
                    'source': source,
                    'amount': amount,
                    'raw_row': row
                })

    # Apply aggregated amounts to result buckets
    for code, info in code_amounts.items():
        amount = info['amount']

        if code in non_income_codes:
            result['non_income'][code] = amount
        elif code == 'SFT-015':
            result['dividend'] += amount
        elif code == 'SFT-016(SB)':
            result['savings_interest'] += amount
        elif code == 'SFT-016(TD)':
            result['fd_interest'] += amount
        elif code == 'TDS-194J':
            result['business_receipts'] += amount
        # Note: TDS-194A is NOT added (duplicate of SFT-016(TD))

    # Now parse detail tables to aggregate TDS
    for table_info in all_tables:
        table = table_info['table']
        if not table or len(table) < 2:
            continue

        header = table[0]
        header_text = ' '.join([str(h or '') for h in header]).lower()

        # Detect if this is a detail table (has QUARTER and TDS columns)
        is_detail = ('quarter' in header_text or 'date' in header_text) and \
                    ('tds' in header_text or 'deducted' in header_text)

        if is_detail:
            # Detail table: SR. NO. | QUARTER | DATE | AMOUNT PAID | TDS DEDUCTED | TDS DEPOSITED | STATUS
            tds_deducted_idx = _find_column_index(header, 'TDS DEDUCTED')
            tds_deposited_idx = _find_column_index(header, 'TDS DEPOSITED')
            status_idx = _find_column_index(header, 'STATUS')
            deductor_idx = _find_column_index(header, 'DEDUCTOR')  # Try to find deductor

            # Use TDS DEDUCTED by default, but track both
            tds_col_idx = tds_deducted_idx if tds_deducted_idx is not None else tds_deposited_idx

            active_sum = 0.0
            inactive_sum = 0.0
            all_sum = 0.0

            for row_idx in range(1, len(table)):
                row = table[row_idx]
                if not row or len(row) < 2:
                    continue

                status = None
                tds_str = None

                if status_idx is not None and len(row) > status_idx:
                    status = (row[status_idx] or "").strip()
                if tds_col_idx is not None and len(row) > tds_col_idx:
                    tds_str = (row[tds_col_idx] or "").strip()

                if not tds_str:
                    continue

                tds_amount = _parse_inr_amount(tds_str)
                if tds_amount == 0.0:
                    continue

                all_sum += tds_amount

                if status:
                    if status == 'Active':
                        active_sum += tds_amount
                    elif status == 'Inactive':
                        inactive_sum += tds_amount

            result['tds_investigation']['active_rows_sum'] += active_sum
            result['tds_investigation']['inactive_rows_sum'] += inactive_sum
            result['tds_investigation']['all_rows_sum'] += all_sum

    # Record investigation findings
    result['tds_investigation']['notes'] = [
        f"Active rows total: {result['tds_investigation']['active_rows_sum']}",
        f"Inactive rows total: {result['tds_investigation']['inactive_rows_sum']}",
        f"All rows total: {result['tds_investigation']['all_rows_sum']}",
        "Target: 13367 (Enlightvision 194J: 10508 + Jana 194A: 2859)",
        "Simple status filtering does not match target; investigating deductor-level totals..."
    ]

    # Temporary: use all rows sum as a starting point
    # This will be updated after investigation
    result['tds'] = result['tds_investigation']['all_rows_sum']

    return result
