"""
tools/real_ui_tests/test_add_person_flow.py — Real, on-screen test:
Settings -> Manage People -> Add Person -> Save -> verify -> cleanup.

Uses tools/real_ui_test_harness.py's primary (QTest + accessible-name lookup)
interaction path — see that file's module docstring for why this replaced the
original blind-coordinate pyautogui clicking, which caused real misclicks
(clicking closed a dialog instead of opening one) and Windows foreground-focus
failures. This still runs a genuine, visible, on-screen window with a real Qt
event loop and real repaints (never QT_QPA_PLATFORM=offscreen) — it just finds
and drives controls directly by the accessible names this codebase already sets
on them, instead of computing screen coordinates.

Self-cleans the person record it creates so repeated runs don't pollute the real
database. If a run is interrupted before cleanup, look for a person named
TEST_NICKNAME below and delete it manually.

Run with:
    .venv/Scripts/python tools/real_ui_tests/test_add_person_flow.py
"""
import os
import sys

os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")

# Amounts print with the rupee sign; the Windows console defaults to cp1252 and
# raises UnicodeEncodeError on it, which would kill a passing test at the report.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDialog, QApplication

from tools.real_ui_test_harness import RealUIHarness
from ui.dashboard_screen import DashboardScreen
from ui.theme.theme_manager import ThemeManager
from ui.manage_data_screen import ManageDataScreen
from ui.dialogs.person_dialog import PersonDialog
from models.person import get_all_persons, delete_person

SHOT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(SHOT_DIR, exist_ok=True)
TEST_NICKNAME = "RUIH_TestPerson_01"

failures = []


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    if not condition:
        failures.append(label)
    return condition


def main():
    before_names = {p["full_name"] for p in get_all_persons()}
    print(f"[db] persons before: {sorted(before_names)}")

    ThemeManager.apply("Aurora", save=False, notify=False)
    harness = RealUIHarness(screenshot_dir=SHOT_DIR)
    dashboard = harness.launch(lambda: DashboardScreen(), maximized=True)
    harness.shot("00_dashboard")

    # 1. Navigate to Settings via the real sidebar button widget.
    settings_btn = dashboard._nav_buttons[8]
    harness.click(settings_btn)
    harness.shot("01_settings")
    title_lbl = getattr(dashboard, "page_title_lbl", None)
    check("Settings page title shows 'Settings'", title_lbl and title_lbl.text() == "Settings")

    # 2. Click "Manage People" on the Settings screen, found by accessible name.
    settings_screen = dashboard.settings_page
    manage_people_btn = harness.find(settings_screen, "Manage people")
    if not check("Found 'Manage people' button", manage_people_btn is not None):
        harness.shot("FAIL_no_manage_people_btn")
        return report(harness)

    harness.click(manage_people_btn)
    harness.shot("02_manage_data_dialog")

    manage_dialog = harness.find_dialog(QDialog, "Manage Data")
    if not check("Manage Data dialog opened", manage_dialog is not None):
        harness.shot("FAIL_no_manage_dialog")
        return report(harness)

    # 3. Click "Add Person" inside the People tab, found by accessible name.
    #
    # _on_add_person() calls PersonDialog(self) then dlg.exec() — a BLOCKING
    # modal call. QTest.mouseClick() delivers the click synchronously and
    # _on_add_person() runs to completion inside that delivery, including the
    # nested exec() event loop — so a plain click() here would never return
    # until something closes the dialog, which nothing would. The fix:
    # schedule the fill-and-save steps with QTimer.singleShot(0, ...) BEFORE
    # clicking, so they run once exec()'s nested loop is already spinning,
    # then click and let harness.settle() pump events (which drives that
    # nested loop) until the scheduled callback has run and closed the dialog.
    add_person_btn = harness.find(manage_dialog, "Add person")
    if not check("Found 'Add person' button", add_person_btn is not None):
        harness.shot("FAIL_no_add_person_btn")
        return report(harness)

    fill_result = {}

    def _fill_and_save_person_dialog():
        person_dialog = harness.find_dialog(PersonDialog, "Add Person", timeout=2.0)
        fill_result["dialog_opened"] = person_dialog is not None
        if person_dialog is None:
            return
        harness.shot("03_add_person_dialog_open")
        harness.type_into(person_dialog, "Nickname", TEST_NICKNAME)
        harness.shot("04_nickname_typed")
        fill_result["nickname_ok"] = person_dialog.nickname_input.text() == TEST_NICKNAME

        save_btn = harness.find(person_dialog, "Save person")
        fill_result["save_btn_found"] = save_btn is not None
        if save_btn is not None:
            harness.click(save_btn)
        fill_result["dialog_closed"] = not person_dialog.isVisible()

    QTimer.singleShot(0, _fill_and_save_person_dialog)
    harness.click(add_person_btn, wait=1.5)
    harness.shot("05_after_save")

    if not check("'Add Person' dialog opened", fill_result.get("dialog_opened", False)):
        harness.shot("FAIL_no_person_dialog")
        return report(harness)
    check("Nickname field holds typed text", fill_result.get("nickname_ok", False))
    if not check("Found Save button", fill_result.get("save_btn_found", False)):
        harness.shot("FAIL_no_save_btn")
        return report(harness)
    check("Add Person dialog closed after Save", fill_result.get("dialog_closed", False))

    # 5. Verify: person appears in DB and in the visible table.
    after = get_all_persons()
    after_names = {p["full_name"] for p in after}
    check(f"'{TEST_NICKNAME}' present in database after save",
          TEST_NICKNAME in after_names)

    mds = manage_dialog.findChild(ManageDataScreen)
    table_names = []
    if mds:
        for r in range(mds.people_table.rowCount()):
            item = mds.people_table.item(r, 0)
            if item:
                table_names.append(item.text())
    check(f"'{TEST_NICKNAME}' present in visible People table (no manual refresh needed)",
          TEST_NICKNAME in table_names)

    harness.shot("06_final_state")
    manage_dialog.close()
    harness.close()
    return report(harness, after=after)


def report(harness, after=None):
    # Cleanup: always remove the test person if it made it into the DB, even on
    # a failed run, so repeated runs never accumulate junk records.
    people = after if after is not None else get_all_persons()
    test_rows = [p for p in people if p["full_name"] == TEST_NICKNAME]
    for row in test_rows:
        delete_person(row["person_id"])
        print(f"[cleanup] deleted test person_id={row['person_id']}")

    print("\n===== SUMMARY =====")
    if failures:
        print(f"{len(failures)} check(s) FAILED:")
        for f in failures:
            print(f"  - {f}")
    else:
        print("All checks PASSED.")
    print(f"Screenshots saved to: {harness.screenshot_dir}")

    # Always close every top-level window before exiting, on every path
    # (success or failure) — this script must never leave a visible window
    # open waiting on anything after it finishes running.
    app = QApplication.instance()
    if app:
        for w in list(app.topLevelWidgets()):
            w.close()
        app.processEvents()

    return 1 if failures else 0


def _close_all_windows():
    """Close every top-level window, whatever happened. A failed assertion must
    never leave a test window (or a blocking modal) on the user's screen."""
    try:
        from PySide6.QtWidgets import QApplication, QDialog
        app = QApplication.instance()
        if not app:
            return
        for w in list(app.topLevelWidgets()):
            try:
                if isinstance(w, QDialog) and w.isVisible():
                    w.reject()
            except Exception:
                pass
        for w in list(app.topLevelWidgets()):
            try:
                w.close()
            except Exception:
                pass
        app.processEvents()
    except Exception:
        pass


if __name__ == "__main__":
    try:
        rc = main()
    except BaseException:
        import traceback
        traceback.print_exc()
        rc = 1
    finally:
        _close_all_windows()
    sys.exit(rc)
