"""Pure validation helpers for the document rebuild preflight."""
import re
from datetime import date
from decimal import Decimal, InvalidOperation


def finite_money(value, label):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{label} is not numeric") from None
    if not number.is_finite():
        raise ValueError(f"{label} is not finite")
    return number


def require_master_credential(present):
    """Readiness requires a usable credential; never include its value in errors."""
    if not present:
        raise ValueError("master credential is unavailable")


def validate_person_seed(name, pan, expected_first_name="Pranav"):
    """Validate the confirmed first name while retaining the full legal name."""
    if not isinstance(name, str) or not name.split() or name.split()[0].casefold() != expected_first_name.casefold():
        raise ValueError("26AS person name does not match the confirmed Pranav seed")
    if not isinstance(pan, str) or not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", pan):
        raise ValueError("26AS has no valid person PAN")


def validate_statement_rows(txns, balance_audit=None):
    """Return the inferred opening balance or raise if ledger rows are incomplete."""
    if not txns:
        raise ValueError("parser returned no transactions")
    required = {"transaction_date", "transaction_type", "amount", "balance_after", "category", "description"}
    previous_date = None
    previous_balance = None
    opening_balance = None
    inferred_rows = []
    for idx, txn in enumerate(txns):
        missing = required - set(txn)
        if missing:
            raise ValueError(f"transaction {idx} missing required fields: {sorted(missing)}")
        if txn["transaction_type"] not in {"Income", "Expense"}:
            raise ValueError(f"transaction {idx} has an unsupported transaction type")
        amount = finite_money(txn["amount"], f"transaction {idx} amount")
        if amount < 0:
            raise ValueError(f"transaction {idx} amount is negative")
        raw_date = txn["transaction_date"]
        try:
            parsed_date = date.fromisoformat(raw_date)
            if parsed_date.isoformat() != raw_date:
                raise ValueError
        except (TypeError, ValueError):
            raise ValueError(f"transaction {idx} has no valid ISO date") from None
        if previous_date is not None and parsed_date < previous_date:
            raise ValueError(f"transaction {idx} is out of chronological order")
        signed_amount = amount if txn["transaction_type"] == "Income" else -amount
        if txn["balance_after"] is None:
            # Internal blank balances can be checked across a bounded span.
            # Both ends must be source-reported balances; never invent an
            # opening/closing anchor or modify the parser's raw transactions.
            if idx == 0 or idx == len(txns) - 1:
                raise ValueError(f"transaction {idx} has no reported boundary balance")
            balance = previous_balance + signed_amount
            inferred_rows.append({
                "index": idx,
                "transaction_date": raw_date,
                "derived_balance_after": float(balance),
                "previous_reported_index": next(
                    j for j in range(idx - 1, -1, -1)
                    if txns[j]["balance_after"] is not None
                ),
                "next_reported_index": None,
            })
        else:
            balance = finite_money(txn["balance_after"], f"transaction {idx} balance")
        if previous_balance is None:
            opening_balance = balance - signed_amount
        elif abs(previous_balance + signed_amount - balance) > Decimal("0.01"):
            raise ValueError(f"transaction {idx} running balance does not reconcile")
        if txn["balance_after"] is not None:
            for inferred in reversed(inferred_rows):
                if inferred["next_reported_index"] is not None:
                    break
                inferred["next_reported_index"] = idx
        previous_balance = balance
        previous_date = parsed_date
    if balance_audit is not None:
        balance_audit.update({
            "reported_balance_count": len(txns) - len(inferred_rows),
            "derived_internal_balances": inferred_rows,
        })
    return float(opening_balance)


def normalize_assessment_year(value):
    """Validate the parsed 26AS year instead of deriving it from today's date."""
    if not isinstance(value, str) or not re.fullmatch(r"\s*(?:19|20)\d{2}\s*[-/\u2013]\s*(?:(?:19|20)\d{2}|\d{2})\s*", value):
        raise ValueError("26AS has no valid assessment year")
    return assessment_year_fields("Assessment Year: " + value)["assessment_year"]


def matching_document_year_fields(header_text, expected_assessment_year):
    expected = normalize_assessment_year(expected_assessment_year)
    fields = assessment_year_fields(header_text)
    if fields["assessment_year"] != expected:
        raise ValueError("PDF year does not agree with 26AS year")
    return fields


def assessment_year_fields(header_text):
    """Extract an explicitly labeled AY/FY from a document header."""
    match = re.search(
        r"\b(?P<label>assessment\s+year|financial\s+year)\b\s*[:\-]?\s*"
        r"(?P<start>(?:19|20)\d{2})\s*[-/–]\s*"
        r"(?P<end>(?:19|20)\d{2}|\d{2})(?!\d)",
        header_text or "",
        flags=re.IGNORECASE,
    )
    if not match:
        raise ValueError("explicit assessment/financial year label not found in PDF header")
    label = match.group("label").lower()
    start = int(match.group("start"))
    end = int(match.group("end"))
    if end < 100:
        end += (start // 100) * 100
        if end < start:
            end += 100
    if end != start + 1:
        raise ValueError("PDF header year span is not consecutive")
    period = f"{start}-{end % 100:02d}"
    if label.startswith("financial"):
        next_start = start + 1
        return {
            "financial_year": period,
            "assessment_year": f"{next_start}-{(next_start + 1) % 100:02d}",
        }
    return {
        "assessment_year": period,
        "financial_year": f"{start - 1}-{start % 100:02d}",
    }
