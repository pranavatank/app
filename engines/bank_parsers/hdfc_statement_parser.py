"""engines/bank_parsers/hdfc_statement_parser.py — HDFC Bank PDF statement parser.

HDFC statement format (per-page):
  Header block (account info) repeated on every page
  Column header: Date | Narration | Chq./Ref.No. | ValueDt | WithdrawalAmt. | DepositAmt. | ClosingBalance
  Transaction line: DD/MM/YY  <narration>  <16-digit-ref>  DD/MM/YY  <amount>  <closing-bal>
  Continuation lines: narration fragments (no date at start)
  Footer: HDFCBANKLIMITED / *Closing balance... / Contents...

Key quirks:
  - Date is DD/MM/YY (2-digit year), not DD/MM/YYYY
  - Ref number is always 16 digits (all zeros for interest/salary credits)
  - Only 2 amounts on each line: either (withdrawal, closing) or (deposit, closing)
  - Debit vs credit is inferred from balance delta or description keywords
  - Narration wraps across multiple continuation lines
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, List, Optional

import pdfplumber

from engines.statement_passwords import (
    StatementPasswordError,
    ensure_pdf_password,
)


# ── Inline helpers (avoid circular import with statement_parser) ──────────────

def _append_issue(debug: Optional[Dict], message: str, limit: int = 200) -> None:
    if debug is None:
        return
    issues = debug.setdefault("issues", [])
    if len(issues) < limit:
        issues.append(message)


def _extract_reference_no(text: str) -> Optional[str]:
    _REF_PATTERNS = [
        r"\b(?:IB|SCREF|CHBATCH|MB|UTR|RRN|NEFT|IMPS)[A-Z0-9]{6,}\b",
        r"\b[A-Z0-9]{10,}/\d+\b",
        r"\b[A-F0-9]{16,}\b",
        r"\b[A-Z0-9]{12,}\b",
    ]
    value = (text or "").upper().strip()
    if not value:
        return None
    matches = []
    for pattern in _REF_PATTERNS:
        matches.extend(re.findall(pattern, value))
    if not matches:
        return None
    ref = matches[-1].strip()
    return ref[:80] if len(ref) >= 8 else None


def _is_statement_summary_line(text: str) -> bool:
    upper = (text or "").upper()
    markers = [
        "STATEMENT SUMMARY", "DATE OF STATEMENT", "STATEMENT PERIOD",
        "BRANCH EMAIL", "MICR", "IFSC", "ACCOUNT NO", "ACCOUNT NUMBER",
        "CUSTOMER ID", "BROUGHT FORWARD", "TOTAL DEBITS", "TOTAL CREDITS",
        "CLOSING BALANCE", "OPENING BALANCE", "TRANSACTIONS",
        "PLEASE DO NOT SHARE", "PAGE NO",
    ]
    return any(m in upper for m in markers)


def _guess_fd_category(desc_upper: str, txn_type: str) -> Optional[str]:
    if txn_type == "Income":
        if any(w in desc_upper for w in ["PRINC AND INT AUTO REDEEM", "AUTO REDEEM", "FD CR", "PAT CR"]):
            return "FD Maturity"
        if any(w in desc_upper for w in ["INT AUTO REDEEM", "FD INTEREST"]):
            return "FD Interest"
        if "INTEREST" in desc_upper and any(w in desc_upper for w in ["FD", "FIXED DEPOSIT", "TERM DEPOSIT"]):
            return "FD Interest"
        if any(w in desc_upper for w in ["MATURITY", "MATURED", "REDEMPTION", "REDEEMED"]):
            return "FD Maturity"
    else:
        if any(w in desc_upper for w in ["TD. GENERIC PAYIN DEBIT", "PAYIN DEBIT", "FIXED DEPOSIT", "TERM DEPOSIT"]):
            return "FD Principal"
    return None

# ── Patterns ──────────────────────────────────────────────────────────────────

# DD/MM/YY at line start (HDFC uses 2-digit year)
# Ref number is 15 or 16 digits (HDFC uses 15 zeros for interest/salary)
_TXN_START = re.compile(
    r"^(\d{2}/\d{2}/\d{2})\s+"          # group 1: date DD/MM/YY
    r"(.+?)\s+"                           # group 2: narration (non-greedy)
    r"(\d{15,16})\s+"                     # group 3: 15-or-16-digit ref
    r"(\d{2}/\d{2}/\d{2})\s+"            # group 4: value date
    r"([\d,]+\.\d{2})\s+"                # group 5: first amount (withdrawal or deposit)
    r"([\d,]+\.\d{2})$"                  # group 6: closing balance
)

# Lines that are page headers / footers — skip them
_SKIP_PATTERNS = [
    re.compile(r"^PageNo\.", re.IGNORECASE),
    re.compile(r"^AccountBranch\s*:", re.IGNORECASE),
    re.compile(r"^Address\s*:", re.IGNORECASE),
    re.compile(r"^City\s*:", re.IGNORECASE),
    re.compile(r"^State\s*:", re.IGNORECASE),
    re.compile(r"^Email\s*:", re.IGNORECASE),
    re.compile(r"^A/COpenDate\s*:", re.IGNORECASE),
    re.compile(r"^JOINTHOLDERS\s*:", re.IGNORECASE),
    re.compile(r"^RTGS/NEFTIFSC\s*:", re.IGNORECASE),
    re.compile(r"^BranchCode\s*:", re.IGNORECASE),
    re.compile(r"^Nomination\s*:", re.IGNORECASE),
    re.compile(r"^From\s*:", re.IGNORECASE),
    re.compile(r"^Date\s+Narration", re.IGNORECASE),
    re.compile(r"^HDFCBANKLIMITED", re.IGNORECASE),
    re.compile(r"^\*Closingbalance", re.IGNORECASE),
    re.compile(r"^Contents", re.IGNORECASE),
    re.compile(r"^StateaccountbranchGSTN", re.IGNORECASE),
    re.compile(r"^HDFCBankGSTIN", re.IGNORECASE),
    re.compile(r"^RegisteredOffice", re.IGNORECASE),
    re.compile(r"^STATEMENTSUMMARY", re.IGNORECASE),
    re.compile(r"^OpeningBalance", re.IGNORECASE),
    re.compile(r"^ClosingBalance", re.IGNORECASE),
    re.compile(r"^TotalDebits", re.IGNORECASE),
    re.compile(r"^TotalCredits", re.IGNORECASE),
    re.compile(r"^GeneratedOn", re.IGNORECASE),
    re.compile(r"^GeneratedBy", re.IGNORECASE),
    re.compile(r"^Thisisacomputer", re.IGNORECASE),
    re.compile(r"^notrequire", re.IGNORECASE),
    re.compile(r"thisstatement", re.IGNORECASE),
    # Pure numeric summary rows (e.g. "53,322.52 415 65 599,927.42 586,316.05 39,711.15")
    re.compile(r"^[\d,\.\s]+$"),
    re.compile(r"^Phoneno\.", re.IGNORECASE),
    re.compile(r"^ODLimit\s*:", re.IGNORECASE),
    re.compile(r"^Currency\s*:", re.IGNORECASE),
    re.compile(r"^CustID\s*:", re.IGNORECASE),
    re.compile(r"^AccountNo\s*:", re.IGNORECASE),
    re.compile(r"^AccountStatus\s*:", re.IGNORECASE),
    re.compile(r"^AccountType\s*:", re.IGNORECASE),
    re.compile(r"^MICR\s*:", re.IGNORECASE),
]

_INCOME_KEYWORDS = [
    "INTEREST", "SALARY", "CREDIT", " CR ", "DEPOSIT", "NEFT CR",
    "IMPS CR", "REFUND", "CASHBACK", "DIVIDEND", "BONUS", "REVERSAL",
    "ALA/C-SALARY", "A2AINT",
]
_EXPENSE_KEYWORDS = [
    "UPI-", "ATM", "DEBIT", " DR ", "WITHDRAWAL", "WDL", "CHARGES",
    "EMI", "LOAN", "INSURANCE", "PREMIUM",
]


def _parse_hdfc_date(text: str) -> Optional[str]:
    """Parse DD/MM/YY → YYYY-MM-DD (assumes 20xx century)."""
    text = text.strip()
    try:
        dt = datetime.strptime(text, "%d/%m/%y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return None


def _parse_amount(text: str) -> float:
    return float(text.replace(",", ""))


def _is_skip_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if _is_statement_summary_line(stripped):
        return True
    for pat in _SKIP_PATTERNS:
        if pat.search(stripped):
            return True
    return False


def _infer_type(narration: str, amount: float, prev_balance: Optional[float],
                closing: float) -> str:
    upper = narration.upper()
    if any(k in upper for k in _INCOME_KEYWORDS):
        return "Income"
    if any(k in upper for k in _EXPENSE_KEYWORDS):
        return "Expense"
    # Fall back to balance delta
    if prev_balance is not None:
        delta = closing - prev_balance
        return "Income" if delta > 0 else "Expense"
    return "Expense"


def _guess_mode(narration: str) -> str:
    upper = narration.upper()
    if "UPI" in upper:
        return "UPI"
    if "ATM" in upper or "CASH" in upper:
        return "Cash"
    if "NEFT" in upper or "IMPS" in upper or "RTGS" in upper:
        return "Bank Transfer"
    if "CARD" in upper or "POS" in upper:
        return "Debit Card"
    return "Bank Transfer"


def _guess_category(narration: str, txn_type: str) -> str:
    upper = narration.upper()
    fd_cat = _guess_fd_category(upper, txn_type)
    if fd_cat:
        return fd_cat
    if txn_type == "Income":
        if "INTEREST" in upper:
            return "Savings Interest"
        if "SALARY" in upper or "ALA/C-SALARY" in upper or "A2AINT" in upper:
            return "Salary"
        if "REFUND" in upper or "REVERSAL" in upper:
            return "Refund"
        return "Other Income"
    else:
        if "ATM" in upper:
            return "Cash"
        if "ZOMATO" in upper or "SWIGGY" in upper or "FOOD" in upper:
            return "Food & Dining"
        if "PETROL" in upper or "FUEL" in upper or "PETROLEUM" in upper:
            return "Fuel"
        if "MEDICAL" in upper or "HOSPITAL" in upper or "PHARMACY" in upper or "APOLLO" in upper:
            return "Medical"
        if "AMAZON" in upper or "FLIPKART" in upper:
            return "Shopping"
        if "EMI" in upper or "LOAN" in upper:
            return "EMI / Loan"
        if "INSURANCE" in upper or "PREMIUM" in upper:
            return "Insurance"
        return "Other Expense"


class HDFCStatementParser:
    """Bank-specific parser for HDFC Bank PDF statements."""

    def parse_pdf(self, file_path: str, password: Optional[str] = None,
                  debug: Optional[Dict] = None) -> List[Dict]:
        transactions: List[Dict] = []
        prev_balance: Optional[float] = None

        try:
            ensure_pdf_password(file_path, password)
            try:
                pdf_ctx = pdfplumber.open(file_path, password=password) if password \
                    else pdfplumber.open(file_path)
            except TypeError as exc:
                raise StatementPasswordError(
                    "pdfplumber version does not support encrypted PDFs."
                ) from exc

            with pdf_ctx as pdf:
                # Collect all logical lines across all pages
                logical_lines = self._extract_logical_lines(pdf, debug)

            for line in logical_lines:
                if debug is not None:
                    debug["rows_scanned"] = debug.get("rows_scanned", 0) + 1

                m = _TXN_START.match(line.strip())
                if not m:
                    continue

                date_str, narration, ref_no, _val_dt, amount_str, closing_str = m.groups()
                txn_date = _parse_hdfc_date(date_str)
                if not txn_date:
                    _append_issue(debug, f"HDFC: invalid date '{date_str}' in line: {line[:80]}")
                    continue

                amount = _parse_amount(amount_str)
                closing = _parse_amount(closing_str)
                if amount <= 0:
                    continue

                narration = narration.strip()
                txn_type = _infer_type(narration, amount, prev_balance, closing)

                # Clean ref: all-zeros ref means no real reference
                ref = ref_no if ref_no not in ("0" * 15, "0" * 16) else None
                if not ref:
                    ref = _extract_reference_no(narration)

                transactions.append({
                    "transaction_date": txn_date,
                    "description": narration[:200],
                    "amount": amount,
                    "transaction_type": txn_type,
                    "category": _guess_category(narration, txn_type),
                    "mode": _guess_mode(narration),
                    "reference_no": ref,
                    "balance_after": closing,
                })
                prev_balance = closing

        except StatementPasswordError:
            raise
        except Exception as exc:
            _append_issue(debug, f"HDFC parser error: {exc}")

        if debug is not None:
            debug["rows_extracted"] = len(transactions)
        return transactions

    def _extract_logical_lines(self, pdf, debug: Optional[Dict]) -> List[str]:
        """
        Merge continuation lines into the transaction line they belong to.

        HDFC wraps long narrations across multiple lines. A new transaction
        always starts with DD/MM/YY. Continuation lines have no date prefix.

        The complete transaction line format is:
          DD/MM/YY <narration> <15-or-16-digit-ref> DD/MM/YY <amount> <balance>
        Continuation lines contain extra narration fragments that belong BEFORE
        the ref/amount tail, so we insert them into the narration rather than
        appending after the balance.
        """
        # Pattern to detect a complete transaction line (has ref + value-date + amounts)
        _COMPLETE = re.compile(
            r"^(\d{2}/\d{2}/\d{2})\s+(.+?)\s+(\d{15,16})\s+(\d{2}/\d{2}/\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s*$"
        )
        # Pattern to detect the tail of a complete line (ref + value-date + amounts)
        _TAIL = re.compile(r"(\d{15,16}\s+\d{2}/\d{2}/\d{2}\s+[\d,]+\.\d{2}\s+[\d,]+\.\d{2})\s*$")

        logical: List[str] = []
        current: Optional[str] = None
        current_tail_start: int = -1  # position where the tail begins in current

        for page_no, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if not text:
                _append_issue(debug, f"HDFC: page {page_no} has no extractable text")
                continue

            for raw_line in text.split("\n"):
                line = raw_line.strip()
                if not line:
                    continue
                if _is_skip_line(line):
                    continue

                # Does this line start a new transaction?
                if re.match(r"^\d{2}/\d{2}/\d{2}\s", line):
                    if current is not None:
                        logical.append(current)
                    current = line
                    # Check if this line is already complete
                    tail_m = _TAIL.search(line)
                    current_tail_start = tail_m.start() if tail_m else -1
                else:
                    # Continuation — insert into narration (before the tail) if possible
                    if current is not None:
                        if current_tail_start > 0:
                            # Insert continuation text into the narration portion
                            narration_part = current[:current_tail_start].rstrip()
                            tail_part = current[current_tail_start:]
                            current = f"{narration_part} {line} {tail_part}"
                            # Recalculate tail position
                            tail_m = _TAIL.search(current)
                            current_tail_start = tail_m.start() if tail_m else -1
                        else:
                            # No tail yet — just append and check again
                            current = current + " " + line
                            tail_m = _TAIL.search(current)
                            current_tail_start = tail_m.start() if tail_m else -1
                    # else: orphan line before first transaction — skip

        if current is not None:
            logical.append(current)

        return logical
