"""
Test that relocated charts render successfully on their new screens.
"""
import os
import sys
import pytest
from PySide6.QtCore import QCoreApplication,QEvent

# Add project root to path
from tests.support.repo_paths import REPO_ROOT
sys.path.insert(0, str(REPO_ROOT))

@pytest.fixture(autouse=True)
def close_test_screens(qapp):
    yield
    for screen in qapp.topLevelWidgets():
        screen.close()
        screen.deleteLater()
    QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)


def test_transactions_charts(qapp):
    """Verify Monthly and Categories charts exist on TransactionsScreen."""
    from ui.transactions_screen import TransactionsScreen
    screen = TransactionsScreen()

    assert hasattr(screen, 'monthly_chart'), "TransactionsScreen missing monthly_chart"
    assert hasattr(screen, 'category_chart'), "TransactionsScreen missing category_chart"
    assert screen.monthly_chart is not None, "monthly_chart is None"
    assert screen.category_chart is not None, "category_chart is None"
    print("[PASS] Transactions charts present")


def test_accounts_bank_chart(qapp):
    """Verify bank_chart was intentionally removed from AccountsScreen (F322)."""
    from ui.accounts_screen import AccountsScreen
    screen = AccountsScreen()

    assert not hasattr(screen, 'bank_chart'), "AccountsScreen should not have bank_chart (removed in F322)"
    assert hasattr(screen, 'container'), "AccountsScreen missing account container"
    print("[PASS] Accounts bank chart correctly removed")


def test_fixed_deposits_interest_chart(qapp):
    """Verify Interest Trend chart exists on FixedDepositsScreen."""
    from ui.fixed_deposits_screen import FixedDepositsScreen
    screen = FixedDepositsScreen()

    assert hasattr(screen, 'interest_chart'), "FixedDepositsScreen missing interest_chart"
    assert screen.interest_chart is not None, "interest_chart is None"
    print("[PASS] Fixed Deposits interest chart present")


@pytest.mark.parametrize("canvas_available", [True, False])
def test_chart_data_keeps_exact_values_and_missing_cells(qapp, monkeypatch, canvas_available):
    from PySide6.QtWidgets import QDialog
    from ui.widgets import chart_widget
    from ui.widgets.excel_table import ExcelTable

    if canvas_available and not chart_widget._MPL_AVAILABLE:
        pytest.skip("Matplotlib canvas unavailable")
    monkeypatch.setattr(chart_widget, "_MPL_AVAILABLE", canvas_available)
    chart = chart_widget.ChartWidget()
    chart.plot_trend_line(
        ["Apr", "May", "Jun"],
        {"Actual": [-12_345.6789, None], "Estimated": [0, 42.5]},
        title="Synthetic interest",
        xlabel="Month",
    )
    chart.refresh_theme()
    dialogs_seen = []

    def verify_dialog(dialog):
        table = dialog.findChild(ExcelTable)
        assert table.accessibleName() == "Synthetic interest data table"
        assert table.rowCount() == 3
        assert [table.horizontalHeaderItem(i).text() for i in range(3)] == ["Month", "Actual", "Estimated"]
        assert table.item(0, 1).text() == "-12345.6789"
        assert table.item(0, 2).text() == "0"
        assert table.item(1, 1).text() == "—"
        assert table.item(1, 2).text() == "42.5"
        dialogs_seen.append(dialog)

    monkeypatch.setattr(QDialog, "exec", verify_dialog)
    assert not chart._table_button.isHidden()
    assert chart._table_button.accessibleName() == "View data for Synthetic interest"
    chart._table_button.click()
    assert len(dialogs_seen) == 1
    chart.show_empty_state()
    assert chart._table_button.isHidden()
