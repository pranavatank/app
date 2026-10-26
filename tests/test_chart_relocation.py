"""
Test that relocated charts render successfully on their new screens.
"""
import os
import sys
import pytest
from PySide6.QtCore import QCoreApplication,QEvent

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
