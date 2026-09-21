"""
tests/test_chart_db_agreement.py — Verify charts plot what the DB aggregates say.

This module opens the REAL database (data/financial.db) in read-only mode,
renders the Income Prediction screen offscreen, and compares plotted values
against direct SQL aggregates and engine calculations. No rows are created;
the DB is never modified. Must not run while real-UI tests are executing.

Mechanism: ui/widgets/chart_widget.py:84 records every plot call as
_last_call = (fn.__name__, args, kwargs), allowing us to read the exact
arguments passed to plot_bar() and plot_line() and verify they match the
underlying data.

Expected values (database state as of task definition):
  - Taxable income (FD Interest + Savings Interest): ~95591.00
  - Non-taxable income (FD Maturity + Other Income): ~6400091.21
  - TDS chart: per-bank projected interest values from tds_risk["by_bank"]
  - Timeline chart: 12 monthly cumulative points, final = projected_total
"""

import os
import sqlite3
import pytest
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

import config
import core.database
from engines.prediction_engine import (
    get_prediction_summary,
    realised_income_to_date,
    TAXABLE_INCOME_CATEGORIES,
    NON_TAXABLE_INCOME_CATEGORIES,
)

# Compute the real database path at import time (absolute path from __file__)
REAL_DB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "financial.db"
)


# ── Fixture: Restore real DB for this module ────────────────────────────────

@pytest.fixture(scope="module", autouse=True)
def use_real_database(monkeypatch_module):
    """
    Restore config.DB_PATH and core.database.DB_PATH to the real database.
    This overrides conftest.py's session-scoped fixture for this module only.

    This fixture runs once per module; all tests in this file will use the real DB.
    It also skips the module if the real DB does not exist.
    """
    if not os.path.exists(REAL_DB):
        pytest.skip(f"Real database not found: {REAL_DB}")

    # Monkeypatch config and core.database to use the real DB
    monkeypatch_module.setattr(config, "DB_PATH", REAL_DB)
    monkeypatch_module.setattr(core.database, "DB_PATH", REAL_DB)


@pytest.fixture(scope="module")
def monkeypatch_module(request):
    """Module-scoped monkeypatch fixture (pytest doesn't provide one natively)."""
    from _pytest.monkeypatch import MonkeyPatch
    m = MonkeyPatch()
    yield m
    m.undo()


# ── Constants ────────────────────────────────────────────────────────────────

def _get_db_uri():
    """Get DB URI dynamically so the monkeypatched config.DB_PATH is used."""
    return f"file:{config.DB_PATH}?mode=ro"
PERSON_ID = 1
FINANCIAL_YEAR = "2025-26"
AS_OF = date(2026, 3, 31)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _ro_conn():
    """Open a read-only connection to the real database."""
    uri = f"file:{REAL_DB}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _plotted(chart) -> tuple[str, tuple, dict]:
    """Extract the last plot call from a ChartWidget."""
    if chart._last_call is None:
        raise AssertionError("Chart was never plotted")
    return chart._last_call


# ── Tests ────────────────────────────────────────────────────────────────────

def test_verify_real_database_in_use():
    """Verify that we're using the real database, not the temp test DB."""
    assert config.DB_PATH == REAL_DB, \
        f"Database mismatch: config.DB_PATH={config.DB_PATH}, REAL_DB={REAL_DB}"
    assert os.path.exists(REAL_DB), f"Real database not found: {REAL_DB}"


def test_tds_chart_matches_per_bank_fd_projection(qapp, monkeypatch):
    """
    TDS Risk chart must plot one bar per bank with values matching
    tds_risk["by_bank"] projected_interest figures to 0.01 tolerance.
    The sum of plotted values must equal the projected total FD interest.
    """
    # Build screen with prediction data set directly
    from ui.income_prediction_screen import IncomePredictionScreen

    # Monkeypatch load_data to be a no-op so async load doesn't race the test
    monkeypatch.setattr(IncomePredictionScreen, 'load_data', lambda self: None)

    screen = IncomePredictionScreen()
    summary = get_prediction_summary(PERSON_ID, FINANCIAL_YEAR, AS_OF)
    screen._prediction_data = summary
    screen._refresh_all_sections()

    # Process Qt events to ensure chart is rendered
    qapp.processEvents()

    # Verify that async load didn't overwrite the data
    assert screen._prediction_data is summary, \
        "Async load overwrote screen._prediction_data; screen is not using the expected summary"

    # Verify chart exists
    assert hasattr(screen, 'tds_chart'), "tds_chart should exist in prediction screen"

    # Read the plotted data from chart._last_call
    name, args, kwargs = _plotted(screen.tds_chart)

    # Verify it was a bar chart
    assert name == "plot_bar", f"Expected plot_bar, got {name}"

    # Extract categories and values from args/kwargs
    # plot_bar(categories, values, title="", xlabel="", ylabel="", color=None)
    categories = args[0] if len(args) > 0 else kwargs.get("categories", [])
    values = args[1] if len(args) > 1 else kwargs.get("values", [])

    # Read expected data from tds_risk
    by_bank = summary.get("tds_risk", {}).get("by_bank", [])
    assert len(by_bank) > 0, "No banks in by_bank data; expected real FD data"

    expected_banks = [b.get("bank_name", "—") for b in by_bank]
    expected_values = [b.get("projected_interest", 0) for b in by_bank]

    # Assert same number of banks
    assert len(categories) == len(expected_banks), \
        f"Bank count mismatch: plotted {len(categories)}, expected {len(expected_banks)}"

    # Assert each bank name and value matches
    for i, (cat, val) in enumerate(zip(categories, values)):
        exp_bank = expected_banks[i]
        exp_val = expected_values[i]
        assert cat == exp_bank, \
            f"Bank {i}: plotted '{cat}', expected '{exp_bank}'"
        assert abs(val - exp_val) <= 0.01, \
            f"Bank {i} ({cat}): plotted {val}, expected {exp_val} (diff={val - exp_val})"

    # Assert sum of plotted values matches the projected total
    plotted_total = sum(values)
    projected_total = summary.get("projected_fd_interest", {}).get("total", 0)
    assert abs(plotted_total - projected_total) <= 0.01, \
        f"Total mismatch: plotted sum {plotted_total}, projected {projected_total}"


def test_timeline_chart_final_point_matches_projected_total(qapp, monkeypatch):
    """
    Monthly timeline chart must plot 12 months with the final cumulative value
    matching the projected total FY income.
    """
    from ui.income_prediction_screen import IncomePredictionScreen

    # Monkeypatch load_data to be a no-op so async load doesn't race the test
    monkeypatch.setattr(IncomePredictionScreen, 'load_data', lambda self: None)

    screen = IncomePredictionScreen()
    summary = get_prediction_summary(PERSON_ID, FINANCIAL_YEAR, AS_OF)
    screen._prediction_data = summary
    screen._refresh_all_sections()

    qapp.processEvents()

    # Verify that async load didn't overwrite the data
    assert screen._prediction_data is summary, \
        "Async load overwrote screen._prediction_data; screen is not using the expected summary"

    # Read the plotted data
    name, args, kwargs = _plotted(screen.timeline_chart)

    # Verify it was a line chart
    assert name == "plot_line", f"Expected plot_line, got {name}"

    # Extract x_data and y_data
    # plot_line(x_data, y_data, title="", xlabel="", ylabel="", color=None)
    x_data = args[0] if len(args) > 0 else kwargs.get("x_data", [])
    y_data = args[1] if len(args) > 1 else kwargs.get("y_data", [])

    # Assert 12 months
    assert len(x_data) == 12, f"Expected 12 months, got {len(x_data)}"
    assert len(y_data) == 12, f"Expected 12 y-values, got {len(y_data)}"

    # Assert final point matches projected total
    final_value = y_data[-1]
    projected_total = summary.get("fy_income", {}).get("projected_total", 0)
    assert projected_total > 0, f"Projected total is {projected_total}, should be > 0"
    assert abs(final_value - projected_total) <= 0.01, \
        f"Final month: plotted {final_value}, expected {projected_total} (diff={final_value - projected_total})"


def test_taxable_income_aggregate_matches_category_sum():
    """
    Direct SQL aggregate of taxable income transactions must match
    the engine's realised_income_to_date["taxable"] calculation.
    Also verify non-taxable aggregate independently.

    Validates against the actual database via SQL, not just engine consistency.
    """
    # Open read-only connection to database
    conn = _ro_conn()
    cursor = conn.cursor()

    # Financial year dates: 2025-04-01 to 2026-03-31
    start_date = "2025-04-01"
    end_date = "2026-03-31"

    # Build placeholders for SQL IN clause
    taxable_categories = tuple(TAXABLE_INCOME_CATEGORIES)
    non_taxable_categories = tuple(NON_TAXABLE_INCOME_CATEGORIES)

    taxable_placeholders = ",".join("?" * len(taxable_categories))
    non_taxable_placeholders = ",".join("?" * len(non_taxable_categories))

    # Query SQL for taxable income sum
    sql_taxable = f"""
        SELECT COALESCE(SUM(amount), 0) FROM Transactions
        WHERE person_id = ? AND transaction_type = 'Income'
            AND transaction_date BETWEEN ? AND ?
            AND category IN ({taxable_placeholders})
    """
    cursor.execute(sql_taxable, (PERSON_ID, start_date, end_date) + taxable_categories)
    sql_taxable_sum = cursor.fetchone()[0]

    # Query SQL for non-taxable income sum
    sql_non_taxable = f"""
        SELECT COALESCE(SUM(amount), 0) FROM Transactions
        WHERE person_id = ? AND transaction_type = 'Income'
            AND transaction_date BETWEEN ? AND ?
            AND category IN ({non_taxable_placeholders})
    """
    cursor.execute(sql_non_taxable, (PERSON_ID, start_date, end_date) + non_taxable_categories)
    sql_non_taxable_sum = cursor.fetchone()[0]

    conn.close()

    # Get engine's calculation
    realised = realised_income_to_date(PERSON_ID, FINANCIAL_YEAR, AS_OF)
    engine_taxable = realised.get("taxable", 0)
    engine_non_taxable = realised.get("non_taxable", 0)
    engine_unclassified = realised.get("unclassified", 0)

    # Verify we have real data (not empty database)
    assert sql_taxable_sum > 0, "Taxable SQL sum is 0, suggesting empty database"
    assert sql_non_taxable_sum > 0, "Non-taxable SQL sum is 0, suggesting empty database"

    # Assert specific expected values from FY 2025-26 person 1
    # These guards verify we're working with the real database
    assert sql_taxable_sum < 200000, \
        f"Taxable SQL sum {sql_taxable_sum} unexpectedly large (should be < 200000)"
    assert sql_non_taxable_sum > 5000000, \
        f"Non-taxable SQL sum {sql_non_taxable_sum} unexpectedly small (should be > 5000000)"

    # Assert the expected values match the real data
    assert abs(sql_taxable_sum - 95591.00) <= 0.01, \
        f"Taxable income mismatch: got {sql_taxable_sum}, expected ~95591.00"
    assert abs(sql_non_taxable_sum - 6400091.21) <= 0.01, \
        f"Non-taxable income mismatch: got {sql_non_taxable_sum}, expected ~6400091.21"

    # Assert SQL aggregates match engine calculations (the critical check)
    assert sql_taxable_sum == pytest.approx(engine_taxable, abs=0.01), \
        f"Taxable mismatch: SQL sum {sql_taxable_sum}, engine {engine_taxable}"
    assert sql_non_taxable_sum == pytest.approx(engine_non_taxable, abs=0.01), \
        f"Non-taxable mismatch: SQL sum {sql_non_taxable_sum}, engine {engine_non_taxable}"

    # Assert the engine's by_category breakdown sums to the totals
    by_category = realised.get("by_category", {})
    taxable_by_cat_sum = sum(by_category.get(cat, 0) for cat in TAXABLE_INCOME_CATEGORIES)
    non_taxable_by_cat_sum = sum(by_category.get(cat, 0) for cat in NON_TAXABLE_INCOME_CATEGORIES)

    # Assert category components sum to engine totals (internal consistency check)
    assert abs(taxable_by_cat_sum - engine_taxable) <= 0.01, \
        f"Taxable category sum mismatch: by_category {taxable_by_cat_sum}, engine {engine_taxable}"
    assert abs(non_taxable_by_cat_sum - engine_non_taxable) <= 0.01, \
        f"Non-taxable category sum mismatch: by_category {non_taxable_by_cat_sum}, engine {engine_non_taxable}"

    # Verify that if realised_income_to_date returns a total key, it equals the sum of components
    if "total" in realised:
        total = realised.get("total", 0)
        expected_total = engine_taxable + engine_non_taxable + engine_unclassified
        assert abs(total - expected_total) <= 0.01, \
            f"Total mismatch: realised['total'] {total}, sum of components {expected_total}"
