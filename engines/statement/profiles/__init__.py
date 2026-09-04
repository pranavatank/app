"""
engines/statement/profiles/__init__.py — Load bank-specific profiles from YAML

Bank profiles move hard-coded bank quirks into data-driven YAML files so adding
a bank requires only a new YAML file, no Python code changes.

Each profile carries:
  - column_synonyms: header words mapping to canonical fields
  - date_formats: accepted date patterns
  - row_order: 'ascending' or 'descending' (with auto-detection as default)
  - amount_columns_both_populated: bool (true only for Jana)
  - narration_vocabulary: FD/interest/charges phrases (reference to parser_utils)
  - fd_conventions: compounding, simple_below_days, day count, rounding adjustment

The loader:
  - Loads a profile by bank name (e.g., 'Jana' -> jana.yaml)
  - Falls back to generic.yaml if file missing, malformed YAML, or unknown bank
  - Merges profile values over generic defaults
  - Never raises; always returns a valid dict
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml
except ImportError:
    yaml = None


_PROFILES_DIR = Path(__file__).parent
_PROFILE_CACHE: Dict[str, Dict[str, Any]] = {}


def _load_yaml_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """
    Load a YAML file safely, returning None if malformed or missing.
    Never raises.
    """
    if yaml is None:
        return None

    if not file_path.exists():
        return None

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if not isinstance(data, dict):
                return None
            return data
    except Exception:
        # Malformed YAML, permission denied, encoding error, etc.
        return None


def _load_generic_profile() -> Dict[str, Any]:
    """
    Load the generic profile, which defines all defaults.
    Falls back to a hardcoded dict if YAML loading fails.
    """
    generic_path = _PROFILES_DIR / "generic.yaml"
    profile = _load_yaml_file(generic_path)
    if profile:
        return profile

    # Hardcoded fallback (same as generic.yaml)
    return {
        "column_synonyms": {
            "date": [
                "transaction date",
                "txn date",
                "tran date",
                "date",
                "value date",
            ],
            "desc": [
                "particulars",
                "narration",
                "description",
                "particular",
            ],
            "debit": ["withdrawal", "withdrawals", "debit"],
            "credit": ["deposit", "deposits", "credit"],
            "balance": ["closingbalance", "closing balance", "balance"],
            "ref": ["reference", "cheque", "chq"],
        },
        "date_formats": [
            "%d-%b-%Y",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%Y-%m-%d",
        ],
        "row_order": "ascending",
        "amount_columns_both_populated": False,
        "narration_vocabulary": {
            "Income": [
                "PRINC AND INT AUTO REDEEM",
                "CREDIT INTEREST CAPITALISED",
                "CREDIT INTEREST CAPITALIZED",
                "CASA CREDIT INTEREST",
                "INT AUTO REDEEM",
                "CLOSURE PROCEEDS",
                "INTEREST ON DEPOSIT",
                "FD INTEREST",
                "AUTO REDEEM",
                "MATURITY",
                "MATURED",
                "REDEMPTION",
                "REDEEMED",
                "FD CR",
                "PAT CR",
            ],
            "Expense": [
                "TD. GENERIC PAYIN DEBIT",
                "SMS ALERTS CHARGES",
                "GOODS AND SERVICES TAX",
                "INITIAL PAYIN",
                "PAYIN DEBIT",
                "FIXED DEPOSIT",
                "TERM DEPOSIT",
                "FD BOOKING",
                "AMB CHARGES",
            ],
        },
        "fd_conventions": {
            "compounding": "quarterly",
            "simple_below_days": 183,
            "day_count": "actual/365",
            "rounding_adjustment": 4,
        },
    }


def load_profile(bank_name: str) -> Dict[str, Any]:
    """
    Load a bank-specific profile by bank name.

    Searches for a YAML file named <bank_name_lowercase>.yaml in the profiles dir.
    If found and valid, merges it with generic defaults.
    If not found, malformed, or unknown bank, falls back to generic without raising.

    Args:
        bank_name: Bank name (e.g., 'Jana', 'IDFC', 'SBI Bank')

    Returns:
        Profile dict with all values set (merged over generic defaults)
    """
    if not bank_name:
        return _load_generic_profile()

    bank_key = bank_name.lower().replace(" ", "").replace("-", "")

    # Check cache first
    if bank_key in _PROFILE_CACHE:
        return _PROFILE_CACHE[bank_key]

    # Load generic as base
    generic = _load_generic_profile()

    # Normalize bank name for file lookup
    # Try several variations: "Jana" -> "jana.yaml", "IDFC Bank" -> "idfc.yaml", etc.
    normalized_name = bank_name.lower().strip()
    # Extract first word and remove common suffixes
    first_word = normalized_name.split()[0].replace("-", "")
    normalized_name = first_word

    # Try to load bank-specific profile
    bank_profile_path = _PROFILES_DIR / f"{normalized_name}.yaml"
    bank_profile = _load_yaml_file(bank_profile_path)

    if not bank_profile:
        # Not found or malformed; use generic
        _PROFILE_CACHE[bank_key] = generic
        return generic

    # Merge bank-specific profile over generic
    merged = _deep_merge(generic, bank_profile)
    _PROFILE_CACHE[bank_key] = merged
    return merged


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge override dict into base dict.
    For dicts, recurse; for other types, override wins.

    Args:
        base: Base dict (typically generic defaults)
        override: Dict with overrides

    Returns:
        Merged dict
    """
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


__all__ = ["load_profile"]
