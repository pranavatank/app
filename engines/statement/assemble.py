"""
engines/statement/assemble.py — Assemble transaction dicts from rows
"""

from datetime import datetime
from typing import Optional
import re

from engines.parser_utils import _guess_fd_category, _extract_reference_no


def parse_amount(text: str) -> Optional[float]:
    """
    Parse amount from text, stripping commas and treating parentheses as negative.

    Examples:
        "1,234.56" -> 1234.56
        "(6,057.72)" -> -6057.72
        "abc" -> None
    """
    if not text:
        return None

    text = text.strip()
    if not text:
        return None

    # Check for parentheses = negative
    negative = text.startswith("(") and text.endswith(")")

    # Clean: remove commas and parentheses
    cleaned = text.replace(",", "").replace("(", "").replace(")", "").strip()

    if not cleaned:
        return None

    try:
        value = float(cleaned)
        return -value if negative else value
    except ValueError:
        return None


def parse_date(text: str) -> Optional[str]:
    """
    Parse date from text in multiple formats, return YYYY-MM-DD.
    If text contains multiple dates, extracts the first one.

    Formats supported:
        - 30-Apr-2025
        - 01/04/2026
        - 06-09-2025
        - 2025-04-01
    """
    if not text:
        return None

    text = text.strip()

    # Try to extract the first date-like substring
    # Split by common separators and try to parse each token
    import re

    date_pattern = r"\d{1,2}[-/][A-Za-z0-9]{1,3}[-/]\d{4}|\d{4}[-/]\d{2}[-/]\d{2}"
    matches = re.findall(date_pattern, text)

    if not matches:
        return None

    # Try to parse the first match
    text = matches[0]

    # Normalize slashes to dashes
    text = text.replace("/", "-")

    formats = [
        "%d-%m-%Y",  # 01-04-2026
        "%d-%b-%Y",  # 30-Apr-2025
        "%d-%B-%Y",  # 30-April-2025
        "%Y-%m-%d",  # 2025-04-01
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(text, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return None


def _extract_cell_values(row: list[dict], columns: dict) -> dict:
    """
    Extract and normalize cell values from a single row.
    Returns: {field: text, ...} dict.
    """
    buckets = {}
    for word in row:
        field = __import__("engines.statement.columns", fromlist=["assign"]).assign(
            word, columns
        )
        if field:
            if field not in buckets:
                buckets[field] = []
            buckets[field].append(word)

    # Join each bucket's text with spaces
    cell_values = {}
    for field, words in buckets.items():
        text_parts = [w["text"] for w in sorted(words, key=lambda w: w["x0"])]
        cell_values[field] = " ".join(text_parts)

    return cell_values


def _is_anchor_row(cell_values: dict) -> bool:
    """
    Check if a row is an anchor (has date AND amount).
    """
    date_text = cell_values.get("date", "").strip()
    if not date_text:
        return False

    # Check if row has date
    date_parts = date_text.split()
    has_date = False
    for part in date_parts:
        if parse_date(part):
            has_date = True
            break

    if not has_date:
        return False

    # Check if row has amount
    debit_text = cell_values.get("debit", "").strip()
    credit_text = cell_values.get("credit", "").strip()
    debit_amount = parse_amount(debit_text) if debit_text else None
    credit_amount = parse_amount(credit_text) if credit_text else None

    # Must have at least one non-zero amount
    has_debit = debit_amount is not None and debit_amount != 0
    has_credit = credit_amount is not None and credit_amount != 0

    return has_debit or has_credit


def _is_fragment_row(cell_values: dict, is_anchor: bool) -> bool:
    """
    Check if a row is a fragment (has desc/ref text AND is not an anchor).
    """
    if is_anchor:
        return False

    desc_text = cell_values.get("desc", "").strip()
    ref_text = cell_values.get("ref", "").strip()

    return bool(desc_text or ref_text)


def assemble_transactions(
    rows: list[list[dict]],
    columns: dict,
    prev_balance: Optional[float] = None,
) -> list[dict]:
    """
    Turn rows into transaction dicts.

    Args:
        rows: List of clustered rows
        columns: Column geometry from build_columns
        prev_balance: Running balance for direction inference if needed

    Returns:
        List of transaction dicts
    """
    transactions = []
    current_balance = prev_balance

    for row in rows:
        cell_values = _extract_cell_values(row, columns)

        # Validate: date must be present and parseable
        date_text = cell_values.get("date", "").strip()
        if not date_text:
            continue

        # Fix date-column bleed: Keep only the FIRST date token, discard further dates,
        # move only non-date tokens to the front of description.
        date_parts = date_text.split()
        txn_date = None
        non_date_tokens = []

        for part in date_parts:
            test_date = parse_date(part)
            if test_date and txn_date is None:
                txn_date = test_date
            elif not test_date:
                non_date_tokens.append(part)

        # Move non-date tokens to front of description
        if non_date_tokens:
            cell_values["desc"] = " ".join(non_date_tokens) + " " + cell_values.get("desc", "")

        if not txn_date:
            continue

        # Validate: must have value in either debit or credit
        debit_text = cell_values.get("debit", "").strip()
        credit_text = cell_values.get("credit", "").strip()

        debit_amount = parse_amount(debit_text) if debit_text else None
        credit_amount = parse_amount(credit_text) if credit_text else None

        # Check if we have any valid amounts
        has_debit = debit_amount is not None
        has_credit = credit_amount is not None

        if not has_debit and not has_credit:
            continue

        if has_debit and has_credit:
            # Both columns have parseable values
            debit_zero = debit_amount == 0 if debit_amount is not None else True
            credit_zero = credit_amount == 0 if credit_amount is not None else True

            if debit_zero and credit_zero:
                continue

            if not debit_zero and credit_zero:
                amount = abs(debit_amount)
                txn_type = "Expense"
            elif debit_zero and not credit_zero:
                amount = abs(credit_amount)
                txn_type = "Income"
            else:
                continue
        elif has_debit:
            if debit_amount == 0:
                continue
            amount = abs(debit_amount)
            txn_type = "Expense"
        else:
            if credit_amount == 0:
                continue
            amount = abs(credit_amount)
            txn_type = "Income"

        # Extract description and reference
        desc_text = cell_values.get("desc", "").strip()
        description = desc_text or "Transaction"
        description_raw = description

        # Extract balance if available
        balance_text = cell_values.get("balance", "").strip()
        balance_after = parse_amount(balance_text) if balance_text else None

        # Extract reference from description
        reference_no = _extract_reference_no(description)

        # Extract and normalize account number
        deposit_account_no = normalize_account_no(description)

        # Guess category
        desc_upper = description.upper()
        category = _guess_fd_category(desc_upper, txn_type) or ("Other Income" if txn_type == "Income" else "Other Expense")

        # Guess mode
        mode = _guess_mode(description)

        transactions.append({
            "transaction_date": txn_date,
            "description": description[:200],
            "description_raw": description_raw,
            "amount": amount,
            "transaction_type": txn_type,
            "category": category,
            "mode": mode,
            "reference_no": reference_no,
            "balance_after": balance_after,
            "deposit_account_no": deposit_account_no,
        })

        if balance_after is not None:
            current_balance = balance_after

    return transactions


def _guess_mode(description: str) -> str:
    """Infer payment mode from description."""
    upper = description.upper()
    if "UPI" in upper:
        return "UPI"
    if "ATM" in upper or "CASH" in upper:
        return "Cash"
    if "CARD" in upper or "POS" in upper:
        return "Debit Card"
    return "Bank Transfer"


def normalize_account_no(text: str) -> Optional[str]:
    """
    Extract and normalize account number from text.

    Patterns:
    - Jana: 4522030015435122/1 -> 45220300154351221 (drop the /)
    - Ujjivan: 4483130330001450 -> as-is (16 digits)
    - Equitas: FD300014105382 -> 300014105382 (strip leading FD)

    Returns normalized account number or None if not found.
    """
    if not text:
        return None

    text = text.strip()

    # Try to find FD-prefixed account numbers (Equitas)
    # Pattern: FD followed by 12+ digits
    fd_match = re.search(r'\bFD(\d{12,})\b', text)
    if fd_match:
        return fd_match.group(1)

    # Try to find account with slash (Jana: 4522030015435122/1)
    # Pattern: digits, slash, digits, joined
    slash_match = re.search(r'\b(\d{16})/(\d+)\b', text)
    if slash_match:
        return slash_match.group(1) + slash_match.group(2)

    # Try to find pure numeric account numbers (Ujjivan: 4483130330001450)
    # Pattern: 16-digit number
    pure_match = re.search(r'\b(\d{16})\b', text)
    if pure_match:
        return pure_match.group(1)

    return None


def deposit_account_matches(a: Optional[str], b: Optional[str]) -> bool:
    """
    Check if two account numbers match.
    Returns True when either normalised value is a prefix of the other.

    Examples:
    - deposit_account_matches("300014105382", "3000141053821") -> True (first is prefix of second)
    - deposit_account_matches("45220300154351221", "4522030015435122/1") -> True (after normalization)
    """
    if not a or not b:
        return False

    # Normalize both
    norm_a = normalize_account_no(a) or a
    norm_b = normalize_account_no(b) or b

    # Check if either is a prefix of the other
    return norm_a.startswith(norm_b) or norm_b.startswith(norm_a)
