"""
engines/statement_metadata_extractor.py — Extract account details from bank statements
"""

import re
from typing import Dict, Optional

MASKED_ACCOUNT_NUMBER = r"[Xx*•]{2,}\d{4}"


def extract_account_metadata(statement_text: str) -> Dict[str, Optional[str]]:
    """Extract explicitly labelled values from a statement header."""
    lines = []
    for line in statement_text.splitlines()[:120]:
        line = re.sub(r"[\t ]+", " ", line).strip()
        # A transaction heading separates the account details from payment narration.
        if re.search(r"\b(?:balance|withdrawals?|deposits?|debit|credit)\b", line, re.I) and re.search(
            r"\b(?:particulars|narration|description|transaction date|value date)\b", line, re.I,
        ):
            break
        lines.append(line)
    header = "\n".join(lines)

    def field(label, value):
        matches = {
            match.group(1).strip() for match in re.finditer(
                rf"(?:^|(?<=[ |]))(?:{label})[ .]*[:=\-]?[ ]*(?:\n[ ]*)?({value})",
                header, re.IGNORECASE | re.MULTILINE,
            )
        }
        return next(iter(matches)) if len(matches) == 1 else None

    def labelled_text(label):
        value = field(
            rf"(?:{label})[ ]*[:=]", r"[^\n:|]{2,150}?(?=[ ]+(?:IFSC|MICR|Customer|Branch|Product|Account|Currency|Nominee|Mobile|Email|Phone)\b|$)",
        )
        return value if value and any(char.isalpha() for char in value) else None

    account_label = r"(?:Account|A[ ]*/?[ ]*C|Acct\.?)[ ]*(?:Number|No\.?|#)"
    masked = field(account_label, rf"{MASKED_ACCOUNT_NUMBER}(?![\w*])")
    metadata = {
        "account_number_full": field(account_label, r"\d{8,22}(?![\w*])"),
        "account_number_masked": "X" * (len(masked) - 4) + masked[-4:] if masked else None,
        "account_holder_name": labelled_text(r"Account(?: Holder)? Name|Customer Name|Name of Account Holder"),
        "customer_id": field(r"Customer[ ]*(?:ID|Number|No\.?)|CIF(?:[ ]*(?:ID|No\.?))?", r"[A-Z]*\d{4,20}\b"),
        "ifsc_code": field(r"IFSC(?:[ ]*Code)?", r"[A-Z]{4}0[A-Z0-9]{6}\b"),
        "micr_code": field(r"MICR(?:[ ]*Code)?", r"\d{9}\b"),
        "ckyc_id": field(r"CKYC[ ]*(?:ID|Number|No\.?)", r"\d{10,16}\b"),
        "branch_name": labelled_text(r"Branch(?: Name)?"),
        "branch_address": labelled_text(r"Branch Address"),
        "communication_address": labelled_text(r"Communication Address|Customer Address|Mailing Address"),
        "email_id": field(r"E-?Mail(?:[ ]*ID)?", r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b"),
        "nominee_name": labelled_text(r"Nominee Name"),
    }
    phone = field(r"(?:Mobile|Phone)(?:[ ]*(?:Number|No\.?))?", r"(?:\+91[- ]?)?[6-9]\d{9}\b")
    metadata["phone_no"] = re.sub(r"[^\d]", "", phone) if phone else None
    date_text = field(
        r"(?:Account[ ]+)?Opening[ ]+Date|(?:A/C|Account)[ ]+Open(?:ed|ing)?[ ]+Date",
        r"(?:\d{4}-\d{2}-\d{2}|\d{2}[/-]\d{2}[/-]\d{4})\b",
    )
    metadata["account_opening_date"] = None
    if date_text:
        from datetime import date
        date_parts = re.split(r"[/-]", date_text)
        if len(date_parts[0]) == 2:
            date_parts.reverse()
        try:
            metadata["account_opening_date"] = date.fromisoformat("-".join(date_parts)).isoformat()
        except ValueError:
            pass
    status = field(r"Account[ ]+Status", r"(?:Active|Inactive|Closed|Dormant)\b")
    metadata["account_status"] = status.title() if status else None
    account_type = field(r"Account[ ]+Type|Product[ ]+Name", r"(?:Savings?|Current|Salary|FD-linked|SA|CA|SB|CC)\b")
    metadata["account_type"] = {
        "SA": "Savings", "SB": "Savings", "SAVING": "Savings", "SAVINGS": "Savings",
        "CA": "Current", "CC": "Current", "CURRENT": "Current",
        "SALARY": "Salary", "FD-LINKED": "FD-linked",
    }.get((account_type or "").upper())
    for key in ("ifsc_code", "customer_id"):
        if metadata[key]:
            metadata[key] = metadata[key].upper()
    currency = field(r"Currency(?:[ ]*Code)?", r"[A-Z]{3}\b")
    metadata["currency"] = currency.upper() if currency else None
    nomination = field(r"Nomination(?:[ ]+Status)?", r"(?:Registered|Not Registered|Yes|No)\b")
    metadata["nomination_status"] = {
        "registered": "Registered", "yes": "Registered", "not registered": "Not Registered", "no": "Not Registered",
    }.get((nomination or "").casefold())
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
