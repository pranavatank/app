r"""tools/real_ui_tests/rebuild_p3_03_income.py — Phase 3.03 Income & Expectations UI test

R-mode: Validates income screen navigation, expectation ledger rows, and the FD TDS
threshold status table.

S-mode: Cycles through income types and frequencies adding expectations, links/unlinks
transactions, tests auto-match, edit/delete, checks H15 projection tracking, and
verifies Salary expectations do not change the saved TaxProfile-based standard
deduction.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.real_ui_tests.rebuild_p3_common import P3Run, main_wrapper
from tools.real_ui_tests.rebuild_common import (
    os_click, os_click_widget, os_type_widget, os_select_combo, answer_modal_dialog,
    answer_message_box, assert_foreground, find_by_accessible_name, set_fy,
    toast_texts, wait_until, parse_inr, os_set_date,
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

FY = "2025-26"
RECURRING_RECORDS = {"Monthly": 12, "Quarterly": 4, "Half-Yearly": 2}
ID_ITEM_COLUMN = 1  # first data column; the table's checkbox column shifts data right by one


def run_r(p):
    """R-mode: read-only validation of income screen."""
    if p.part == "dialogs":
        raise RuntimeError("income dialog focus mode is S-only")
    page = p.nav("Income & Expectations")

    tables_found = {
        "ledger": find_by_accessible_name(page, "Income expectation ledger table") is not None,
        "tds": find_by_accessible_name(page, "FD TDS threshold status table") is not None,
        "expectations": find_by_accessible_name(page, "Income expectations") is not None,
    }

    p.checks.check("income ledger table found", tables_found["ledger"])
    p.checks.check("tds status table found", tables_found["tds"])
    p.checks.check("expectations table found", tables_found["expectations"])

    # Check: expectations rowCount vs DB
    try:
        result = p.sql("SELECT COUNT(*) FROM IncomeExpectation")
        db_count = result[0][0] if result else 0
        table_count = page.table_expectations.rowCount()
        ok = table_count == db_count
        detail = f"table={table_count} db={db_count}"
        p.checks.check("expectations rowCount matches DB", ok, detail)
        p.a11y("expectations table", f"rowCount={table_count}")
    except Exception as e:
        p.checks.check("expectations rowCount check", False, str(e))

    # Check: TDS table vs fd_tds_threshold_status (only if function exists and is pure-read)
    try:
        from engines.interest_engine import fd_tds_threshold_status
        status_data = fd_tds_threshold_status(1, "2025-26")
        if status_data and "banks" in status_data:
            tds_table_count = page.table_tds.rowCount()
            db_count = len(status_data["banks"])
            ok = tds_table_count == db_count
            detail = f"table={tds_table_count} banks={db_count}"
            p.checks.check("tds threshold rowCount vs engine", ok, detail)
    except Exception as e:
        p.checks.check("tds threshold check", False, str(e))

    p.observe("R03", "Income screen read-only checks complete")


def run_s(p):
    """S-mode: add expectations, link transactions, test matching and tax impacts."""
    if p.part == "dialogs":
        _run_dialog_focus(p)
        return
    page = p.nav("Income & Expectations")
    p.observe("S03.nav", "Navigated to Income & Expectations")

    # Get available persons and accounts
    try:
        persons_result = p.sql("SELECT person_id, full_name FROM Person LIMIT 1")
        if not persons_result:
            p.checks.check("person available", False, "no persons in DB")
            return
        person_id = persons_result[0][0]
        p.observe("S03.person", f"person_id={person_id}")

        accounts_result = p.sql(
            "SELECT account_id FROM BankAccount WHERE person_id=? LIMIT 1",
            (person_id,)
        )
        if not accounts_result:
            p.checks.check("account available", False, "no accounts for person")
            return
        account_id = accounts_result[0][0]
        p.observe("S03.account", f"account_id={account_id}")

    except Exception as e:
        p.checks.check("fetch person/account", False, str(e))
        return

    proj_total_start = _projected_total(person_id)

    # Salary is last so the tax check without Salary runs before it is added
    income_types = ["Rent", "Interest", "Dividend", "Business", "Freelance", "Other", "Salary"]
    frequencies = ["One-Time", "Monthly", "Quarterly", "Half-Yearly", "Annual"]
    non_salary_types = [t for t in income_types if t != "Salary"]

    added_count = _add_expectations(p, page, person_id, account_id, non_salary_types, frequencies)
    expected_adds = len(non_salary_types) * len(frequencies)
    p.checks.check("add income expectations", added_count == expected_adds, f"added {added_count} of {expected_adds}")
    p.harness.settle(1.0)

    result = p.sql("SELECT COUNT(*) FROM IncomeExpectation WHERE person_id=?", (person_id,))
    db_count = result[0][0] if result else 0
    p.observe("S03.db_count", f"DB has {db_count} expectations for person")

    target_id = _first_one_off_expectation(p, person_id)
    if target_id is None:
        p.checks.check("one-off expectation available", False, "no One-Time/Annual expectation was added")
    else:
        _check_edit(p, page, target_id)
        _check_link_and_unlink(p, page, target_id)
        _check_auto_match(p, page, person_id)
        _check_delete(p, page, target_id)

    saved_profile_deduction = _check_std_ded(p, "before Salary expectations")
    # Estimating can create a zero-valued TaxProfile on a fresh rebuild.
    profile_salary_before = _saved_profile_salary(p, person_id)
    if profile_salary_before is not None and profile_salary_before > 0:
        p.checks.check("saved Salary TaxProfile produces a standard deduction",
                       saved_profile_deduction is not None and saved_profile_deduction < 0,
                       f"salary_income={profile_salary_before}; deduction={saved_profile_deduction}")
    else:
        p.checks.check("no saved salary produces no standard deduction",
                       saved_profile_deduction in (None, 0),
                       f"salary_income={profile_salary_before}; deduction={saved_profile_deduction}")

    page = p.nav("Income & Expectations")
    _add_expectations(p, page, person_id, account_id, ["Salary"], frequencies)
    profile_salary_after = _saved_profile_salary(p, person_id)
    p.checks.check("Salary expectations leave saved TaxProfile unchanged",
                   profile_salary_after == profile_salary_before,
                   f"before={profile_salary_before}; after={profile_salary_after}")
    _check_std_ded(p, "after Salary expectations",
                   lambda value: value == saved_profile_deduction)

    # Check prediction summary for H15 (projected_total) and ledger vs SQL
    try:
        from engines.prediction_engine import get_prediction_summary
        summary = get_prediction_summary(person_id, "2025-26")
        if "fy_income" in summary and "projected_total" in summary["fy_income"]:
            proj_total = summary["fy_income"]["projected_total"]
            p.observe("S03.H15.projected_total", f"₹{proj_total:,.2f}")
            if proj_total_start is not None:
                p.observe("S03.H15.projected_total_start", f"₹{proj_total_start:,.2f}")
                p.observe("S03.H15.projected_total_change", f"start={proj_total_start} end={proj_total}")
            p.checks.check("H15 projection available", True)

            ledger_count = p.sql("SELECT COUNT(*) FROM IncomeExpectation WHERE person_id=?", (person_id,))
            ledger_total = ledger_count[0][0] if ledger_count else 0
            p.observe("S03.ledger_rowcount", f"Ledger has {ledger_total} rows")

            p.checks.check("ledger expectations not empty", ledger_total > 0)
        else:
            p.checks.check("H15 projection available", False, "key not in summary")
    except Exception as e:
        p.checks.check("H15 projection check", False, repr(e))

    p.observe("S03", "Income S-mode tests complete")


def _projected_total(person_id):
    try:
        from engines.prediction_engine import get_prediction_summary
        return get_prediction_summary(person_id, FY).get("fy_income", {}).get("projected_total")
    except Exception:
        return None


# ------------------------------------------------------------------ modal helpers --

def _disarm(*prearms):
    """Stop pollers that never fired so they cannot grab a later dialog."""
    for prearm in prearms:
        if not prearm.done:
            prearm._timer.stop()
            prearm.done = True


def _dismiss_modals():
    """Reject whatever dialog or message box a failed step left open."""
    for _ in range(5):
        modal = QApplication.activeModalWidget()
        if modal is None:
            return
        modal.reject()
        QApplication.processEvents()


def _click_and_wait(p, root, button_name, *prearms):
    """Click a button that opens modal(s) and wait until every armed prearm has handled its modal."""
    try:
        os_click(p.harness, root, button_name, wait=0.5)
        if not wait_until(p.harness, lambda: all(prearm.done for prearm in prearms), timeout=15):
            raise RuntimeError(f"{button_name!r}: expected modal never appeared")
        for prearm in prearms:
            error = prearm.error or prearm.info.get("error")
            if error:
                raise RuntimeError(f"{button_name!r}: modal handler failed: {error!r}")
    finally:
        _disarm(*prearms)


def _run_modal(p, root, button_name, *prearms):
    """Top-level variant of _click_and_wait: no modal is left open whatever happens."""
    try:
        _click_and_wait(p, root, button_name, *prearms)
    finally:
        _dismiss_modals()


def _prepare_dialog(p, dlg):
    """Wait until the dialog is mapped and foreground, so widget geometry is final before any click."""
    mapped = wait_until(
        p.harness,
        lambda: dlg.isVisible() and dlg.windowHandle() is not None and dlg.windowHandle().isExposed(),
        timeout=5,
    )
    if not mapped:
        raise RuntimeError(f"{dlg.windowTitle()!r} dialog never became visible")
    p.harness.settle(0.5)
    assert_foreground(dlg)


def _select_by_data(combo, data):
    index = combo.findData(data)
    if index < 0:
        raise LookupError(f"combo has no item with data {data!r}")
    combo.setCurrentIndex(index)


def _ensure_dashboard_fy(p, context):
    """The top-bar FY drifted away from FY mid-test in an earlier run; record it and restore it."""
    shown = p.dashboard.fy_combo.currentText()
    if shown != FY:
        p.checks.check(f"dashboard FY unchanged before {context}", False, f"found {shown!r}, expected {FY!r}")
        assert_foreground(p.dashboard)
        set_fy(p.harness, p.dashboard, FY)


# --------------------------------------------------------------------- add flow --

def _add_expectations(p, page, person_id, account_id, income_types, frequencies):
    """Add one expectation per income type and frequency. Returns the number added."""
    added_count = 0
    for income_type in income_types:
        for frequency in frequencies:
            if _add_expectation(p, page, person_id, account_id, income_type, frequency):
                added_count += 1
    return added_count


def _count_expectations(p, person_id, income_type, frequency):
    result = p.sql(
        "SELECT COUNT(*) FROM IncomeExpectation "
        "WHERE person_id=? AND financial_year=? AND income_type=? AND frequency=?",
        (person_id, FY, income_type, frequency),
    )
    return result[0][0]


def _add_expectation(p, page, person_id, account_id, income_type, frequency):
    """Add one expectation set through the dialog. True only if the expected rows reached the DB."""
    label = f"add {income_type}/{frequency}"
    records_expected = RECURRING_RECORDS.get(frequency, 1)
    try:
        _ensure_dashboard_fy(p, label)
        count_before = _count_expectations(p, person_id, income_type, frequency)

        prearms = [answer_modal_dialog(
            p.harness, p.app, QDialog, "Add Income Expectation",
            lambda dlg: _fill_income_dialog(p, dlg, income_type, frequency, person_id, account_id)
        )]
        if frequency in RECURRING_RECORDS:
            prearms.append(answer_message_box(
                p.harness, p.app, QMessageBox.StandardButton.Yes,
                expect_title="Create Recurring Expectations"
            ))
        _run_modal(p, page, "Add income expectation", *prearms)

        records_added = _count_expectations(p, person_id, income_type, frequency) - count_before
        ok = records_added == records_expected
        p.checks.check(label, ok, f"records added={records_added} expected={records_expected}")
        p.harness.settle(0.5)
        return ok
    except Exception as e:
        p.checks.check(label, False, repr(e))
        return False


def _fill_income_dialog(p, dlg, income_type, frequency, person_id, account_id):
    """Fill and submit an IncomeExpectationDialog."""
    _prepare_dialog(p, dlg)

    # Account list is reloaded per person and starts with a placeholder, so select by data
    _select_by_data(dlg.person_combo, person_id)
    _select_by_data(dlg.account_combo, account_id)
    p.harness.settle(0.3)

    os_select_combo(p.harness, dlg.income_type_combo, income_type)
    os_type_widget(p.harness, dlg.amount_spin, "50000", retries=2)
    os_select_combo(p.harness, dlg.frequency_combo, frequency)

    if frequency in RECURRING_RECORDS:
        os_type_widget(p.harness, dlg.day_spin, "15", retries=2)
    else:
        dlg.date_edit.setDate(QDate(int(FY[:4]), 12, 15))

    # The dialog defaults to the oldest FY, not the one on screen
    os_select_combo(p.harness, dlg.fy_combo, FY)
    os_type_widget(p.harness, dlg.notes_edit, f"RUIH_{income_type}", retries=2)
    p.harness.settle(0.3)

    if dlg.account_combo.currentData() != account_id or dlg.fy_combo.currentText() != FY:
        raise RuntimeError(
            f"dialog not ready to save: account={dlg.account_combo.currentData()!r} fy={dlg.fy_combo.currentText()!r}"
        )

    os_click(p.harness, dlg, "Add income expectation", wait=1.0)
    if dlg.isVisible():
        raise RuntimeError("dialog stayed open after Add (validation rejected it)")


# ----------------------------------------------------------- edit/link/delete flows --

def _first_one_off_expectation(p, person_id):
    """Editing a recurring row overwrites its dated expected_date with the dialog's day number, so use a dated row."""
    result = p.sql(
        "SELECT expectation_id FROM IncomeExpectation WHERE person_id=? AND financial_year=? "
        "AND frequency IN ('One-Time', 'Annual') ORDER BY expectation_id LIMIT 1",
        (person_id, FY),
    )
    return result[0][0] if result else None


def _expectation_row(page, expectation_id):
    table = page.table_expectations
    for row in range(table.rowCount()):
        item = table.item(row, ID_ITEM_COLUMN)
        if item is not None and item.data(Qt.ItemDataRole.UserRole) == expectation_id:
            return row
    raise LookupError(f"expectation {expectation_id} is not in the table")


def _select_expectation(p, page, expectation_id):
    table = page.table_expectations
    row = _expectation_row(page, expectation_id)
    table.scrollToItem(table.item(row, ID_ITEM_COLUMN))
    table.setCurrentCell(row, ID_ITEM_COLUMN)
    table.selectRow(row)
    p.harness.settle(0.3)
    return row


def _tick_row(p, table, row):
    """Tick the row checkbox with a real click; the screen's Delete acts on checked rows, not the selection."""
    table.scrollToItem(table.item(row, ID_ITEM_COLUMN))
    p.harness.settle(0.3)
    os_click_widget(p.harness, table.cellWidget(row, 0), wait=0.3)
    if row not in table.getCheckedRows():
        raise RuntimeError(f"row {row} checkbox did not toggle")


def _check_edit(p, page, expectation_id):
    try:
        def fill_edit(dlg):
            _prepare_dialog(p, dlg)
            os_type_widget(p.harness, dlg.amount_spin, "75000", retries=2)
            p.harness.settle(0.3)
            os_click(p.harness, dlg, "Save income expectation", wait=1.0)
            if dlg.isVisible():
                raise RuntimeError("edit dialog stayed open after Save")

        _select_expectation(p, page, expectation_id)
        edit_prearm = answer_modal_dialog(p.harness, p.app, QDialog, "Edit Income Expectation", fill_edit)
        _run_modal(p, page, "Edit selected income expectation", edit_prearm)

        p.harness.settle(0.5)
        result = p.sql("SELECT expected_amount FROM IncomeExpectation WHERE expectation_id=?", (expectation_id,))
        edited_amount = result[0][0] if result else None
        p.checks.check("edit amount to 75000", edited_amount == 75000.0, f"expectation_id={expectation_id} amount={edited_amount}")
        p.observe("S03.edit", "Amount changed and verified")
    except Exception as e:
        p.checks.check("edit income expectation", False, repr(e))


def _check_link_and_unlink(p, page, expectation_id, expected_transaction_id=None):
    """Link then unlink the expectation from its Edit dialog, verifying the DB after each."""
    try:
        def linked_transaction_id():
            result = p.sql("SELECT actual_transaction_id FROM IncomeExpectation WHERE expectation_id=?", (expectation_id,))
            return result[0][0] if result else None

        def fill_link_transaction(link_dlg):
            _prepare_dialog(p, link_dlg)
            if expected_transaction_id is None:
                if link_dlg.table.rowCount() == 0:
                    raise RuntimeError("no unlinked income transactions available to link")
                target_row = 0
            else:
                target_row = next((row for row in range(link_dlg.table.rowCount())
                                   if link_dlg.table.item(row, 0) is not None and
                                   link_dlg.table.item(row, 0).data(Qt.ItemDataRole.UserRole) == expected_transaction_id), None)
                if target_row is None:
                    visible_ids = [link_dlg.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
                                   for row in range(link_dlg.table.rowCount()) if link_dlg.table.item(row, 0)]
                    raise RuntimeError(
                        f"fixture transaction {expected_transaction_id} missing from link picker; "
                        f"visible transaction IDs={visible_ids}"
                    )
                hidden_id = link_dlg.table.item(target_row, 4)
                if hidden_id is None or int(hidden_id.text()) != expected_transaction_id:
                    raise RuntimeError(f"link picker hidden ID mismatch for fixture row {target_row}: {hidden_id.text() if hidden_id else None}")
            item = link_dlg.table.item(target_row, 0)
            link_dlg.table.scrollToItem(item)
            p.harness.settle(0.3)
            rect = link_dlg.table.visualItemRect(item)
            if not rect.isValid() or rect.isEmpty() or not link_dlg.table.viewport().rect().contains(rect.center()):
                raise RuntimeError(f"target transaction row is not visible: row={target_row}, rect={rect}")
            import pyautogui
            from tools.real_ui_tests.rebuild_common import _verify_click_target
            local = link_dlg.table.viewport().mapTo(link_dlg.table, rect.center())
            point = link_dlg.table.mapToGlobal(local)
            px, py = p.harness.to_physical(point)
            assert_foreground(link_dlg)
            blocker = _verify_click_target(link_dlg.table.viewport(), point, px, py)
            if blocker is not None:
                raise RuntimeError(f"transaction row click blocked: {blocker}")
            pyautogui.click(px, py)
            p.harness.settle(0.3)
            if link_dlg.table.currentRow() != target_row:
                raise RuntimeError(f"transaction row selection failed: wanted={target_row}, got={link_dlg.table.currentRow()}")
            if expected_transaction_id is not None:
                selected_user_item = link_dlg.table.item(link_dlg.table.currentRow(), 0)
                selected_hidden_id = link_dlg.table.item(link_dlg.table.currentRow(), 4)
                if (selected_user_item is None or selected_user_item.data(Qt.ItemDataRole.UserRole) != expected_transaction_id
                        or selected_hidden_id is None or int(selected_hidden_id.text()) != expected_transaction_id):
                    raise RuntimeError(f"selected transaction ID mismatch: expected={expected_transaction_id}")
            os_click(p.harness, link_dlg, "Link selected transaction", wait=0.5)

        def fill_edit_for_link(edit_dlg):
            _prepare_dialog(p, edit_dlg)
            link_prearm = answer_modal_dialog(p.harness, p.app, QDialog, "Link Transaction", fill_link_transaction)
            _click_and_wait(p, edit_dlg, "Link actual transaction", link_prearm)
            os_click(p.harness, edit_dlg, "Cancel income expectation dialog", wait=0.5)

        def fill_edit_for_unlink(edit_dlg):
            _prepare_dialog(p, edit_dlg)
            unlink_prearm = answer_message_box(
                p.harness, p.app, QMessageBox.StandardButton.Yes, expect_title="Confirm Unlink"
            )
            _click_and_wait(p, edit_dlg, "Unlink transaction", unlink_prearm)
            os_click(p.harness, edit_dlg, "Cancel income expectation dialog", wait=0.5)

        _run_in_edit_dialog(p, page, expectation_id, fill_edit_for_link)
        linked_id = linked_transaction_id()
        if expected_transaction_id is None:
            link_ok = linked_id is not None
        else:
            link_ok = linked_id == expected_transaction_id
        p.checks.check("link sets expected actual_transaction_id", link_ok,
                       f"expectation_id={expectation_id}; expected={expected_transaction_id}; actual={linked_id}")

        _run_in_edit_dialog(p, page, expectation_id, fill_edit_for_unlink)
        p.checks.check("unlink clears actual_transaction_id", linked_transaction_id() is None, f"expectation_id={expectation_id}")
    except Exception as e:
        p.checks.check("link/unlink transaction", False, repr(e))


def _run_in_edit_dialog(p, page, expectation_id, fill_fn):
    _select_expectation(p, page, expectation_id)
    edit_prearm = answer_modal_dialog(p.harness, p.app, QDialog, "Edit Income Expectation", fill_fn)
    _run_modal(p, page, "Edit selected income expectation", edit_prearm)


def _check_auto_match(p, page, person_id):
    try:
        before_result = p.sql("SELECT COUNT(*) FROM IncomeExpectation WHERE person_id=? AND actual_transaction_id IS NOT NULL", (person_id,))
        before_count = before_result[0][0] if before_result else 0

        os_click(p.harness, page, "Auto-match income expectations", wait=1.5)
        toasts = toast_texts()

        p.harness.settle(0.5)
        after_result = p.sql("SELECT COUNT(*) FROM IncomeExpectation WHERE person_id=? AND actual_transaction_id IS NOT NULL", (person_id,))
        after_count = after_result[0][0] if after_result else 0

        p.observe("S03.auto_match", f"before={before_count} after={after_count} toast={str(toasts)}")
        if after_count > before_count:
            p.checks.check("auto-match added links", True)
    except Exception as e:
        p.checks.check("auto-match income expectations", False, repr(e))


def _check_delete(p, page, expectation_id):
    try:
        row = _select_expectation(p, page, expectation_id)
        _tick_row(p, page.table_expectations, row)

        confirm_prearm = answer_message_box(
            p.harness, p.app, QMessageBox.StandardButton.Yes, expect_title="Confirm Delete"
        )
        _run_modal(p, page, "Delete selected income expectation", confirm_prearm)

        p.harness.settle(1.0)
        result = p.sql("SELECT COUNT(*) FROM IncomeExpectation WHERE expectation_id=?", (expectation_id,))
        rows_left = result[0][0] if result else None
        p.checks.check("delete row from table", rows_left == 0, f"expectation_id={expectation_id} rows left={rows_left}")
        p.observe("S03.delete", "Delete verified against DB")
    except Exception as e:
        p.checks.check("delete income expectation", False, repr(e))


def _run_dialog_focus(p):
    """Small S-only reproduction for edit/footer and exact transaction linking."""
    if p.env != "S":
        raise RuntimeError("income dialog focus mode is S-only")
    from ui.dialogs.income_expectation_dialog import IncomeExpectationDialog
    from ui.dialogs.transaction_dialog import TransactionDialog
    from models.person import get_all_persons
    from models.bank_account import get_all_accounts
    from PySide6.QtWidgets import QDialogButtonBox
    import uuid

    fixture = p.sql(
        "SELECT p.person_id, p.full_name, a.account_id FROM Person p "
        "JOIN BankAccount a ON a.person_id=p.person_id ORDER BY p.person_id, a.account_id LIMIT 1"
    )
    if not fixture:
        raise RuntimeError("dialog focus requires an existing person/account fixture")
    person_id, _person_name, account_id = fixture[0]
    suffix = uuid.uuid4().hex[:12].upper()
    note = f"RUIH_FOCUS_EXPECTATION_{suffix}"
    description = f"RUIH_FOCUS_INCOME_TXN_{suffix}"
    if p.sql("SELECT expectation_id FROM IncomeExpectation WHERE notes=?", (note,)):
        raise RuntimeError("unique focused expectation note already exists")
    if p.sql("SELECT transaction_id FROM Transactions WHERE description=?", (description,)):
        raise RuntimeError("unique focused transaction description already exists")

    income_page = p.nav("Income & Expectations")

    def fill_expectation(dlg):
        _prepare_dialog(p, dlg)
        _select_by_data(dlg.person_combo, person_id)
        _select_by_data(dlg.account_combo, account_id)
        os_select_combo(p.harness, dlg.income_type_combo, "Other")
        os_type_widget(p.harness, dlg.amount_spin, "54321", retries=2)
        os_select_combo(p.harness, dlg.frequency_combo, "One-Time")
        dlg.date_edit.setDate(QDate(2025, 12, 15))
        os_select_combo(p.harness, dlg.fy_combo, FY)
        os_type_widget(p.harness, dlg.notes_edit, note, retries=2)
        if dlg.account_combo.currentData() != account_id or dlg.fy_combo.currentText() != FY:
            raise RuntimeError("focused expectation account/FY selection mismatch")
        os_click(p.harness, dlg, "Add income expectation", wait=0.8)
        if dlg.isVisible():
            raise RuntimeError("focused expectation dialog remained open after Add")

    add_expectation = answer_modal_dialog(
        p.harness, p.app, IncomeExpectationDialog, "Add Income Expectation", fill_expectation
    )
    _run_modal(p, income_page, "Add income expectation", add_expectation)
    if not add_expectation.done or add_expectation.error or add_expectation.info.get("error"):
        raise RuntimeError(f"focused expectation creation failed: {add_expectation.error or add_expectation.info}")
    expectation_rows = p.sql(
        "SELECT expectation_id, person_id, account_id, expected_amount, actual_transaction_id "
        "FROM IncomeExpectation WHERE notes=?", (note,)
    )
    p.checks.check("focused expectation created exactly once",
                   len(expectation_rows) == 1 and expectation_rows[0][1:4] == (person_id, account_id, 54321.0)
                   and expectation_rows[0][4] is None,
                   f"rows={expectation_rows}")
    if len(expectation_rows) != 1:
        raise RuntimeError(f"expected one focused expectation, got {expectation_rows}")
    expectation_id = expectation_rows[0][0]

    # Create a matching unlinked income transaction through the actual Add Transaction dialog.
    txn_page = p.nav("Transactions")
    persons = get_all_persons()
    accounts = get_all_accounts()
    person = next((row for row in persons if row["person_id"] == person_id), None)
    account = next((row for row in accounts if row["account_id"] == account_id), None)
    if person is None or account is None:
        raise RuntimeError(f"fixture person/account unavailable: person={person_id}, account={account_id}")
    account_label = f"{account.get('bank_display_name') or account['bank_name']} ({account['account_type']})"

    def fill_transaction(dlg):
        _prepare_dialog(p, dlg)
        os_select_combo(p.harness, dlg.cmb_person, person["full_name"])
        os_select_combo(p.harness, dlg.cmb_account, account_label)
        if dlg.cmb_account.currentData() != account_id:
            raise RuntimeError(f"focused transaction account mismatch: {dlg.cmb_account.currentData()}")
        os_set_date(p.harness, dlg.date_edit, QDate(2025, 6, 15))
        os_select_combo(p.harness, dlg.cmb_type, "Income")
        os_select_combo(p.harness, dlg.cmb_category, "Salary")
        os_type_widget(p.harness, dlg.amount_spin, "54321", retries=2)
        os_type_widget(p.harness, dlg.desc_edit, description, retries=2)
        box = dlg.findChild(QDialogButtonBox)
        if box is None:
            raise RuntimeError("Transaction dialog Save/Add footer missing")
        os_click_widget(p.harness, box.button(QDialogButtonBox.StandardButton.Ok), wait=0.8)
        if dlg.isVisible():
            raise RuntimeError("focused transaction dialog remained open after Add")

    add_transaction = answer_modal_dialog(
        p.harness, p.app, TransactionDialog, "Add Transaction", fill_transaction
    )
    try:
        os_click_widget(p.harness, txn_page.btn_add, wait=0.8)
        if not wait_until(p.harness, lambda: add_transaction.done, timeout=15):
            raise RuntimeError("focused Add Transaction dialog did not open")
    finally:
        _disarm(add_transaction)
        _dismiss_modals()
    if not add_transaction.done or add_transaction.error or add_transaction.info.get("error"):
        raise RuntimeError(f"focused transaction creation failed: {add_transaction.error or add_transaction.info}")
    txn_core = p.sql(
        "SELECT transaction_id, person_id, account_id, transaction_type, amount "
        "FROM Transactions WHERE description=?", (description,)
    )
    p.checks.check("focused transaction created exactly once",
                   len(txn_core) == 1 and txn_core[0][1:] == (person_id, account_id, "Income", 54321.0),
                   f"rows={txn_core}")
    if len(txn_core) != 1:
        raise RuntimeError(f"expected one focused transaction, got {txn_core}")
    transaction_id = txn_core[0][0]
    p.observe("income_dialog_focus_ids", f"expectation={expectation_id}; transaction={transaction_id}")

    page = p.nav("Income & Expectations")
    _check_edit(p, page, expectation_id)
    _check_link_and_unlink(p, page, expectation_id, expected_transaction_id=transaction_id)
    _check_delete(p, page, expectation_id)


def _saved_profile_salary(p, person_id):
    """Return the selected person's saved salary for the test FY, if present."""
    result = p.sql(
        "SELECT salary_income FROM TaxProfile WHERE person_id=? AND financial_year=?",
        (person_id, FY),
    )
    return result[0][0] if result else None


def _check_std_ded(p, label, is_expected=None):
    """Run Tax on App Actual Data and return the saved-profile deduction shown."""
    try:
        tax_page = p.nav("Tax")
        p.harness.settle(2.0)

        if not hasattr(tax_page, "source_combo"):
            raise RuntimeError("source_combo attribute not found on tax_page")

        os_select_combo(p.harness, tax_page.source_combo, "App Actual Data")
        p.harness.settle(0.5)

        os_click_widget(p.harness, tax_page.btn_calc, wait=1.0)
        p.harness.settle(0.5)

        if not hasattr(tax_page, "waterfall_std_ded"):
            raise RuntimeError("waterfall_std_ded attribute not found on tax_page")

        std_ded_val = tax_page.waterfall_std_ded.value
        if is_expected is not None:
            p.checks.check(f"waterfall_std_ded {label}", is_expected(std_ded_val), f"value={std_ded_val}")
        p.observe(f"S03.waterfall_std_ded.{label}", f"Value: {std_ded_val}")
        return std_ded_val

    except Exception as e:
        p.checks.check(f"tax screen std_ded {label}", False, repr(e))
        return None
    finally:
        _dismiss_modals()


if __name__ == "__main__":
    focus_mode = ("--part" in sys.argv and
                  sys.argv.index("--part") + 1 < len(sys.argv) and
                  sys.argv[sys.argv.index("--part") + 1] == "dialogs")
    main_wrapper("03", "income_dialogs" if focus_mode else "income", run_r, run_s)
