"""engines/parser_registry.py — Lightweight registry for bank-specific parsers."""
from typing import Callable, Optional

_REGISTRY: dict[str, Callable] = {}


def register(bank_key: str, parser_callable: Callable) -> None:
    """Register a parser callable for a bank key (e.g. 'sbi')."""
    _REGISTRY[bank_key.lower()] = parser_callable


def get(bank_key: str) -> Optional[Callable]:
    return _REGISTRY.get((bank_key or "").lower())


def list_registered() -> list[str]:
    return list(_REGISTRY.keys())
