#!/usr/bin/env python3
"""Test that all screens construct successfully under all themes."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from core.database import initialise_database

# Track theme names
THEMES = ["Aurora", "Midnight", "Forest", "Sunset"]

def test_screen_construction():
    """Construct every screen under all 4 themes."""
    app = QApplication(sys.argv)
    initialise_database()

    from ui.theme import Theme, ThemeManager

    results = []
    failures = []

    for theme_name in THEMES:
        print(f"\nTesting theme: {theme_name}")
        ThemeManager.apply(theme_name)
        app.setStyleSheet(Theme.get_stylesheet())

        # List of all screens to test
        screens = [
            ("AccountsScreen", "ui.accounts_screen", "AccountsScreen"),
            ("TransactionsScreen", "ui.transactions_screen", "TransactionsScreen"),
            ("FixedDepositsScreen", "ui.fixed_deposits_screen", "FixedDepositsScreen"),
            ("IncomeManagementScreen", "ui.income_management_screen", "IncomeManagementScreen"),
            ("StatementImportScreen", "ui.statement_import_screen_modern", "StatementImportScreen"),
            ("AISTISImportScreen", "ui.ais_tis_import_screen_v2", "AISTISImportScreenV2"),
            ("TaxScreen", "ui.tax_screen", "TaxScreen"),
            ("SettingsScreen", "ui.settings_screen", "SettingsScreen"),
            ("LoginScreen", "ui.login_screen", "LoginScreen"),
            ("SetupScreen", "ui.setup_screen", "SetupScreen"),
        ]

        for screen_name, module_name, class_name in screens:
            try:
                module = __import__(module_name, fromlist=[class_name])
                screen_class = getattr(module, class_name)

                # Construct the screen
                screen = screen_class()
                results.append(f"[OK] {theme_name}: {screen_name}")
                print(f"  [OK] {screen_name}")
                screen.deleteLater()
            except Exception as e:
                error_msg = f"[FAIL] {theme_name}: {screen_name}: {type(e).__name__}: {str(e)}"
                failures.append(error_msg)
                results.append(error_msg)
                print(f"  [FAIL] {screen_name}: {e}")

    print("\n" + "="*70)
    print("RESULTS:")
    print("="*70)
    for result in results:
        print(result)

    if failures:
        print(f"\n[FAIL] {len(failures)} screen(s) failed to construct")
        return False
    else:
        print(f"\n[PASS] All screens constructed successfully under all {len(THEMES)} themes")
        return True

if __name__ == "__main__":
    try:
        success = test_screen_construction()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[FAIL] Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
