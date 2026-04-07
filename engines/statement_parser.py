"""
engines/statement_parser.py — PDF/Excel bank statement import (Phase 6)
"""

import json
import os
import re
import warnings
from datetime import datetime
from typing import List, Dict, Optional
from urllib import error as url_error
from urllib import request as url_request

import pdfplumber
import pandas as pd
from models.transaction import check_duplicate


_REF_PATTERNS = [
    r"\b(?:IB|SCREF|CHBATCH|MB|UTR|RRN|NEFT|IMPS)[A-Z0-9]{6,}\b",
    r"\b[A-Z0-9]{10,}/\d+\b",
    r"\b[A-F0-9]{16,}\b",
    r"\b[A-Z0-9]{12,}\b",
]


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


def _append_issue(debug: Optional[Dict], message: str, limit: int = 200) -> None:
    """Collect parse issues without allowing unbounded memory growth."""
    if debug is None:
        return
    issues = debug.setdefault("issues", [])
    if len(issues) < limit:
        issues.append(message)


# ── Bank-specific parsing templates ──────────────────────────────────────────

class BankTemplate:
    """Base class for bank-specific statement parsing."""
    
    def parse_pdf(self, file_path: str) -> List[Dict]:
        """Parse PDF statement. Override in subclass."""
        raise NotImplementedError
    
    def parse_excel(self, file_path: str) -> List[Dict]:
        """Parse Excel statement. Override in subclass."""
        raise NotImplementedError


class GenericPDFParser(BankTemplate):
    """Generic fallback parser for PDF statements."""

    def parse_pdf(self, file_path: str, debug: Optional[Dict] = None) -> List[Dict]:
        transactions = []

        try:
            with pdfplumber.open(file_path) as pdf:
                for page_no, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text()
                    if not text:
                        _append_issue(debug, f"PDF page {page_no}: no extractable text")
                        continue

                    lines = self._normalize_pdf_lines(text)
                    for line_no, line in enumerate(lines, start=1):
                        candidate_lines = self._split_compound_transaction_line(line)
                        for candidate in candidate_lines:
                            debug and debug.__setitem__("rows_scanned", debug.get("rows_scanned", 0) + 1)
                            txn, reason = self._parse_line(candidate)
                            if txn:
                                transactions.append(txn)
                            elif candidate.strip() and self._looks_like_transaction_line(candidate):
                                preview = candidate.strip()[:110]
                                _append_issue(
                                    debug,
                                    f"PDF page {page_no}, line {line_no}: {reason}; text='{preview}'"
                                )
        except Exception as e:
            _append_issue(debug, f"PDF parsing error: {e}")
            print(f"PDF parsing error: {e}")

        if debug is not None:
            debug["rows_extracted"] = len(transactions)
        return transactions

    def _normalize_pdf_lines(self, text: str) -> List[str]:
        """Merge wrapped narration/reference lines into logical rows."""
        date_re = re.compile(r"\d{2}[/-](?:\d{2}|[A-Za-z]{3})[/-]\d{4}|\d{4}-\d{2}-\d{2}")
        raw_lines = [ln.strip() for ln in (text or "").split("\n") if ln and ln.strip()]
        logical: List[str] = []

        for ln in raw_lines:
            if date_re.search(ln):
                if logical and not date_re.search(logical[-1]):
                    logical[-1] = f"{logical[-1]} {ln}".strip()
                else:
                    logical.append(ln)
            else:
                if logical:
                    logical[-1] = f"{logical[-1]} {ln}".strip()
                else:
                    logical.append(ln)
        return logical

    def _split_compound_transaction_line(self, line: str) -> List[str]:
        """Split lines that contain multiple serial/date transactions in one text row."""
        text = (line or "").strip()
        if not text:
            return []

        # Unity-like PDFs may extract multiple rows into one line:
        # ... 14 '2025-02-28 ... 15 '2025-03-01 ...
        start_re = re.compile(r"(?:^|\s)(\d+\s+'?\d{4}-\d{2}-\d{2})")
        starts = list(start_re.finditer(text))
        if not starts:
            return [text]

        parts: List[str] = []
        for idx, m in enumerate(starts):
            begin = m.start(1)
            end = starts[idx + 1].start(1) if (idx + 1) < len(starts) else len(text)
            part = text[begin:end].strip()
            if part:
                parts.append(part)

        return parts or [text]

    def _looks_like_transaction_line(self, line: str) -> bool:
        text = line.strip()
        if not text:
            return False

        if text.upper().startswith("OPENING BALANCE"):
            return False
        if re.match(r"^\(?\d[\d,]*\.\d{1,2}\)?(?:\s+\(?\d[\d,]*\.\d{1,2}\)?){2,}$", text):
            return False

        starts_with_date = re.match(r"^(?:\d+\s+)?'?\d{4}-\d{2}-\d{2}|^\d{2}[-/](?:\d{2}|[A-Za-z]{3})[-/]\d{4}", text) is not None
        has_amount = re.search(r"\(?\d[\d,]*\.\d{1,2}\)?|\(?\.\d{1,2}\)?", text) is not None
        if starts_with_date and has_amount:
            return True

        has_channel = any(k in text.upper() for k in ["UPI", "IMPS", "NEFT", "IFT", "ATM", "DEBIT", "CREDIT"])
        return has_channel and has_amount

    def _parse_amount_token(self, token: str) -> Optional[float]:
        raw = token.strip()
        if not raw:
            return None

        negative = raw.startswith("(") and raw.endswith(")")
        cleaned = raw.replace(",", "").replace("(", "").replace(")", "")
        if cleaned.startswith("."):
            cleaned = f"0{cleaned}"

        try:
            value = float(cleaned)
        except ValueError:
            return None

        return -value if negative else value

    def _parse_date(self, text: str) -> Optional[str]:
        value = text.strip().replace("/", "-")
        for fmt in ["%d-%m-%Y", "%d-%b-%Y", "%d-%B-%Y", "%Y-%m-%d"]:
            try:
                return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    def _guess_mode(self, description: str) -> str:
        upper = description.upper()
        if "UPI" in upper:
            return "UPI"
        if "ATM" in upper or "CASH" in upper:
            return "Cash"
        if "CARD" in upper or "POS" in upper:
            return "Debit Card"
        return "Bank Transfer"

    def _parse_line(self, line: str) -> tuple[Optional[Dict], str]:
        """Try to extract transaction from a line."""
        text = line.strip()
        if not text:
            return None, "empty line"

        # Strip leading serial no. and optional quote before ISO date.
        text = re.sub(r"^\d+\s+'(?=\d{4}-\d{2}-\d{2}\b)", "", text)
        text = re.sub(r"^\d+\s+(?=\d{4}-\d{2}-\d{2}\b)", "", text)
        text = re.sub(r"^'(?=\d{4}-\d{2}-\d{2}\b)", "", text)

        # Pattern with two dates near the front.
        row_match = re.match(
            r"^((?:\d{2}[-/](?:\d{2}|[A-Za-z]{3})[-/]\d{4})|(?:\d{4}-\d{2}-\d{2}))\s+"
            r"((?:\d{2}[-/](?:\d{2}|[A-Za-z]{3})[-/]\d{4})|(?:\d{4}-\d{2}-\d{2}))\s+(.+)$",
            text,
        )

        if row_match:
            txn_date = self._parse_date(row_match.group(1))
            if not txn_date:
                return None, "invalid date value"

            remainder = row_match.group(3).strip()
            amount_tokens = re.findall(r"\(?\d[\d,]*\.\d{1,2}\)?|\(?\.\d{1,2}\)?", remainder)
            if len(amount_tokens) < 2:
                return None, "expected amount and balance"

            amount_token = amount_tokens[-2]
            balance_token = amount_tokens[-1]
            amount = self._parse_amount_token(amount_token)
            if amount is None or amount == 0:
                return None, "invalid amount format"
            amount = abs(amount)

            balance_after = self._parse_amount_token(balance_token)
            amount_pos = remainder.rfind(amount_token)
            description = remainder[:amount_pos].strip() if amount_pos > 0 else "Transaction"
            if not description:
                description = "Transaction"

            txn_type = "Expense"
            upper = description.upper()
            if any(word in upper for word in ["CREDIT", "CR", "DEPOSIT", "SALARY", "INTEREST", "REDEEM", "REFUND"]):
                txn_type = "Income"

            return {
                "transaction_date": txn_date,
                "description": description[:200],
                "amount": amount,
                "transaction_type": txn_type,
                "category": self._guess_category(description, txn_type),
                "mode": self._guess_mode(description),
                "reference_no": _extract_reference_no(text),
                "balance_after": balance_after,
            }, "ok"

        # One-date row (date may appear after narration in some layouts).
        date_match = re.search(r"((?:\d{2}[/-]\d{2}[/-]\d{4})|(?:\d{4}-\d{2}-\d{2}))", text)
        if not date_match:
            return None, "missing transaction date at line start"

        txn_date = self._parse_date(date_match.group(1))
        if not txn_date:
            return None, "invalid date value"

        amount_pattern = r"(\(?[\d,]*\.\d{1,2}\)?)"
        amount_matches = list(re.finditer(amount_pattern, text))
        amounts = [m.group(1) for m in amount_matches]
        if not amounts:
            return None, "missing amount"

        parsed_amounts = [self._parse_amount_token(tok) for tok in amounts]
        if all(v is None for v in parsed_amounts):
            return None, "invalid amount format"
        parsed_abs = [abs(v) if isinstance(v, float) else None for v in parsed_amounts]

        desc_prefix = text[:date_match.start()].strip()
        desc_start = date_match.end()
        first_amount_match = amount_matches[0]
        desc_end = first_amount_match.start()
        desc_suffix = text[desc_start:desc_end].strip() if desc_end > desc_start else ""
        tail_start = amount_matches[-1].end() if amount_matches else len(text)
        desc_tail = text[tail_start:].strip(" -") if tail_start < len(text) else ""
        description = f"{desc_prefix} {desc_suffix} {desc_tail}".strip() or "Transaction"
        desc_upper = description.upper()

        amount = None
        txn_type = None
        balance_after = None

        if len(parsed_abs) >= 3 and all(isinstance(v, float) for v in parsed_abs[-3:]):
            first_val, second_val, third_val = parsed_abs[-3], parsed_abs[-2], parsed_abs[-1]
            # Typical 3-column statements: Deposit, Withdrawal, Balance.
            if first_val > 0 and second_val == 0:
                amount = first_val
                balance_after = third_val if third_val > 0 else None
            elif second_val > 0 and first_val == 0:
                amount = second_val
                balance_after = third_val if third_val > 0 else None

        if amount is None:
            positive = [v for v in parsed_abs if isinstance(v, float) and v > 0]
            if not positive:
                return None, "invalid amount format"
            amount = positive[0]

        if txn_type is None:
            expense_hint = any(k in desc_upper for k in ["DEBIT", " DR ", "WITHDRAW", "CHARGES", "GST", "TAX", "PAYIN"])
            income_hint = any(k in desc_upper for k in [
                "CREDIT", " CR ", " CR.", "INT CR", "INTEREST", " DEPOSIT", "SALARY",
                "REDEEM", "REFUND", "PAT CR", "FD CR"
            ])
            if expense_hint and not income_hint:
                txn_type = "Expense"
            elif income_hint:
                txn_type = "Income"
            else:
                txn_type = "Expense"

        if balance_after is None and len(parsed_amounts) >= 1 and isinstance(parsed_amounts[-1], float):
            balance_after = parsed_amounts[-1]

        return {
            "transaction_date": txn_date,
            "description": description[:200],
            "amount": amount,
            "transaction_type": txn_type,
            "category": self._guess_category(description, txn_type),
            "mode": self._guess_mode(description),
            "reference_no": _extract_reference_no(text),
            "balance_after": balance_after,
        }, "ok"
    
    def _guess_category(self, description: str, txn_type: str) -> str:
        """Guess category from description."""
        desc_upper = description.upper()
        
        if txn_type == "Income":
            if any(word in desc_upper for word in ["PRINC AND INT AUTO REDEEM", "AUTO REDEEM", "FD CR", "PAT CR"]):
                return "FD Maturity"
            if any(word in desc_upper for word in ["INT AUTO REDEEM", "FD INTEREST"]):
                return "FD Interest"
            if any(word in desc_upper for word in ["SALARY", "SAL"]):
                return "Salary"
            elif any(word in desc_upper for word in ["INTEREST", "INT"]):
                if any(word in desc_upper for word in ["FD", "FIXED DEPOSIT"]):
                    return "FD Interest"
                return "Savings Interest"
            return "Other Income"
        else:
            if any(word in desc_upper for word in ["ATM", "CASH"]):
                return "Cash"
            elif any(word in desc_upper for word in ["TD. GENERIC PAYIN DEBIT", "PAYIN DEBIT", "FIXED DEPOSIT", "TERM DEPOSIT"]):
                return "FD Principal"
            elif any(word in desc_upper for word in ["FOOD", "RESTAURANT", "ZOMATO", "SWIGGY"]):
                return "Food & Dining"
            elif any(word in desc_upper for word in ["FUEL", "PETROL", "DIESEL"]):
                return "Fuel"
            elif any(word in desc_upper for word in ["EMI", "LOAN"]):
                return "EMI / Loan"
            elif any(word in desc_upper for word in ["ELECTRICITY", "WATER", "GAS"]):
                return "Utilities"
            elif any(word in desc_upper for word in ["MEDICAL", "HOSPITAL", "PHARMACY"]):
                return "Medical"
            elif any(word in desc_upper for word in ["AMAZON", "FLIPKART", "SHOPPING"]):
                return "Shopping"
            return "Other Expense"


class GenericExcelParser(BankTemplate):
    """Generic fallback parser for Excel statements."""
    
    def parse_excel(self, file_path: str, debug: Optional[Dict] = None) -> List[Dict]:
        transactions = []
        
        try:
            # Try reading with different engines
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message="Workbook contains no default style, apply openpyxl's default",
                    category=UserWarning,
                )
                try:
                    df = pd.read_excel(file_path, engine='openpyxl')
                except Exception:
                    df = pd.read_excel(file_path)
            
            # Common column name variations across banks.
            date_cols = [
                'Transaction Date', 'Txn Date', 'Date', 'Value Date',
                'Posting Date', 'Tran Date'
            ]
            desc_cols = [
                'Particulars', 'Narration', 'Description', 'Details',
                'Transaction Details', 'Remarks', 'Ref Remarks'
            ]
            debit_cols = [
                'Debit', 'Withdrawal', 'Withdrawal INR', 'Debit Amount',
                'Withdrawals', 'Dr Amount', 'Money Out'
            ]
            credit_cols = [
                'Credit', 'Deposit', 'Deposits', 'Deposit INR',
                'Credit Amount', 'Cr Amount', 'Money In'
            ]
            balance_cols = [
                'Balance', 'Closing Balance', 'ClosingBalance INR',
                'Balance INR', 'Available Balance', 'Running Balance'
            ]
            amount_cols = ['Amount', 'Txn Amount', 'Transaction Amount']
            drcr_cols = ['Dr Cr', 'CR DR', 'Debit Credit', 'Type', 'Txn Type']
            ref_cols = [
                'Reference', 'Reference No', 'Reference Number',
                'Ref', 'Ref No', 'Ref No.', 'Transaction Reference',
                'UTR', 'UTR No', 'Cheque No', 'Chq No'
            ]

            df = self._prepare_dataframe(df, file_path, date_cols, desc_cols, debug)
            
            # Find actual column names
            date_col = self._find_column(df, date_cols)
            desc_col = self._find_column(df, desc_cols)
            debit_col = self._find_column(df, debit_cols)
            credit_col = self._find_column(df, credit_cols)
            balance_col = self._find_column(df, balance_cols)
            amount_col = self._find_column(df, amount_cols)
            drcr_col = self._find_column(df, drcr_cols)
            ref_col = self._find_column(df, ref_cols)

            inferred = self._infer_columns_by_content(
                df,
                {
                    "date_col": date_col,
                    "desc_col": desc_col,
                    "debit_col": debit_col,
                    "credit_col": credit_col,
                    "balance_col": balance_col,
                    "amount_col": amount_col,
                    "drcr_col": drcr_col,
                    "ref_col": ref_col,
                },
                debug,
            )
            date_col = inferred["date_col"]
            desc_col = inferred["desc_col"]
            debit_col = inferred["debit_col"]
            credit_col = inferred["credit_col"]
            balance_col = inferred["balance_col"]
            amount_col = inferred["amount_col"]
            drcr_col = inferred["drcr_col"]
            ref_col = inferred.get("ref_col")
            
            if not date_col or not desc_col:
                _append_issue(
                    debug,
                    "Excel header mapping failed: required columns date/description not found"
                )
                return transactions
            
            for idx, row in df.iterrows():
                row_num = idx + 2
                if debug is not None:
                    debug["rows_scanned"] = debug.get("rows_scanned", 0) + 1
                try:
                    # Parse date
                    date_val = row[date_col]
                    if pd.isna(date_val):
                        # Header/footer and empty lines are common in statements.
                        continue

                    if isinstance(date_val, str):
                        label_norm, _ = self._normalize_header(date_val)
                        if label_norm in ["date", "transaction date", "txn date", "value date"]:
                            continue
                    
                    txn_ts = pd.to_datetime(date_val, dayfirst=True, errors='coerce')
                    if pd.isna(txn_ts):
                        # Skip non-transaction profile rows in account-summary sections.
                        if isinstance(date_val, str) and any(ch.isalpha() for ch in date_val):
                            continue
                        _append_issue(debug, f"Excel row {row_num}: invalid date '{date_val}'")
                        continue
                    txn_date = txn_ts.strftime('%Y-%m-%d')
                    
                    # Get description
                    description = str(row[desc_col]) if not pd.isna(row[desc_col]) else "Transaction"
                    description = description.strip() or "Transaction"

                    reference_no = None
                    if ref_col and ref_col in row and not pd.isna(row[ref_col]):
                        ref_raw = str(row[ref_col]).strip()
                        if ref_raw and ref_raw.lower() != "nan":
                            reference_no = re.sub(r"\s+", "", ref_raw).upper()[:80]
                    if not reference_no:
                        reference_no = _extract_reference_no(description)
                    
                    # Determine amount and type
                    debit = self._to_number(row[debit_col]) if debit_col and not pd.isna(row[debit_col]) else 0.0
                    credit = self._to_number(row[credit_col]) if credit_col and not pd.isna(row[credit_col]) else 0.0
                    debit = abs(debit)
                    credit = abs(credit)
                    
                    if credit > 0:
                        amount = credit
                        txn_type = "Income"
                    elif debit > 0:
                        amount = debit
                        txn_type = "Expense"
                    elif amount_col and not pd.isna(row[amount_col]):
                        amount_value = self._to_number(row[amount_col])
                        if amount_value == 0:
                            _append_issue(debug, f"Excel row {row_num}: amount is zero")
                            continue
                        amount = abs(amount_value)
                        marker = str(row[drcr_col]).upper() if drcr_col and not pd.isna(row[drcr_col]) else ""
                        if any(k in marker for k in ["CR", "CREDIT", "DEP"]):
                            txn_type = "Income"
                        elif any(k in marker for k in ["DR", "DEBIT", "WITHDRAW"]):
                            txn_type = "Expense"
                        else:
                            txn_type = "Expense" if amount_value < 0 else "Income"
                    else:
                        _append_issue(debug, f"Excel row {row_num}: debit and credit are empty/zero")
                        continue
                    
                    # Get balance
                    balance_after = None
                    if balance_col and not pd.isna(row[balance_col]):
                        balance_after = self._to_number(row[balance_col])
                    
                    transactions.append({
                        "transaction_date": txn_date,
                        "description": description[:200],
                        "amount": float(amount),
                        "transaction_type": txn_type,
                        "category": self._guess_category(description, txn_type),
                        "mode": "Bank Transfer",
                        "reference_no": reference_no,
                        "balance_after": balance_after
                    })
                    
                except Exception as e:
                    _append_issue(debug, f"Excel row {row_num}: {e}")
                    continue
        
        except Exception as e:
            _append_issue(debug, f"Excel parsing error: {e}")
            print(f"Excel parsing error: {e}")
        
        if debug is not None:
            debug["rows_extracted"] = len(transactions)
        return transactions

    def _normalize_header(self, value) -> tuple[str, str]:
        """Return normalized and compact representations of header text."""
        text = str(value or "")
        text = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")
        text = text.replace('"', ' ')
        text = text.lower().strip()
        text = re.sub(r"[^a-z0-9]+", " ", text)
        normalized = re.sub(r"\s+", " ", text).strip()
        compact = normalized.replace(" ", "")
        return normalized, compact

    def _find_column(self, df: pd.DataFrame, possible_names: List[str]) -> Optional[str]:
        """Find best matching column name from bank-specific header variants."""
        best_col = None
        best_score = -1

        normalized_aliases = []
        for alias in possible_names:
            alias_norm, alias_compact = self._normalize_header(alias)
            if alias_norm:
                normalized_aliases.append((alias_norm, alias_compact))

        for col in df.columns:
            col_norm, col_compact = self._normalize_header(col)
            if not col_norm:
                continue
            for alias_norm, alias_compact in normalized_aliases:
                if alias_norm in col_norm or alias_compact in col_compact:
                    score = len(alias_norm)
                    if score > best_score:
                        best_score = score
                        best_col = col

        return best_col

    def _prepare_dataframe(self, df: pd.DataFrame, file_path: str,
                           date_cols: List[str], desc_cols: List[str],
                           debug: Optional[Dict] = None) -> pd.DataFrame:
        """Auto-detect header row when files use shifted or merged headers."""
        if self._find_column(df, date_cols) and self._find_column(df, desc_cols):
            return df

        try:
            try:
                raw = pd.read_excel(file_path, header=None, engine='openpyxl')
            except Exception:
                raw = pd.read_excel(file_path, header=None)
        except Exception:
            return df

        # Some bank files place transaction headers after account-profile blocks.
        max_scan_rows = min(80, len(raw.index))
        for header_idx in range(max_scan_rows):
            header_row = raw.iloc[header_idx].tolist()
            candidate_headers = ["" if pd.isna(v) else str(v) for v in header_row]
            candidate_df = raw.iloc[header_idx + 1:].copy()
            candidate_df.columns = candidate_headers

            if self._find_column(candidate_df, date_cols) and self._find_column(candidate_df, desc_cols):
                _append_issue(debug, f"Excel header auto-detected from row {header_idx + 1}")
                return candidate_df.reset_index(drop=True)

            # Some statements split header labels across two rows (e.g., Withdrawal + INR).
            if header_idx + 1 < max_scan_rows:
                next_row = raw.iloc[header_idx + 1].tolist()
                merged_headers = []
                for h, n in zip(header_row, next_row):
                    h_txt = "" if pd.isna(h) else str(h).strip()
                    n_txt = "" if pd.isna(n) else str(n).strip()
                    if h_txt and n_txt and n_txt.lower() not in h_txt.lower():
                        merged_headers.append(f"{h_txt} {n_txt}".strip())
                    else:
                        merged_headers.append(h_txt or n_txt)

                merged_df = raw.iloc[header_idx + 2:].copy()
                merged_df.columns = merged_headers
                if self._find_column(merged_df, date_cols) and self._find_column(merged_df, desc_cols):
                    _append_issue(debug, f"Excel merged-header auto-detected from rows {header_idx + 1}-{header_idx + 2}")
                    return merged_df.reset_index(drop=True)

        return df

    def _infer_columns_by_content(self, df: pd.DataFrame, resolved: Dict[str, Optional[str]],
                                  debug: Optional[Dict] = None) -> Dict[str, Optional[str]]:
        """Infer key columns from data patterns when header names are unreliable."""
        inferred = dict(resolved)
        if df.empty:
            return inferred

        sample = df.head(250)

        def date_ratio(series: pd.Series) -> float:
            values = [v for v in series.tolist() if not pd.isna(v)]
            if not values:
                return 0.0
            parsed = pd.to_datetime(values, dayfirst=True, errors='coerce')
            ok = parsed.notna().sum()
            return ok / max(1, len(values))

        def text_score(series: pd.Series) -> float:
            vals = [str(v).strip() for v in series.tolist() if not pd.isna(v)]
            vals = [v for v in vals if v]
            if not vals:
                return 0.0
            alpha = sum(any(ch.isalpha() for ch in v) for v in vals)
            avg_len = sum(len(v) for v in vals) / len(vals)
            return (alpha / len(vals)) * min(avg_len / 12.0, 1.0)

        def numeric_ratio(series: pd.Series) -> float:
            vals = [v for v in series.tolist() if not pd.isna(v)]
            if not vals:
                return 0.0
            nums = sum(1 for v in vals if abs(self._to_number(v)) > 0)
            return nums / max(1, len(vals))

        cols = list(sample.columns)

        def usable_column(col_name) -> bool:
            norm, _ = self._normalize_header(col_name)
            if not norm:
                return False
            if norm.startswith("unnamed"):
                return False
            return True

        cols = [c for c in cols if usable_column(c)]
        if not cols:
            cols = list(sample.columns)

        if "ref_col" not in inferred:
            inferred["ref_col"] = resolved.get("ref_col")

        if inferred.get("date_col") is None:
            best_col = None
            best_ratio = 0.0
            for col in cols:
                ratio = date_ratio(sample[col])
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_col = col
            if best_col is not None and best_ratio >= 0.30:
                inferred["date_col"] = best_col
                _append_issue(debug, f"Excel inferred date column from content: '{best_col}'")

        if inferred.get("desc_col") is None:
            best_col = None
            best_score = 0.0
            for col in cols:
                if col == inferred.get("date_col"):
                    continue
                score = text_score(sample[col])
                if score > best_score:
                    best_score = score
                    best_col = col
            if best_col is not None and best_score >= 0.25:
                inferred["desc_col"] = best_col
                _append_issue(debug, f"Excel inferred description column from content: '{best_col}'")

        numeric_candidates = []
        for col in cols:
            if col in [inferred.get("date_col"), inferred.get("desc_col")]:
                continue
            ratio = numeric_ratio(sample[col])
            if ratio >= 0.20:
                numeric_candidates.append((col, ratio))
        numeric_candidates.sort(key=lambda x: x[1], reverse=True)

        if inferred.get("balance_col") is None and numeric_candidates:
            inferred["balance_col"] = numeric_candidates[0][0]

        remaining_numeric = [c for c, _ in numeric_candidates if c != inferred.get("balance_col")]

        if inferred.get("debit_col") is None and remaining_numeric:
            inferred["debit_col"] = remaining_numeric[0]
        if inferred.get("credit_col") is None and len(remaining_numeric) > 1:
            inferred["credit_col"] = remaining_numeric[1]
        if inferred.get("amount_col") is None and remaining_numeric:
            inferred["amount_col"] = remaining_numeric[0]

        return inferred

    def _to_number(self, value) -> float:
        """Parse numeric values from mixed bank formats (comma, parenthesis, DR/CR)."""
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)

        text = str(value).strip()
        if not text:
            return 0.0

        upper = text.upper()
        negative = False
        if "(" in upper and ")" in upper:
            negative = True
        if " DR" in upper or upper.endswith("DR"):
            negative = True

        cleaned = upper
        cleaned = cleaned.replace("INR", "").replace("RS.", "").replace("RS", "")
        cleaned = cleaned.replace("CR", "").replace("DR", "")
        cleaned = cleaned.replace(",", "").replace("(", "").replace(")", "").strip()
        if cleaned.startswith("."):
            cleaned = f"0{cleaned}"

        match = re.search(r"-?\d*\.?\d+", cleaned)
        if not match:
            return 0.0

        number = float(match.group(0))
        if negative and number > 0:
            number = -number
        return number
    
    def _guess_category(self, description: str, txn_type: str) -> str:
        """Guess category from description."""
        desc_upper = description.upper()
        
        if txn_type == "Income":
            if any(word in desc_upper for word in ["SALARY", "SAL"]):
                return "Salary"
            elif any(word in desc_upper for word in ["INTEREST", "INT"]):
                return "Savings Interest"
            return "Other Income"
        else:
            if any(word in desc_upper for word in ["ATM", "CASH"]):
                return "Cash"
            elif any(word in desc_upper for word in ["FOOD", "RESTAURANT", "ZOMATO", "SWIGGY"]):
                return "Food & Dining"
            elif any(word in desc_upper for word in ["FUEL", "PETROL", "DIESEL"]):
                return "Fuel"
            elif any(word in desc_upper for word in ["EMI", "LOAN"]):
                return "EMI / Loan"
            elif any(word in desc_upper for word in ["ELECTRICITY", "WATER", "GAS"]):
                return "Utilities"
            elif any(word in desc_upper for word in ["MEDICAL", "HOSPITAL", "PHARMACY"]):
                return "Medical"
            elif any(word in desc_upper for word in ["AMAZON", "FLIPKART", "SHOPPING"]):
                return "Shopping"
            return "Other Expense"


class LocalAIStatementParser:
    """Offline parser that uses a local Ollama model to extract transactions."""

    def __init__(self):
        self.endpoint = os.getenv("OLLAMA_ENDPOINT", "http://127.0.0.1:11434")
        self.model = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
        self.timeout_seconds = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "12"))

    def parse_statement(self, file_path: str, file_type: str, debug: Optional[Dict] = None) -> List[Dict]:
        text = self._extract_text(file_path, file_type)
        if not text:
            _append_issue(debug, "AI parser: no text could be extracted from source file")
            return []

        if debug is not None:
            debug["rows_scanned"] = debug.get("rows_scanned", 0) + len([l for l in text.splitlines() if l.strip()])

        prompt = self._build_prompt(text)
        raw = self._call_ollama(prompt, debug)
        if not raw:
            _append_issue(debug, "AI parser: model returned no transaction objects")
            return []

        return self._normalize_transactions(raw, debug)

    def _extract_text(self, file_path: str, file_type: str) -> str:
        if file_type.upper() == "PDF":
            return self._extract_pdf_text(file_path)
        if file_type.upper() in ["EXCEL", "XLS", "XLSX"]:
            return self._extract_excel_text(file_path)
        return ""

    def _extract_pdf_text(self, file_path: str) -> str:
        pages = []
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    if text.strip():
                        pages.append(text)
        except Exception:
            return ""
        return "\n\n".join(pages)

    def _extract_excel_text(self, file_path: str) -> str:
        try:
            try:
                df = pd.read_excel(file_path, engine="openpyxl")
            except Exception:
                df = pd.read_excel(file_path)
        except Exception:
            return ""

        # Keep prompt size bounded for smaller local models.
        df = df.head(1500)
        header = " | ".join([str(c) for c in df.columns])
        rows = []
        for _, row in df.iterrows():
            values = ["" if pd.isna(v) else str(v) for v in row.values]
            rows.append(" | ".join(values))
        return "\n".join([header] + rows)

    def _build_prompt(self, statement_text: str) -> str:
        return f"""
You are an expert bank statement extraction system.
Extract all transactions from the text below.

Return ONLY JSON in this exact structure:
{{
  "transactions": [
    {{
      "transaction_date": "YYYY-MM-DD",
      "description": "string",
      "amount": 123.45,
      "transaction_type": "Income or Expense",
      "category": "string",
      "mode": "Bank Transfer or UPI or Cash or Card",
      "balance_after": null
    }}
  ]
}}

Rules:
- Include all valid transactions.
- If date format is ambiguous, prefer DD/MM/YYYY interpretation.
- Amount must be positive numeric.
- transaction_type must be exactly "Income" or "Expense".
- If category unknown, use "Other Income" for income and "Other Expense" for expense.
- If mode unknown, use "Bank Transfer".
- If running balance unavailable, use null.
- Do not include markdown or explanations.

STATEMENT_TEXT_START
{statement_text[:60000]}
STATEMENT_TEXT_END
""".strip()

    def _call_ollama(self, prompt: str, debug: Optional[Dict] = None) -> List[Dict]:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }

        req = url_request.Request(
            url=f"{self.endpoint}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:
            with url_request.urlopen(req, timeout=self.timeout_seconds) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except (url_error.URLError, TimeoutError, json.JSONDecodeError) as e:
            _append_issue(debug, f"AI parser request failed: {e}")
            return []

        model_text = body.get("response", "")
        if not model_text:
            _append_issue(debug, "AI parser response missing 'response' payload")
            return []

        try:
            parsed = json.loads(model_text)
        except json.JSONDecodeError as e:
            preview = model_text[:180].replace("\n", " ")
            _append_issue(debug, f"AI parser produced non-JSON output: {e}; preview='{preview}'")
            return []

        txns = parsed.get("transactions", [])
        if not isinstance(txns, list):
            _append_issue(debug, "AI parser JSON missing 'transactions' list")
            return []
        return txns

    def _normalize_transactions(self, transactions: List[Dict], debug: Optional[Dict] = None) -> List[Dict]:
        cleaned = []

        for index, item in enumerate(transactions, start=1):
            if not isinstance(item, dict):
                _append_issue(debug, f"AI row {index}: object is not a transaction dictionary")
                continue

            txn_date = self._normalize_date(item.get("transaction_date"))
            amount = self._normalize_amount(item.get("amount"))
            txn_type = str(item.get("transaction_type", "")).strip().title()
            description = str(item.get("description", "Transaction")).strip()[:200]

            if txn_type not in ["Income", "Expense"]:
                _append_issue(debug, f"AI row {index}: invalid transaction_type '{item.get('transaction_type')}'")
                continue
            if not txn_date or amount is None or amount <= 0:
                _append_issue(
                    debug,
                    f"AI row {index}: invalid date/amount (date='{item.get('transaction_date')}', amount='{item.get('amount')}')"
                )
                continue

            category = str(item.get("category") or "").strip()
            if not category:
                category = "Other Income" if txn_type == "Income" else "Other Expense"

            mode = str(item.get("mode") or "Bank Transfer").strip()
            balance_after = self._normalize_amount(item.get("balance_after"))

            cleaned.append({
                "transaction_date": txn_date,
                "description": description or "Transaction",
                "amount": amount,
                "transaction_type": txn_type,
                "category": category,
                "mode": mode,
                "balance_after": balance_after
            })

        if debug is not None:
            debug["rows_extracted"] = len(cleaned)
        return cleaned

    def _normalize_date(self, value) -> Optional[str]:
        if value is None:
            return None

        text = str(value).strip()
        if not text:
            return None

        try:
            return pd.to_datetime(text, dayfirst=True).strftime("%Y-%m-%d")
        except Exception:
            return None

    def _normalize_amount(self, value) -> Optional[float]:
        if value is None:
            return None

        if isinstance(value, (int, float)):
            return float(value)

        text = str(value).strip().replace(",", "")
        if not text:
            return None

        match = re.search(r"-?\d+(?:\.\d+)?", text)
        if not match:
            return None

        try:
            return float(match.group(0))
        except Exception:
            return None


# ── Main parser interface ─────────────────────────────────────────────────────

def parse_statement_with_debug(file_path: str, file_type: str, bank_name: str = "Generic") -> tuple[List[Dict], Dict]:
    """
    Parse bank statement and return list of transactions with diagnostics.
    
    Args:
        file_path: Path to statement file
        file_type: "PDF" or "Excel"
        bank_name: Bank name for template selection
    
    Returns:
        (transactions, debug_info)
    """
    parser_mode = os.getenv("STATEMENT_PARSER_MODE", "auto").strip().lower()
    debug_info: Dict = {
        "mode_requested": parser_mode,
        "mode_used": "",
        "attempts": [],
        "issues": []
    }

    if parser_mode in ["ai", "auto"]:
        ai_parser = LocalAIStatementParser()
        ai_debug: Dict = {"issues": [], "rows_scanned": 0, "rows_extracted": 0}
        ai_transactions = ai_parser.parse_statement(file_path, file_type, ai_debug)
        debug_info["attempts"].append({
            "mode": "ai",
            "rows_scanned": ai_debug.get("rows_scanned", 0),
            "rows_extracted": ai_debug.get("rows_extracted", len(ai_transactions)),
            "issues": ai_debug.get("issues", [])
        })
        if ai_transactions:
            debug_info["mode_used"] = "ai"
            debug_info["issues"].extend(ai_debug.get("issues", []))
            return ai_transactions, debug_info
        if parser_mode == "ai":
            debug_info["mode_used"] = "ai"
            debug_info["issues"].extend(ai_debug.get("issues", []))
            return [], debug_info
    
    if file_type.upper() == "PDF":
        parser = GenericPDFParser()
        rule_debug: Dict = {"issues": [], "rows_scanned": 0, "rows_extracted": 0}
        transactions = parser.parse_pdf(file_path, rule_debug)
        debug_info["mode_used"] = "rule-pdf"
        debug_info["attempts"].append({
            "mode": "rule-pdf",
            "rows_scanned": rule_debug.get("rows_scanned", 0),
            "rows_extracted": rule_debug.get("rows_extracted", len(transactions)),
            "issues": rule_debug.get("issues", [])
        })
        debug_info["issues"].extend(rule_debug.get("issues", []))
        return transactions, debug_info
    elif file_type.upper() in ["EXCEL", "XLS", "XLSX"]:
        parser = GenericExcelParser()
        rule_debug = {"issues": [], "rows_scanned": 0, "rows_extracted": 0}
        transactions = parser.parse_excel(file_path, rule_debug)
        debug_info["mode_used"] = "rule-excel"
        debug_info["attempts"].append({
            "mode": "rule-excel",
            "rows_scanned": rule_debug.get("rows_scanned", 0),
            "rows_extracted": rule_debug.get("rows_extracted", len(transactions)),
            "issues": rule_debug.get("issues", [])
        })
        debug_info["issues"].extend(rule_debug.get("issues", []))
        return transactions, debug_info
    else:
        debug_info["mode_used"] = "unsupported-file-type"
        debug_info["issues"].append(f"Unsupported file type '{file_type}'")
        return [], debug_info


def parse_statement(file_path: str, file_type: str, bank_name: str = "Generic") -> List[Dict]:
    """Backward-compatible parser that returns only transactions."""
    transactions, _ = parse_statement_with_debug(file_path, file_type, bank_name)
    return transactions


def filter_duplicates(transactions: List[Dict], account_id: int) -> tuple[List[Dict], int]:
    """
    Filter out duplicate transactions.
    
    Returns:
        (unique_transactions, duplicate_count)
    """
    unique = []
    duplicate_count = 0
    
    for txn in transactions:
        is_dup = check_duplicate(
            account_id,
            txn["transaction_date"],
            txn["amount"],
            txn["description"]
        )
        
        if not is_dup:
            unique.append(txn)
        else:
            duplicate_count += 1
    
    return unique, duplicate_count


def validate_transactions(transactions: List[Dict]) -> tuple[List[Dict], List[str]]:
    """
    Validate parsed transactions.
    
    Returns:
        (valid_transactions, error_messages)
    """
    valid = []
    errors = []
    
    for idx, txn in enumerate(transactions):
        # Check required fields
        if not txn.get("transaction_date"):
            errors.append(f"Row {idx+1}: Missing date")
            continue
        
        if not txn.get("amount") or txn["amount"] <= 0:
            errors.append(f"Row {idx+1}: Invalid amount")
            continue
        
        if not txn.get("transaction_type"):
            errors.append(f"Row {idx+1}: Missing transaction type")
            continue
        
        valid.append(txn)
    
    return valid, errors
