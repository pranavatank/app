"""Bank-specific statement parsers."""

from .sbi_statement_parser import parse_sbi_pdf
from engines.parser_registry import register as _register

# Register available parsers in the registry for plugin discovery
try:
	_register("sbi", parse_sbi_pdf)
except Exception:
	pass

__all__ = ["parse_sbi_pdf"]
