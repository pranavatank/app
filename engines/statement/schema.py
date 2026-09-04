"""
engines/statement/schema.py — Canonical field names and synonym matching
"""

FIELDS = {
    "date": ["transaction date", "txn date", "tran date", "date", "value date"],
    "desc": ["particulars", "narration", "description", "particular"],
    "debit": ["withdrawal", "withdrawals", "debit"],
    "credit": ["deposit", "deposits", "credit"],
    "balance": ["closingbalance", "closing balance", "balance"],
    "ref": ["reference", "cheque", "chq"],
}


def match_field(text: str) -> str | None:
    """
    Match a text token against canonical field names.
    Returns the field key ("date", "desc", "debit", etc.) or None.
    """
    if not text:
        return None

    normalized = text.lower().strip()
    # Remove non-alphanumeric for matching (e.g., "Closing Balance" -> "closingbalance")
    normalized_compact = "".join(c for c in normalized if c.isalnum() or c.isspace())
    normalized_compact = " ".join(normalized_compact.split())  # Normalize spaces
    normalized_compact = normalized_compact.replace(" ", "")

    for field_key, synonyms in FIELDS.items():
        for synonym in synonyms:
            # Try both with-space and compact matching
            if normalized == synonym or normalized_compact == synonym.replace(" ", ""):
                return field_key

    return None
