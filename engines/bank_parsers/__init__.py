"""Bank-specific statement parsers."""

from .sbi_statement_parser import parse_sbi_pdf
from .hdfc_statement_parser import HDFCStatementParser
from .yes_bank_statement_parser import YESBankStatementParser
from engines.parser_registry import register as _register

# Register available parsers in the registry for plugin discovery
try:
	_register("sbi", parse_sbi_pdf)
except Exception:
	pass

try:
	_register("hdfc bank", HDFCStatementParser())
except Exception:
	pass

try:
	_register("yes bank", YESBankStatementParser())
except Exception:
	pass

__all__ = ["parse_sbi_pdf", "HDFCStatementParser", "YESBankStatementParser"]
