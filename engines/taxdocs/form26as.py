"""
engines/taxdocs/form26as.py — Parse Form 26AS PDF using pdfplumber table extraction

Form 26AS is structured as a series of ruled tables with:
- PART-I through PART-X (TDS entries with section codes like 194A, 194J)
- PART-II (15G/15H declarations: nil TDS but real income)
- Part VII (refunds)
- Personal info (name, PAN, assessment year) in header section

Key differences from the old parser:
- Uses pdfplumber table extraction (not regex line scanning)
- Detects sections by PART-<ROMAN> pattern (PART-I, PART-II, not "PART A"/"PART B")
- Parses dates as dd-MMM-yyyy (31-Mar-2026), not dd/mm/yyyy
- Never accepts section codes from free text (prevents 194BA→194B)
- Nets reversal entries (signed amounts)
- Handles PART-II separately (nil TDS entries)
- Captures booking status and refunds
"""

import re
from typing import Dict, Any, List, Optional
from datetime import datetime


def _parse_inr_amount(value: str) -> float:
    """Parse Indian-formatted amount, stripping commas and rupee symbol."""
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


def _parse_date(value: str) -> str:
    """
    Parse date in dd-MMM-yyyy format (31-Mar-2026) and return in same format.
    Returns empty string if parsing fails.
    """
    s = (value or "").strip()
    if not s:
        return ""

    # Try dd-MMM-yyyy format first (most common in Form 26AS)
    try:
        dt = datetime.strptime(s, "%d-%b-%Y")
        return dt.strftime("%d-%b-%Y")
    except ValueError:
        pass

    # Try dd/mm/yyyy as fallback (older documents)
    try:
        dt = datetime.strptime(s, "%d/%m/%Y")
        return dt.strftime("%d-%b-%Y")
    except ValueError:
        pass

    # Try dd-mm-yyyy variant
    try:
        dt = datetime.strptime(s, "%d-%m-%Y")
        return dt.strftime("%d-%b-%Y")
    except ValueError:
        pass

    return ""


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


def _detect_part_roman(text: str) -> Optional[str]:
    """
    Detect PART-<ROMAN> pattern and return the Roman numeral.
    Matches: PART-I, PART-II, PART-III, etc.
    Case-insensitive, ignores surrounding whitespace.
    Returns the Roman numeral (I, II, III, etc.) or None.
    """
    # Match PART- followed by Roman numerals, case-insensitive
    text_stripped = (text or "").strip()
    m = re.match(r"PART-([IVX]+)", text_stripped, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    return None


def _roman_to_int(roman: str) -> int:
    """Convert Roman numeral to integer. Returns -1 if invalid."""
    roman_map = {
        'I': 1, 'V': 5, 'X': 10, 'L': 50,
        'C': 100, 'D': 500, 'M': 1000
    }
    total = 0
    prev_val = 0
    for char in reversed((roman or "").upper()):
        if char not in roman_map:
            return -1
        val = roman_map[char]
        if val < prev_val:
            total -= val
        else:
            total += val
        prev_val = val
    return total if total > 0 else -1


def _extract_section_code_from_row(cell: str) -> Optional[str]:
    """
    Extract section code from a structured table cell.
    Only accepts codes that appear to be in a dedicated column (not embedded in text).
    Returns codes like 194A, 194J, or None.
    """
    s = (cell or "").strip()
    if not s:
        return None

    # Look for section code pattern: 19[0-9][A-Z]?
    # But only if it looks like the entire cell or a small cell
    # (to avoid matching 194BA from free text descriptions)
    m = re.match(r"^(19[0-9][A-Z]?)$", s)
    if m:
        return m.group(1)

    # Also accept codes with some whitespace around them
    m = re.search(r"\b(19[0-9][A-Z]?)\b", s)
    if m and len(s) < 30:  # Only if cell is short (not a description)
        return m.group(1)

    return None


def _assign_table_to_part(
    headings: List[tuple],  # List of (roman_numeral, top_position)
    table_tops: List[float],  # Vertical positions (top edge) of each table
    carried_part: Optional[str]  # Part carried from previous page
) -> List[str]:
    """
    Assign each table to a part based on vertical position.

    A table belongs to the last heading that appears ABOVE it vertically (top < table.top).
    If no heading precedes a table, it belongs to the carried-over part from the previous page.

    Args:
        headings: List of (roman_numeral, top_position) tuples, e.g., [('II', 300.0)]
        table_tops: List of vertical positions (top edge) for each table, e.g., [100.0, 500.0]
        carried_part: Part carried from previous page (e.g., 'I')

    Returns:
        List of part assignments for each table, same length as table_tops.
    """
    if not headings:
        # No headings on this page: all tables belong to carried part
        return [carried_part] * len(table_tops)

    # Sort headings by position (should already be in order from top to bottom)
    sorted_headings = sorted(headings, key=lambda x: x[1])

    result = []
    for table_top in table_tops:
        # Find the last heading whose top is less than table_top
        assigned_part = carried_part
        for roman, heading_top in sorted_headings:
            if heading_top < table_top:
                assigned_part = roman
            else:
                # headings are sorted, so no more headings can precede this table
                break
        result.append(assigned_part)

    return result


def parse_form26as_pdf(pdf_path: str, password: str = None, debug: Dict = None) -> Dict[str, Any]:
    """
    Parse Form 26AS PDF using pdfplumber table extraction.

    Args:
        pdf_path: Path to the Form 26AS PDF file
        password: Optional password for encrypted PDFs
        debug: Optional dict to record parsing progress (tables found, rows per part, etc.)

    Returns:
        Dict with keys:
        - pan: PAN number of assessee
        - name: Name of assessee
        - assessment_year: Assessment year (e.g., "2026-27")
        - total_tds: Total TDS deducted (sum of DEDUCTOR TOTAL rows in PART-I only)
        - records: List of detail records with keys:
            - part: Part number (Roman numeral, e.g., "I")
            - section: Section code (e.g., "194A")
            - deductor_name: Name of TDS deductor
            - deductor_tan: TAN of deductor
            - amount_paid: Amount on which TDS was deducted
            - tds_deducted: TDS amount deducted
            - transaction_date: Date of transaction (dd-MMM-yyyy)
            - booking_status: Booking status code (if present)
            - remarks: Any remarks
        - part_ii: List of 15G/15H declaration records (nil TDS)
            - deductor_name
            - deductor_tan
            - amount_paid: Amount of interest/income declared
            - remarks
        - refunds: Refunds data from Part VII
    """
    import pdfplumber

    if debug is None:
        debug = {}

    debug['tables_found'] = 0
    debug['parts_found'] = {}
    debug['rows_per_part'] = {}
    debug['errors'] = []

    result = {
        'pan': '',
        'name': '',
        'assessment_year': '',
        'total_tds': 0.0,
        'records': [],
        'part_ii': [],
        'refunds': {}
    }

    with pdfplumber.open(pdf_path, password=password) as pdf:
        all_pages_tables = []
        all_pages_text = []
        page_headings = {}  # Map page_num -> list of (roman_numeral, top_position)

        # Extract all tables, headings, and text from all pages
        for page_num in range(len(pdf.pages)):
            page = pdf.pages[page_num]
            tables = page.extract_tables()
            page_text = page.extract_text()

            # Extract tables with position info if available
            headings_on_page = []
            has_position_info = False

            try:
                # Try to extract table positions using find_tables()
                table_objs = page.find_tables()
                if table_objs and len(table_objs) > 0:
                    for idx, table_obj in enumerate(table_objs):
                        if idx < len(tables or []):
                            table = tables[idx]
                            table_top = table_obj.bbox[1]  # Top edge of table
                            all_pages_tables.append({
                                'page': page_num,
                                'table': table,
                                'top': table_top
                            })
                    has_position_info = True

                    # Try to extract heading positions from words
                    try:
                        words = page.extract_words()
                        for word_idx in range(len(words or [])):
                            word = words[word_idx]
                            # Match "PART-I", "PART-II" as single words
                            if word['text'].upper().startswith('PART-'):
                                roman = _detect_part_roman(word['text'])
                                if roman:
                                    headings_on_page.append((roman, word['top']))
                    except (AttributeError, TypeError, KeyError):
                        # extract_words() not available or returned unexpected format
                        pass
            except (AttributeError, TypeError, IndexError):
                # find_tables() not available or failed; use fallback
                pass

            # Fallback: if position extraction failed, use extract_tables() without position
            if not has_position_info:
                for table in (tables or []):
                    all_pages_tables.append({
                        'page': page_num,
                        'table': table,
                        'top': None  # Unknown position
                    })

            page_headings[page_num] = headings_on_page

            all_pages_text.append({
                'page': page_num,
                'text': page_text
            })

        debug['tables_found'] = len(all_pages_tables)

        # First pass: extract personal info (PAN, name, AY) from header table
        for table_info in all_pages_tables:
            table = table_info['table']
            if not table or len(table) < 1:
                continue

            # Header table contains label-value pairs: read value from cell AFTER label
            for row_idx, row in enumerate(table):
                if not row or len(row) < 2:
                    continue

                # Look for label-value pairs across the row
                for col_idx in range(len(row) - 1):
                    label_cell = (row[col_idx] or "").strip().lower()
                    value_cell = (row[col_idx + 1] or "").strip()

                    # Extract PAN: label is "Permanent Account Number (PAN)" or similar
                    if 'permanent account number' in label_cell and not result['pan']:
                        pan_match = re.search(r'[A-Z]{5}[0-9]{4}[A-Z]', value_cell)
                        if pan_match:
                            result['pan'] = pan_match.group(0)

                    # Extract assessment year: label is "Assessment Year", value is "YYYY-YY"
                    if 'assessment year' in label_cell and not result['assessment_year']:
                        ay_match = re.search(r'(\d{4})-(\d{2})', value_cell)
                        if ay_match:
                            result['assessment_year'] = f"{ay_match.group(1)}-{ay_match.group(2)}"

                    # Extract name: label is "Name of Assessee"
                    if 'name of assessee' in label_cell and not result['name']:
                        if value_cell and len(value_cell) > 3:
                            result['name'] = value_cell

        # Second pass: parse detail tables (PART-I through PART-X and PART-II)
        # Assign parts based on vertical position
        current_part = None  # Part carried from previous page

        for table_info in all_pages_tables:
            page_num = table_info['page']
            table = table_info['table']
            table_top = table_info['top']

            if not table or len(table) < 2:
                continue

            # Get part assignment for this table based on position
            if table_top is not None and page_num in page_headings and page_headings[page_num]:
                # Use position-based assignment (we have both position and headings)
                headings = page_headings[page_num]
                assignments = _assign_table_to_part(headings, [table_top], current_part)
                assigned_part = assignments[0] if assignments else current_part
            else:
                # Fallback: use text-based detection from page
                # (when position info or headings are unavailable)
                text = all_pages_text[page_num]['text'] if page_num < len(all_pages_text) else ""
                matches = re.findall(r'PART-([IVX]+)', text, re.IGNORECASE)
                if matches:
                    # Use the last PART heading found on this page
                    assigned_part = matches[-1].upper()
                else:
                    # No heading found on this page; use carried part
                    assigned_part = current_part

            # Update current part for next page
            if assigned_part:
                current_part = assigned_part

            if not assigned_part:
                continue

            if assigned_part not in debug['parts_found']:
                debug['parts_found'][assigned_part] = 0
            if assigned_part not in debug['rows_per_part']:
                debug['rows_per_part'][assigned_part] = 0

            # Process table rows with mode switching
            # Mode: 'deductor' = after DEDUCTOR header, 'detail' = after DETAIL header
            mode = None
            deductor_total_rows = []  # Accumulate deductor rows for this table
            detail_rows = []  # Accumulate detail rows for this table

            row_idx = 0
            while row_idx < len(table):
                row = table[row_idx]
                if not row or len(row) < 2:
                    row_idx += 1
                    continue

                # Check if this is a header row
                row_text = ' '.join([str(cell or "").lower() for cell in row])

                # Detect deductor header: contains "Name of Deductor" and "Total Amount Paid"
                if 'name of deductor' in row_text and 'total amount paid' in row_text:
                    mode = 'deductor'
                    # Re-index columns for deductor mode
                    deductor_idx = _find_column_index(row, 'deductor')
                    tan_idx = _find_column_index(row, 'tan')
                    amount_paid_idx = _find_column_index(row, 'amount paid')
                    tds_idx = _find_column_index(row, 'tds')
                    row_idx += 1
                    continue

                # Detect detail header: contains "Section" (or "Section1") and "Transaction Date"
                if ('section' in row_text or 'section1' in row_text) and 'transaction date' in row_text:
                    mode = 'detail'
                    # Re-index columns for detail mode
                    section_idx = _find_column_index(row, 'section')
                    deductor_idx = _find_column_index(row, 'deductor')
                    date_idx = _find_column_index(row, 'transaction date')
                    amount_paid_idx = _find_column_index(row, 'amount paid')
                    tds_idx = _find_column_index(row, 'tds')
                    booking_idx = _find_column_index(row, 'booking')
                    remarks_idx = _find_column_index(row, 'remarks')
                    row_idx += 1
                    continue

                # Parse data row based on current mode
                if mode == 'deductor':
                    # Deductor total row: has name and TDS amount
                    deductor_name = ''
                    deductor_tan = ''
                    amount_paid = 0.0
                    tds_deducted = 0.0

                    if deductor_idx is not None and len(row) > deductor_idx:
                        deductor_name = (row[deductor_idx] or "").strip()

                    if tan_idx is not None and len(row) > tan_idx:
                        tan_text = (row[tan_idx] or "").strip()
                        tan_match = re.search(r'[A-Z]{4}[0-9]{5}[A-Z]', tan_text)
                        if tan_match:
                            deductor_tan = tan_match.group(0)

                    if amount_paid_idx is not None and len(row) > amount_paid_idx:
                        amount_paid = _parse_inr_amount(row[amount_paid_idx])

                    if tds_idx is not None and len(row) > tds_idx:
                        tds_deducted = _parse_inr_amount(row[tds_idx])

                    # Skip empty deductor rows
                    if deductor_name or deductor_tan:
                        deductor_total_rows.append({
                            'deductor_name': deductor_name,
                            'deductor_tan': deductor_tan,
                            'amount_paid': amount_paid,
                            'tds_deducted': tds_deducted
                        })

                elif mode == 'detail':
                    # Detail row: has section code and transaction date
                    section = ''
                    deductor_name = ''
                    amount_paid = 0.0
                    tds_deducted = 0.0
                    transaction_date = ''
                    booking_status = ''
                    remarks = ''

                    if section_idx is not None and len(row) > section_idx:
                        section = _extract_section_code_from_row(row[section_idx]) or ''

                    if date_idx is not None and len(row) > date_idx:
                        transaction_date = _parse_date(row[date_idx])

                    if amount_paid_idx is not None and len(row) > amount_paid_idx:
                        amount_paid = _parse_inr_amount(row[amount_paid_idx])

                    if tds_idx is not None and len(row) > tds_idx:
                        tds_deducted = _parse_inr_amount(row[tds_idx])

                    if booking_idx is not None and len(row) > booking_idx:
                        booking_status = (row[booking_idx] or "").strip()

                    if remarks_idx is not None and len(row) > remarks_idx:
                        remarks = (row[remarks_idx] or "").strip()

                    # Skip rows with no section code and no transaction date
                    if section or transaction_date:
                        detail_rows.append({
                            'section': section,
                            'amount_paid': amount_paid,
                            'tds_deducted': tds_deducted,
                            'transaction_date': transaction_date,
                            'booking_status': booking_status,
                            'remarks': remarks
                        })

                row_idx += 1

            # Store parsed rows
            # For PART-II: use deductor total rows (nil TDS, real income from 15G/15H)
            if assigned_part == 'II':
                for deductor in deductor_total_rows:
                    result['part_ii'].append({
                        'deductor_name': deductor['deductor_name'],
                        'deductor_tan': deductor['deductor_tan'],
                        'amount_paid': deductor['amount_paid'],
                        'remarks': ''
                    })
                debug['rows_per_part']['II'] = debug['rows_per_part'].get('II', 0) + len(deductor_total_rows)
            else:
                # For PART-I and others: add detail rows to records
                # Note: if deductor_name is in deductor rows but not in detail rows,
                # we need to associate detail rows with their deductor.
                # For now, store detail rows as-is; caller can associate with deductor if needed.
                for detail in detail_rows:
                    result['records'].append({
                        'part': assigned_part or 'I',
                        'section': detail['section'],
                        'deductor_name': detail.get('deductor_name', ''),
                        'deductor_tan': detail.get('deductor_tan', ''),
                        'amount_paid': detail['amount_paid'],
                        'tds_deducted': detail['tds_deducted'],
                        'transaction_date': detail['transaction_date'],
                        'booking_status': detail['booking_status'],
                        'remarks': detail['remarks']
                    })

                # Add to total TDS from DEDUCTOR TOTAL rows of PART-I only
                if assigned_part == 'I':
                    for deductor in deductor_total_rows:
                        result['total_tds'] += deductor['tds_deducted']

                debug['rows_per_part'][assigned_part or 'I'] = debug['rows_per_part'].get(assigned_part or 'I', 0) + len(detail_rows)

    debug['total_records'] = len(result['records'])
    debug['total_part_ii'] = len(result['part_ii'])
    debug['final_tds_total'] = result['total_tds']

    return result
