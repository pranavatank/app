"""
engines/statement_metadata_extractor.py — Extract account details from bank statements
"""

import re
from typing import Dict, Optional


def extract_account_metadata(statement_text: str) -> Dict[str, Optional[str]]:
    """
    Extract account metadata from bank statement text.
    
    Returns dict with keys:
    - customer_id, account_number_full, ifsc_code, micr_code, ckyc_id
    - branch_name, branch_address, communication_address
    - email_id, phone_no, account_opening_date, account_status
    - account_type, currency, nomination_status, nominee_name
    """
    metadata = {}
    
    # Normalize text - handle Excel multi-column layouts
    # Replace multiple tabs/spaces with single space
    normalized_text = re.sub(r'[\t\s]+', ' ', statement_text)
    
    # Customer ID
    match = re.search(r'Customer\s+(?:ID|Id|Number)\s*[:\-]?\s*(\S+)', normalized_text, re.IGNORECASE)
    metadata['customer_id'] = match.group(1) if match else None
    
    # Account Number - multiple patterns
    patterns = [
        r'Account\s+Number\s*[:\-]?\s*(\d+)',
        r'A/C\s+No\.?\s*[:\-]?\s*(\d+)',
        r'Account\s+No\.?\s*[:\-]?\s*(\d+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized_text, re.IGNORECASE)
        if match:
            metadata['account_number_full'] = match.group(1)
            break
    if not metadata.get('account_number_full'):
        metadata['account_number_full'] = None
    
    # IFSC Code
    match = re.search(r'IFSC\s*(?:Code)?\s*[:\-]?\s*([A-Z]{4}0[A-Z0-9]{6})', normalized_text, re.IGNORECASE)
    metadata['ifsc_code'] = match.group(1).upper() if match else None
    
    # MICR Code
    match = re.search(r'MICR\s*(?:Code)?\s*[:\-]?\s*(\d{9})', normalized_text, re.IGNORECASE)
    metadata['micr_code'] = match.group(1) if match else None
    
    # CKYC ID
    match = re.search(r'CKYC\s+(?:ID|Id)\s*[:\-]?\s*(\d+)', normalized_text, re.IGNORECASE)
    metadata['ckyc_id'] = match.group(1) if match else None
    
    # Branch Name
    match = re.search(r'Branch\s+Name\s*[:\-]?\s*([^\n\r]+?)(?=\s+Branch|\s+Product|\s+Account|\n|\r|$)', normalized_text, re.IGNORECASE)
    if match:
        metadata['branch_name'] = match.group(1).strip()
    else:
        metadata['branch_name'] = None
    
    # Branch Address - handle multi-line
    match = re.search(r'Branch\s+Address\s*[:\-]?\s*([^\n\r]+?)(?=\s+Product|\s+Account|\s+IFSC|\s+Available|\n\n|\r\r|$)', normalized_text, re.IGNORECASE)
    if match:
        addr = match.group(1).strip()
        # Clean up address - remove extra spaces
        addr = re.sub(r'\s+', ' ', addr)
        metadata['branch_address'] = addr
    else:
        metadata['branch_address'] = None
    
    # Communication Address - look for customer address
    match = re.search(r'(?:Address|Customer Address)\s*[:\-]?\s*([^\n\r]+?)(?=\s+Mobile|\s+Email|\s+Branch|\n\n|\r\r|$)', normalized_text, re.IGNORECASE)
    if match:
        addr = match.group(1).strip()
        # Handle multi-line addresses in Excel format
        # Look for continuation lines
        addr_parts = [addr]
        remaining = normalized_text[match.end():]
        # Get next few lines that look like address continuation
        for line_match in re.finditer(r'([A-Z][^\n\r]{5,50}?)(?=\s+[A-Z]{2,}|\n|\r|$)', remaining[:200]):
            line = line_match.group(1).strip()
            if not re.match(r'^(Mobile|Email|Branch|Product|Account|IFSC)', line, re.IGNORECASE):
                addr_parts.append(line)
            else:
                break
        metadata['communication_address'] = ' '.join(addr_parts)
    else:
        metadata['communication_address'] = None
    
    # Email - handle various formats
    match = re.search(r'Email\s*(?:ID)?\s*[:\-]?\s*([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})', normalized_text, re.IGNORECASE)
    metadata['email_id'] = match.group(1) if match else None
    
    # Phone/Mobile - handle various formats
    match = re.search(r'(?:Mobile|Phone|Contact)(?:\s+No\.?)?\s*[:\-]?\s*([\d\+\-\s]{10,15})', normalized_text, re.IGNORECASE)
    if match:
        phone = re.sub(r'[\s\-\+]', '', match.group(1))
        # Keep only last 10-12 digits
        phone = phone[-12:] if len(phone) > 12 else phone
        metadata['phone_no'] = phone
    else:
        metadata['phone_no'] = None
    
    # Account Opening Date
    match = re.search(r'(?:Account\s+)?Opening\s+Date\s*[:\-]?\s*(\d{4}-\d{2}-\d{2}|\d{2}[/-]\d{2}[/-]\d{4})', normalized_text, re.IGNORECASE)
    if match:
        date_str = match.group(1)
        if '/' in date_str or '-' in date_str:
            parts = re.split(r'[/-]', date_str)
            if len(parts[0]) == 4:  # YYYY-MM-DD
                metadata['account_opening_date'] = date_str
            else:  # DD/MM/YYYY or DD-MM-YYYY
                metadata['account_opening_date'] = f"{parts[2]}-{parts[1]}-{parts[0]}"
    else:
        metadata['account_opening_date'] = None
    
    # Account Status
    match = re.search(r'(?:Account\s+)?Status\s*[:\-]?\s*(Active|Inactive|Closed|Dormant)', normalized_text, re.IGNORECASE)
    metadata['account_status'] = match.group(1).title() if match else None
    
    # Account Type - handle various formats
    patterns = [
        r'Account\s+Type\s*[:\-]?\s*([A-Z]{2,})',
        r'Product\s+Name\s*[:\-]?\s*([^\n\r]+?)(?=\s+Account|\n|\r|$)',
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized_text, re.IGNORECASE)
        if match:
            acc_type = match.group(1).strip()
            # Map common abbreviations
            type_map = {
                'SA': 'Savings',
                'CA': 'Current',
                'SB': 'Savings',
                'CC': 'Current',
            }
            metadata['account_type'] = type_map.get(acc_type.upper(), acc_type)
            break
    if not metadata.get('account_type'):
        metadata['account_type'] = None
    
    # Currency
    match = re.search(r'Currency\s*[:\-]?\s*([A-Z]{3})', normalized_text, re.IGNORECASE)
    if match:
        metadata['currency'] = match.group(1).upper()
    else:
        # Check for INR mentions
        if re.search(r'\(INR\)|INR|₹', normalized_text):
            metadata['currency'] = 'INR'
        else:
            metadata['currency'] = None
    
    # Nomination
    match = re.search(r'Nomination\s*[:\-]?\s*(Registered|Not Registered|Yes|No)', normalized_text, re.IGNORECASE)
    if match:
        nom_status = match.group(1).lower()
        if nom_status in ['yes', 'registered']:
            metadata['nomination_status'] = 'Registered'
        elif nom_status in ['no', 'not registered']:
            metadata['nomination_status'] = 'Not Registered'
    else:
        metadata['nomination_status'] = None
    
    # Nominee Name
    match = re.search(r'Nominee\s+Name\s*[:\-]?\s*([^\n\r]+?)(?=\s+Mobile|\s+Email|\s+Branch|\n|\r|$)', normalized_text, re.IGNORECASE)
    if match:
        metadata['nominee_name'] = match.group(1).strip()
    else:
        metadata['nominee_name'] = None
    
    return metadata


def mask_account_number(full_number: str) -> str:
    """Convert full account number to masked format (e.g., XXXX1234)."""
    if not full_number or len(full_number) < 4:
        return full_number
    return 'X' * (len(full_number) - 4) + full_number[-4:]


def mask_email(email: str) -> str:
    """Mask email address (e.g., a********k@gmail.com)."""
    if not email or '@' not in email:
        return email
    local, domain = email.split('@', 1)
    if len(local) <= 2:
        return email
    return local[0] + '*' * (len(local) - 2) + local[-1] + '@' + domain


def mask_phone(phone: str) -> str:
    """Mask phone number (e.g., ********7882)."""
    if not phone:
        return phone
    digits = re.sub(r'\D', '', phone)
    if len(digits) < 4:
        return phone
    return '*' * (len(digits) - 4) + digits[-4:]
