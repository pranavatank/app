"""
engines/statement/assemble.py — Assemble transaction dicts from rows
"""

from datetime import datetime
from typing import Optional

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
        # Bucket words by column
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

        # Validate: date must be present and parseable
        date_text = cell_values.get("date", "").strip()
        if not date_text:
            continue

        # Fix date-column bleed: Jana's narration starts left of header center,
        # so first narration word lands in date bucket. Keep only the leading date token,
        # move remaining tokens to description.
        date_parts = date_text.split()
        txn_date = None
        for i, part in enumerate(date_parts):
            test_date = parse_date(part)
            if test_date:
                txn_date = test_date
                # Move remaining parts to description
                if i > 0:
                    extra_tokens = date_parts[:i]
                    cell_values["desc"] = " ".join(extra_tokens) + " " + cell_values.get("desc", "")
                if i < len(date_parts) - 1:
                    extra_tokens = date_parts[i + 1:]
                    cell_values["desc"] = " ".join(extra_tokens) + " " + cell_values.get("desc", "")
                break

        if not txn_date:
            continue

        # Validate: must have value in either debit or credit
        debit_text = cell_values.get("debit", "").strip()
        credit_text = cell_values.get("credit", "").strip()

        debit_amount = parse_amount(debit_text) if debit_text else None
        credit_amount = parse_amount(credit_text) if credit_text else None

        # RULE 1: When BOTH columns carry a value, the NON-ZERO one wins
        # - both present and exactly one non-zero -> that column decides direction+amount
        # - both present and both zero -> skip the row
        # - exactly one present -> that column decides
        # - neither present -> skip the row

        # Check if we have any valid amounts
        has_debit = debit_amount is not None
        has_credit = credit_amount is not None

        if not has_debit and not has_credit:
            # Neither column has a parseable value
            continue

        if has_debit and has_credit:
            # Both columns have parseable values
            debit_zero = debit_amount == 0 if debit_amount is not None else True
            credit_zero = credit_amount == 0 if credit_amount is not None else True

            if debit_zero and credit_zero:
                # Both are zero -> skip row
                continue

            if not debit_zero and credit_zero:
                # Only debit is non-zero -> Expense
                amount = abs(debit_amount)
                txn_type = "Expense"
            elif debit_zero and not credit_zero:
                # Only credit is non-zero -> Income
                amount = abs(credit_amount)
                txn_type = "Income"
            else:
                # Both are non-zero (shouldn't happen normally)
                # Reject this row as it's ambiguous
                continue
        elif has_debit:
            # Only debit column present
            if debit_amount == 0:
                continue
            amount = abs(debit_amount)
            txn_type = "Expense"
        else:
            # Only credit column present
            if credit_amount == 0:
                continue
            amount = abs(credit_amount)
            txn_type = "Income"

        # Extract description and reference
        desc_text = cell_values.get("desc", "").strip()
        description = desc_text or "Transaction"

        # Extract balance if available
        balance_text = cell_values.get("balance", "").strip()
        balance_after = parse_amount(balance_text) if balance_text else None

        # Extract reference from description
        reference_no = _extract_reference_no(description)

        # Guess category (can use narration)
        desc_upper = description.upper()
        category = _guess_fd_category(desc_upper, txn_type) or "Other Income" if txn_type == "Income" else "Other Expense"

        # Guess mode
        mode = _guess_mode(description)

        transactions.append({
            "transaction_date": txn_date,
            "description": description[:200],
            "amount": amount,
            "transaction_type": txn_type,
            "category": category,
            "mode": mode,
            "reference_no": reference_no,
            "balance_after": balance_after,
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
