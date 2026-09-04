"""
tests/test_statement_package.py — Regression suite for coordinate parser

This guards against data loss in the statement parsing pipeline.
CRITICAL: These tests MUST pass before any changes to engines/statement/.

Expected baseline:
  Equitas: 38 rows
  IDFC: 376 rows, debit 480013.35, credit 467264.82
  Jana: 65 rows
  Ujjivan: 27 rows

All banks: direction_errors must return wrong == 0.
"""

from __future__ import annotations

import os
import functools
from pathlib import Path
import pytest

from engines.pdf_extractor import extract_pdf_text
from engines.statement import parse_statement_pdf
from engines.statement.validate import direction_errors, extract_control_totals, reconcile_totals


# ── Fixtures and module skip ──────────────────────────────────────────────────

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "data" / "PersonalData" / "Pranav"

pytestmark = pytest.mark.skipif(
    not FIXTURE_DIR.is_dir(),
    reason="owner's document fixtures not present (data/PersonalData/) — see REBUILD_PLAN T004",
)


def _password(label_substring: str) -> str:
    """
    Return password for a given label substring.

    Check env vars first (PFM_AIS_TIS_PASSWORD, PFM_EQUITAS_PASSWORD),
    else parse password.txt for a line whose label contains substring (case-insensitive).
    Skip the test if password.txt missing and env var not set.
    """
    # Build a map of expected env vars for common labels
    env_map = {
        "AIS/TIS": "PFM_AIS_TIS_PASSWORD",
        "Equitas": "PFM_EQUITAS_PASSWORD",
    }

    # Check env var first
    for key, env_var in env_map.items():
        if label_substring.lower() in key.lower():
            val = os.environ.get(env_var)
            if val:
                return val

    # Fall back to password.txt
    password_file = FIXTURE_DIR / "password.txt"
    if not password_file.exists():
        pytest.skip(
            f"password.txt not found and env vars not set (check {', '.join(env_map.values())})"
        )

    text = password_file.read_text()
    for line in text.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        label, password = line.split(":", 1)
        if label_substring.lower() in label.lower():
            return password.strip()

    pytest.skip(f"password label '{label_substring}' not found in password.txt")


# ── Cached PDF parsing (module scope) ─────────────────────────────────────────

@functools.lru_cache(maxsize=16)
def _extract_pdf_cached(pdf_path: str, password: str | None = None) -> str:
    """Cached PDF text extraction."""
    result = extract_pdf_text(pdf_path, password=password)
    return result.text


@pytest.fixture(scope="module")
def statements():
    """Parse and cache all four bank statements."""
    pwd = _password("Equitas")

    statements_dict = {}
    statements_dir = FIXTURE_DIR / "Statement"

    for bank_file in [
        ("Equitas.pdf", "Equitas", pwd),
        ("IDFC.pdf", "IDFC", None),
        ("Jana - Pranav.pdf", "Jana", None),
        ("Ujjivan - Pranav.pdf", "Ujjivan", None),
    ]:
        file_name, bank_name, bank_pwd = bank_file
        path = statements_dir / file_name
        if path.exists():
            statements_dict[bank_name] = parse_statement_pdf(
                str(path), password=bank_pwd
            )

    return statements_dict


# ════════════════════════════════════════════════════════════════════════════════
# REGRESSION GUARDS: Row counts and control totals
# ════════════════════════════════════════════════════════════════════════════════


class TestStatementRowCounts:
    """
    Pure regression guards: exact row counts must be preserved.

    If row count changes, data is being silently lost or fabricated.
    """

    @pytest.mark.parametrize("bank_name,expected_rows", [
        ("Equitas", 38),
        ("IDFC", 376),
        ("Jana", 65),
        ("Ujjivan", 27),
    ])
    def test_exact_row_count(self, statements, bank_name, expected_rows):
        """Exact row count must match baseline. Any change indicates data loss."""
        if bank_name not in statements:
            pytest.skip(f"{bank_name} statement not found")

        txns = statements[bank_name]
        assert len(txns) == expected_rows, (
            f"{bank_name}: expected {expected_rows} rows, got {len(txns)}. "
            "This indicates either data loss or fabrication."
        )


class TestStatementDirectionErrors:
    """
    Direction accuracy: transaction_type must match balance_after delta sign.

    All banks must have zero direction errors in the baseline.
    """

    @pytest.mark.parametrize("bank_name", [
        "Equitas",
        "IDFC",
        "Jana",
        "Ujjivan",
    ])
    def test_direction_errors_is_zero(self, statements, bank_name):
        """Direction errors (wrong count) must be zero."""
        if bank_name not in statements:
            pytest.skip(f"{bank_name} statement not found")

        txns = statements[bank_name]
        tied, wrong = direction_errors(txns)

        assert wrong == 0, (
            f"{bank_name}: {wrong} direction errors found. "
            f"({tied} tied rows, {wrong} have wrong direction)"
        )


class TestIDFCControlTotals:
    """
    IDFC-specific: verify parsed totals match printed control totals.

    IDFC prints totals on every page; page 1 is the canonical source.
    """

    def test_idfc_debit_total(self, statements):
        """IDFC parsed debit total must equal 480013.35."""
        if "IDFC" not in statements:
            pytest.skip("IDFC statement not found")

        txns = statements["IDFC"]
        parsed_debit = sum(
            t.get("amount", 0)
            for t in txns
            if t.get("transaction_type") == "Expense"
        )

        assert abs(parsed_debit - 480013.35) < 0.01, (
            f"IDFC parsed debit total: {parsed_debit:.2f}, expected 480013.35"
        )

    def test_idfc_credit_total(self, statements):
        """IDFC parsed credit total must equal 467264.82."""
        if "IDFC" not in statements:
            pytest.skip("IDFC statement not found")

        txns = statements["IDFC"]
        parsed_credit = sum(
            t.get("amount", 0)
            for t in txns
            if t.get("transaction_type") == "Income"
        )

        assert abs(parsed_credit - 467264.82) < 0.01, (
            f"IDFC parsed credit total: {parsed_credit:.2f}, expected 467264.82"
        )
