r"""tools/real_ui_tests/rebuild_p3_10_topbar.py — Phase 3.10 Top bar and navigation.

R only: Navigate all 10 screens, test combos, sidebar toggle, logout flow.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.real_ui_tests.rebuild_p3_common import P3Run, main_wrapper
from tools.real_ui_tests.rebuild_common import (
    os_select_combo, answer_message_box, answer_password_dialog,
    login_to_dashboard, os_click_widget, os_type, adopt_window, os_click
)


def run_r(p):
    dashboard = p.dashboard

    nav_labels = [
        "Overview", "Accounts", "Transactions", "Income & Expectations",
        "Fixed Deposits", "Statement Import", "Tax Documents", "Tax",
        "Income Prediction", "Settings"
    ]

    for label in nav_labels:
        page = p.nav(label)
        p.checks.check(f"Navigation to {label} successful", page is not None)

    p.nav("Overview")
    p.harness.settle(0.5)

    person_items = [dashboard.person_combo.itemText(i) for i in range(dashboard.person_combo.count())]
    p.observe("H10", f"person_combo has {len(person_items)} items: {person_items}")

    from core import session
    current_person_id = session.session.selected_person_id
    p.observe("H11", f"initial selected_person_id={current_person_id}")

    if "All Persons" in person_items:
        os_select_combo(p.harness, dashboard.person_combo, "All Persons")
        p.harness.settle(0.5)
        ok = dashboard.person_combo.currentText() == "All Persons"
        p.checks.check("Person combo select to All Persons", ok)
        ok_session = session.session.selected_person_id is None
        p.checks.check("session.selected_person_id is None for All Persons", ok_session)

    if "Pranav" in person_items:
        os_select_combo(p.harness, dashboard.person_combo, "Pranav")
        p.harness.settle(0.5)
        ok = dashboard.person_combo.currentText() == "Pranav"
        p.checks.check("Person combo select to Pranav", ok)
        ok_session = session.session.selected_person_id == 1
        p.checks.check("session.selected_person_id is 1 for Pranav", ok_session)

    os_select_combo(p.harness, dashboard.person_combo, "All Persons")
    p.harness.settle(0.5)

    account_items = [dashboard.account_combo.itemText(i) for i in range(dashboard.account_combo.count())]
    p.observe("H12", f"account_combo has {len(account_items)} items")

    if "All Accounts" in account_items:
        os_select_combo(p.harness, dashboard.account_combo, "All Accounts")
        p.harness.settle(0.5)
        ok = dashboard.account_combo.currentText() == "All Accounts"
        p.checks.check("Account combo select to All Accounts", ok)
        ok_session = session.session.selected_account_id is None
        p.checks.check("session.selected_account_id is None for All Accounts", ok_session)

    from tools.real_ui_tests.rebuild_common import parse_inr, db_ro
    for item in account_items:
        if item != "All Accounts":
            os_select_combo(p.harness, dashboard.account_combo, item)
            p.harness.settle(0.5)
            ok = dashboard.account_combo.currentText() == item
            p.checks.check(f"Account combo select to {item}", ok)
            ok_session = session.session.selected_account_id is not None
            p.checks.check(f"session.selected_account_id set for {item}", ok_session)
            acct_id = dashboard.account_combo.currentData()
            acct_balance = db_ro().execute(
                "SELECT current_balance FROM BankAccount WHERE account_id=?",
                (acct_id,)
            ).fetchone()
            if acct_balance:
                acct_balance = acct_balance[0]
                kpi_text = dashboard.kpi_balance._value_lbl.text()
                kpi_val = parse_inr(kpi_text)
                ok_kpi = kpi_val is not None and abs(kpi_val - acct_balance) < 0.01
                p.checks.check(f"Total Balance KPI for {item} matches SQL", ok_kpi,
                              f"ui={kpi_val} sql={acct_balance}")

    os_select_combo(p.harness, dashboard.account_combo, "All Accounts")
    p.harness.settle(0.5)

    fy_items = [dashboard.fy_combo.itemText(i) for i in range(dashboard.fy_combo.count())]
    p.observe("H13", f"fy_combo items: {fy_items}")

    expected_fys = ["2024-25", "2025-26", "2026-27"]
    for expected_fy in expected_fys:
        if expected_fy in fy_items:
            os_select_combo(p.harness, dashboard.fy_combo, expected_fy)
            p.harness.settle(0.5)
            ok = dashboard.fy_combo.currentText() == expected_fy
            p.checks.check(f"FY combo select to {expected_fy}", ok)
            ok_session = session.session.selected_fy == expected_fy
            p.checks.check(f"session.selected_fy is {expected_fy}", ok_session)

    os_select_combo(p.harness, dashboard.fy_combo, "2025-26")
    p.harness.settle(0.5)

    from PySide6.QtWidgets import QWidget
    sidebar = dashboard.findChild(QWidget, "sidebar")

    initial_width = sidebar.width() if sidebar else 248
    p.observe("H14", f"initial_sidebar_width={initial_width}")

    is_expanded = dashboard.sidebar_expanded
    toggle_text = "Collapse sidebar" if is_expanded else "Expand sidebar"

    os_click_widget(p.harness, dashboard._sidebar_toggle_btn, wait=1.0)
    p.harness.settle(1.0)

    new_width = sidebar.width() if sidebar else None
    p.observe("H15", f"after_toggle_sidebar_width={new_width}")

    width_changed = new_width is not None and new_width != initial_width
    p.checks.check("Sidebar width changed after toggle", width_changed,
                   f"initial={initial_width} new={new_width}")

    ok_expanded = dashboard.sidebar_expanded != is_expanded
    p.checks.check("sidebar_expanded property toggled", ok_expanded)

    import core.session
    config_file = Path(core.session._CONFIG_FILE)
    if config_file.exists():
        import json
        try:
            theme_prefs = json.loads(config_file.read_text())
            sidebar_open_pref = theme_prefs.get("sidebar_open")
            ok_pref = sidebar_open_pref == dashboard.sidebar_expanded
            p.checks.check("theme_prefs.json sidebar_open updated", ok_pref,
                           f"pref={sidebar_open_pref} state={dashboard.sidebar_expanded}")
        except Exception as e:
            p.checks.check("theme_prefs.json sidebar_open readable", False, str(e))

    os_click_widget(p.harness, dashboard._sidebar_toggle_btn, wait=1.0)
    p.harness.settle(1.0)

    ok_restored = dashboard.sidebar_expanded == is_expanded
    p.checks.check("Sidebar restored to original state", ok_restored)

    from PySide6.QtWidgets import QMessageBox
    msg_answer = answer_message_box(p.harness, p.app, QMessageBox.StandardButton.No, expect_title="Logout")
    p.app.processEvents()
    time.sleep(0.1)

    os_click(p.harness, dashboard, "Logout", wait=0.6)
    p.harness.settle(1.0)

    if hasattr(msg_answer, "info"):
        p.observe("H16", f"logout_msgbox={msg_answer.info}")

    ok_still_dashboard = any(isinstance(w, type(dashboard)) and w.isVisible() for w in p.app.allWidgets())
    p.checks.check("Dashboard still visible after rejecting logout", ok_still_dashboard)

    msg_answer2 = answer_message_box(p.harness, p.app, QMessageBox.StandardButton.Yes, expect_title="Logout")
    p.app.processEvents()
    time.sleep(0.1)

    os_click(p.harness, dashboard, "Logout", wait=0.6)
    p.harness.settle(1.0)

    from ui.login_screen import LoginScreen
    ok_login_shown = any(isinstance(w, LoginScreen) and w.isVisible() for w in p.app.allWidgets())
    p.checks.check("LoginScreen shown after logout", ok_login_shown)

    ok_aes_key = session.session.aes_key is None
    p.checks.check("session.aes_key is None after logout", ok_aes_key)

    login_screen = next((w for w in p.app.allWidgets() if isinstance(w, LoginScreen) and w.isVisible()), None)
    if login_screen:
        adopt_window(login_screen)
        os_type(p.harness, login_screen, "Master password", "RUIH_wrong_pw1", secret=True)
        os_click(p.harness, login_screen, "Unlock account", wait=0.8)
        p.harness.settle(1.0)

        error_text = login_screen.error_label.text() if hasattr(login_screen, "error_label") else ""
        ok_error = len(error_text) > 0
        p.checks.check("Login error shown for wrong password", ok_error, f"error={error_text}")

        login_to_dashboard(p.harness, login_screen=login_screen)
        p.harness.settle(1.0)

        ok_logged_back = any(isinstance(w, type(dashboard)) and w.isVisible() for w in p.app.allWidgets())
        p.checks.check("Dashboard shown after re-login", ok_logged_back)

        ok_aes_key_restored = session.session.aes_key is not None
        p.checks.check("session.aes_key restored after re-login", ok_aes_key_restored)

        for w in p.app.allWidgets():
            if isinstance(w, type(dashboard)) and w.isVisible():
                dashboard = w
                break
        p.dashboard = dashboard
        p.harness.window = dashboard


def run_s(p):
    p.checks.check("S part", True, "n/a")


if __name__ == "__main__":
    main_wrapper("10", "topbar", run_r, run_s)
