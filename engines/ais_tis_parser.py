"""
engines/ais_tis_parser.py — Parse AIS/TIS JSON from Income Tax portal
"""

import json
import re
from typing import Dict, Any


_INR_RE = re.compile(r"^-?\d{1,3}(?:,\d{3})*(?:\.\d+)?$|^-?\d+(?:\.\d+)?$")


def _parse_inr_amount(value: str) -> float:
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


def _bucket_for_code(code: str, desc: str, heading: str) -> str:
    """Classify an AIS/TIS record into an aggregate bucket."""
    code_u = (code or "").upper()
    desc_l = (desc or "").lower()
    heading_l = (heading or "").lower()

    if "192" in code_u:
        return "salary_income"

    # Interest
    if "194A" in code_u or "interest" in desc_l:
        if "deposit" in heading_l or "deposit" in desc_l or "bank" in desc_l:
            return "fd_interest"
        return "other_interest"

    if "dividend" in desc_l:
        return "dividend_income"
    if "rent" in desc_l or "rental" in desc_l:
        return "rental_income"

    return "other_income"


def parse_ais_pdf_text(extracted_text: str) -> Dict[str, Any]:
    """Parse extracted AIS PDF text and produce the same aggregate fields as JSON parsing.

    This is best-effort and intentionally conservative:
    - Income amounts are taken from the AIS summary rows (the ones with COUNT and AMOUNT).
    - TDS is summed from detail rows that include quarter/date/status columns.
    """

    text = extracted_text or ""
    lines = [ln.strip() for ln in text.splitlines()]

    result: Dict[str, Any] = {
        'salary_income': 0,
        'fd_interest': 0,
        'savings_interest': 0,
        'other_interest': 0,
        'dividend_income': 0,
        'rental_income': 0,
        'other_income': 0,
        'tds_deducted': 0,
        'details': []
    }

    current_heading = ""
    current_summary: Dict[str, Any] = {}

    # Summary row example:
    # 1 TDS-194A Interest other than ... received JANA SMALL FINANCE BANK LIMITED (BLRJ07125G) 40 54,695
    # The "description" and "source" fields can contain spaces, so we parse from the end:
    # <sr> <code> <desc_and_source...> <count> <amount>
    summary_re = re.compile(
        r"^\s*(\d+)\s+(TDS-[0-9A-Za-z]+)\s+(.+?)\s+(\d+)\s+([0-9,]+(?:\.[0-9]+)?)\s*$"
    )

    # Bank/source often ends with a TAN in parentheses, e.g. "... LIMITED (BLRJ07125G)"
    source_tail_re = re.compile(r"([A-Z0-9][A-Z0-9 &.,'\-]+\([A-Z0-9]{10}\))\s*$")
    tan_re = re.compile(r"\(([A-Z0-9]{10})\)")

    # Detail row example:
    # 1 Q3(Oct-Dec) 31/12/2025 16,646 1,665 1,665 Active
    detail_re = re.compile(
        r"^\s*(\d+)\s+(Q[1-4]\([^)]*\))\s+(\d{2}/\d{2}/\d{4})\s+([0-9,]+(?:\.[0-9]+)?)\s+([0-9,]+(?:\.[0-9]+)?)\s+([0-9,]+(?:\.[0-9]+)?)\s+(Active|Inactive)\s*$"
    )

    def _bucket_for_code(code: str, desc: str, heading: str) -> str:
        code_u = (code or "").upper()
        desc_l = (desc or "").lower()
        heading_l = (heading or "").lower()

        if "192" in code_u:
            return "salary_income"

        # Interest
        if "194A" in code_u or "interest" in desc_l:
            if "deposit" in heading_l or "deposit" in desc_l or "bank" in desc_l:
                return "fd_interest"
            return "other_interest"

        if "dividend" in desc_l:
            return "dividend_income"
        if "rent" in desc_l or "rental" in desc_l:
            return "rental_income"

        # Anything else goes into other income.
        return "other_income"

    for ln in lines:
        if not ln:
            continue

        # Track section headings to improve classification.
        if ln.lower() in {
            "interest from deposit",
            "business receipts",
            "salary",
            "dividend",
            "rental income",
        }:
            current_heading = ln
            continue

        m = summary_re.match(ln)
        if m:
            _sr_no, code, desc_and_source, count_s, amount_s = m.groups()
            desc_and_source = (desc_and_source or "").strip()

            source = ""
            desc = desc_and_source
            source_tan = ""
            msrc = source_tail_re.search(desc_and_source)
            if msrc:
                source = msrc.group(1).strip()
                mtan = tan_re.search(source)
                source_tan = mtan.group(1).strip() if mtan else ""
                desc = desc_and_source[:msrc.start(1)].strip()
            amount = _parse_inr_amount(amount_s)
            bucket = _bucket_for_code(code, desc, current_heading)
            result[bucket] += amount

            current_summary = {
                "record_type": "summary",
                "information_code": code,
                "information_description": desc,
                "information_source": source,
                "source_tan": source_tan or None,
                "count": int(count_s) if count_s.isdigit() else None,
                "amount": amount,
                "bucket": bucket,
                "raw_line": ln,
            }
            result['details'].append(dict(current_summary))
            continue

        m = detail_re.match(ln)
        if m:
            _sr_no, quarter, payment_date, amount_paid_s, tds_deducted_s, tds_deposited_s, status = m.groups()
            amount_paid = _parse_inr_amount(amount_paid_s)
            tds_deducted = _parse_inr_amount(tds_deducted_s)
            tds_deposited = _parse_inr_amount(tds_deposited_s)
            result['tds_deducted'] += tds_deducted

            rec = {
                "record_type": "detail",
                "information_code": current_summary.get("information_code"),
                "information_description": current_summary.get("information_description"),
                "information_source": current_summary.get("information_source"),
                "source_tan": current_summary.get("source_tan"),
                "bucket": current_summary.get("bucket"),
                "quarter": quarter,
                "payment_date": payment_date,
                "amount_paid": amount_paid,
                "tds_deducted": tds_deducted,
                "tds_deposited": tds_deposited,
                "status": status,
                "raw_line": ln,
            }
            result['details'].append(rec)
            continue

    return result


def parse_ais_json(json_data: str) -> Dict[str, Any]:
    """Parse AIS JSON and extract income data."""
    try:
        data = json.loads(json_data) if isinstance(json_data, str) else json_data
        
        result = {
            'salary_income': 0,
            'fd_interest': 0,
            'savings_interest': 0,
            'other_interest': 0,
            'dividend_income': 0,
            'rental_income': 0,
            'other_income': 0,
            'tds_deducted': 0,
            'details': []
        }
        
        # Navigate AIS structure
        ais_data = data.get('AIS', {}) or data.get('ais', {}) or data
        
        # Part A - TDS/TCS
        part_a = ais_data.get('partA', {}) or ais_data.get('PartA', {})
        if part_a:
            tds_entries = part_a.get('tds', []) or part_a.get('TDS', [])
            for entry in tds_entries:
                amount = float(entry.get('totalTaxDeducted', 0) or entry.get('amtPaid', 0) or 0)
                result['tds_deducted'] += amount
                
                # Salary (Section 192)
                section = entry.get('section', '') or entry.get('sectionCode', '')
                if '192' in str(section):
                    income = float(entry.get('totalIncome', 0) or entry.get('amtPaid', 0) or 0)
                    result['salary_income'] += income
                    result['details'].append({
                        'type': 'Salary',
                        'section': section,
                        'amount': income,
                        'tds': amount,
                        'deductor': entry.get('deductorName', 'Unknown')
                    })
        
        # Part B - Information from other sources
        part_b = ais_data.get('partB', {}) or ais_data.get('PartB', {})
        if part_b:
            # Interest income
            interest_entries = part_b.get('interest', []) or part_b.get('Interest', [])
            for entry in interest_entries:
                amount = float(entry.get('amount', 0) or 0)
                source = (entry.get('source', '') or entry.get('description', '')).lower()
                
                if 'fixed deposit' in source or 'fd' in source or 'term deposit' in source:
                    result['fd_interest'] += amount
                    result['details'].append({
                        'type': 'FD Interest',
                        'amount': amount,
                        'source': entry.get('source', 'Unknown')
                    })
                elif 'savings' in source or 'sb' in source:
                    result['savings_interest'] += amount
                    result['details'].append({
                        'type': 'Savings Interest',
                        'amount': amount,
                        'source': entry.get('source', 'Unknown')
                    })
                else:
                    result['other_interest'] += amount
                    result['details'].append({
                        'type': 'Other Interest',
                        'amount': amount,
                        'source': entry.get('source', 'Unknown')
                    })
            
            # Dividend income
            dividend_entries = part_b.get('dividend', []) or part_b.get('Dividend', [])
            for entry in dividend_entries:
                amount = float(entry.get('amount', 0) or 0)
                result['dividend_income'] += amount
                result['details'].append({
                    'type': 'Dividend',
                    'amount': amount,
                    'source': entry.get('source', 'Unknown')
                })
            
            # Rental income
            rental_entries = part_b.get('rental', []) or part_b.get('Rental', [])
            for entry in rental_entries:
                amount = float(entry.get('amount', 0) or 0)
                result['rental_income'] += amount
                result['details'].append({
                    'type': 'Rental Income',
                    'amount': amount,
                    'source': entry.get('source', 'Unknown')
                })
        
        return result
        
    except Exception as e:
        raise ValueError(f"Failed to parse AIS JSON: {str(e)}")


def parse_tis_json(json_data: str) -> Dict[str, Any]:
    """Parse TIS JSON and extract income data."""
    try:
        data = json.loads(json_data) if isinstance(json_data, str) else json_data
        
        result = {
            'salary_income': 0,
            'fd_interest': 0,
            'savings_interest': 0,
            'other_interest': 0,
            'dividend_income': 0,
            'rental_income': 0,
            'other_income': 0,
            'tds_deducted': 0,
            'details': []
        }
        
        # TIS structure
        tis_data = data.get('TIS', {}) or data.get('tis', {}) or data
        
        # TDS details
        tds_details = tis_data.get('tdsDetails', []) or tis_data.get('TDSDetails', [])
        for entry in tds_details:
            section = entry.get('section', '') or entry.get('sectionCode', '')
            income = float(entry.get('incomeAmount', 0) or entry.get('totalIncome', 0) or 0)
            tds = float(entry.get('tdsAmount', 0) or entry.get('taxDeducted', 0) or 0)
            
            result['tds_deducted'] += tds
            
            if '192' in str(section):
                result['salary_income'] += income
                result['details'].append({
                    'type': 'Salary',
                    'section': section,
                    'amount': income,
                    'tds': tds,
                    'deductor': entry.get('deductorName', 'Unknown')
                })
            elif '194A' in str(section):
                result['other_interest'] += income
                result['details'].append({
                    'type': 'Interest Income',
                    'section': section,
                    'amount': income,
                    'tds': tds,
                    'deductor': entry.get('deductorName', 'Unknown')
                })
        
        return result
        
    except Exception as e:
        raise ValueError(f"Failed to parse TIS JSON: {str(e)}")


def parse_tis_pdf_text(extracted_text: str) -> Dict[str, Any]:
    """Parse extracted TIS PDF text.

    TIS PDFs usually provide:
    - Category-level totals (Processed by System, Accepted by Taxpayer)
    - Annexure with per-source amounts and TAN codes (in parentheses)

    Returns a dict compatible with AISTISImport aggregates, plus a detailed record list.
    """

    text = extracted_text or ""
    lines = [ln.strip() for ln in text.splitlines()]

    result: Dict[str, Any] = {
        'salary_income': 0,
        'fd_interest': 0,
        'savings_interest': 0,
        'other_interest': 0,
        'dividend_income': 0,
        'rental_income': 0,
        'other_income': 0,
        'tds_deducted': 0,
        'details': []
    }

    def _bucket_for_category(cat: str) -> str:
        c = (cat or "").lower()
        if "interest from deposit" in c:
            return "fd_interest"
        if "interest" in c:
            return "other_interest"
        if "salary" in c:
            return "salary_income"
        if "dividend" in c:
            return "dividend_income"
        if "rent" in c:
            return "rental_income"
        if "business receipt" in c or "business receipts" in c:
            return "other_income"
        return "other_income"

    # Category summary row example:
    # 1 Interest from deposit 1,52,000 1,52,000
    cat_re = re.compile(r"^\s*(\d+)\s+([A-Za-z].*?)\s+([0-9,]+(?:\.[0-9]+)?)\s+([0-9,]+(?:\.[0-9]+)?)\s*$")

    seen_category_rows: set[tuple[str, float, float]] = set()

    for ln in lines:
        # Avoid matching annexure detail rows (they also start with SR NO).
        ln_l = ln.lower()
        if "tds/" in ln_l or "amount paid" in ln_l or "credited" in ln_l:
            continue
        m = cat_re.match(ln)
        if not m:
            continue
        _sr, category, processed_s, accepted_s = m.groups()
        processed = _parse_inr_amount(processed_s)
        accepted = _parse_inr_amount(accepted_s)

        key = ((category or "").strip().lower(), processed, accepted)
        if key in seen_category_rows:
            continue
        seen_category_rows.add(key)

        bucket = _bucket_for_category(category)
        result[bucket] += accepted
        result['details'].append({
            "record_type": "summary",
            "information_code": "",
            "information_description": category,
            "information_source": "",
            "bucket": bucket,
            "amount": accepted,
            "amount_processed": processed,
            "amount_accepted": accepted,
            "raw_line": ln,
        })

    # Annexure source blocks: multi-line records with TAN and 3 amounts.
    # We'll scan blocks starting with "<n> TDS/".
    joined_lines = []
    for ln in lines:
        if not ln:
            continue
        # Normalize smart quotes to plain.
        ln = ln.replace("“", '"').replace("”", '"').replace("’", "'")
        joined_lines.append(ln)

    blocks: list[list[str]] = []
    current: list[str] = []
    for ln in joined_lines:
        if re.match(r"^\d+\s+TDS/", ln):
            if current:
                blocks.append(list(current))
            current = [ln]
        else:
            if current:
                # Stop if we hit a new category header
                if ln.startswith("SR. NO.") and "INFORMATION CATEGORY" in ln.upper():
                    blocks.append(list(current))
                    current = []
                # Stop if we hit footer/header markers that are not part of the record.
                elif ln.startswith("Download ID") or ln.startswith("Generation Date") or ln.startswith("PAN Name") or ln.startswith("Page "):
                    blocks.append(list(current))
                    current = []
                else:
                    current.append(ln)
    if current:
        blocks.append(list(current))

    tan_re = re.compile(r"\(([A-Z0-9]{10})\)")
    section_re = re.compile(r"Section\s+(\d+[A-Z]?)", re.IGNORECASE)

    def _extract_company_name(chunk: str) -> str:
        # Grab a best-effort company name ending with LIMITED.
        chunk_u = re.sub(r"\s+", " ", (chunk or "").strip())
        # Prefer sequences like "... BANK LIMITED" / "... PRIVATE LIMITED".
        m = re.search(
            r"([A-Z][A-Z &.,'\-]{2,}(?:SMALL FINANCE BANK LIMITED|FINANCE BANK LIMITED|BANK LIMITED|PRIVATE LIMITED|LIMITED))",
            chunk_u,
        )
        return (m.group(1).strip() if m else "")

    _COMPANY_STOPWORDS = {
        "TDS", "TCS", "ON", "SECURITIES", "INTEREST", "OTHER", "THAN", "RECEIVED",
        "AMOUNT", "PAID", "CREDITED", "RECEIPT", "FEES", "FOR", "PROFESSIONAL",
        "OR", "TECHNICAL", "SERVICES", "SECTION", "FROM", "DEPOSIT", "OF",
        "DOWNLOAD", "ID", "IP", "ADDRESS", "GENERATION", "DATE", "PAGE",
    }

    def _extract_company_name_from_block_lines(block_lines: list[str]) -> str:
        parts: list[str] = []
        for ln in (block_lines or []):
            s = re.sub(r"\s+", " ", (ln or "").strip())
            if not s:
                continue
            # Remove SR no + leading marker
            s = re.sub(r"^\d+\s+", "", s)
            # Remove TAN and Section fragments
            s = re.sub(r"\([A-Z0-9]{10}\)", "", s)
            s = re.sub(r"\(Section[^)]*\)", "", s, flags=re.IGNORECASE)
            # Remove amounts and punctuation
            s = re.sub(r"\d{1,3}(?:,\d{3})*(?:\.\d+)?", " ", s)
            s = re.sub(r"[^A-Z ]", " ", s.upper())
            words = [w for w in s.split() if w and w not in _COMPANY_STOPWORDS]
            if words:
                parts.append(" ".join(words))

        if not parts:
            return ""

        # Deduplicate while preserving order.
        seen = set()
        ordered = []
        for p in parts:
            if p not in seen:
                ordered.append(p)
                seen.add(p)

        candidate = " ".join(ordered).strip()
        # Trim leading generic fragments if any.
        candidate = re.sub(r"^(?:TDS|TCS)\s+", "", candidate).strip()
        return candidate

    def _extract_desc(chunk: str) -> str:
        # Between "TDS/" and company name, keep a short description.
        s = re.sub(r"\s+", " ", (chunk or "").strip())
        s = s.replace("TDS/", "").replace("TCS", "").strip()
        # Cut at "Amount paid" marker if present
        s = re.split(r"Amount\s+paid", s, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        # Avoid including the company name.
        comp = _extract_company_name(s)
        if comp and comp in s:
            s = s.split(comp)[0].strip()
        return s[:160]

    for block_lines in blocks:
        chunk_norm = re.sub(r"\s+", " ", " ".join(block_lines)).strip()
        tans = tan_re.findall(chunk_norm)
        section_m = section_re.search(chunk_norm)
        section = section_m.group(1).upper() if section_m else ""

        # Amounts: last 3 monetary tokens in the chunk are typically reported/processed/accepted.
        # Avoid being confused by section numbers (194A) and TAN digits by filtering.
        clean = re.sub(r"\([A-Z0-9]{10}\)", "", chunk_norm)
        clean = re.sub(r"\bSection\s+\d+[A-Z]?\b", "", clean, flags=re.IGNORECASE)
        nums = re.findall(r"\d{1,3}(?:,\d{3})*(?:\.\d+)?", clean)
        amounts = []
        for n in nums:
            n = (n or "").strip()
            if not n:
                continue
            if "," not in n and not (n.isdigit() and len(n) >= 4):
                continue
            amounts.append(_parse_inr_amount(n))

        amount_reported = amount_processed = amount_accepted = None
        if len(amounts) >= 3:
            amount_reported, amount_processed, amount_accepted = amounts[-3], amounts[-2], amounts[-1]
        elif len(amounts) == 2:
            amount_processed, amount_accepted = amounts[-2], amounts[-1]
        elif len(amounts) == 1:
            amount_accepted = amounts[-1]

        tan = tans[-1] if tans else ""
        company = _extract_company_name_from_block_lines(block_lines) or _extract_company_name(chunk_norm)
        desc = _extract_desc(chunk_norm)

        information_source = company
        if tan:
            information_source = f"{company} ({tan})" if company else tan

        info_code = f"TDS-{section}" if section else ""
        bucket = _bucket_for_code(info_code or "", desc, "")

        if isinstance(amount_accepted, (int, float)):
            # Avoid double-counting if category summary already filled totals; we do NOT add here.
            pass

        result['details'].append({
            "record_type": "detail",
            "information_code": info_code,
            "information_description": desc or "",
            "information_source": information_source,
            "source_tan": tan,
            "bucket": bucket,
            "amount": amount_accepted if amount_accepted is not None else 0.0,
            "amount_reported": amount_reported,
            "amount_processed": amount_processed,
            "amount_accepted": amount_accepted,
            # Reuse amount_paid so the existing table can show a number even when there's no quarter/date.
            "amount_paid": amount_accepted,
            "raw_line": chunk_norm,
        })

    return result
