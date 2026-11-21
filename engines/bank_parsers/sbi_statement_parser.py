"""
engines/bank_parsers/sbi_statement_parser.py — SBI-specific PDF statement parser.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Dict
import re

from engines.parser_utils import _guess_fd_category
from engines.statement_passwords import (
    ensure_pdf_password,
    StatementPasswordError,
)


_REF_PATTERNS = [
    r"\b(?:IB|SCREF|CHBATCH|MB|UTR|RRN|NEFT|IMPS)[A-Z0-9]{6,}\b",
    r"\b[A-Z0-9]{10,}/\d+\b",
    r"\b[A-F0-9]{16,}\b",
    r"\b[A-Z0-9]{12,}\b",
    r"\bSBIN\d{9,}\b",
]


def _append_issue(debug: Optional[Dict], message: str, limit: int = 200) -> None:
    if debug is None:
        return
    issues = debug.setdefault("issues", [])
    if len(issues) < limit:
        issues.append(message)


def _is_summary_line(text: str) -> bool:
    upper = (text or "").upper()
    if not upper:
        return False
    compact = re.sub(r"\s+", "", upper)
    summary_markers = [
        "STATEMENT SUMMARY",
        "DATE OF STATEMENT",
        "STATEMENT PERIOD",
        "BRANCH EMAIL",
        "MICR",
        "IFSC",
        "ACCOUNT NO",
        "ACCOUNT NUMBER",
        "CUSTOMER ID",
        "CKYCR",
        "CKYC",
        "INTEREST RATE",
        "BROUGHT FORWARD",
        "TOTAL DEBITS",
        "TOTAL CREDITS",
        "CLOSING BALANCE",
        "OPENING BALANCE",
        "TRANSACTIONS",
        "PLEASE DO NOT SHARE",
        "PAGE NO",
    ]
    if any(marker in upper for marker in summary_markers):
        return True
    if "INTERESTRATE" in compact:
        return True
    return False


def _strip_footer_noise(text: str) -> str:
    if not text:
        return text
    cleaned = re.sub(r"\bPAGE\s+NO\.?\s*\d+\b", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bSTATEMENT\s+SUMMARY.*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bDATE\s+OF\s+STATEMENT.*", "", cleaned, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip()


def _parse_date(date_text: str) -> Optional[str]:
    value = date_text.strip().replace("-", "/")
    for fmt in ["%d/%m/%Y", "%d/%m/%y"]:
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _extract_reference_no(text: str) -> Optional[str]:
    value = (text or "").upper().strip()
    if not value:
        return None
    matches = []
    for pattern in _REF_PATTERNS:
        matches.extend(re.findall(pattern, value))
    if not matches:
        return None
    ref = matches[-1].strip()
    if len(ref) < 8:
        return None
    return ref[:80]


def _infer_txn_type(desc_upper: str) -> Optional[str]:
    if not desc_upper:
        return None

    debit_markers = [
        "UPI/DR", "WDL", "WDL TFR", "ATM WDL", "ATM CASH",
        "WITHDRAW", "WITHDRAWAL", "DEBIT", " DR ", "CHARGES", "GST", "TAX",
        "INB NEFT", "UTR NO",
    ]
    credit_markers = [
        "DEP TFR", "CREDIT", " CR ", " CR.", "INTEREST CREDIT", "INTEREST",
        "PPO,", "NEFT*RBIS",
    ]

    has_debit = any(marker in desc_upper for marker in debit_markers)
    has_credit = any(marker in desc_upper for marker in credit_markers)
    if has_debit and has_credit:
        return None
    if has_debit:
        return "Expense"
    if has_credit:
        return "Income"
    return None


def _guess_mode(desc_upper: str) -> str:
    if "UPI" in desc_upper:
        return "UPI"
    if "ATM" in desc_upper or "CASH" in desc_upper:
        return "Cash"
    return "Bank Transfer"


def _guess_category(desc_upper: str, txn_type: str) -> str:
    fd_category = _guess_fd_category(desc_upper, txn_type)
    if fd_category:
        return fd_category

    if txn_type == "Income":
        if "INTEREST" in desc_upper and "CREDIT" in desc_upper:
            return "Savings Interest"
        if "PPO" in desc_upper or "PENSION" in desc_upper:
            return "Pension"
        return "Other Income"

    if "ATM" in desc_upper and "WDL" in desc_upper:
        return "Cash"
    if "UPI" in desc_upper:
        return "Other Expense"
    return "Other Expense"


def _clean_description(text: str) -> str:
    """Clean description by removing dates, amounts, and reference numbers."""
    cleaned = text
    # Remove dates
    cleaned = re.sub(r"\b\d{2}[/-]\d{2}[/-]\d{2,4}\b", "", cleaned)
    # Remove standalone amounts with dashes
    cleaned = re.sub(r"\s+-\s+-\s+[\d,]+\.\d{2}\s+[\d,]+\.\d{2}\s+", " ", cleaned)
    cleaned = re.sub(r"\s+-\s+[\d,]+\.\d{2}\s+-\s+[\d,]+\.\d{2}\s+", " ", cleaned)
    # Remove amounts at end
    cleaned = re.sub(r"\s+[\d,]+\.\d{2}\s+[\d,]+\.\d{2}$", "", cleaned)
    # Remove long reference numbers
    cleaned = re.sub(r"\b\d{10,}\b", "", cleaned)
    cleaned = re.sub(r"\b(?:SBIN|RBI)[A-Z0-9]{8,}\b", "", cleaned)
    cleaned = re.sub(r"\b[A-Z0-9]{12,}\b", "", cleaned)
    # Normalize whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or "Transaction"


_DATE_START = re.compile(r"^(\d{2}[/-]\d{2}[/-]\d{2,4})\b")
_MONEY = r"[+-]?\d[\d,]*\.\d{2}"
# Restrict amounts to the table's tail. Integer runs elsewhere belong to narration
# or a bank reference. A dash in a money column represents a blank.
_MONEY_TAIL = re.compile(rf"(?<!\S)(?P<columns>(?:{_MONEY}|-)(?:\s+(?:{_MONEY}|-)){{1,3}})\s*$")

def _read_money_tail(text):
    match = _MONEY_TAIL.search(text)
    if not match:
        return None
    tokens = match.group("columns").split()
    if tokens[-1] == "-":
        return None
    values = [float(token.replace(",", "")) if token != "-" else 0.0 for token in tokens]
    columns, balance = values[-3:-1], values[-1]
    if len(columns) == 2 and (columns[0] == 0) != (columns[1] == 0):
        amount = abs(columns[0] or columns[1])
        explicit_type = "Expense" if columns[0] else "Income"
    else:
        amount = abs(values[-2])
        explicit_type = None
    return match.start(), amount, balance, explicit_type


def parse_sbi_pdf(file_path: str, password: Optional[str] = None,
                  debug: Optional[Dict] = None) -> List[Dict]:
    """Parse SBI PDF statement format (Date, Details, Debit, Credit, Balance)."""
    try:
        import pdfplumber
    except ModuleNotFoundError as exc:
        raise StatementPasswordError("SBI parser requires pdfplumber.") from exc

    ensure_pdf_password(file_path, password)

    try:
        if password:
            pdf_ctx = pdfplumber.open(file_path, password=password)
        else:
            pdf_ctx = pdfplumber.open(file_path)
    except TypeError as exc:
        raise StatementPasswordError(
            "Your pdfplumber version does not support encrypted PDFs."
        ) from exc

    with pdf_ctx as pdf:
        raw_lines = []
        for page in pdf.pages:
            text = page.extract_text() or ""
            for ln in text.split("\n"):
                line = ln.strip()
                if not line:
                    continue
                raw_lines.append(line)

    logical = []
    current = []
    for line in raw_lines:
        if _DATE_START.match(line):
            if current:
                logical.append(current)
            current = [line]
        elif _is_summary_line(line):
            if current:
                logical.append(current)
                current = []
        elif current:
            current.append(line)
    if current:
        logical.append(current)

    if debug is not None:
        debug["rows_scanned"] = len(logical)
    parsed = []
    for lines in logical:
        date_match = _DATE_START.match(lines[0])
        txn_date = _parse_date(date_match.group(1))
        if not txn_date:
            continue
        head = _strip_footer_noise(lines[0][date_match.end():])
        # SBI can wrap the narration under a complete monetary row. Prefer the
        # dated line's own tail, then allow a split tail on its continuation.
        money = _read_money_tail(head)
        if money:
            start, amount, balance, printed_direction = money
            description = " ".join([head[:start], *lines[1:]])
        else:
            combined = _strip_footer_noise(" ".join([head, *lines[1:]]))
            money = _read_money_tail(combined)
            if not money:
                continue
            start, amount, balance, printed_direction = money
            description = combined[:start]
        parsed.append((txn_date, description, amount, balance, printed_direction))

    if parsed and parsed[0][0] > parsed[-1][0]:
        parsed.reverse()
    transactions = []
    previous = None
    for txn_date, description, amount, balance, printed_direction in parsed:
        delta = round(balance - previous, 2) if previous is not None else None
        previous = balance
        if amount <= 0:
            continue
        upper = description.upper()
        if delta and abs(delta) == amount:
            txn_type = "Income" if delta > 0 else "Expense"
        else:
            txn_type = printed_direction or _infer_txn_type(upper)
        if not txn_type:
            _append_issue(debug, "SBI row has no supported debit or credit direction.")
            continue
        transactions.append({
            "transaction_date": txn_date,
            "description": _clean_description(description)[:200],
            "amount": amount,
            "transaction_type": txn_type,
            "category": _guess_category(upper, txn_type),
            "mode": _guess_mode(upper),
            "reference_no": _extract_reference_no(description),
            "balance_after": balance,
        })

    if debug is not None:
        debug["rows_extracted"] = len(transactions)

    return transactions
