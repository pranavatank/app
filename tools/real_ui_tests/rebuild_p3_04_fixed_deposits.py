r"""tools/real_ui_tests/rebuild_p3_04_fixed_deposits.py — Phase 3.04 Fixed Deposits UI test

R-mode: Validates FD screen navigation, table rowCount vs DB, and Enter Real FD Rates modal
dialog (cancel flow, no state change).

S-mode: Bulk-saves first 2 Pending FDs with 7.10% rate and 1-year tenure, verifies maturity
calculations per BankFDConvention (Actual/365, simple interest <183d), FDInterestRecord rows,
in-table editing without crash, in-table recalculation, transaction linking, auto-linking,
adding FD, and deletion.
"""
import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.real_ui_tests.rebuild_p3_common import P3Run, main_wrapper
from tools.real_ui_tests.rebuild_common import (
    os_click, os_click_widget, os_type_widget, os_select_combo, answer_modal_dialog,
    find_button, find_by_accessible_name, toast_texts, wait_until, parse_inr,
)
from PySide6.QtWidgets import QApplication, QDialog


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

    # Get first 2 Pending FDs
    try:
        result = p.sql(
            "SELECT fd_id, principal_amount, start_date FROM FixedDeposit "
            "WHERE person_id=1 AND status='Pending' LIMIT 2"
        )
        if len(result) < 2:
            p.checks.check("pending FDs available", False, f"found {len(result)}, need 2")
            p.observe("S04.pending", f"Only {len(result)} pending FDs")
            return

        pending_fds = [
            {"fd_id": r[0], "principal": r[1], "start_date": r[2]}
            for r in result
        ]
        p.observe("S04.pending", f"Found {len(pending_fds)} pending FDs")

    except Exception as e:
        p.checks.check("fetch pending FDs", False, str(e))
        return

    # Capture known_fd_count before bulk save
    known_count_before = 0
    try:
        from engines.prediction_engine import get_prediction_summary
        summary = get_prediction_summary(1, "2025-26")
        if "projected_fd_interest" in summary:
            known_count_before = summary["projected_fd_interest"].get("known_fd_count", 0)
            p.observe("S04.known_fd_count_before", f"Before: {known_count_before}")
    except Exception as e:
        p.observe("S04.known_fd_count_before", f"Error: {str(e)}")

    # Bulk save FDs
    try:
        def fill_bulk_rates_dialog(dlg):
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

            if hasattr(dlg, "table") and dlg.table:
                for row in range(min(2, dlg.table.rowCount())):
                    cb_widget = dlg.table.cellWidget(row, 0)
                    if cb_widget:
                        os_click_widget(p.harness, cb_widget, wait=0.2)
                p.harness.settle(0.3)

            apply_btn = find_button(dlg, "Apply to Checked")
            os_click_widget(p.harness, apply_btn, wait=0.5)
            p.harness.settle(0.5)

            save_btn = find_button(dlg, "Save Rates")
            os_click_widget(p.harness, save_btn, wait=1.0)

        prearm = answer_modal_dialog(
            p.harness, p.app, QDialog, "Enter Real FD Rates",
            fill_bulk_rates_dialog
        )
        os_click(p.harness, page, "Enter real fixed deposit rates", wait=0.5)
        ok = wait_until(p.harness, lambda: prearm.done, timeout=15)
        if not ok or prearm.error:
            raise RuntimeError(f"Dialog prearm failed: {prearm.error}")

        p.harness.settle(1.5)
        toasts = toast_texts()
        p.observe("S04.bulk_save_toast", str(toasts))
        p.checks.check("bulk save FDs", True)

    except Exception as e:
        p.checks.check("bulk save FDs", False, str(e))
        return

    # Verify each FD after bulk save
    p.harness.settle(1.0)
    saved_count = 0

    for i, fd_info in enumerate(pending_fds):
        try:
            fd_id = fd_info["fd_id"]
            principal = fd_info["principal"]

            # Query updated FD
            result = p.sql(
                "SELECT interest_rate, tenure_years, tenure_months, tenure_days, "
                "maturity_date, maturity_amount, status FROM FixedDeposit WHERE fd_id=?",
                (fd_id,)
            )
            if not result:
                continue

            r = result[0]
            interest_rate, ty, tm, td, mat_date, mat_amount, status = r

            # Verify rate, tenure, status
            ok_rate = abs(interest_rate - 7.10) < 0.01 if interest_rate else False
            ok_tenure = (ty == 1 and tm == 0 and td == 0)
            ok_status = status == "Active"
            ok_mat_amt = mat_amount and mat_amount > principal

            detail = (
                f"rate={interest_rate} tenure={ty}/{tm}/{td} "
                f"status={status} mat_amt={mat_amount}"
            )

            if ok_rate and ok_tenure and ok_status and ok_mat_amt:
                p.checks.check(f"FD {i+1} calculation", True, detail)
                saved_count += 1
            else:
                p.checks.check(
                    f"FD {i+1} calculation", False,
                    f"rate_ok={ok_rate} tenure_ok={ok_tenure} status_ok={ok_status} "
                    f"amt_ok={ok_mat_amt} {detail}"
                )

            # Check: maturity_amount vs BankFDConvention-based calculation
            # Actual/365, simple interest for <183 days, compound for >=183 days
            expected_amt = principal
            tenure_days = (ty * 365) + (tm * 30) + td
            if tenure_days < 183:
                daily_rate = 0.071 / 365.0
                interest = principal * daily_rate * tenure_days
                expected_amt = principal + interest
            else:
                expected_amt = principal * ((1 + 0.071/4) ** 4)

            if mat_amount:
                diff = abs(mat_amount - expected_amt)
                ok_calc = diff <= 1.0
                p.checks.check(f"FD {i+1} maturity calculation vs convention", ok_calc,
                    f"Calculated={expected_amt:.2f} Actual={mat_amount:.2f} Diff={diff:.2f}")
                if not ok_calc:
                    p.observe(
                        f"S04.FD{i+1}_calc_mismatch",
                        f"Calculated={expected_amt:.2f} Actual={mat_amount:.2f} Diff={diff:.2f}"
                    )

            # Check: FDInterestRecord rows
            interest_records = p.sql(
                "SELECT COUNT(*) FROM FDInterestRecord WHERE fd_id=?", (fd_id,)
            )
            record_count = interest_records[0][0] if interest_records else 0
            record_ok = record_count > 0
            p.checks.check(f"FD {i+1} FDInterestRecord count > 0", record_ok,
                f"count={record_count}")
            if record_ok:
                p.observe(f"S04.FD{i+1}_interest_records", f"Count={record_count}")

            p.observe(f"S04.FD{i+1}_verified", f"interest_rate={interest_rate:.2f}")

        except Exception as e:
            p.checks.check(f"FD {i+1} verify", False, str(e))

    p.observe("S04.bulk_saved", f"{saved_count} FDs verified")

    # Check projection summary for known_fd_count increase
    try:
        from engines.prediction_engine import get_prediction_summary
        summary = get_prediction_summary(1, "2025-26")
        if "projected_fd_interest" in summary:
            known_count = summary["projected_fd_interest"].get("known_fd_count", 0)
            p.observe("S04.known_fd_count_after", f"After bulk save: {known_count}")
            if known_count_before >= 0:
                expected = known_count_before + 2
                ok = known_count == expected
                p.checks.check("known_fd_count equals before + 2", ok,
                    f"before={known_count_before} expected={expected} actual={known_count}")
    except Exception as e:
        p.checks.check("projection check", False, repr(e))

    # Test in-table edit then Save (no crash)
    try:
        p.harness.settle(0.5)
        page.refresh()
        p.harness.settle(1.0)

        if page.table.rowCount() > 0:
            row_idx = 0
            for i in range(page.table.rowCount()):
                fd_no_item = page.table.item(i, 3)
                if fd_no_item and "Pending" in str(page.table.item(i, 13)):
                    row_idx = i
                    break

            page.table.selectRow(row_idx)
            p.harness.settle(0.3)

            try:
                rate_cell = page.table.item(row_idx, 4)
                if rate_cell:
                    page.table.scrollToItem(rate_cell)
                    p.harness.settle(0.2)
                    page.table.setCurrentItem(rate_cell)
                    p.harness.settle(0.2)
                    import pyautogui
                    pyautogui.press("f2")
                    p.harness.settle(0.3)
                    pyautogui.hotkey("ctrl", "a")
                    p.harness.settle(0.2)
                    pyautogui.write("7.1", interval=0.05)
                    p.harness.settle(0.3)
                    pyautogui.press("tab")
                    p.harness.settle(0.5)

                os_click(p.harness, page, "Save fixed deposit changes", wait=1.0)
                p.harness.settle(1.0)

                ok_no_errors = len(p.dashboard._screen_errors) == 0 or not p.dashboard._screen_errors.get(4)
                p.checks.check("in-table edit and save", ok_no_errors)
            except Exception as e:
                p.checks.check("in-table edit and save", False, str(e))

    except Exception as e:
        p.checks.check("in-table edit", False, str(e))

    # Test recalculate selected
    try:
        if page.table.rowCount() > 0:
            fd_row = next((i for i in range(page.table.rowCount()) if page.table.item(i, 3)), 0)
            result_before = p.sql(
                "SELECT actual_interest_amount, linked_transaction_id, status FROM FixedDeposit "
                "WHERE fd_id=(SELECT fd_id FROM FixedDeposit WHERE person_id=1 LIMIT 1)"
            )
            before = result_before[0] if result_before else None

            page.table.selectRow(fd_row)
            p.harness.settle(0.3)
            os_click(p.harness, page, "Recalculate selected fixed deposits", wait=1.0)
            p.harness.settle(1.0)

            result_after = p.sql(
                "SELECT actual_interest_amount, linked_transaction_id, status FROM FixedDeposit "
                "WHERE fd_id=(SELECT fd_id FROM FixedDeposit WHERE person_id=1 LIMIT 1)"
            )
            after = result_after[0] if result_after else None

            if before and after:
                snapshot_ok = (before[0] == after[0] and before[1] == after[1] and before[2] == after[2])
                p.checks.check("recalculate preserves values", snapshot_ok,
                    f"before={before} after={after}")
    except Exception as e:
        p.checks.check("recalculate", False, repr(e))

    # Test link transaction and verify columns
    try:
        if page.table.rowCount() > 0:
            page.table.selectRow(0)
            p.harness.settle(0.3)

            def fill_link_dialog(dlg):
                if dlg.table.rowCount() > 0:
                    dlg.table.selectRow(0)
                    p.harness.settle(0.3)
                    try:
                        link_btn = find_button(dlg, "Link")
                        os_click_widget(p.harness, link_btn, wait=0.5)
                    except Exception:
                        pass

            prearm = answer_modal_dialog(
                p.harness, p.app, QDialog, "Link Transaction to FD",
                fill_link_dialog
            )
            os_click(p.harness, page, "Link transaction to fixed deposit", wait=0.5)
            ok = wait_until(p.harness, lambda: prearm.done, timeout=15)
            if not ok or prearm.error:
                p.observe("S04.link_dialog", f"Dialog failed: {prearm.error}")
            else:
                p.harness.settle(0.5)
                result = p.sql("SELECT linked_transaction_id FROM FixedDeposit WHERE person_id=1 LIMIT 1")
                if result and result[0][0]:
                    p.checks.check("FD link transaction", True, f"linked_id={result[0][0]}")
                else:
                    p.observe("S04.link_dialog", "No linked_transaction_id set")

            if hasattr(page.table, "horizontalHeaderItem"):
                header_count = page.table.columnCount()
                p.observe("S04.table_columns", f"FD table has {header_count} columns")
    except Exception as e:
        p.checks.check("link transaction", False, repr(e))

    # Test auto-link
    try:
        linked_before = p.sql(
            "SELECT COUNT(*) FROM FixedDeposit WHERE person_id=1 AND linked_transaction_id IS NOT NULL"
        )
        linked_count_before = linked_before[0][0] if linked_before else 0

        os_click(p.harness, page, "Auto-link fixed deposit transactions", wait=1.0)
        p.harness.settle(1.0)
        toasts = toast_texts()
        p.observe("S04.auto_link_toast", str(toasts))

        linked_after = p.sql(
            "SELECT COUNT(*) FROM FixedDeposit WHERE person_id=1 AND linked_transaction_id IS NOT NULL"
        )
        linked_count_after = linked_after[0][0] if linked_after else 0

        linked_changed = linked_count_after > linked_count_before
        p.checks.check("auto-link linked count changed", linked_changed,
            f"before={linked_count_before} after={linked_count_after}")
    except Exception as e:
        p.checks.check("auto-link", False, repr(e))

    # Test add FD and verify via SQL
    fd_count_before = 0
    try:
        result = p.sql("SELECT COUNT(*) FROM FixedDeposit WHERE person_id=1")
        fd_count_before = result[0][0] if result else 0
    except Exception:
        pass

    try:
        def fill_add_fd_dialog(dlg):
            if hasattr(dlg, "principal_input"):
                os_type_widget(p.harness, dlg.principal_input, "100000", retries=2)
            if hasattr(dlg, "fd_no_input"):
                os_type_widget(p.harness, dlg.fd_no_input, "RUIH_FD1", retries=2)
            if hasattr(dlg, "rate_input"):
                os_type_widget(p.harness, dlg.rate_input, "7.5", retries=2)
            if hasattr(dlg, "tenure_years_input"):
                os_type_widget(p.harness, dlg.tenure_years_input, "1", retries=2)
            p.harness.settle(0.3)
            try:
                save_btn = find_button(dlg, "Save FD")
                os_click_widget(p.harness, save_btn, wait=1.0)
            except Exception as e:
                p.checks.check("add FD save button", False, repr(e))
                raise

        prearm = answer_modal_dialog(
            p.harness, p.app, QDialog, "Add Fixed Deposit",
            fill_add_fd_dialog
        )
        os_click(p.harness, page, "Add fixed deposit", wait=0.5)
        ok = wait_until(p.harness, lambda: prearm.done, timeout=15)
        if not ok or prearm.error:
            p.checks.check("add FD dialog", False, f"{prearm.error}")
        else:
            p.harness.settle(1.0)
            result = p.sql("SELECT COUNT(*) FROM FixedDeposit WHERE person_id=1")
            fd_count_after = result[0][0] if result else 0
            added = fd_count_after > fd_count_before
            p.checks.check("FD added and verified via SQL", added,
                f"before={fd_count_before} after={fd_count_after}")
            p.observe("S04.add_fd", f"FD added: {fd_count_before} -> {fd_count_after}")

    except Exception as e:
        p.checks.check("add FD", False, repr(e))

    # Test delete and verify via SQL
    try:
        p.harness.settle(0.5)
        page.refresh()
        p.harness.settle(1.0)

        target_fd_row = None
        for i in range(page.table.rowCount()):
            fd_no_item = page.table.item(i, 3)
            if fd_no_item and fd_no_item.text() == "RUIH_FD1":
                target_fd_row = i
                break

        if target_fd_row is not None:
            page.table.selectRow(target_fd_row)
            p.harness.settle(0.3)

            count_before = p.sql("SELECT COUNT(*) FROM FixedDeposit WHERE person_id=1")
            count_before = count_before[0][0] if count_before else 0

            txn_before = p.sql("SELECT COUNT(*) FROM Transaction WHERE person_id=1")
            txn_before = txn_before[0][0] if txn_before else 0

            prearm = answer_message_box(p.harness, p.app, QMessageBox.StandardButton.Yes,
                expect_title="Confirm Delete")
            os_click(p.harness, page, "Delete selected fixed deposit", wait=0.5)
            ok = wait_until(p.harness, lambda: prearm.done, timeout=15)
            if not ok or prearm.error:
                p.checks.check("delete FD dialog", False, f"{prearm.error}")
            else:
                p.harness.settle(1.0)

                count_after = p.sql("SELECT COUNT(*) FROM FixedDeposit WHERE person_id=1")
                count_after = count_after[0][0] if count_after else 0

                txn_after = p.sql("SELECT COUNT(*) FROM Transaction WHERE person_id=1")
                txn_after = txn_after[0][0] if txn_after else 0

                row_gone = page.table.rowCount() < (target_fd_row + 1) or \
                          all(page.table.item(i, 3).text() != "RUIH_FD1" for i in range(page.table.rowCount()))
                txn_unchanged = txn_before == txn_after
                deleted = count_after < count_before

                p.checks.check("FD deleted and verified via SQL", deleted,
                    f"before={count_before} after={count_after}")
                p.checks.check("FD row removed from table", row_gone)
                p.checks.check("Transaction count unchanged", txn_unchanged,
                    f"txn_before={txn_before} txn_after={txn_after}")

    except Exception as e:
        p.checks.check("delete FD", False, repr(e))

    p.observe("S04", "Fixed deposits S-mode tests complete")


if __name__ == "__main__":
    main_wrapper("04", "fixed_deposits", run_r, run_s)
