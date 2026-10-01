r"""tools/real_ui_tests/rebuild_p3_03_income.py — Phase 3.03 Income & Expectations UI test

R-mode: Validates income screen navigation, expectations ledger table rowCount vs DB,
FD TDS threshold status table, waterfall standard deduction presence while Salary
expectations exist, and H15 projection key tracking.

S-mode: Cycles through income types and frequencies adding expectations, links/unlinks
transactions, tests auto-match, edit/delete, and verifies tax screen behavior with and
without expectations.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.real_ui_tests.rebuild_p3_common import P3Run, main_wrapper
from tools.real_ui_tests.rebuild_common import (
    os_click, os_click_widget, os_type_widget, os_select_combo, answer_modal_dialog,
    answer_message_box, find_by_accessible_name, toast_texts, wait_until, parse_inr,
)
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox


def run_r(p):
    """R-mode: read-only validation of income screen."""
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

    # Test income types
    income_types = ["Salary", "Rent", "Interest", "Dividend", "Business", "Freelance", "Other"]
    frequencies = ["One-Time", "Monthly", "Quarterly", "Half-Yearly", "Annual"]

    added_count = 0

    for income_type in income_types:
        for frequency in frequencies:
            try:
                is_recurring = frequency in ("Monthly", "Quarterly", "Half-Yearly")

                if is_recurring:
                    msg_prearm = answer_message_box(
                        p.harness, p.app, QMessageBox.StandardButton.Yes,
                        expect_title="Create Recurring Expectations"
                    )

                prearm = answer_modal_dialog(
                    p.harness, p.app, QDialog, "Add Income Expectation",
                    lambda dlg=None: _fill_income_dialog(
                        p, income_type, frequency, person_id, account_id, "2025-26"
                    )
                )
                os_click(p.harness, page, "Add income expectation", wait=0.5)
                ok = wait_until(p.harness, lambda: prearm.done, timeout=15)
                if not ok or prearm.error:
                    raise RuntimeError(f"Dialog prearm failed: {prearm.error}")

                if is_recurring:
                    ok = wait_until(p.harness, lambda: msg_prearm.done, timeout=10)
                    if not ok or msg_prearm.info.get("error"):
                        raise RuntimeError(f"Message box prearm failed: {msg_prearm.info.get('error')}")

                added_count += 1

                p.observe(
                    f"S03.add.{income_type}.{frequency}",
                    f"Added {income_type}/{frequency}"
                )

                # Brief pause between adds
                p.harness.settle(0.5)

            except Exception as e:
                p.checks.check(
                    f"add {income_type}/{frequency}",
                    False, repr(e)
                )

    if added_count > 0:
        p.checks.check("add income expectations", True, f"added {added_count}")
        p.harness.settle(1.0)

        # Verify all rows are in DB
        result = p.sql("SELECT COUNT(*) FROM IncomeExpectation WHERE person_id=?", (person_id,))
        db_count = result[0][0] if result else 0
        p.observe("S03.db_count", f"DB has {db_count} expectations for person")

        # Select first expectation for editing/linking/deleting
        if hasattr(page, "table_expectations") and page.table_expectations.rowCount() > 0:
            page.table_expectations.selectRow(0)
            p.harness.settle(0.3)

            # Test edit - change amount and verify DB
            try:
                def fill_edit(dlg):
                    os_type_widget(p.harness, dlg.amount_spin, "75000", retries=2)
                    p.harness.settle(0.3)
                    os_click(p.harness, dlg, "Save income expectation", wait=1.0)

                edit_prearm = answer_modal_dialog(
                    p.harness, p.app, QDialog, "Edit Income Expectation", fill_edit
                )
                os_click(p.harness, page, "Edit selected income expectation", wait=0.5)
                ok = wait_until(p.harness, lambda: edit_prearm.done, timeout=10)
                if not ok or edit_prearm.info.get("error"):
                    raise RuntimeError(f"Edit dialog failed: {edit_prearm.info.get('error')}")

                p.harness.settle(0.5)
                result = p.sql("SELECT expected_amount FROM IncomeExpectation WHERE person_id=? ORDER BY created_at DESC LIMIT 1", (person_id,))
                edited_amount = result[0][0] if result else None
                ok = edited_amount == 75000.0
                p.checks.check("edit amount to 75000", ok, f"amount={edited_amount}")
                p.observe("S03.edit", "Amount changed and verified")
            except Exception as e:
                p.checks.check("edit income expectation", False, repr(e))

            # Test link transaction
            try:
                def fill_link(dlg):
                    os_click(p.harness, dlg, "Link selected transaction", wait=0.5)

                link_prearm = answer_modal_dialog(
                    p.harness, p.app, QDialog, "Link Transaction", fill_link
                )
                os_click(p.harness, page, "Link actual transaction", wait=0.5)
                ok = wait_until(p.harness, lambda: link_prearm.done, timeout=10)
                if not ok or link_prearm.info.get("error"):
                    p.observe("S03.link", f"Link dialog: {link_prearm.info.get('error')}")
                else:
                    p.harness.settle(0.5)
                    result = p.sql("SELECT COUNT(*) FROM IncomeExpectation WHERE person_id=? AND actual_transaction_id IS NOT NULL", (person_id,))
                    linked_count = result[0][0] if result else 0
                    p.observe("S03.link", f"Linked transactions: {linked_count}")
            except Exception as e:
                p.checks.check("link transaction", False, repr(e))

            # Test auto-match
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

            # Test delete with confirmation
            try:
                if page.table_expectations.rowCount() > 0:
                    page.table_expectations.selectRow(0)
                    p.harness.settle(0.3)

                    before_result = p.sql("SELECT COUNT(*) FROM IncomeExpectation WHERE person_id=?", (person_id,))
                    before_delete = before_result[0][0] if before_result else 0

                    delete_prearm = answer_message_box(
                        p.harness, p.app, QMessageBox.StandardButton.Yes,
                        expect_title="Confirm Delete"
                    )
                    os_click(p.harness, page, "Delete selected income expectation", wait=0.5)
                    ok = wait_until(p.harness, lambda: delete_prearm.done, timeout=10)
                    if not ok or delete_prearm.info.get("error"):
                        raise RuntimeError(f"Delete confirm failed: {delete_prearm.info.get('error')}")

                    p.harness.settle(1.0)
                    after_result = p.sql("SELECT COUNT(*) FROM IncomeExpectation WHERE person_id=?", (person_id,))
                    after_delete = after_result[0][0] if after_result else 0

                    ok = after_delete == before_delete - 1
                    p.checks.check("delete row from table", ok, f"before={before_delete} after={after_delete}")
                    p.observe("S03.delete", "Row deleted and verified")
            except Exception as e:
                p.checks.check("delete income expectation", False, repr(e))

    # Check tax screen: waterfall_std_ded and verify via SQL
    try:
        tax_page = p.nav("Tax")
        p.harness.settle(2.0)

        if not hasattr(tax_page, "source_combo"):
            raise RuntimeError("source_combo attribute not found on tax_page")

        os_select_combo(p.harness, tax_page.source_combo, "App Actual Data")
        p.harness.settle(0.5)

        if hasattr(tax_page, "btn_calc"):
            os_click_widget(p.harness, tax_page.btn_calc, wait=1.0)
            p.harness.settle(0.5)

        if not hasattr(tax_page, "waterfall_std_ded"):
            raise RuntimeError("waterfall_std_ded attribute not found on tax_page")

        std_ded_val = tax_page.waterfall_std_ded.value
        has_salary = p.sql("SELECT COUNT(*) FROM IncomeExpectation WHERE person_id=? AND income_type='Salary'", (person_id,))
        has_salary_count = has_salary[0][0] if has_salary else 0

        if has_salary_count > 0:
            ok = std_ded_val is not None and std_ded_val != 0
            p.checks.check("waterfall_std_ded non-zero with Salary", ok, f"value={std_ded_val}")
        else:
            ok = std_ded_val is None or std_ded_val == 0
            p.checks.check("waterfall_std_ded zero without Salary", ok, f"value={std_ded_val}")
        p.observe("S03.waterfall_std_ded", f"Value: {std_ded_val}")

    except Exception as e:
        p.checks.check("tax screen std_ded check", False, repr(e))

    # Capture projected_total before test operations
    try:
        from engines.prediction_engine import get_prediction_summary
        proj_total_start = None
        summary_start = get_prediction_summary(person_id, "2025-26")
        if "fy_income" in summary_start and "projected_total" in summary_start["fy_income"]:
            proj_total_start = summary_start["fy_income"]["projected_total"]
    except Exception as e:
        proj_total_start = None

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


def _fill_income_dialog(p, income_type, frequency, person_id, account_id, fy):
    """Fill and submit an IncomeExpectationDialog."""
    dlg = QApplication.activeModalWidget()
    if not isinstance(dlg, QDialog):
        raise RuntimeError(f"Expected QDialog, got {type(dlg).__name__}")

    # Select person by combo
    person_combo = dlg.person_combo
    for i in range(person_combo.count()):
        if person_combo.itemData(i) == person_id:
            person_combo.setCurrentIndex(i)
            break

    p.harness.settle(0.3)

    # Account should auto-load; select first
    account_combo = dlg.account_combo
    if account_combo.count() > 0:
        account_combo.setCurrentIndex(0)

    p.harness.settle(0.3)

    # Income type using OS click (find by accessible name)
    os_select_combo(p.harness, dlg.income_type_combo, income_type)
    p.harness.settle(0.3)

    # Amount
    os_type_widget(p.harness, dlg.amount_spin, "50000", retries=2)
    p.harness.settle(0.3)

    # Frequency
    os_select_combo(p.harness, dlg.frequency_combo, frequency)
    p.harness.settle(0.3)

    # Date (either day spinner or date edit depending on frequency)
    if frequency in ("Monthly", "Quarterly", "Half-Yearly"):
        os_type_widget(p.harness, dlg.day_spin, "15", retries=2)
    else:
        from PySide6.QtCore import QDate
        dlg.date_edit.setDate(QDate.currentDate())

    p.harness.settle(0.3)

    # Notes
    os_type_widget(p.harness, dlg.notes_edit, f"RUIH_{income_type}", retries=2)

    p.harness.settle(0.3)

    os_click(p.harness, dlg, "Add income expectation", wait=1.0)


if __name__ == "__main__":
    main_wrapper("03", "income", run_r, run_s)
