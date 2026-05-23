"""
engines/form26as_parser.py — Form 26AS PDF parser.

Extracts TDS records from Form 26AS PDF files.
"""

import re
from datetime import datetime


def parse_form26as_pdf(pdf_text: str) -> dict:
    """
    Parse Form 26AS PDF text and extract TDS records.
    
    Returns dict with:
        - pan: PAN number
        - name: Taxpayer name
        - assessment_year: AY
        - records: list of TDS records
    """
    result = {
        "pan": "",
        "name": "",
        "assessment_year": "",
        "records": [],
    }
    
    lines = pdf_text.split("\n")
    
    # Extract PAN
    for line in lines:
        if "PAN" in line.upper() and not result["pan"]:
            match = re.search(r"[A-Z]{5}[0-9]{4}[A-Z]", line)
            if match:
                result["pan"] = match.group(0)
        
        # Extract name
        if "NAME" in line.upper() and not result["name"]:
            parts = line.split(":")
            if len(parts) > 1:
                result["name"] = parts[1].strip()
        
        # Extract AY
        if "ASSESSMENT YEAR" in line.upper() or "A.Y." in line.upper():
            match = re.search(r"20\d{2}-\d{2}", line)
            if match:
                result["assessment_year"] = match.group(0)
    
    # Parse Part A - TDS records
    in_part_a = False
    current_record = {}
    
    for i, line in enumerate(lines):
        line_upper = line.upper()
        
        # Detect Part A section
        if "PART A" in line_upper or "DETAILS OF TAX DEDUCTED AT SOURCE" in line_upper:
            in_part_a = True
            continue
        
        # Exit Part A
        if in_part_a and ("PART B" in line_upper or "PART C" in line_upper):
            in_part_a = False
            if current_record:
                result["records"].append(current_record)
                current_record = {}
            continue
        
        if not in_part_a:
            continue
        
        # Extract TAN
        tan_match = re.search(r"[A-Z]{4}[0-9]{5}[A-Z]", line)
        if tan_match:
            if current_record:
                result["records"].append(current_record)
            current_record = {
                "deductor_tan": tan_match.group(0),
                "deductor_name": "",
                "section": "",
                "transaction_date": "",
                "amount_paid": 0.0,
                "tds_deducted": 0.0,
                "tds_deposited": 0.0,
                "status": "F",
                "certificate_no": "",
                "remarks": "",
                "raw_line": line,
            }
            
            # Try to extract deductor name from same or next line
            name_part = line.replace(tan_match.group(0), "").strip()
            if name_part and len(name_part) > 3:
                current_record["deductor_name"] = name_part
            elif i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and not re.search(r"\d{2}/\d{2}/\d{4}", next_line):
                    current_record["deductor_name"] = next_line
        
        # Extract section code
        section_match = re.search(r"19[0-9][A-Z]?", line)
        if section_match and current_record:
            current_record["section"] = section_match.group(0)
        
        # Extract dates
        date_match = re.search(r"(\d{2}/\d{2}/\d{4})", line)
        if date_match and current_record and not current_record["transaction_date"]:
            current_record["transaction_date"] = date_match.group(1)
        
        # Extract amounts (look for patterns like 1,23,456.00)
        amount_matches = re.findall(r"[\d,]+\.\d{2}", line)
        if amount_matches and current_record:
            amounts = [float(a.replace(",", "")) for a in amount_matches]
            if len(amounts) >= 2:
                current_record["amount_paid"] = amounts[0]
                current_record["tds_deducted"] = amounts[1]
                if len(amounts) >= 3:
                    current_record["tds_deposited"] = amounts[2]
        
        # Extract certificate number
        cert_match = re.search(r"[A-Z0-9]{15,}", line)
        if cert_match and current_record and not current_record["certificate_no"]:
            current_record["certificate_no"] = cert_match.group(0)
    
    # Add last record
    if current_record:
        result["records"].append(current_record)
    
    return result


def parse_form26as_text_simple(text: str) -> list[dict]:
    """
    Simple line-by-line parser for Form 26AS.
    Returns list of TDS records.
    """
    records = []
    lines = text.split("\n")
    
    for line in lines:
        # Skip empty or header lines
        if not line.strip() or len(line.strip()) < 20:
            continue
        
        # Look for TAN pattern
        tan_match = re.search(r"[A-Z]{4}[0-9]{5}[A-Z]", line)
        if not tan_match:
            continue
        
        tan = tan_match.group(0)
        
        # Extract amounts
        amounts = re.findall(r"[\d,]+\.\d{2}", line)
        if not amounts:
            continue
        
        amount_paid = float(amounts[0].replace(",", "")) if len(amounts) > 0 else 0.0
        tds_deducted = float(amounts[1].replace(",", "")) if len(amounts) > 1 else 0.0
        
        # Extract section
        section_match = re.search(r"19[0-9][A-Z]?", line)
        section = section_match.group(0) if section_match else ""
        
        # Extract date
        date_match = re.search(r"(\d{2}/\d{2}/\d{4})", line)
        transaction_date = date_match.group(1) if date_match else ""
        
        # Extract deductor name (text before TAN)
        name_part = line[:line.index(tan)].strip() if tan in line else ""
        
        records.append({
            "deductor_tan": tan,
            "deductor_name": name_part,
            "section": section,
            "transaction_date": transaction_date,
            "amount_paid": amount_paid,
            "tds_deducted": tds_deducted,
            "tds_deposited": tds_deducted,
            "status": "F",
            "certificate_no": "",
            "remarks": "",
            "raw_line": line,
        })
    
    return records


def extract_financial_year_from_ay(assessment_year: str) -> str:
    """Convert AY to FY. e.g., '2024-25' -> '2023-24'"""
    if not assessment_year or "-" not in assessment_year:
        return ""
    
    try:
        ay_start = int(assessment_year.split("-")[0])
        fy_start = ay_start - 1
        return f"{fy_start}-{str(fy_start + 1)[2:]}"
    except:
        return ""
