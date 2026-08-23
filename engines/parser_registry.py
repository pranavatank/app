"""engines/parser_registry.py — Lightweight registry for bank-specific parsers."""
from typing import Callable, Optional

_REGISTRY: dict[str, Callable] = {}


def register(bank_key: str, parser_callable: Callable) -> None:
    """Register a parser callable for a bank key (e.g. 'hdfc bank')."""
    _REGISTRY[bank_key.lower()] = parser_callable


def get(bank_key: str) -> Optional[Callable]:
    """Return parser for bank_key using exact match first, then substring match.

    This lets a stored bank name like 'HDFC' or 'HDFC Bank Ltd' resolve to
    the parser registered under 'hdfc bank'.
    """
    key = (bank_key or "").lower().strip()
    if not key:
        return None
    # 1. Exact match
    if key in _REGISTRY:
        return _REGISTRY[key]
    # 2. Registered key is a substring of the supplied name  (e.g. 'hdfc bank' in 'hdfc bank ltd')
    for registered_key, parser in _REGISTRY.items():
        if registered_key in key:
            return parser
    # 3. Supplied name is a substring of a registered key  (e.g. 'hdfc' in 'hdfc bank')
    for registered_key, parser in _REGISTRY.items():
        if key in registered_key:
            return parser
    return None


def list_registered() -> list[str]:
    return list(_REGISTRY.keys())
