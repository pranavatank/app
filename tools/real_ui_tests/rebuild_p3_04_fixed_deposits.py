r"""tools/real_ui_tests/rebuild_p3_04_fixed_deposits.py — Phase 3.04 Fixed Deposits UI test

R-mode: Validates FD screen navigation, table rowCount vs DB, and Enter Real FD Rates modal
dialog (cancel flow, no state change).

S-mode: Bulk-saves first 2 Pending Details FDs with 7.10% rate and 1-year tenure, verifies
maturity amounts against the spec formula (Actual/365, quarterly compounding, ROUNDUP, minus 4),
FDInterestRecord rows, in-table editing, in-table recalculation, transaction linking,
auto-linking, adding FD, and deletion.
"""
import math
import sys
from pathlib import Path
from datetime import date

import pyautogui

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.real_ui_tests.rebuild_p3_common import P3Run, main_wrapper
from tools.real_ui_tests.rebuild_common import (
    os_click, os_click_widget, os_type_widget, os_select_combo, answer_modal_dialog,
    answer_message_box, assert_foreground, find_button, find_by_accessible_name,
    toast_texts, wait_until, parse_inr,
)
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

FY = "2025-26"
PERSON_ID = 1
PENDING_STATUS = "Pending Details"
NEW_FD_NO = "RUIH_FD1"
COL_PERSON = 1  # carries the fd_id in its UserRole
COL_FD_NO = 3
COL_RATE = 5
COL_STATUS = 14


def run_r(p):
    """R-mode: read-only validation of fixed deposits screen."""
    page = p.nav("Fixed Deposits")

    table_found = find_by_accessible_name(page, "Fixed deposits table") is not None
    p.checks.check("fixed deposits table found", table_found)

    # Check: table rowCount vs DB
    try:
        result = p.sql("SELECT COUNT(*) FROM FixedDeposit WHERE person_id=1")
        db_count = result[0][0] if result else 0
        table_count = page.table.rowCount()
        ok = table_count == db_count
        detail = f"table={table_count} db={db_count}"
        p.checks.check("FD table rowCount matches DB", ok, detail)
        p.a11y("FD table", f"rowCount={table_count}")
    except Exception as e:
        p.checks.check("FD rowCount check", False, str(e))

    # Check: Enter Real FD Rates dialog (cancel flow only)
    try:
        def fill_test_rates_dialog(dlg):
            os_type_widget(p.harness, dlg.rate_spin, "7.10", retries=2)
            p.harness.settle(0.3)
            os_type_widget(p.harness, dlg.years_spin, "1", retries=2)
            p.harness.settle(0.3)
            os_type_widget(p.harness, dlg.months_spin, "0", retries=2)
            p.harness.settle(0.3)
            os_type_widget(p.harness, dlg.days_spin, "0", retries=2)
            p.harness.settle(0.3)
            try:
                os_select_combo(p.harness, dlg.compounding_combo, "Quarterly")
            except Exception:
                pass
            p.harness.settle(0.5)
            cancel_btn = find_button(dlg, "Cancel")
            os_click_widget(p.harness, cancel_btn, wait=0.8)

        prearm = answer_modal_dialog(
            p.harness, p.app, QDialog, "Enter Real FD Rates",
            fill_test_rates_dialog
        )
        os_click(p.harness, page, "Enter real fixed deposit rates", wait=0.5)
        ok = wait_until(p.harness, lambda: prearm.done, timeout=15)
        if not ok or prearm.error:
            p.checks.check("FD dialog test", False, str(prearm.error or "timeout"))
        else:
            p.checks.check("FD dialog cancel preserves state", True)

    except Exception as e:
        p.checks.check("FD dialog test", False, str(e))

    p.observe("R04", "Fixed deposits read-only checks complete")


def run_s(p):
    """S-mode: bulk save FDs, verify calculations, test editing and linking."""
    page = p.nav("Fixed Deposits")
    p.observe("S04.nav", "Navigated to Fixed Deposits")

    try:
        result = p.sql(
            "SELECT fd_id FROM FixedDeposit WHERE person_id=? AND status=? ORDER BY fd_id",
            (PERSON_ID, PENDING_STATUS),
        )
        if len(result) < 2:
            p.checks.check("pending FDs available", False, f"found {len(result)}, need 2")
            p.observe("S04.pending", f"Only {len(result)} pending FDs")
            return
        pending_ids = {r[0] for r in result}
        p.observe("S04.pending", f"Found {len(pending_ids)} pending FDs")

    except Exception as e:
        p.checks.check("fetch pending FDs", False, str(e))
        return

    # Capture known_fd_count before bulk save
    known_count_before = 0
    try:
        from engines.prediction_engine import get_prediction_summary
        summary = get_prediction_summary(PERSON_ID, FY)
        if "projected_fd_interest" in summary:
            known_count_before = summary["projected_fd_interest"].get("known_fd_count", 0)
            p.observe("S04.known_fd_count_before", f"Before: {known_count_before}")
    except Exception as e:
        p.observe("S04.known_fd_count_before", f"Error: {str(e)}")

    try:
        saved_fd_ids = _bulk_save_two_pending(p, page, pending_ids)
        p.harness.settle(1.5)
        p.observe("S04.bulk_save_toast", str(toast_texts()))
        p.checks.check("bulk save FDs", True, f"fd_ids={saved_fd_ids}")
    except Exception as e:
        p.checks.check("bulk save FDs", False, str(e))
        return

    p.harness.settle(1.0)
    _verify_saved_fds(p, saved_fd_ids)
    _check_known_fd_count(p, known_count_before)

    page.refresh()
    p.harness.settle(1.0)
    _check_in_table_edit(p, page)
    _check_recalculate(p, page, saved_fd_ids[0])
    _check_link(p, page)
    _check_auto_link(p, page)

    new_fd_id = _check_add_fd(p, page)
    if new_fd_id is not None:
        _check_delete_fd(p, page)

    p.observe("S04", "Fixed deposits S-mode tests complete")


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


def _run_modal(p, root, button_name, *prearms):
    """Click a button that opens modal(s), wait for the armed prearms; no modal is left open whatever happens."""
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


# ---------------------------------------------------------------- table helpers --

def _fd_row(page, fd_id):
    for row in range(page.table.rowCount()):
        item = page.table.item(row, COL_PERSON)
        if item is not None and item.data(Qt.ItemDataRole.UserRole) == fd_id:
            return row
    raise LookupError(f"fd_id {fd_id} is not in the table")


def _fd_row_by_number(page, fd_no):
    for row in range(page.table.rowCount()):
        item = page.table.item(row, COL_FD_NO)
        if item is not None and item.text() == fd_no:
            return row
    return None


def _select_fd(p, page, fd_id):
    row = _fd_row(page, fd_id)
    page.table.scrollToItem(page.table.item(row, COL_PERSON))
    page.table.setCurrentCell(row, COL_PERSON)
    p.harness.settle(0.3)
    return row


def _tick_row(p, page, row):
    """Tick the row checkbox with a real click; Save, Recalculate and Delete act on checked rows, not the selection."""
    page.table.scrollToItem(page.table.item(row, COL_PERSON))
    p.harness.settle(0.3)
    os_click_widget(p.harness, page.table.cellWidget(row, 0), wait=0.3)
    if row not in page.table.getCheckedRows():
        raise RuntimeError(f"row {row} checkbox did not toggle")


def _fd_values(p, fd_id, columns):
    result = p.sql(f"SELECT {columns} FROM FixedDeposit WHERE fd_id=?", (fd_id,))
    return result[0] if result else None


# ----------------------------------------------------------------- bulk save flow --

def _bulk_save_two_pending(p, page, pending_ids):
    """Check the first two Pending Details rows in the bulk dialog and save 7.10% / 1 year. Returns their fd_ids."""
    checked_fd_ids = []

    def fill_bulk_rates_dialog(dlg):
        _prepare_dialog(p, dlg)
        if dlg.table is None:
            raise RuntimeError("bulk rate dialog has no rows")

        os_type_widget(p.harness, dlg.rate_spin, "7.10", retries=2)
        p.harness.settle(0.3)
        os_type_widget(p.harness, dlg.years_spin, "1", retries=2)
        p.harness.settle(0.3)
        os_type_widget(p.harness, dlg.months_spin, "0", retries=2)
        p.harness.settle(0.3)
        os_type_widget(p.harness, dlg.days_spin, "0", retries=2)
        p.harness.settle(0.3)
        os_select_combo(p.harness, dlg.compounding_combo, "Quarterly")
        p.harness.settle(0.5)

        rows = [row for row, fd_id in sorted(dlg._fd_id_map.items()) if fd_id in pending_ids][:2]
        if len(rows) < 2:
            raise RuntimeError(f"bulk dialog lists {len(rows)} pending rows, need 2")
        for row in rows:
            os_click_widget(p.harness, dlg.table.cellWidget(row, 0), wait=0.2)
        if sorted(dlg.table.getCheckedRows()) != rows:
            raise RuntimeError(f"checked rows {dlg.table.getCheckedRows()} != {rows}")
        checked_fd_ids.extend(dlg._fd_id_map[row] for row in rows)
        p.harness.settle(0.3)

        os_click_widget(p.harness, find_button(dlg, "Apply to Checked"), wait=0.5)
        p.harness.settle(0.5)
        os_click_widget(p.harness, find_button(dlg, "Save Rates"), wait=1.0)
        if dlg.isVisible():
            raise RuntimeError("bulk rate dialog stayed open after Save Rates")

    prearm = answer_modal_dialog(p.harness, p.app, QDialog, "Enter Real FD Rates", fill_bulk_rates_dialog)
    _run_modal(p, page, "Enter real fixed deposit rates", prearm)
    return checked_fd_ids


def _expected_maturity(principal, rate_pct, start_date, maturity_date):
    """Spec column H: ROUNDUP(F*(1+G/400)^(4*days/365)) - 4 (docs/AUDIT_AND_REBUILD_PLAN.md)."""
    days = (date.fromisoformat(maturity_date) - date.fromisoformat(start_date)).days
    return math.ceil(principal * (1 + rate_pct / 400) ** (4 * days / 365)) - 4


def _verify_saved_fds(p, saved_fd_ids):
    saved_count = 0

    for i, fd_id in enumerate(saved_fd_ids, start=1):
        try:
            r = _fd_values(
                p, fd_id,
                "interest_rate, tenure_years, tenure_months, tenure_days, maturity_date, "
                "maturity_amount, status, principal_amount, start_date",
            )
            if r is None:
                p.checks.check(f"FD {i} calculation", False, f"fd_id={fd_id} not found")
                continue

            interest_rate, ty, tm, td, mat_date, mat_amount, status, principal, start_date = r

            ok_rate = abs(interest_rate - 7.10) < 0.01 if interest_rate else False
            ok_tenure = (ty == 1 and tm == 0 and td == 0)
            ok_status = status == "Active"
            ok_mat_amt = bool(mat_amount and mat_amount > principal)

            detail = (
                f"fd_id={fd_id} rate={interest_rate} tenure={ty}/{tm}/{td} "
                f"status={status} mat_amt={mat_amount}"
            )

            if ok_rate and ok_tenure and ok_status and ok_mat_amt:
                p.checks.check(f"FD {i} calculation", True, detail)
                saved_count += 1
            else:
                p.checks.check(
                    f"FD {i} calculation", False,
                    f"rate_ok={ok_rate} tenure_ok={ok_tenure} status_ok={ok_status} "
                    f"amt_ok={ok_mat_amt} {detail}"
                )

            if mat_amount and mat_date and start_date:
                expected_amt = _expected_maturity(principal, 7.10, start_date, mat_date)
                diff = abs(mat_amount - expected_amt)
                p.checks.check(
                    f"FD {i} maturity calculation vs convention", diff <= 1.0,
                    f"Calculated={expected_amt:.2f} Actual={mat_amount:.2f} Diff={diff:.2f}"
                )
                if diff > 0:
                    p.observe(
                        f"S04.FD{i}_calc_mismatch",
                        f"Calculated={expected_amt:.2f} Actual={mat_amount:.2f} Diff={diff:.2f}"
                    )

            interest_records = p.sql("SELECT COUNT(*) FROM FDInterestRecord WHERE fd_id=?", (fd_id,))
            record_count = interest_records[0][0] if interest_records else 0
            record_ok = record_count > 0
            p.checks.check(f"FD {i} FDInterestRecord count > 0", record_ok, f"count={record_count}")
            if record_ok:
                p.observe(f"S04.FD{i}_interest_records", f"Count={record_count}")

            p.observe(f"S04.FD{i}_verified", f"interest_rate={interest_rate:.2f}")

        except Exception as e:
            p.checks.check(f"FD {i} verify", False, str(e))

    p.observe("S04.bulk_saved", f"{saved_count} FDs verified")


def _check_known_fd_count(p, known_count_before):
    try:
        from engines.prediction_engine import get_prediction_summary
        summary = get_prediction_summary(PERSON_ID, FY)
        if "projected_fd_interest" in summary:
            known_count = summary["projected_fd_interest"].get("known_fd_count", 0)
            p.observe("S04.known_fd_count_after", f"After bulk save: {known_count}")
            expected = known_count_before + 2
            p.checks.check(
                "known_fd_count equals before + 2", known_count == expected,
                f"before={known_count_before} expected={expected} actual={known_count}"
            )
    except Exception as e:
        p.checks.check("projection check", False, repr(e))


# ------------------------------------------------------------- edit/recalc/link flows --

def _check_in_table_edit(p, page):
    """Type a new rate into a still-Pending row, tick it and Save; the rate must reach the DB."""
    try:
        result = p.sql(
            "SELECT fd_id FROM FixedDeposit WHERE person_id=? AND status=? ORDER BY fd_id LIMIT 1",
            (PERSON_ID, PENDING_STATUS),
        )
        if not result:
            p.checks.check("in-table edit and save", False, "no pending FD left to edit")
            return
        fd_id = result[0][0]

        row = _select_fd(p, page, fd_id)
        rate_item = page.table.item(row, COL_RATE)
        assert_foreground(p.dashboard)
        page.table.setFocus()
        page.table.setCurrentItem(rate_item)
        p.harness.settle(0.3)
        pyautogui.press("f2")
        p.harness.settle(0.3)
        pyautogui.hotkey("ctrl", "a")
        p.harness.settle(0.2)
        pyautogui.write("7.1", interval=0.05)
        p.harness.settle(0.3)
        pyautogui.press("enter")
        p.harness.settle(0.5)
        if rate_item.text() != "7.1":
            raise RuntimeError(f"rate cell shows {rate_item.text()!r} after typing, expected '7.1'")

        _tick_row(p, page, _fd_row(page, fd_id))
        os_click(p.harness, page, "Save fixed deposit changes", wait=1.0)
        p.harness.settle(1.0)

        saved_rate = _fd_values(p, fd_id, "interest_rate")[0]
        no_screen_error = not p.dashboard._screen_errors.get(4)
        p.checks.check(
            "in-table edit and save", saved_rate is not None and abs(saved_rate - 7.1) < 0.001 and no_screen_error,
            f"fd_id={fd_id} saved_rate={saved_rate} screen_error={not no_screen_error}"
        )
    except Exception as e:
        p.checks.check("in-table edit and save", False, str(e))
    finally:
        _dismiss_modals()


def _check_recalculate(p, page, fd_id):
    """Recalculate a bulk-saved FD from its table values; actual interest, link and status must survive."""
    try:
        columns = "actual_interest_amount, linked_transaction_id, status, maturity_amount"
        before = _fd_values(p, fd_id, columns)

        row = _select_fd(p, page, fd_id)
        _tick_row(p, page, row)
        os_click(p.harness, page, "Recalculate selected fixed deposits", wait=1.0)
        p.harness.settle(1.0)

        after = _fd_values(p, fd_id, columns)
        snapshot_ok = (
            before is not None and after is not None
            and before[:3] == after[:3]
            and abs((before[3] or 0) - (after[3] or 0)) < 0.01
        )
        p.checks.check("recalculate preserves values", snapshot_ok, f"fd_id={fd_id} before={before} after={after}")
    except Exception as e:
        p.checks.check("recalculate", False, repr(e))
    finally:
        _dismiss_modals()


def _check_link(p, page):
    """Link a transaction to the first FD that has candidates; verify the DB and the table columns."""
    try:
        from models.fixed_deposit import get_fd_link_candidates

        all_ids = [r[0] for r in p.sql("SELECT fd_id FROM FixedDeposit WHERE person_id=? ORDER BY fd_id", (PERSON_ID,))]
        fd_id = next((candidate for candidate in all_ids if get_fd_link_candidates(candidate)), None)
        if fd_id is None:
            p.observe("S04.link_dialog", "No FD has link candidates; skipped")
            return

        def fill_link_dialog(dlg):
            _prepare_dialog(p, dlg)
            if dlg.table.rowCount() == 0:
                raise RuntimeError("link dialog lists no transactions")
            dlg.table.setCurrentCell(0, 0)
            dlg.table.selectRow(0)
            p.harness.settle(0.3)
            os_click_widget(p.harness, find_button(dlg, "Link Selected"), wait=0.5)
            if dlg.isVisible():
                raise RuntimeError("link dialog stayed open after Link Selected")

        _select_fd(p, page, fd_id)
        prearm = answer_modal_dialog(p.harness, p.app, QDialog, "Link Account Transaction", fill_link_dialog)
        _run_modal(p, page, "Link transaction to fixed deposit", prearm)

        p.harness.settle(0.5)
        linked_id = _fd_values(p, fd_id, "linked_transaction_id")[0]
        p.checks.check("FD link transaction", linked_id is not None, f"fd_id={fd_id} linked_id={linked_id}")
        p.observe("S04.table_columns", f"FD table has {page.table.columnCount()} columns")
    except Exception as e:
        p.checks.check("link transaction", False, repr(e))


def _check_auto_link(p, page):
    try:
        linked_before = p.sql(
            "SELECT COUNT(*) FROM FixedDeposit WHERE person_id=? AND linked_transaction_id IS NOT NULL", (PERSON_ID,)
        )[0][0]

        os_click(p.harness, page, "Auto-link fixed deposit transactions", wait=1.0)
        p.harness.settle(1.0)
        toasts = toast_texts()
        p.observe("S04.auto_link_toast", str(toasts))

        linked_after = p.sql(
            "SELECT COUNT(*) FROM FixedDeposit WHERE person_id=? AND linked_transaction_id IS NOT NULL", (PERSON_ID,)
        )[0][0]

        # The screen reports "Linked N ..." or "No FD references were matched ..."; the DB must agree
        reported_link = any("Linked" in text for text in toasts)
        p.checks.check(
            "auto-link result matches DB", (linked_after > linked_before) == reported_link,
            f"before={linked_before} after={linked_after} toasts={toasts}"
        )
    except Exception as e:
        p.checks.check("auto-link", False, repr(e))


# ---------------------------------------------------------------- add/delete flows --

def _check_add_fd(p, page):
    """Add an FD through the dialog. Returns its fd_id, or None if it was not added."""
    try:
        count_before = p.sql("SELECT COUNT(*) FROM FixedDeposit WHERE person_id=?", (PERSON_ID,))[0][0]

        def fill_add_fd_dialog(dlg):
            _prepare_dialog(p, dlg)
            _select_by_data(dlg.person_combo, PERSON_ID)
            os_type_widget(p.harness, dlg.principal_input, "100000", retries=2)
            os_type_widget(p.harness, dlg.fd_no_input, NEW_FD_NO, retries=2)
            os_type_widget(p.harness, dlg.rate_input, "7.5", retries=2)
            os_type_widget(p.harness, dlg.tenure_years_input, "1", retries=2)
            p.harness.settle(0.3)
            os_click_widget(p.harness, find_button(dlg, "Save FD"), wait=1.0)
            if dlg.isVisible():
                raise RuntimeError("add FD dialog stayed open after Save FD")

        prearm = answer_modal_dialog(p.harness, p.app, QDialog, "Add Fixed Deposit", fill_add_fd_dialog)
        _run_modal(p, page, "Add fixed deposit", prearm)

        p.harness.settle(1.0)
        count_after = p.sql("SELECT COUNT(*) FROM FixedDeposit WHERE person_id=?", (PERSON_ID,))[0][0]
        new_ids = p.sql(
            "SELECT fd_id FROM FixedDeposit WHERE person_id=? AND fd_reference_no=?", (PERSON_ID, NEW_FD_NO)
        )
        added = count_after == count_before + 1 and len(new_ids) == 1
        p.checks.check("FD added and verified via SQL", added, f"before={count_before} after={count_after}")
        p.observe("S04.add_fd", f"FD added: {count_before} -> {count_after}")
        return new_ids[0][0] if added else None
    except Exception as e:
        p.checks.check("add FD", False, repr(e))
        return None


def _check_delete_fd(p, page):
    try:
        page.refresh()
        p.harness.settle(1.0)

        target_row = _fd_row_by_number(page, NEW_FD_NO)
        if target_row is None:
            p.checks.check("delete FD", False, f"{NEW_FD_NO} is not in the table")
            return

        count_before = p.sql("SELECT COUNT(*) FROM FixedDeposit WHERE person_id=?", (PERSON_ID,))[0][0]
        txn_before = p.sql("SELECT COUNT(*) FROM Transactions WHERE person_id=?", (PERSON_ID,))[0][0]

        _tick_row(p, page, target_row)
        prearm = answer_message_box(
            p.harness, p.app, QMessageBox.StandardButton.Yes, expect_title="Delete Fixed Deposits"
        )
        _run_modal(p, page, "Delete selected fixed deposit", prearm)

        p.harness.settle(1.0)
        count_after = p.sql("SELECT COUNT(*) FROM FixedDeposit WHERE person_id=?", (PERSON_ID,))[0][0]
        txn_after = p.sql("SELECT COUNT(*) FROM Transactions WHERE person_id=?", (PERSON_ID,))[0][0]

        p.checks.check("FD deleted and verified via SQL", count_after == count_before - 1,
                       f"before={count_before} after={count_after}")
        p.checks.check("FD row removed from table", _fd_row_by_number(page, NEW_FD_NO) is None)
        p.checks.check("Transaction count unchanged", txn_before == txn_after,
                       f"txn_before={txn_before} txn_after={txn_after}")
    except Exception as e:
        p.checks.check("delete FD", False, repr(e))


if __name__ == "__main__":
    main_wrapper("04", "fixed_deposits", run_r, run_s)
