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


def _guess_fd_category(desc_upper: str, txn_type: str) -> Optional[str]:
    """
    Shared FD-aware category detection, used by every parser path (rule-based
    PDF/Excel, bank-specific plugins, and the AI parser) so FD booking/
    maturity/interest transactions get the same category regardless of which
    parser produced them. Returns None if the description isn't FD-related —
    callers fall back to their own generic category logic in that case.
    """
    if txn_type == "Income":
        if any(word in desc_upper for word in ["PRINC AND INT AUTO REDEEM", "AUTO REDEEM", "FD CR", "PAT CR"]):
            return "FD Maturity"
        if any(word in desc_upper for word in ["INT AUTO REDEEM", "FD INTEREST"]):
            return "FD Interest"
        if "INTEREST" in desc_upper and any(word in desc_upper for word in ["FD", "FIXED DEPOSIT", "TERM DEPOSIT"]):
            return "FD Interest"
        if any(word in desc_upper for word in ["MATURITY", "MATURED", "REDEMPTION", "REDEEMED"]):
            return "FD Maturity"
        return None
    else:
        if any(word in desc_upper for word in ["TD. GENERIC PAYIN DEBIT", "PAYIN DEBIT", "FIXED DEPOSIT", "TERM DEPOSIT"]):
            return "FD Principal"
        return None


__all__ = ["_REF_PATTERNS", "_extract_reference_no", "_append_issue", "_guess_fd_category"]
