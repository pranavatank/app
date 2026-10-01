r"""tools/real_ui_tests/rebuild_p3_common.py — Common harness for Phase 3 UI tests.

Lazy-loads navigation items and page screens. Strict R-mode guards ensure the real
database remains unchanged during read-only test runs. Integrates fingerprinting,
accessibility tracking, watchdog monitoring, and structured results output.
"""
import os
import sys
import json
import time
import sqlite3
import argparse
import faulthandler
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.real_ui_tests.rebuild_common import (
    bootstrap_app, login_to_dashboard, set_fy, nav_click, db_ro,
    fingerprint_real_db, diff_fingerprints, require_scratch,
    append_progress, read_theme_prefs, restore_theme_prefs,
    Checks, run_logged, redacting_logger, close_all_windows,
    start_modal_watchdog, REAL_DB_PATH, RUIH_DIR,
)
from tools.real_ui_test_harness import RealUIHarness

import config

# Lazy-loaded navigation labels; import happens only inside functions
NAV = None

def _get_nav():
    global NAV
    if NAV is None:
        from ui.dashboard_screen import _NAV_ITEMS
        NAV = [item[0] for item in _NAV_ITEMS]
    return NAV

# Strict guard: real DB must not change in R runs
R_ALLOWED = set()

# Page attribute names by navigation index
PAGE_ATTRS = {
    0: None,  # Overview: built early, not stored as self.overview_page
    1: "accounts_page",
    2: "transactions_page",
    3: "income_page",
    4: "fd_page",
    5: "import_page",
    6: "tax_documents_page",
    7: "tax_page",
    8: "prediction_page",
    9: "settings_page",
}


class P3Run:
    """Phase 3 test run harness: setup, navigation, observation, and teardown."""

    def __init__(self, nn, screen, env):
        """Initialize P3 run. env in {"R", "S"}.

        R: read-only on real DB; validates env constraints (FINMGR_SCRATCH not set, real path).
        S: scratch DB via require_scratch(); allows mutations for testing.
        """
        self.env = env
        self.nn = nn
        self.screen = screen
        self.part = None  # May be set by argparse for partial runs

        if env == "R":
            real_path = Path(config.DB_PATH).resolve()
            if real_path != REAL_DB_PATH.resolve():
                print(f"ERROR: R-mode but config.DB_PATH != REAL_DB_PATH")
                print(f"  config.DB_PATH:    {real_path}")
                print(f"  REAL_DB_PATH:      {REAL_DB_PATH.resolve()}")
                sys.exit(2)
            if os.environ.get("FINMGR_SCRATCH"):
                print(f"ERROR: R-mode but FINMGR_SCRATCH is set")
                sys.exit(2)
        elif env == "S":
            require_scratch()
        else:
            raise ValueError(f"env must be 'R' or 'S', got {env!r}")

        self.log = redacting_logger(f"P3_{nn}_{screen}_{env}")
        self.checks = Checks(self.log)
        self.observations = []
        self.prefs_bytes = read_theme_prefs()

        # Fingerprint real DB before bootstrap (only meaningful in R-mode, but capture always)
        real_path = Path(config.DB_PATH).resolve()
        if real_path == REAL_DB_PATH.resolve():
            self.fp_before = fingerprint_real_db(str(real_path))
        else:
            self.fp_before = None

        faulthandler.dump_traceback_later(3600, exit=True)

        self.app = None
        self.harness = None
        self.dashboard = None
        self.expected_titles = set()
        self.watchdog = None

    def start(self, fy="2025-26"):
        """Bootstrap app, login, set FY, start watchdog. Return dashboard."""
        self.app = bootstrap_app()
        self.harness = RealUIHarness(screenshot_dir=str(RUIH_DIR))
        self.dashboard = login_to_dashboard(self.harness)
        set_fy(self.harness, self.dashboard, fy)
        self.expected_titles = set()
        self.watchdog = start_modal_watchdog(self.harness, self.log, self.expected_titles)
        self.log.log(f"P3Run started: env={self.env} nn={self.nn} screen={self.screen}")
        return self.dashboard

    def nav(self, label):
        """Navigate to page by label. Check index, title, screen errors. Return page widget."""
        nav_labels = _get_nav()
        if label not in nav_labels:
            raise LookupError(f"nav label not found: {label!r}, available: {nav_labels}")
        idx = nav_labels.index(label)

        nav_click(self.harness, self.dashboard, label)
        self.harness.settle(2.5)

        ok_idx = self.dashboard.stack.currentIndex() == idx
        self.checks.check(f"nav {label} index", ok_idx, f"expected {idx}, got {self.dashboard.stack.currentIndex()}")

        page_title = self.dashboard.page_title_lbl.text()
        ok_title = page_title == label
        self.checks.check(f"nav {label} title", ok_title, f"expected {label!r}, got {page_title!r}")

        ok_error = idx not in self.dashboard._screen_errors
        self.checks.check(f"nav {label} no screen error", ok_error,
                         detail=self.dashboard._screen_errors.get(idx, ""))

        # Get and return the page widget
        page = self.dashboard._screen_pages.get(idx)
        if page is None:
            # May need to trigger lazy load; in normal nav flow it should be loaded
            page = self.dashboard._get_screen_page(idx)
        return page

    def a11y(self, control, located_by):
        """Record accessibility observation: control locator."""
        self.checks.a11y.append({"control": control, "located_by": located_by})

    def observe(self, key, text):
        """Record a named observation (e.g., screen state, UI value). Text is redacted in logs."""
        from tools.real_ui_tests.rebuild_common import redact
        redacted = redact(text) if text else text
        self.log.log(f"[OBS] {key}: {redacted}")
        self.observations.append({"key": key, "text": redacted})

    def sql(self, q, params=()):
        """Execute read-only query against DB. Return fetchall(), close connection."""
        conn = db_ro()
        try:
            return conn.execute(q, params).fetchall()
        finally:
            conn.close()

    def finish(self):
        """Teardown: close windows, restore prefs, verify DB unchanged (R-mode), save results."""
        faulthandler.cancel_dump_traceback_later()
        try:
            close_all_windows()
            restore_theme_prefs(self.prefs_bytes)

            # R-mode: verify DB fingerprint unchanged
            if self.env == "R" and self.fp_before is not None:
                real_path = Path(config.DB_PATH).resolve()
                fp_after = fingerprint_real_db(str(real_path))
                changed = diff_fingerprints(self.fp_before, fp_after, allowed=R_ALLOWED)
                ok = len(changed) == 0
                detail = f"changed tables: {changed}" if changed else ""
                self.checks.check("real DB fingerprint unchanged (R)", ok, detail)

            # Add watchdog failures as FAIL checks
            if self.watchdog and self.watchdog.failures:
                for fail in self.watchdog.failures:
                    self.checks.check(f"watchdog {fail['title']}", False, detail=str(fail))

            # Write results JSON
            results_path = RUIH_DIR / f"P3_{self.nn}_{self.screen}_{self.env}.json"
            extra = {"screen": self.screen, "env": self.env, "watchdog": self.watchdog.failures if self.watchdog else [], "observations": self.observations}
            rc = self.checks.finish(str(results_path), extra=extra)

            # Append progress
            total = len(self.checks.results)
            passed = sum(1 for r in self.checks.results if r["ok"])
            append_progress(f"P3.{self.nn} {self.screen} {self.env}: {passed}/{total} PASS")

            return rc
        except Exception as e:
            self.log.log(f"finish() error: {e!r}")
            import traceback
            self.log.log(traceback.format_exc())
            return 1

def main_wrapper(nn, screen, run_r, run_s):
    """Main entry point for P3 tests.

    Parses --env (required, R/S) before any Qt import (so --help is safe).
    Creates P3Run, calls start(), runs run_r(p) or run_s(p), calls finish() in finally.

    Args:
        nn: phase number (string, e.g., "01")
        screen: screen name (string, e.g., "overview")
        run_r: callable(P3Run) for R-mode
        run_s: callable(P3Run) for S-mode
    """
    parser = argparse.ArgumentParser(description=f"Phase 3.{nn} {screen} test")
    parser.add_argument("--env", required=True, choices=["R", "S"],
                       help="R: read-only real DB, S: scratch DB")
    parser.add_argument("--part", default=None,
                       help="Optional: partial run identifier (e.g., 'a', 'b')")
    args = parser.parse_args()

    env = args.env
    run_fn = run_r if env == "R" else run_s

    def main():
        p = P3Run(nn, screen, env)
        p.part = args.part
        try:
            p.start()
            run_fn(p)
        except Exception as e:
            p.log.log(traceback.format_exc())
            p.checks.check("run completed", False, repr(e))
            rc = p.finish()
        else:
            rc = p.finish()
        finally:
            sys.exit(rc)

    run_logged(main, f"P3_{nn}_{screen}_crash")


if __name__ == "__main__":
    # Simple help handler (no Qt import)
    if "--help" in sys.argv or "-h" in sys.argv:
        print("rebuild_p3_common.py: import this module; do not run directly")
        print("\nUsage: from tools.real_ui_tests.rebuild_p3_common import P3Run, main_wrapper")
        print("  main_wrapper(nn, screen, run_r, run_s) — entry point for P3 test scripts")
        print("  P3Run(nn, screen, env) — test run harness")
        sys.exit(0)
    print("rebuild_p3_common.py: import this module; do not run directly")
    sys.exit(1)
