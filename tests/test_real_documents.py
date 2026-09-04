"""
tests/test_real_documents.py — Regression suite pinning owner's true tax figures
against the real documents in data/PersonalData/Pranav/.

DESIGN:
- Skip module if fixtures missing (pytestmark).
- Cache expensive PDF parsing at module scope.
- One assertion per test.
- xfail(strict=True) for currently-failing tests; reason holds measured vs true baseline.
- No xfail for tests that pass today (pure regression guards).

Ground truth from spec (TIS document, FY2025-26):
  - fd_interest: 256642
  - savings_interest: 46183
  - dividend_income: 2655
  - other_income: 105069 (business receipts 194J)
  - tds_deducted: 13367
  - time-deposit purchases: 1300000 (INVESTMENT, never income)
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from datetime import date, timedelta
import pytest
import functools

from engines.pdf_extractor import extract_pdf_text
from engines.ais_tis_parser import parse_ais_pdf_text, parse_tis_pdf_text
from engines.form26as_parser import parse_form26as_pdf
from engines.statement_parser import parse_statement


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


# ── Cached PDF text extraction (expensive; module scope) ────────────────────

@functools.lru_cache(maxsize=16)
def _extract_pdf_cached(pdf_path: str, password: str | None = None) -> str:
    """Cached PDF text extraction."""
    result = extract_pdf_text(pdf_path, password=password)
    return result.text


def _get_ais_text() -> str:
    """Extract AIS.pdf text once per module."""
    pwd = _password("AIS/TIS")
    return _extract_pdf_cached(str(FIXTURE_DIR / "AIS.pdf"), pwd)


def _get_tis_text() -> str:
    """Extract TIS.pdf text once per module."""
    pwd = _password("AIS/TIS")
    return _extract_pdf_cached(str(FIXTURE_DIR / "TIS.pdf"), pwd)


def _get_26as_text() -> str:
    """Extract 26AS.pdf text once per module (no password)."""
    return _extract_pdf_cached(str(FIXTURE_DIR / "26AS.pdf"))


# ── Cached parsed dicts (module scope) ────────────────────────────────────────

@pytest.fixture(scope="module")
def ais_dict():
    """Parse and cache AIS.pdf."""
    text = _get_ais_text()
    return parse_ais_pdf_text(text)


@pytest.fixture(scope="module")
def tis_dict():
    """Parse and cache TIS.pdf."""
    text = _get_tis_text()
    return parse_tis_pdf_text(text)


@pytest.fixture(scope="module")
def form26as_dict():
    """Parse and cache 26AS.pdf."""
    text = _get_26as_text()
    return parse_form26as_pdf(text)


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
            statements_dict[bank_name] = parse_statement(
                str(path), "pdf", bank_name=bank_name, password=bank_pwd
            )

    return statements_dict


# ── Helper: statement direction accuracy ──────────────────────────────────────

def _check_statement_direction_accuracy(transactions: list) -> tuple:
    """
    Check transaction_type against balance_after delta sign.

    Returns (tied, wrong) counts:
    - tied: number of rows whose balance_after delta ties out to the row amount
    - wrong: subset of those tied rows that carry the wrong direction
    """
    tied = 0
    wrong = 0
    prev = None

    for row in transactions:
        balance = row.get("balance_after")

        # Skip rows with None balance
        if balance is None:
            prev = None
            continue

        balance = round(float(balance), 2)

        if prev is not None:
            delta = round(balance - prev, 2)
            amt = round(float(row.get("amount") or 0), 2)

            # Only count rows where abs(delta) matches amount within 0.02
            if abs(abs(delta) - amt) < 0.02 and amt > 0:
                tied += 1
                expected_type = "Income" if delta > 0 else "Expense"
                if row.get("transaction_type") != expected_type:
                    wrong += 1

        prev = balance

    return tied, wrong


# ════════════════════════════════════════════════════════════════════════════════
# AIS TESTS
# ════════════════════════════════════════════════════════════════════════════════


class TestAIS:
    """AIS.pdf parsing tests. True values from spec."""

    @pytest.mark.xfail(
        strict=True,
        reason="baseline 245389 vs true 256642 — fixed by T017"
    )
    def test_ais_fd_interest(self, ais_dict):
        """FD interest from AIS."""
        assert ais_dict["fd_interest"] == 256642

    @pytest.mark.xfail(
        strict=True,
        reason="baseline 0 vs true 46183 — fixed by T017"
    )
    def test_ais_savings_interest(self, ais_dict):
        """Savings bank interest from AIS."""
        assert ais_dict["savings_interest"] == 46183

    @pytest.mark.xfail(
        strict=True,
        reason="baseline 0 vs true 2655 — fixed by T017"
    )
    def test_ais_dividend_income(self, ais_dict):
        """Dividend income from AIS."""
        assert ais_dict["dividend_income"] == 2655

    @pytest.mark.xfail(
        strict=True,
        reason="baseline 19194 vs true 13367 — fixed by T017"
    )
    def test_ais_tds_deducted(self, ais_dict):
        """TDS deducted from AIS."""
        assert ais_dict["tds_deducted"] == 13367

    def test_ais_other_income(self, ais_dict):
        """Other income (business receipts 194J) from AIS. Already correct."""
        assert ais_dict["other_income"] == 105069


# ════════════════════════════════════════════════════════════════════════════════
# TIS TESTS
# ════════════════════════════════════════════════════════════════════════════════


class TestTIS:
    """TIS.pdf parsing tests. True values from spec."""

    def test_tis_fd_interest(self, tis_dict):
        """FD interest from TIS. Already correct."""
        assert tis_dict["fd_interest"] == 256642

    @pytest.mark.xfail(
        strict=True,
        reason="baseline 0 vs true 46183 — fixed by T018"
    )
    def test_tis_savings_interest(self, tis_dict):
        """Savings bank interest from TIS."""
        assert tis_dict["savings_interest"] == 46183

    @pytest.mark.xfail(
        strict=True,
        reason="baseline 349008 vs true 0 — fixed by T018"
    )
    def test_tis_other_interest(self, tis_dict):
        """Other interest from TIS."""
        assert tis_dict["other_interest"] == 0

    @pytest.mark.xfail(
        strict=True,
        reason="baseline 5310 vs true 2655 — fixed by T018"
    )
    def test_tis_dividend_income(self, tis_dict):
        """Dividend income from TIS (currently double-counted)."""
        assert tis_dict["dividend_income"] == 2655

    @pytest.mark.xfail(
        strict=True,
        reason="baseline 2705069 vs true 105069 — fixed by T018; currently includes 1300000 * 2 time-deposit purchases"
    )
    def test_tis_other_income(self, tis_dict):
        """Other income (business receipts) from TIS.

        Note: baseline 2705069 includes time-deposit purchases (1300000 x 2),
        which are investments, not income. Must be excluded.
        """
        assert tis_dict["other_income"] == 105069

    @pytest.mark.xfail(
        strict=True,
        reason="baseline 0 vs true 13367 — fixed by T018"
    )
    def test_tis_tds_deducted(self, tis_dict):
        """TDS deducted from TIS."""
        assert tis_dict["tds_deducted"] == 13367

    @pytest.mark.xfail(
        strict=True,
        reason="baseline has 1300000 leaking into income buckets — fixed by T018"
    )
    def test_tis_no_time_deposit_purchase_leakage(self, tis_dict):
        """Ensure time-deposit purchases (1300000) never appear as income.

        No field should equal or exceed 1300000 (the purchase amount).
        """
        for key in ["fd_interest", "savings_interest", "other_interest", "dividend_income", "other_income"]:
            val = tis_dict.get(key, 0)
            assert val < 1300000, f"{key}={val} >= purchase amount 1300000"


# ════════════════════════════════════════════════════════════════════════════════
# FORM 26AS TESTS
# ════════════════════════════════════════════════════════════════════════════════


class TestForm26AS:
    """Form 26AS parsing tests. True values from spec."""

    @pytest.mark.xfail(
        strict=True,
        reason="baseline 6 vs true >=100 (document has 200+ detail rows) — fixed by T019"
    )
    def test_form26as_record_count(self, form26as_dict):
        """Form 26AS should have at least 100 TDS records.

        The document has 200+ detail rows; currently only 6 are recovered.
        """
        assert len(form26as_dict["records"]) >= 100

    @pytest.mark.xfail(
        strict=True,
        reason="baseline 1847 vs true 13367 — fixed by T019"
    )
    def test_form26as_total_tds(self, form26as_dict):
        """Sum of tds_deducted across all records should equal 13367."""
        total = sum(float(r.get("tds_deducted") or 0) for r in form26as_dict["records"])
        assert total == 13367

    @pytest.mark.xfail(
        strict=True,
        reason="baseline has 194B records (lottery misparsed from legend) — fixed by T019"
    )
    def test_form26as_no_194b_section(self, form26as_dict):
        """No record should have section code '194B' (lottery winnings misparsed)."""
        for record in form26as_dict["records"]:
            section = record.get("section", "")
            assert section != "194B", f"Found misparsed 194B record: {record}"

    @pytest.mark.xfail(
        strict=True,
        reason="baseline has empty transaction_date in all records — fixed by T019"
    )
    def test_form26as_transaction_dates_present(self, form26as_dict):
        """Every record must have a non-empty transaction_date."""
        for record in form26as_dict["records"]:
            date_val = record.get("transaction_date", "").strip()
            assert date_val, f"Record has empty transaction_date: {record}"


# ════════════════════════════════════════════════════════════════════════════════
# STATEMENT DIRECTION ACCURACY TESTS
# ════════════════════════════════════════════════════════════════════════════════


class TestStatementDirectionAccuracy:
    """
    Verify that transaction_type matches the sign of balance_after delta.

    Measured baseline from spec:
      Equitas  rows=42   tied=31   wrong=16  err=51.6%
      IDFC     rows=377  tied=371  wrong=100 err=27.0%
      Jana     rows=65   tied=25   wrong=9   err=36.0%
      Ujjivan  rows=27   tied=22   wrong=13  err=59.1%
    """

    @pytest.mark.parametrize("bank_name,expected_tied,expected_wrong,error_rate", [
        ("Equitas", 31, 16, 0.516),
        ("IDFC", 371, 100, 0.270),
        ("Jana", 25, 9, 0.360),
        ("Ujjivan", 22, 13, 0.591),
    ])
    @pytest.mark.xfail(
        strict=True,
        reason="statement direction accuracy mismatch — fixed by T010-T012"
    )
    def test_statement_direction_accuracy(self, statements, bank_name, expected_tied, expected_wrong, error_rate):
        """Check that all transactions have correct direction."""
        if bank_name not in statements:
            pytest.skip(f"{bank_name} statement not found")

        txns = statements[bank_name]
        tied, wrong = _check_statement_direction_accuracy(txns)

        # Should have zero wrong counts when fixed
        assert wrong == 0, (
            f"{bank_name}: {wrong} of {tied} balance-tied rows have the wrong direction "
            f"(baseline {expected_wrong} of {expected_tied}, {error_rate * 100:.1f}%)"
        )

    @pytest.mark.parametrize("bank_name,expected_rows", [
        ("Equitas", 42),
        ("IDFC", 377),
        ("Jana", 65),
        ("Ujjivan", 27),
    ])
    def test_statement_row_count(self, statements, bank_name, expected_rows):
        """Pure regression guard: row count must stay constant."""
        if bank_name not in statements:
            pytest.skip(f"{bank_name} statement not found")

        txns = statements[bank_name]
        assert len(txns) == expected_rows, f"{bank_name}: row count changed from {expected_rows} to {len(txns)}"

    @pytest.mark.xfail(
        strict=True,
        reason="Ujjivan statement (all FD closures) yields zero Income rows, should yield at least one — fixed by T010-T012"
    )
    def test_ujjivan_has_income_rows(self, statements):
        """Ujjivan is a statement of FD closures and should have at least one Income row."""
        if "Ujjivan" not in statements:
            pytest.skip("Ujjivan statement not found")

        txns = statements["Ujjivan"]
        income_rows = [t for t in txns if t.get("transaction_type") == "Income"]
        assert len(income_rows) >= 1, f"Ujjivan has {len(income_rows)} Income rows, expected >= 1"


# ════════════════════════════════════════════════════════════════════════════════
# END OF test_real_documents.py
# ════════════════════════════════════════════════════════════════════════════════
