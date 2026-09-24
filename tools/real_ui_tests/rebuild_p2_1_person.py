r"""tools/real_ui_tests/rebuild_p2_1_person.py — Phase 2.1 Person.

Precondition: Person = 0. If Person = 1 and all fields match, skip.
"""
import sys
import json
import sqlite3
import faulthandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from tools.real_ui_tests.rebuild_common import (
    bootstrap_app, adopt_window, os_click, os_type, os_select_combo,
    login_to_dashboard, set_fy, snapshot_db, db_ro, append_progress,
    redacting_logger, nav_click, prearm, wait_until,
)
from tools.real_ui_test_harness import RealUIHarness, find_by_accessible_name, find_dialog_by_title

faulthandler.dump_traceback_later(900, exit=True)
log = redacting_logger("P2_1_person")

RUIH_DIR = Path(__file__).resolve().parent / "screenshots" / "rebuild"


def main():
    from config import DB_PATH
    from PySide6.QtCore import QDate
    from PySide6.QtWidgets import QDialog

    seed = json.loads((RUIH_DIR / "P0_person_seed.json").read_text(encoding="utf-8"))
    full_pan = seed["pan"]
    name_tokens = (seed["full_name"] or "").split()
    first_name = name_tokens[0] if name_tokens else ""
    last_name = name_tokens[-1] if len(name_tokens) > 1 else None
    middle_name = " ".join(name_tokens[1:-1]) if len(name_tokens) > 2 else None
    log.log(f"person seed: first={first_name!r} middle={middle_name!r} last={last_name!r} pan_present={bool(full_pan)}")

    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    n_person = conn.execute("SELECT COUNT(*) FROM Person").fetchone()[0]
    conn.close()
    if n_person == 1:
        log.log("Person already = 1; checking whether fields match before skipping")
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        row = conn.execute(
            "SELECT person_id, full_name, first_name, last_name, date_of_birth, pan_number FROM Person"
        ).fetchone()
        conn.close()
        log.log(f"existing Person row: person_id={row[0]} full_name={row[1]!r} pan_matches={row[5]==full_pan}")
        if row[1] == "Pranav" and row[5] == full_pan:
            log.log("Fields match — P2.1 already complete, skipping data entry, will still verify + snapshot")
            skip_entry = True
        else:
            log.log("STOP: Person=1 but fields do not match expectations. Escalating.")
            sys.exit(1)
    elif n_person == 0:
        skip_entry = False
    else:
        log.log(f"STOP: unexpected Person count = {n_person}")
        sys.exit(1)

    app = bootstrap_app()
    harness = RealUIHarness(screenshot_dir=str(RUIH_DIR))
    dashboard = login_to_dashboard(harness)
    set_fy(harness, dashboard, "2025-26")
    log.log("logged in, FY set to 2025-26")

    if not skip_entry:
        nav_click(harness, dashboard, "Settings")
        os_click(harness, dashboard, "Manage people", wait=1.0)

        from ui.manage_data_screen import ManageDataScreen
        dlg = None
        ok = wait_until(harness, lambda: find_dialog_by_title(QDialog, "Manage Data", timeout=0.1) is not None, timeout=5)
        dlg = find_dialog_by_title(QDialog, "Manage Data", timeout=1.0)
        assert dlg is not None, "Manage Data dialog not found"
        log.log("Manage Data dialog open")

        manage_widget = dlg.findChild(ManageDataScreen)
        tabs = manage_widget.tabs
        tab_rect = tabs.tabBar().tabRect(0)
        from PySide6.QtCore import Qt
        harness.click(tabs.tabBar(), wait=0.5)  # focus first
        from PySide6.QtTest import QTest
        QTest.mouseClick(tabs.tabBar(), Qt.MouseButton.LeftButton, pos=tab_rect.center())
        harness.settle(0.5)
        log.log(f"People tab selected: currentIndex={tabs.currentIndex()}")
        assert tabs.currentIndex() == 0

        state = {}

        def fill():
            from ui.dialogs.person_dialog import PersonDialog
            pd = find_dialog_by_title(PersonDialog, "Add Person", timeout=5.0)
            if pd is None:
                state["error"] = "PersonDialog not found"
                return
            os_type(harness, pd, "Nickname", "Pranav")
            if first_name:
                os_type(harness, pd, "First name", first_name)
            if middle_name:
                os_type(harness, pd, "Middle name", middle_name)
            if last_name:
                os_type(harness, pd, "Last name", last_name)
            dob_widget = find_by_accessible_name(pd, "Date of birth")
            dob_widget.setDate(QDate(2004, 3, 8))
            harness.settle(0.3)
            log.log(f"DOB set via setDate() fallback (non-OS, avoids dd/MM/yy 2-digit-year ambiguity): "
                    f"date()={dob_widget.date().toString('yyyy-MM-dd')}")
            if full_pan:
                os_type(harness, pd, "PAN number", full_pan, secret=True)
            os_click(harness, pd, "Save person", wait=1.0)
            state["saved"] = True

        prearm(app, fill)
        os_click(harness, manage_widget, "Add person", wait=2.0)
        harness.settle(1.0)
        if state.get("error"):
            log.log(f"STOP: {state['error']}")
            sys.exit(1)
        log.log(f"PersonDialog fill+save state={state}")

        dlg.close()
        harness.settle(0.5)

    # --- Verify ---
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    rows = conn.execute(
        "SELECT person_id, full_name, first_name, last_name, date_of_birth, pan_number FROM Person"
    ).fetchall()
    log.log(f"Person rows: count={len(rows)}")
    assert len(rows) == 1
    pid, full_name, fn, ln, dob, pan = rows[0]
    log.log(f"person_id={pid} full_name={full_name!r} pan_matches_26AS={pan == full_pan} dob={dob}")
    assert pid == 1 and full_name == "Pranav"
    assert pan == full_pan
    assert dob == "2004-03-08", f"DOB mismatch: {dob}"
    conn.close()

    snap = snapshot_db("P2_1")
    log.log(f"snapshot: {snap}")
    append_progress(f"P2.1 person complete. person_id=1 full_name=Pranav dob=2004-03-08 snapshot={snap}")
    log.log("P2.1 DONE")


if __name__ == "__main__":
    main()
