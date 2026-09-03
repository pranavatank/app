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


def _parse_amount_tokens(tokens: List[float]) -> tuple[Optional[float], Optional[float], Optional[float]]:
    if not tokens:
        return None, None, None

    if len(tokens) >= 3:
        debit_val, credit_val, balance = tokens[-3], tokens[-2], tokens[-1]
        return debit_val, credit_val, balance

    if len(tokens) == 2:
        amount, balance = tokens[0], tokens[1]
        return amount, None, balance

    if len(tokens) == 1:
        return tokens[0], None, None

    return None, None, None


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

    date_re = re.compile(r"^\s*(\d{2}[/-]\d{2}[/-]\d{2,4})\b")
    rows: List[str] = []
    current = ""

    for line in raw_lines:
        if _is_summary_line(line):
            continue

        if date_re.match(line):
            if current:
                rows.append(current.strip())
            current = line
        else:
            if current:
                current = f"{current} {line}".strip()
            else:
                # Skip stray lines before first date
                continue

    if current:
        rows.append(current.strip())

    transactions = []
    if debug is not None:
        debug["rows_scanned"] = len(rows)

    amount_re = re.compile(r"\d{1,3}(?:,\d{3})*(?:\.\d{1,2})")

    prev_balance: Optional[float] = None

    for row in rows:
        cleaned = _strip_footer_noise(row)
        if not cleaned:
            continue

        date_match = date_re.match(cleaned)
        if not date_match:
            _append_issue(debug, f"SBI row missing date: '{cleaned[:120]}'")
            continue

        date_text = date_match.group(1)
        txn_date = _parse_date(date_text)
        if not txn_date:
            _append_issue(debug, f"SBI row invalid date: '{date_text}'")
            continue

        details = cleaned[date_match.end():].strip()
        if not details:
            _append_issue(debug, f"SBI row missing details: '{cleaned[:120]}'")
            continue

        if _is_summary_line(details):
            continue

        desc_upper = details.upper()
        inferred_type = _infer_txn_type(desc_upper)

        tokens = [
            float(tok.replace(",", ""))
            for tok in amount_re.findall(details)
        ]
        debit, credit, balance = _parse_amount_tokens(tokens)

        txn_type = None
        amount: Optional[float] = None

        # Prefer balance delta when possible (most reliable for SBI PDFs).
        if balance is not None and prev_balance is not None:
            delta = balance - prev_balance
            if abs(delta) > 0.005:
                txn_type = "Income" if delta > 0 else "Expense"
                amount = abs(delta)
        elif balance is not None and prev_balance is None:
            # First transaction - if balance > 0, it's likely a credit
            if balance > 0:
                # Check if we have debit/credit columns
                if len(tokens) >= 3:
                    # tokens = [debit, credit, balance]
                    debit_val = tokens[-3] if tokens[-3] > 0 else 0
                    credit_val = tokens[-2] if tokens[-2] > 0 else 0
                    if credit_val > 0 and debit_val == 0:
                        txn_type = "Income"
                        amount = credit_val
                    elif debit_val > 0 and credit_val == 0:
                        txn_type = "Expense"
                        amount = debit_val

        # If delta unavailable, fall back to markers and nearby amount token.
        if amount is None:
            txn_type = inferred_type
            if txn_type is None:
                txn_type = "Expense"

            if len(tokens) >= 3:
                # Try to use debit/credit columns
                debit_val = tokens[-3] if len(tokens) >= 3 and tokens[-3] > 0 else 0
                credit_val = tokens[-2] if len(tokens) >= 2 and tokens[-2] > 0 else 0
                if credit_val > 0 and debit_val == 0:
                    amount = credit_val
                    txn_type = "Income"
                elif debit_val > 0 and credit_val == 0:
                    amount = debit_val
                    txn_type = "Expense"
                elif len(tokens) >= 2:
                    amount = tokens[-2]
            elif len(tokens) >= 2:
                amount = tokens[-2]
            elif tokens:
                amount = tokens[-1]

        if amount is None or amount <= 0:
            _append_issue(debug, f"SBI row missing amount: '{details[:120]}'")
            continue

        # Clean description
        clean_desc = _clean_description(details)

        transactions.append({
            "transaction_date": txn_date,
            "description": clean_desc[:200],
            "amount": float(amount),
            "transaction_type": txn_type,
            "category": _guess_category(desc_upper, txn_type),
            "mode": _guess_mode(desc_upper),
            "reference_no": _extract_reference_no(details),
            "balance_after": balance,
        })

        if balance is not None:
            prev_balance = balance

    if debug is not None:
        debug["rows_extracted"] = len(transactions)

    return transactions
