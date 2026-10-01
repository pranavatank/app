r"""tools/real_ui_tests/rebuild_p3_11_hard_refresh.py — Phase 3.11 Hard Refresh test (R only)

Validates that hard refresh reloads all app modules, preserves session state.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.real_ui_tests.rebuild_p3_common import P3Run, main_wrapper
from tools.real_ui_tests.rebuild_common import os_click, read_secret
from PySide6.QtWidgets import QApplication


def run_r(p):
    if os.environ.get('FINMGR_SCRATCH'):
        p.log.log("Exiting: FINMGR_SCRATCH is set in R-mode")
        sys.exit(2)

    nav_labels = [
        "Overview", "Accounts", "Transactions", "Income & Expectations",
        "Fixed Deposits", "Statement Import", "Tax Documents", "Tax",
        "Income Prediction", "Settings"
    ]

    p.nav("Settings")
    p.harness.settle(0.5)

    try:
        os_click(p.harness, p.dashboard, "Hard Refresh", wait=0.5)
    except Exception:
        p.checks.check("hard refresh button found", False, "click failed")
        return

    p.harness.settle(3.0)

    secret = read_secret('master')

    from core import session
    old_stack = p.dashboard.stack
    old_title = p.dashboard.page_title_lbl

    aes_key_before = None
    if hasattr(session, 'session') and hasattr(session.session, 'aes_key'):
        aes_key_before = session.session.aes_key

    selected_fy_before = None
    if hasattr(session, 'session') and hasattr(session.session, 'selected_fy'):
        selected_fy_before = session.session.selected_fy

    p.observe("P3.11_R_aes_key", str(aes_key_before is None))
    p.observe("P3.11_R_selected_fy", str(selected_fy_before))

    try:
        dashboard_widgets = [w for w in QApplication.instance().topLevelWidgets()
                             if hasattr(w, '_screen_pages')]
        if dashboard_widgets:
            p.dashboard = dashboard_widgets[0]
            p.harness.window = p.dashboard
            ok_reference = p.dashboard is not None
            p.checks.check("hard refresh dashboard reference updated", ok_reference)
            ok_stack = p.dashboard.stack is not old_stack
            p.checks.check("hard refresh rebuilds stack", ok_stack)
            ok_errors = p.dashboard._screen_errors == {}
            p.checks.check("hard refresh clears screen errors", ok_errors)
            ok_title_hidden = not old_title.isVisible()
            p.checks.check("hard refresh resets page title visibility", ok_title_hidden)
        else:
            p.checks.check("hard refresh dashboard reference updated", False, "no dashboard found")
    except Exception as e:
        p.checks.check("hard refresh dashboard update", False, str(e))

    aes_key_after = None
    if hasattr(session, 'session') and hasattr(session.session, 'aes_key'):
        aes_key_after = session.session.aes_key
    ok_aes_after = aes_key_after is not None
    p.checks.check("hard refresh keeps session key", ok_aes_after,
                  f"aes_key is None: {aes_key_after is None}")

    for label in nav_labels:
        try:
            page = p.nav(label)
            p.harness.settle(0.5)
            ok = page is not None
            p.checks.check(f"hard refresh nav {label} ok", ok)
        except Exception as e:
            p.checks.check(f"hard refresh nav {label} ok", False, detail=str(e))


def run_s(p):
    p.checks.check("S mode unused", True, "n/a")


if __name__ == "__main__":
    main_wrapper("11", "Hard Refresh", run_r, run_s)
