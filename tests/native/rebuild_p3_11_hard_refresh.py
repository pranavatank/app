r"""tests/native/rebuild_p3_11_hard_refresh.py — Phase 3.11 Hard Refresh test (R only)

Validates that hard refresh reloads all app modules, preserves session state.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tests.native.rebuild_p3_common import P3Run, main_wrapper, _get_nav
from tests.native.rebuild_common import os_click, read_secret
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid


def run_r(p):
    if os.environ.get('FINMGR_SCRATCH'):
        p.log.log("Exiting: FINMGR_SCRATCH is set in R-mode")
        sys.exit(2)

    nav_labels = list(_get_nav())

    p.nav("Settings")
    p.harness.settle(0.5)

    # Keep before-state references before clicking: the refresh rebuilds the
    # dashboard synchronously inside the button handler, and old Qt wrappers
    # may be deleted as part of that rebuild.
    from core import session as session_module
    old_stack = p.dashboard.stack
    old_title = p.dashboard.page_title_lbl
    old_session = session_module.session
    old_set_fy = session_module.Session.set_financial_year
    selected_fy_before = old_session.selected_fy
    key_present_before = old_session.aes_key is not None
    key_fingerprint_before = old_session.aes_key
    p.observe("P3.11_R_aes_key_present_before", str(key_present_before))
    p.observe("P3.11_R_selected_fy_before", str(selected_fy_before))

    try:
        p.wait_for_page_jobs("before Hard Refresh")
        os_click(p.harness, p.dashboard, "Hard Refresh", wait=0.5)
    except Exception:
        p.checks.check("hard refresh button found", False, "click failed")
        return

    p.harness.settle(3.0)

    # Module reload resets the helper's redaction registry. Re-register the
    # master secret for any later diagnostics; never retain or log its value.
    read_secret("master")

    import importlib
    current_session_module = importlib.import_module("core.session")
    current_session = current_session_module.session
    p.checks.check("hard refresh reloaded core.session implementation",
                   current_session_module.Session.set_financial_year is not old_set_fy)

    dashboard_widgets = [w for w in QApplication.instance().topLevelWidgets()
                         if hasattr(w, '_screen_pages')]
    if dashboard_widgets:
        refreshed_dashboard = dashboard_widgets[0]
        p.dashboard = refreshed_dashboard
        p.harness.window = refreshed_dashboard
        p.checks.check("hard refresh dashboard reference updated", refreshed_dashboard is not None)
        p.checks.check("hard refresh rebuilds stack", refreshed_dashboard.stack is not old_stack)
        p.checks.check("hard refresh clears screen errors", refreshed_dashboard._screen_errors == {})
        # Deleted Qt wrappers are expected after rebuilding. Check validity
        # before touching the old title; if it remains alive, verify it hid.
        old_title_valid = isValid(old_title)
        p.checks.check("hard refresh disposes old page title", not old_title_valid or not old_title.isVisible())
    else:
        p.checks.check("hard refresh dashboard reference updated", False, "no dashboard found")

    key_present_after = current_session.aes_key is not None
    key_equal_after = current_session.aes_key == key_fingerprint_before
    p.checks.check("hard refresh preserves session key", key_present_before and key_present_after and key_equal_after,
                  f"present before={key_present_before}, after={key_present_after}; value_equal={key_equal_after}")
    p.checks.check("hard refresh retains selected FY", current_session.selected_fy == selected_fy_before,
                   f"before={selected_fy_before}, after={current_session.selected_fy}")

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
