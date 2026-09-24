r"""tools/real_ui_tests/rebuild_p2_2_banks.py — Phase 2.2 Banks.

Precondition: Bank = 0. If Bank = 4 and all rows match, skip.
"""
import sys
import sqlite3
import faulthandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from tools.real_ui_tests.rebuild_common import (
    bootstrap_app, adopt_window, os_click, os_type,
    login_to_dashboard, set_fy, snapshot_db, append_progress,
    redacting_logger, nav_click, prearm, wait_until,
)
from tools.real_ui_test_harness import RealUIHarness, find_by_accessible_name, find_dialog_by_title

faulthandler.dump_traceback_later(900, exit=True)
log = redacting_logger("P2_2_banks")
RUIH_DIR = Path(__file__).resolve().parent / "screenshots" / "rebuild"

BANKS = [
    ("Jana", "Jana Small Finance Bank", "BLRJ07125G"),
    ("IDFC FIRST", "IDFC FIRST Bank", None),
    ("Ujjivan", "Ujjivan Small Finance Bank", "DELU05703F"),
    ("Equitas", "Equitas Small Finance Bank", "CHEV00751C"),
]


def main():
    from config import DB_PATH
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QDialog

    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    n_bank = conn.execute("SELECT COUNT(*) FROM Bank").fetchone()[0]
    conn.close()

    if n_bank == 4:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        rows = conn.execute("SELECT bank_name, nickname, tan_code FROM Bank ORDER BY bank_id").fetchall()
        conn.close()
        expected = {(name, nick) for nick, name, tan in BANKS}
        got = {(r[0], r[1]) for r in rows}
        log.log(f"Bank already = 4: {rows}")
        if got == expected:
            log.log("Fields match — skipping entry, will verify + snapshot")
            skip_entry = True
        else:
            log.log(f"STOP: Bank=4 but rows do not match. expected={expected} got={got}")
            sys.exit(1)
    elif n_bank == 0:
        skip_entry = False
    else:
        log.log(f"STOP: unexpected Bank count = {n_bank}")
        sys.exit(1)

    app = bootstrap_app()
    harness = RealUIHarness(screenshot_dir=str(RUIH_DIR))
    dashboard = login_to_dashboard(harness)
    set_fy(harness, dashboard, "2025-26")
    log.log("logged in, FY set to 2025-26")

    if not skip_entry:
        nav_click(harness, dashboard, "Settings")
        os_click(harness, dashboard, "Manage banks (master)", wait=1.0)

        from ui.manage_data_screen import ManageDataScreen
        wait_until(harness, lambda: find_dialog_by_title(QDialog, "Manage Data", timeout=0.1) is not None, timeout=5)
        dlg = find_dialog_by_title(QDialog, "Manage Data", timeout=1.0)
        assert dlg is not None
        manage_widget = dlg.findChild(ManageDataScreen)
        tabs = manage_widget.tabs
        tab_rect = tabs.tabBar().tabRect(1)  # Banks tab
        QTest.mouseClick(tabs.tabBar(), Qt.MouseButton.LeftButton, pos=tab_rect.center())
        harness.settle(0.5)
        log.log(f"Banks tab selected: currentIndex={tabs.currentIndex()}")
        assert tabs.currentIndex() == 1

        # Cancel path exercise first
        from ui.dialogs.bank_dialog import BankDialog
        cancel_state = {}

        def cancel_fill():
            bd = find_dialog_by_title(BankDialog, "Add Bank", timeout=5.0)
            if bd is None:
                cancel_state["error"] = "BankDialog not found (cancel test)"
                return
            os_type(harness, bd, "Bank nickname", "RUIH_CancelTest")
            os_click(harness, bd, "Cancel bank dialog", wait=0.8)
            cancel_state["done"] = True

        prearm(app, cancel_fill)
        os_click(harness, manage_widget, "Add bank", wait=1.5)
        harness.settle(0.5)
        log.log(f"cancel path state={cancel_state}")
        assert cancel_state.get("done"), cancel_state.get("error")
        n_after_cancel = manage_widget.banks_table.rowCount()
        log.log(f"banks_table.rowCount() after cancel = {n_after_cancel} (expect 0)")
        assert n_after_cancel == 0

        for nickname, bank_name, tan in BANKS:
            state = {}

            def fill(nickname=nickname, bank_name=bank_name, tan=tan, state=state):
                bd = find_dialog_by_title(BankDialog, "Add Bank", timeout=5.0)
                if bd is None:
                    state["error"] = f"BankDialog not found for {nickname}"
                    return
                os_type(harness, bd, "Bank nickname", nickname)
                os_type(harness, bd, "Bank name", bank_name)
                if tan:
                    os_type(harness, bd, "Bank TAN", tan)
                os_click(harness, bd, "Save bank", wait=1.0)
                state["saved"] = True

            prearm(app, fill)
            os_click(harness, manage_widget, "Add bank", wait=1.5)
            harness.settle(0.5)
            log.log(f"bank {nickname!r} fill state={state}")
            assert state.get("saved"), state.get("error")

        dlg.close()
        harness.settle(0.5)

    # --- Verify ---
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    rows = conn.execute("SELECT bank_name, nickname, tan_code FROM Bank ORDER BY bank_id").fetchall()
    conn.close()
    log.log(f"Bank rows: {rows}")
    assert len(rows) == 4
    expected = [(name, nick, tan) for nick, name, tan in BANKS]
    got = [(r[0], r[1], r[2]) for r in rows]
    log.log(f"expected={expected}")
    log.log(f"got={got}")
    assert got == expected, f"bank rows mismatch: {got} != {expected}"

    snap = snapshot_db("P2_2")
    log.log(f"snapshot: {snap}")
    append_progress(f"P2.2 banks complete. 4 banks: {[n for n,_,_ in BANKS]}. snapshot={snap}")
    log.log("P2.2 DONE")


if __name__ == "__main__":
    main()
