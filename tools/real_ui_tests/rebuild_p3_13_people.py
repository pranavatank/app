"""Phase 3.13 People real-UI regression: add/edit DOB on scratch only."""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.real_ui_tests.rebuild_p3_common import P3Run, main_wrapper
from tools.real_ui_tests.rebuild_common import (
    os_click, os_click_widget, os_type, answer_modal_dialog,
)
from tools.real_ui_test_harness import find_by_accessible_name, find_dialog_by_title
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QDialog, QTableWidget


def _open_people(p):
    from ui.manage_data_screen import ManageDataScreen

    settings = p.nav("Settings")
    os_click(p.harness, settings, "Manage people", wait=1.0)
    dlg = find_dialog_by_title(QDialog, "Manage Data", timeout=5)
    if dlg is None:
        raise RuntimeError("Manage Data dialog did not open from Settings > People")
    manage = dlg.findChild(ManageDataScreen)
    if manage is None:
        raise RuntimeError("Manage Data dialog has no ManageDataScreen")
    tabs = manage.tabs
    people_index = next((i for i in range(tabs.count()) if tabs.tabText(i) == "People"), -1)
    if people_index < 0:
        raise RuntimeError("People tab is missing")
    rect = tabs.tabBar().tabRect(people_index)
    # Click the actual People tab label, rather than changing currentIndex in code.
    import pyautogui
    center = tabs.tabBar().mapToGlobal(rect.center())
    px, py = p.harness.to_physical(center)
    from tools.real_ui_tests.rebuild_common import assert_foreground, _verify_click_target
    assert_foreground(tabs.window())
    blocker = _verify_click_target(tabs.tabBar(), center, px, py)
    if blocker is not None:
        raise RuntimeError(f"People tab OS click blocked: {blocker}")
    pyautogui.click(px, py)
    p.harness.settle(0.5)
    if tabs.currentIndex() != people_index:
        raise RuntimeError(f"People tab failed to select: currentIndex={tabs.currentIndex()}")
    return dlg, manage


def _type_dob_os(p, dateedit, iso_date):
    """Enter each QDateEdit section through OS keystrokes and demand exact readback."""
    year, month, day = (int(x) for x in iso_date.split("-"))
    from PySide6.QtWidgets import QDateTimeEdit
    import pyautogui

    target = QDate(year, month, day)
    if not target.isValid():
        raise ValueError(f"invalid test DOB {iso_date}")
    os_click_widget(p.harness, dateedit, wait=0.2)
    # QDateEdit displays years as two digits; typing a four-digit year into
    # that section can be interpreted ambiguously. Navigate its year section
    # with real Up/Down keystrokes, then enter month/day through OS input.
    current_year = dateedit.date().year()
    year_delta = year - current_year
    if abs(year_delta) > 120:
        raise RuntimeError(f"DOB year navigation exceeds safety bound: {current_year} -> {year}")
    dateedit.setSelectedSection(QDateTimeEdit.Section.YearSection)
    p.harness.settle(0.1)
    if year_delta:
        pyautogui.press("up" if year_delta > 0 else "down", presses=abs(year_delta), interval=0.025)
        p.harness.settle(0.25)
    for section, text in (
        (QDateTimeEdit.Section.MonthSection, f"{month:02d}"),
        (QDateTimeEdit.Section.DaySection, f"{day:02d}"),
    ):
        dateedit.setSelectedSection(section)
        p.harness.settle(0.1)
        pyautogui.write(text, interval=0.08)
        p.harness.settle(0.25)
    actual = dateedit.date()
    if actual != target:
        raise RuntimeError(f"OS DOB entry readback mismatch: wanted {iso_date}, got {actual.toString('yyyy-MM-dd')}")


def _run_add(p, manage, nickname, dob):
    from ui.dialogs.person_dialog import PersonDialog

    state = {"dob_readback": None}
    def fill(dlg):
        os_type(p.harness, dlg, "Nickname", nickname)
        os_type(p.harness, dlg, "First name", "Synthetic")
        os_type(p.harness, dlg, "Last name", "Fixture")
        dateedit = find_by_accessible_name(dlg, "Date of birth")
        _type_dob_os(p, dateedit, dob)
        state["dob_readback"] = dateedit.date().toString("yyyy-MM-dd")
        os_click(p.harness, dlg, "Save person", wait=1.0)

    p.expected_titles.add("Add Person")
    callback = answer_modal_dialog(p.harness, p.app, PersonDialog, "Add Person", fill)
    try:
        os_click(p.harness, manage, "Add person", wait=1.0)
        p.harness.settle(0.5)
        error = callback.info.get("error") or (repr(callback.error) if callback.error else None)
        if not callback.done or error:
            raise RuntimeError(f"Add Person callback failed: done={callback.done}, error={error}")
    finally:
        p.expected_titles.discard("Add Person")
    p.checks.check("add callback completed", callback.done and not callback.error and not callback.info.get("error"),
                   f"done={callback.done}; error={callback.info.get('error') or callback.error!r}")
    p.checks.check("DOB read back after OS entry", state["dob_readback"] == dob,
                   f"expected={dob}; readback={state['dob_readback']}")


def _select_fixture_row(p, table, nickname):
    import pyautogui
    from tools.real_ui_tests.rebuild_common import assert_foreground
    from tools.real_ui_tests.rebuild_common import _verify_click_target

    match = next((r for r in range(table.rowCount())
                  if table.item(r, 0) and table.item(r, 0).text() == nickname), None)
    if match is None:
        raise RuntimeError(f"new synthetic person row missing: {nickname}")
    item = table.item(match, 0)
    table.scrollToItem(item)
    p.harness.settle(0.3)
    rect = table.visualItemRect(item)
    if not rect.isValid() or rect.isEmpty() or not table.viewport().rect().contains(rect.center()):
        raise RuntimeError(f"fixture row is not visible for OS selection: row={match}, rect={rect}")
    local = table.viewport().mapTo(table, rect.center())
    global_pos = table.mapToGlobal(local)
    px, py = p.harness.to_physical(global_pos)
    assert_foreground(table.window())
    blocker = _verify_click_target(table.viewport(), global_pos, px, py)
    if blocker is not None:
        raise RuntimeError(f"OS row click blocked: {blocker}")
    pyautogui.click(px, py)
    p.harness.settle(0.3)
    if table.currentRow() != match:
        raise RuntimeError(f"fixture row selection failed: wanted={match}, current={table.currentRow()}")
    return match


def run_r(p):
    # Read-only smoke coverage of the same visible Settings > People entry.
    dlg, _manage = _open_people(p)
    p.checks.check("Manage Data opened from People", dlg.isVisible() and dlg.windowTitle() == "Manage Data")
    dlg.reject()


def run_s(p):
    from ui.dialogs.person_dialog import PersonDialog

    # Refuse to overwrite a prior fixture and capture the baseline without touching it.
    baseline = p.sql("SELECT person_id, full_name FROM Person ORDER BY person_id")
    suffix = uuid.uuid4().hex[:10].upper()
    nickname = f"RUIH_People_{suffix}"
    if any(row[1] == nickname for row in baseline):
        raise RuntimeError("generated synthetic person nickname already exists")
    dlg, manage = _open_people(p)
    people_table = manage.people_table
    if not isinstance(people_table, QTableWidget):
        raise RuntimeError("People table was not found")

    add_dob = "1994-03-08"
    _run_add(p, manage, nickname, add_dob)
    added = p.sql("SELECT person_id, date_of_birth FROM Person WHERE full_name = ?", (nickname,))
    p.checks.check("synthetic person persisted with exact DOB", len(added) == 1 and added[0][1] == add_dob,
                   f"rows={added}")
    if len(added) != 1:
        raise RuntimeError(f"expected exactly one synthetic person, got {len(added)}")
    person_id = added[0][0]
    p.observe("synthetic_person_id", str(person_id))

    # Select only the exact new row through a guarded OS click, then edit it.
    _select_fixture_row(p, people_table, nickname)
    edit_dob = "1996-11-23"
    state = {"dob_readback": None}
    def fill_edit(edit_dlg):
        dateedit = find_by_accessible_name(edit_dlg, "Date of birth")
        _type_dob_os(p, dateedit, edit_dob)
        state["dob_readback"] = dateedit.date().toString("yyyy-MM-dd")
        os_click(p.harness, edit_dlg, "Save person", wait=1.0)

    p.expected_titles.add("Edit Person")
    callback = answer_modal_dialog(p.harness, p.app, PersonDialog, "Edit Person", fill_edit)
    try:
        os_click(p.harness, manage, "Edit person", wait=1.0)
        p.harness.settle(0.5)
        error = callback.info.get("error") or (repr(callback.error) if callback.error else None)
        if not callback.done or error:
            raise RuntimeError(f"Edit Person callback failed: done={callback.done}, error={error}")
    finally:
        p.expected_titles.discard("Edit Person")
    updated = p.sql("SELECT person_id, date_of_birth FROM Person WHERE full_name = ?", (nickname,))
    p.checks.check("edit callback completed", callback.done and not callback.error and not callback.info.get("error"),
                   f"done={callback.done}; error={callback.info.get('error') or callback.error!r}")
    p.checks.check("edited DOB readback exact", state["dob_readback"] == edit_dob,
                   f"expected={edit_dob}; readback={state['dob_readback']}")
    p.checks.check("edit preserved person ID and persisted DOB",
                   len(updated) == 1 and updated[0] == (person_id, edit_dob), f"rows={updated}; original_id={person_id}")

    # Close the manager through its visible close control; never delete synthetic rows.
    dlg.reject()
    final = p.sql("SELECT person_id FROM Person WHERE full_name = ?", (nickname,))
    p.checks.check("synthetic person remains for audit", final == [(person_id,)], f"rows={final}")


if __name__ == "__main__":
    main_wrapper("13", "people", run_r, run_s)
