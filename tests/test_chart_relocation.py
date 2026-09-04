"""
Test that relocated charts render successfully on their new screens.
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_transactions_charts():
    """Verify Monthly and Categories charts exist on TransactionsScreen."""
    from PyQt6.QtWidgets import QApplication
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance() or QApplication([])

    from ui.transactions_screen import TransactionsScreen
    screen = TransactionsScreen()

    assert hasattr(screen, 'monthly_chart'), "TransactionsScreen missing monthly_chart"
    assert hasattr(screen, 'category_chart'), "TransactionsScreen missing category_chart"
    assert screen.monthly_chart is not None, "monthly_chart is None"
    assert screen.category_chart is not None, "category_chart is None"
    print("[PASS] Transactions charts present")


def test_accounts_bank_chart():
    """Verify Bank-wise chart exists on AccountsScreen."""
    from PyQt6.QtWidgets import QApplication
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance() or QApplication([])

    from ui.accounts_screen import AccountsScreen
    screen = AccountsScreen()

    assert hasattr(screen, 'bank_chart'), "AccountsScreen missing bank_chart"
    assert screen.bank_chart is not None, "bank_chart is None"
    print("[PASS] Accounts bank chart present")


def test_fixed_deposits_interest_chart():
    """Verify Interest Trend chart exists on FixedDepositsScreen."""
    from PyQt6.QtWidgets import QApplication
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance() or QApplication([])

    from ui.fixed_deposits_screen import FixedDepositsScreen
    screen = FixedDepositsScreen()

    assert hasattr(screen, 'interest_chart'), "FixedDepositsScreen missing interest_chart"
    assert screen.interest_chart is not None, "interest_chart is None"
    print("[PASS] Fixed Deposits interest chart present")


if __name__ == "__main__":
    test_transactions_charts()
    test_accounts_bank_chart()
    test_fixed_deposits_interest_chart()
    print("\n[OK] All chart relocation tests passed!")
