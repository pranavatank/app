"""
engines/statement_passwords.py — Shared password helpers for statement parsers.
"""

from __future__ import annotations

from typing import Optional


class StatementPasswordError(Exception):
    """Base error for password-protected statement files."""


class StatementPasswordRequiredError(StatementPasswordError):
    """Raised when a password is required but missing."""


class StatementPasswordInvalidError(StatementPasswordError):
    """Raised when a provided password is invalid."""


def ensure_pdf_password(file_path: str, password: Optional[str]) -> None:
    try:
        from pypdf import PdfReader
    except ModuleNotFoundError as exc:
        raise StatementPasswordError(
            "PDF password handling requires 'pypdf'."
        ) from exc

    reader = PdfReader(file_path)
    if not getattr(reader, "is_encrypted", False):
        return
    if not password:
        raise StatementPasswordRequiredError("PDF is password-protected.")
    try:
        if reader.decrypt(password) == 0:
            raise StatementPasswordInvalidError("Invalid PDF password.")
    except StatementPasswordInvalidError:
        raise
    except Exception as exc:
        raise StatementPasswordInvalidError("Invalid PDF password.") from exc
