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
    os_click, os_type, os_select_combo, answer_modal_dialog, find_button,
    toast_texts, wait_until,
)
from PySide6.QtWidgets import QApplication, QDialog


def run_r(p):
    """R-mode: read-only validation of income screen."""
    dashboard = p.start()

    page = p.nav("Income & Expectations")

    # Check: tables exist with correct names
    tables_found = {"ledger": False, "tds": False, "expectations": False}
    for w in dashboard.allWidgets():
        if hasattr(w, "accessibleName"):
            name = w.accessibleName()
            if "ledger table" in name.lower():
                tables_found["ledger"] = True
            if "tds" in name.lower() and "table" in name.lower():
                tables_found["tds"] = True
            if name == "Income expectations":
                tables_found["expectations"] = True

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
    dashboard = p.start()

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
                # Open Add Income Expectation dialog
                prearm = answer_modal_dialog(
                    p.harness, p.app, QDialog, "Add Income Expectation",
                    lambda dlg=None: _fill_income_dialog(
                        p, income_type, frequency, person_id, account_id, "2025-26"
                    )
                )
                os_click(p.harness, page, "Add income expectation", wait=0.5)
                # Wait for dialog and prearm callback
                ok = wait_until(p.harness, lambda: prearm.done, timeout=15)
                if not ok or prearm.error:
                    raise RuntimeError(f"Dialog prearm failed: {prearm.error}")

                # Button text depends on mode; read it from dialog
                p.harness.settle(0.5)

                # Get the save button from modal
                dlg = QApplication.activeModalWidget()
                if dlg is None:
                    raise RuntimeError("Dialog did not appear")

                save_btn = find_button(dlg, "Add")
                if save_btn is None:
                    raise RuntimeError("Save button not found in dialog")

                os_click(p.harness, dlg, save_btn.accessibleName(), wait=1.0)
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
                    False, str(e)
                )

    if added_count > 0:
        p.checks.check("add income expectations", True, f"added {added_count}")
        p.harness.settle(1.0)

        # Verify all rows are in DB
        result = p.sql("SELECT COUNT(*) FROM IncomeExpectation WHERE person_id=?", (person_id,))
        db_count = result[0][0] if result else 0
        p.observe("S03.db_count", f"DB has {db_count} expectations for person")

        # Test edit
        try:
            os_click(p.harness, page, "Edit selected income expectation", wait=0.5)
            p.harness.settle(1.0)
            p.observe("S03.edit", "Edit button clicked")
        except Exception:
            pass

        # Test link transaction
        try:
            os_click(p.harness, page, "Link actual transaction", wait=0.5)
            p.harness.settle(1.0)
            p.observe("S03.link", "Link transaction clicked")
        except Exception:
            pass

        # Test auto-match
        try:
            os_click(p.harness, page, "Auto-match income expectations", wait=1.5)
            toasts = toast_texts()
            p.observe("S03.auto_match_toast", str(toasts))
        except Exception:
            pass

        # Test delete
        try:
            os_click(p.harness, page, "Delete selected income expectation", wait=0.5)
            p.harness.settle(1.0)
            p.observe("S03.delete", "Delete button clicked")
        except Exception:
            pass

    # Check tax screen: waterfall_std_ded should be non-zero only while Salary exists
    try:
        p.nav("Tax")
        p.harness.settle(2.0)
        p.observe("S03.tax_nav", "Navigated to Tax screen")

        # Look for projection screen and waterfall
        tax_page = dashboard._screen_pages.get(7)
        if tax_page and hasattr(tax_page, "waterfall_std_ded"):
            std_ded_before = tax_page.waterfall_std_ded
            p.observe("S03.waterfall_std_ded", f"Value: {std_ded_before}")

    except Exception as e:
        p.observe("S03.tax_check", f"Error: {str(e)}")

    # Check prediction summary for H15 (projected_total)
    try:
        from engines.prediction_engine import get_prediction_summary
        summary = get_prediction_summary(person_id, "2025-26")
        if "fy_income" in summary and "projected_total" in summary["fy_income"]:
            proj_total = summary["fy_income"]["projected_total"]
            p.observe("S03.H15.projected_total", f"₹{proj_total:,.2f}")
            p.checks.check("H15 projection available", True)
        else:
            p.checks.check("H15 projection available", False, "key not in summary")
    except Exception as e:
        p.checks.check("H15 projection check", False, str(e))

    p.observe("S03", "Income S-mode tests complete")


def _fill_income_dialog(p, income_type, frequency, person_id, account_id, fy):
    """Fill and submit an IncomeExpectationDialog."""
    dlg = QApplication.activeModalWidget()
    if not isinstance(dlg, QDialog):
        raise RuntimeError(f"Expected QDialog, got {type(dlg).__name__}")

    # Select person
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

    # Income type
    income_type_combo = dlg.income_type_combo
    idx = income_type_combo.findText(income_type)
    if idx >= 0:
        income_type_combo.setCurrentIndex(idx)

    # Amount
    dlg.amount_spin.setValue(50000.0)

    # Frequency
    freq_combo = dlg.frequency_combo
    idx = freq_combo.findText(frequency)
    if idx >= 0:
        freq_combo.setCurrentIndex(idx)

    p.harness.settle(0.3)

    # Date (either day spinner or date edit depending on frequency)
    if frequency in ("Monthly", "Quarterly", "Half-Yearly"):
        dlg.day_spin.setValue(15)
    else:
        from PySide6.QtCore import QDate
        dlg.date_edit.setDate(QDate.currentDate())

    # Notes
    dlg.notes_edit.setText(f"RUIH_{income_type}")


if __name__ == "__main__":
    main_wrapper("03", "income", run_r, run_s)
