"""
engines/parser_utils.py — Shared parser utilities

This module holds parser helpers that are used by both statement_parser and the
bank-specific parsers (SBI, YES Bank, HDFC). It deliberately has no intra-package
imports so it cannot participate in an import cycle.
"""

import re
from typing import Dict, Optional


_REF_PATTERNS = [
    r"\b(?:IB|SCREF|CHBATCH|MB|UTR|RRN|NEFT|IMPS)[A-Z0-9]{6,}\b",
    r"\b[A-Z0-9]{10,}/\d+\b",
    r"\b[A-F0-9]{16,}\b",
    r"\b[A-Z0-9]{12,}\b",
]


def _extract_reference_no(text: str) -> Optional[str]:
    """
    Extract a reference number from text.
    Prioritizes prefixed patterns (IB/SCREF/CHBATCH/MB/UTR/RRN/NEFT/IMPS).
    For the generic pattern, requires at least one digit and rejects pure English words.
    """
    value = (text or "").upper().strip()
    if not value:
        return None

    # Try prefixed patterns first (highest priority)
    prefixed_pattern = _REF_PATTERNS[0]
    prefixed_matches = re.findall(prefixed_pattern, value)
    if prefixed_matches:
        ref = prefixed_matches[0].strip()
        if len(ref) >= 8:
            return ref[:80]

    # Try other specific patterns
    for pattern in _REF_PATTERNS[1:3]:
        matches = re.findall(pattern, value)
        if matches:
            ref = matches[0].strip()
            if len(ref) >= 8:
                return ref[:80]

    # Generic alphanumeric pattern: must contain at least one digit and not be pure English
    generic_pattern = _REF_PATTERNS[3]
    matches = re.findall(generic_pattern, value)
    if matches:
        for match in matches:
            ref = match.strip()
            # Must contain at least one digit
            if not any(c.isdigit() for c in ref):
                continue
            # Must not be a pure English word (check if all letters are in common words)
            # Simple heuristic: if it's all uppercase and has no digits, or is in a word list, skip it
            if ref.isalpha():
                # Pure alphabetic - likely a word, skip it
                continue
            if len(ref) >= 8:
                return ref[:80]

    return None


def _append_issue(debug: Optional[Dict], message: str, limit: int = 200) -> None:
    """Collect parse issues without allowing unbounded memory growth."""
    if debug is None:
        return
    issues = debug.setdefault("issues", [])
    if len(issues) < limit:
        issues.append(message)


# FD categorisation patterns, sorted by descending length (longest patterns checked first).
# This prevents shorter patterns from shadowing longer, more specific ones.
# E.g., "INT AUTO REDEEM" must match before "AUTO REDEEM" because the latter is a substring.
# The invariant: a longer, more specific phrase always wins over a shorter one it contains.
_FD_CATEGORY_PATTERNS = {
    "Income": [
        ("PRINC AND INT AUTO REDEEM", "FD Maturity"),
        ("CREDIT INTEREST CAPITALISED", "Savings Interest"),
        ("CREDIT INTEREST CAPITALIZED", "Savings Interest"),
        ("CASA CREDIT INTEREST", "Savings Interest"),
        ("INT AUTO REDEEM", "FD Interest"),
        ("CLOSURE PROCEEDS", "FD Maturity"),
        ("INTEREST ON DEPOSIT", "FD Interest"),
        ("FD INTEREST", "FD Interest"),
        ("AUTO REDEEM", "FD Maturity"),
        ("MATURITY", "FD Maturity"),
        ("MATURED", "FD Maturity"),
        ("REDEMPTION", "FD Maturity"),
        ("REDEEMED", "FD Maturity"),
        ("FD CR", "FD Maturity"),
        ("PAT CR", "FD Maturity"),
    ],
    "Expense": [
        ("TD. GENERIC PAYIN DEBIT", "FD Principal"),
        ("SMS ALERTS CHARGES", "Bank Charges"),
        ("GOODS AND SERVICES TAX", "Bank Charges"),
        ("INITIAL PAYIN", "FD Principal"),
        ("PAYIN DEBIT", "FD Principal"),
        ("FIXED DEPOSIT", "FD Principal"),
        ("TERM DEPOSIT", "FD Principal"),
        ("FD BOOKING", "FD Principal"),
        ("AMB CHARGES", "Bank Charges"),
    ],
}

# Sort by pattern length (descending) to ensure longest patterns are checked first
for txn_type in _FD_CATEGORY_PATTERNS:
    _FD_CATEGORY_PATTERNS[txn_type].sort(key=lambda x: len(x[0]), reverse=True)


def _guess_fd_category(desc_upper: str, txn_type: str) -> Optional[str]:
    """
    Shared FD-aware category detection, used by every parser path (rule-based
    PDF/Excel, bank-specific plugins, and the AI parser) so FD booking/
    maturity/interest transactions get the same category regardless of which
    parser produced them. Returns None if the description isn't FD-related —
    callers fall back to their own generic category logic in that case.

    Patterns are checked in descending order of length to ensure specific patterns
    always match before short substrings. E.g., "INT AUTO REDEEM" matches before
    "AUTO REDEEM" (which is a substring), and both match before generic "INTEREST".
    """
    patterns = _FD_CATEGORY_PATTERNS.get(txn_type, [])
    for pattern, category in patterns:
        if pattern in desc_upper:
            return category

    # Special case: "INTEREST" in Income transactions with FD/TERM DEPOSIT keywords
    if txn_type == "Income" and "INTEREST" in desc_upper:
        if any(word in desc_upper for word in ["FD", "FIXED DEPOSIT", "TERM DEPOSIT"]):
            return "FD Interest"

    return None


__all__ = ["_REF_PATTERNS", "_extract_reference_no", "_append_issue", "_guess_fd_category"]
