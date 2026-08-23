"""
engines/bank_parsers/yes_bank_statement_parser.py
YES Bank PDF statement parser — uses pdfplumber table extraction so that
Withdrawals and Deposits columns are never confused.

YES Bank table columns (as extracted by pdfplumber):
  Value Date | Cheque No/ Reference No | Description | Withdrawals | Deposits | Running Balance

The "Transaction Date" column appears only in the raw text header; the table
rows carry only the Value Date, so we use that as the transaction date.
"""

import re
from datetime import datetime
from typing import Dict, List, Optional

import pdfplumber

from engines.statement_parser import (
    _extract_reference_no,
    _append_issue,
    _guess_fd_category,
)
from engines.statement_passwords import (
    StatementPasswordError,
    ensure_pdf_password,
)


_SKIP_DESCRIPTIONS = {
    "opening balance", "closing balance", "total withdrawals",
    "total deposits", "total debits", "total credits",
    "brought forward", "carried forward",
}

_HEADER_KEYWORDS = {
    "value date", "cheque no", "reference no", "description",
    "withdrawals", "deposits", "running balance", "transaction date",
}


def _parse_amount(text) -> Optional[float]:
    if text is None:
        return None
    s = str(text).strip().replace(",", "")
    if not s or s == "-":
        return None
    try:
        v = float(s)
        return v if v > 0 else None
    except ValueError:
        return None


def _parse_date(text) -> Optional[str]:
    if not text:
        return None
    s = str(text).strip()
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _is_header_row(row: list) -> bool:
    joined = " ".join(str(c or "").lower() for c in row)
    return any(kw in joined for kw in _HEADER_KEYWORDS)


def _is_skip_row(desc: str) -> bool:
    return desc.lower().strip() in _SKIP_DESCRIPTIONS


def _guess_mode(desc: str) -> str:
    u = desc.upper()
    if "UPI" in u:
        return "UPI"
    if "NEFT" in u or "RTGS" in u or "IMPS" in u:
        return "Bank Transfer"
    if "ATM" in u or "CASH" in u:
        return "Cash"
    if "CARD" in u or "POS" in u:
        return "Debit Card"
    return "Bank Transfer"


def _guess_category(desc: str, txn_type: str) -> str:
    u = desc.upper()
    fd_cat = _guess_fd_category(u, txn_type)
    if fd_cat:
        return fd_cat
    if txn_type == "Income":
        if "INTEREST" in u or "INT" in u:
            return "Savings Interest"
        if "SALARY" in u or "SAL" in u:
            return "Salary"
        if "REFUND" in u:
            return "Other Income"
        if "NEFT" in u and "CR" in u:
            return "Other Income"
        return "Other Income"
    else:
        if "CBDT" in u or "TAX" in u or "TDS" in u:
            return "Tax Payment"
        if "UPI" in u:
            return "Other Expense"
        if "ATM" in u:
            return "Cash"
        return "Other Expense"


class YESBankStatementParser:
    """Parser for YES Bank PDF statements using table extraction."""

    def parse_pdf(self, file_path: str, password: Optional[str] = None,
                  debug: Optional[Dict] = None) -> List[Dict]:
        transactions: List[Dict] = []

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
                for page_no, page in enumerate(pdf.pages, start=1):
                    tables = page.extract_tables()
                    for table in tables:
                        for row in table:
                            if debug is not None:
                                debug["rows_scanned"] = debug.get("rows_scanned", 0) + 1

                            if not row or _is_header_row(row):
                                continue

                            txn = self._parse_row(row, debug, page_no)
                            if txn:
                                transactions.append(txn)

        except StatementPasswordError:
            raise
        except Exception as e:
            _append_issue(debug, f"YES Bank parser error: {e}")

        if debug is not None:
            debug["rows_extracted"] = len(transactions)
        return transactions

    def _parse_row(self, row: list, debug: Optional[Dict], page_no: int) -> Optional[Dict]:
        # Expected columns: Value Date | Ref No | Description | Withdrawals | Deposits | Balance
        # Be tolerant of rows with fewer columns (multi-line cells merged differently)
        if len(row) < 4:
            return None

        date_raw = str(row[0] or "").strip()
        ref_raw  = str(row[1] or "").strip() if len(row) > 1 else ""
        desc_raw = str(row[2] or "").strip() if len(row) > 2 else ""
        with_raw = str(row[3] or "").strip() if len(row) > 3 else ""
        dep_raw  = str(row[4] or "").strip() if len(row) > 4 else ""
        bal_raw  = str(row[5] or "").strip() if len(row) > 5 else ""

        txn_date = _parse_date(date_raw)
        if not txn_date:
            return None

        # Clean multi-line description (pdfplumber joins with \n)
        desc = re.sub(r"\s+", " ", desc_raw.replace("\n", " ")).strip()
        if not desc or _is_skip_row(desc):
            return None

        withdrawal = _parse_amount(with_raw)
        deposit    = _parse_amount(dep_raw)
        balance    = _parse_amount(bal_raw)

        if withdrawal and not deposit:
            amount   = withdrawal
            txn_type = "Expense"
        elif deposit and not withdrawal:
            amount   = deposit
            txn_type = "Income"
        elif deposit and withdrawal:
            # Both filled — shouldn't happen but take the larger
            if deposit >= withdrawal:
                amount, txn_type = deposit, "Income"
            else:
                amount, txn_type = withdrawal, "Expense"
        else:
            _append_issue(debug, f"YES Bank page {page_no}: no amount in row date={date_raw} desc={desc[:60]}")
            return None

        # Reference number: prefer the dedicated column, fall back to description
        ref_no = ref_raw if ref_raw and ref_raw.upper() != "NA" else None
        if not ref_no:
            ref_no = _extract_reference_no(desc)
        if ref_no:
            ref_no = ref_no[:80]

        return {
            "transaction_date": txn_date,
            "description":      desc[:200],
            "amount":           amount,
            "transaction_type": txn_type,
            "category":         _guess_category(desc, txn_type),
            "mode":             _guess_mode(desc),
            "reference_no":     ref_no,
            "balance_after":    balance,
        }
