"""
engines/statement/validate.py — Transaction validation
"""

from datetime import datetime
from typing import Optional


class LowConfidenceParse(Exception):
    """Raised when parsed transactions have confidence below threshold."""

    def __init__(self, confidence: float, failing_rows: list[dict]):
        self.confidence = confidence
        self.failing_rows = failing_rows
        super().__init__(
            f"Low confidence parse: {confidence:.1%} (failing rows: {len(failing_rows)})"
        )


def direction_errors(transactions: list[dict]) -> tuple[int, int]:
    """
    Validate transaction directions using the balance-delta rule.

    A row is "tied" when abs(abs(balance_delta) - amount) < 0.02 and amount > 0.
    Returns tuple (tied_count, wrong_count).

    Args:
        transactions: List of transaction dicts with transaction_type, amount, balance_after

    Returns:
        (tied, wrong) where:
            tied = number of balance-tied rows
            wrong = number of rows with wrong direction (tied but opposite sign)
    """
    tied = 0
    wrong = 0

    for i, txn in enumerate(transactions):
        if txn.get("balance_after") is None:
            continue

        # Need previous balance for delta
        if i == 0:
            continue

        prev_txn = transactions[i - 1]
        prev_balance = prev_txn.get("balance_after")
        if prev_balance is None:
            continue

        current_balance = txn["balance_after"]
        amount = txn.get("amount", 0)
        txn_type = txn.get("transaction_type", "Expense")

        if amount <= 0:
            continue

        # Calculate delta
        delta = current_balance - prev_balance

        # Check if balance-tied: abs(abs(delta) - amount) < 0.02
        if abs(abs(delta) - amount) < 0.02:
            tied += 1

            # Check if direction is wrong
            # If delta > 0 (balance increased), should be Income; if delta < 0, should be Expense
            if delta > 0 and txn_type == "Expense":
                wrong += 1
            elif delta < 0 and txn_type == "Income":
                wrong += 1

    return (tied, wrong)


def _parse_transaction_date(date_str: str) -> Optional[datetime]:
    """
    Parse a transaction date string into a datetime object.
    Supports the same formats as assemble.parse_date.

    Args:
        date_str: Date string in format like "2025-04-01", "01-04-2026", "30-Apr-2025"

    Returns:
        datetime object or None if parsing fails
    """
    if not date_str:
        return None

    date_str = date_str.strip()

    # Import parse_date from assemble and use it, then parse the result
    from engines.statement.assemble import parse_date as assemble_parse_date

    parsed = assemble_parse_date(date_str)
    if not parsed:
        return None

    # parsed is YYYY-MM-DD format
    try:
        return datetime.strptime(parsed, "%Y-%m-%d")
    except ValueError:
        return None


def normalise_order(transactions: list[dict]) -> list[dict]:
    """
    Normalise transaction order to always be chronological ascending.

    If the list runs newest-first (descending), reverse it.
    This must be called BEFORE any balance reasoning.

    Args:
        transactions: List of transaction dicts with transaction_date

    Returns:
        Reversed list if descending, original list if ascending
    """
    if not transactions or len(transactions) < 2:
        return transactions

    first_date = _parse_transaction_date(transactions[0].get("transaction_date", ""))
    last_date = _parse_transaction_date(transactions[-1].get("transaction_date", ""))

    if not first_date or not last_date:
        return transactions

    # If first date is after last date, the list is descending -> reverse it
    if first_date > last_date:
        return list(reversed(transactions))

    return transactions


def balance_walk(transactions: list[dict]) -> list[dict]:
    """
    For every consecutive pair, report rows where balance_after delta
    does not equal +/- amount within 0.02.

    Rows with missing balance_after break the chain rather than counting as failures.

    Args:
        transactions: List of transaction dicts with amount, balance_after

    Returns:
        List of dicts with failing row info, one entry per failing row
    """
    failing_rows = []

    for i, txn in enumerate(transactions):
        if txn.get("balance_after") is None:
            # Missing balance breaks chain
            continue

        if i == 0:
            # No previous balance to compare
            continue

        prev_txn = transactions[i - 1]
        prev_balance = prev_txn.get("balance_after")
        if prev_balance is None:
            # Previous balance missing, chain broken
            continue

        current_balance = txn["balance_after"]
        amount = txn.get("amount", 0)

        if amount <= 0:
            continue

        # Calculate delta
        delta = current_balance - prev_balance

        # Check if balance ties to amount within 0.02
        if abs(abs(delta) - amount) >= 0.02:
            failing_rows.append({
                "index": i,
                "transaction_date": txn.get("transaction_date"),
                "description": txn.get("description"),
                "amount": amount,
                "delta": delta,
                "balance_after": current_balance,
                "prev_balance": prev_balance,
            })

    return failing_rows


def confidence(transactions: list[dict]) -> float:
    """
    Calculate the fraction of balance-tied rows that reconcile.

    Returns a value from 0.0 to 1.0 representing the fraction of
    balance-tied rows whose amount matches the balance delta within 0.02.

    Args:
        transactions: List of transaction dicts

    Returns:
        Confidence score (0.0 to 1.0)
    """
    if not transactions:
        return 0.0

    tied, wrong = direction_errors(transactions)

    if tied == 0:
        return 0.0

    reconciled = tied - wrong
    return reconciled / tied


def extract_control_totals(pages: list[list[dict]]) -> dict:
    """
    Extract control totals from IDFC statement.

    IDFC prints "Opening Balance | Total Debit | Total Credit | Closing Balance"
    on every page, with values beneath it on page 1.

    Args:
        pages: List of page word lists (one list per page)

    Returns:
        Dict with whatever totals are found, or empty dict
    """
    from engines.statement.rows import cluster_into_rows
    from engines.statement.columns import find_header, build_columns
    from engines.statement.assemble import parse_amount

    if not pages:
        return {}

    # Look for control totals row on first page
    first_page_rows = cluster_into_rows(pages[0])

    # Look for a row containing "Opening Balance" or "Total Debit"
    totals = {}

    for i, row in enumerate(first_page_rows):
        row_text = " ".join(w["text"] for w in row).lower()

        # Check if this row looks like control totals header
        if ("opening balance" in row_text or "total debit" in row_text) and "closing balance" in row_text:
            # This might be the header; values should be in next row
            if i + 1 < len(first_page_rows):
                values_row = first_page_rows[i + 1]
                # Try to parse amounts from the value row
                amounts = []
                for word in sorted(values_row, key=lambda w: w["x0"]):
                    amount = parse_amount(word["text"])
                    if amount is not None:
                        amounts.append(amount)

                # We expect 4 values: opening, total debit, total credit, closing
                if len(amounts) >= 2:
                    # Assume positions correspond to opening, debit, credit, closing
                    if len(amounts) >= 4:
                        totals["opening_balance"] = amounts[0]
                        totals["total_debit"] = amounts[1]
                        totals["total_credit"] = amounts[2]
                        totals["closing_balance"] = amounts[3]
                    elif len(amounts) == 3:
                        totals["total_debit"] = amounts[0]
                        totals["total_credit"] = amounts[1]
                        totals["closing_balance"] = amounts[2]
                    elif len(amounts) == 2:
                        totals["total_debit"] = amounts[0]
                        totals["total_credit"] = amounts[1]

    return totals


def reconcile_totals(transactions: list[dict], totals: dict) -> dict:
    """
    Reconcile parsed vs printed control totals.

    For IDFC: sum parsed debit/credit amounts against printed totals.

    Args:
        transactions: List of parsed transaction dicts
        totals: Dict from extract_control_totals

    Returns:
        Dict with reconciliation report
    """
    if not totals:
        return {}

    parsed_debit = sum(
        t.get("amount", 0)
        for t in transactions
        if t.get("transaction_type") == "Expense"
    )
    parsed_credit = sum(
        t.get("amount", 0)
        for t in transactions
        if t.get("transaction_type") == "Income"
    )

    result = {
        "parsed_debit": parsed_debit,
        "parsed_credit": parsed_credit,
    }

    if "total_debit" in totals:
        result["printed_debit"] = totals["total_debit"]
        result["debit_difference"] = totals["total_debit"] - parsed_debit

    if "total_credit" in totals:
        result["printed_credit"] = totals["total_credit"]
        result["credit_difference"] = totals["total_credit"] - parsed_credit

    return result
