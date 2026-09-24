r"""tools/real_ui_tests/rebuild_p2_0_setup.py — Phase 2.0 first-run setup.

Precondition: DB absent, or SELECT COUNT(*) FROM AuthSecurity = 0.
"""
import sys
import os
import time
import faulthandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from tools.real_ui_tests.rebuild_common import (
    bootstrap_app, read_secret, adopt_window, os_click, os_type,
    login_to_dashboard, snapshot_db, db_ro, append_progress, redacting_logger,
)
from tools.real_ui_test_harness import RealUIHarness

faulthandler.dump_traceback_later(900, exit=True)
log = redacting_logger("P2_0_setup")


def main():
    import sqlite3
    from config import DB_PATH

    already_set_up = False
    if os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        try:
            n = conn.execute("SELECT COUNT(*) FROM AuthSecurity").fetchone()[0]
        except sqlite3.OperationalError:
            n = 0
        conn.close()
        if n > 0:
            log.log(f"AuthSecurity already has {n} row(s); checking resume rule")
            master_pw = read_secret("master")
            from core.auth import verify_login
            ok = verify_login(master_pw)[0]
            log.log(f"verify_login(stored master pw)[0] = {ok}")
            if ok:
                log.log("P2.0 setup step already complete (login works) — will log in directly "
                         "and still run full verification + snapshot")
                already_set_up = True
            else:
                log.log("STOP: AuthSecurity exists but master password does not verify. Escalating per plan resume rule.")
                sys.exit(1)

    app = bootstrap_app()
    log.log("bootstrap_app() done, DB initialised")

    harness = RealUIHarness(screenshot_dir=str(Path(__file__).resolve().parent / "screenshots" / "rebuild"))

    if not already_set_up:
        from ui.setup_screen import SetupScreen
        from core.auth import is_first_run

        setup = harness.launch(lambda: SetupScreen(), title="RUIH_SETUP", maximized=False)
        adopt_window(setup)
        log.log("SetupScreen launched")

        # --- Negative checks first (never write) ---
        os_type(harness, setup, "Master password input", "abcd", secret=True)
        os_type(harness, setup, "Confirm password input", "abcd", secret=True)
        os_click(harness, setup, "Create account", wait=1.0)
        still_first = is_first_run()
        log.log(f"negative check 1 (short/matching 5-char): is_first_run()={still_first}")
        assert still_first, "REGRESSION: short password was accepted"

        os_type(harness, setup, "Master password input", "abcdefgh", secret=True)
        os_type(harness, setup, "Confirm password input", "zzzzzzzz", secret=True)
        os_click(harness, setup, "Create account", wait=1.0)
        still_first = is_first_run()
        log.log(f"negative check 2 (mismatched): is_first_run()={still_first}")
        assert still_first, "REGRESSION: mismatched password was accepted"

        # --- Real setup ---
        master_pw = read_secret("master")
        os_type(harness, setup, "Master password input", master_pw, secret=True)
        os_type(harness, setup, "Confirm password input", master_pw, secret=True)

        totp_check = harness.find(setup, "Enable two-factor authentication")
        log.log(f"TOTP checkbox isChecked() before save = {totp_check.isChecked()}")
        assert totp_check.isChecked() is False

        os_click(harness, setup, "Create account", wait=1.5)

        deadline = time.time() + 10
        login_screen = None
        while time.time() < deadline:
            if hasattr(setup, "login") and setup.login is not None and setup.login.isVisible():
                login_screen = setup.login
                break
            app.processEvents()
            time.sleep(0.2)
        if login_screen is None:
            log.log("FINDING (Critical): setup.login did not become visible within 10s after "
                     "'Create account'. Root cause confirmed by direct inspection: "
                     "ui/setup_screen.py:_on_setup calls show_success()/show_warning() "
                     "(ui/widgets/toast_utils.py) BEFORE any DashboardScreen has ever been "
                     "constructed in this process, so the module-level _toast_container is "
                     "still None and show_toast() raises RuntimeError — which aborts the rest "
                     "of _on_setup (creating/showing self.login, self.close()) even though the "
                     "DB write (setup_master_password) already completed. A real first-time "
                     "user clicking 'Create account' would see the app appear to hang on the "
                     "setup screen after account creation succeeds, with no visible transition "
                     "to login, and would have to restart the app to reach LoginScreen.")
            from core.auth import is_first_run as _ifr
            log.log(f"Confirming DB write nonetheless succeeded: is_first_run() now = {_ifr()}")
            assert not _ifr(), "setup_master_password did not persist despite the exception"
            log.log("Working around the bug for this rebuild run: launching a fresh LoginScreen "
                     "directly (equivalent to a real user restarting main.py), which is the only "
                     "way a real user could proceed past this bug.")
            from ui.login_screen import LoginScreen
            login_screen = harness.launch(lambda: LoginScreen(), title="RUIH_LOGIN", maximized=False)
            adopt_window(login_screen)
        else:
            log.log("setup.login is visible — setup succeeded without hitting the toast bug this time")

        dashboard = login_to_dashboard(harness, master_pw=master_pw, login_screen=login_screen)
        log.log("login_to_dashboard succeeded, dashboard adopted")
    else:
        dashboard = login_to_dashboard(harness, master_pw=master_pw)
        log.log("login_to_dashboard succeeded (resume path), dashboard adopted")

    # --- Verify ---
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    row = conn.execute("SELECT totp_secret, privacy_mode_enabled, device_id_hash FROM AuthSecurity").fetchall()
    assert len(row) == 1, f"AuthSecurity row count != 1: {len(row)}"
    totp_secret, privacy_mode, device_hash = row[0]
    log.log(f"AuthSecurity: rows=1 totp_secret_is_null={totp_secret is None} privacy_mode_enabled={privacy_mode}")

    from core.auth import get_device_fingerprint, verify_login
    expected_fp = get_device_fingerprint()
    log.log(f"device_id_hash matches get_device_fingerprint(): {device_hash == expected_fp}")

    verify_ok = verify_login(master_pw)[0]
    log.log(f"verify_login(pw)[0] = {verify_ok}")
    assert verify_ok

    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()]
    log.log(f"CREATE TABLE count = {len(tables)}: {sorted(tables)}")

    slab_count = conn.execute("SELECT COUNT(*) FROM TaxSlabConfig").fetchone()[0]
    tp_rows = conn.execute(
        "SELECT financial_year, rebate_87a_limit, standard_deduction FROM TaxParams"
    ).fetchall()
    log.log(f"TaxSlabConfig={slab_count} (expect 14) TaxParams rows={tp_rows} (expect 2, "
            f"rebate_87a_limit=1200000, standard_deduction=75000)")

    fd_conv = conn.execute("SELECT COUNT(*) FROM BankFDConvention").fetchone()[0]
    log.log(f"BankFDConvention={fd_conv} (expect 0, no banks yet)")
    conn.close()

    n_nav = len(dashboard._nav_buttons)
    n_stack = dashboard.stack.count()
    person_items = [dashboard.person_combo.itemText(i) for i in range(dashboard.person_combo.count())]
    log.log(f"nav_buttons={n_nav} stack.count()={n_stack} person_combo={person_items}")
    assert n_nav == 10 and n_stack == 10
    assert person_items == ["All Persons"]

    snap = snapshot_db("P2_0")
    log.log(f"snapshot: {snap}")
    append_progress(f"P2.0 setup complete. snapshot={snap}")
    log.log("P2.0 DONE")


def _has_cols(conn, table):
    try:
        conn.execute(f"SELECT param_name FROM {table} LIMIT 1")
        return True
    except Exception:
        return False


if __name__ == "__main__":
    main()
