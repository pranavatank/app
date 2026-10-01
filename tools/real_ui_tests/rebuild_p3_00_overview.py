r"""tools/real_ui_tests/rebuild_p3_00_overview.py — Phase 3.00 Overview page.

R: Navigate to Overview, validate KPI texts and SQL, test account combos, verify charts/panels.
S: Test Privacy mode toggle.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.real_ui_tests.rebuild_p3_common import P3Run, main_wrapper
from tools.real_ui_tests.rebuild_common import (
    os_select_combo, parse_inr, answer_message_box
)


def run_r(p):
    dashboard = p.dashboard
    p.nav("Overview")

    os_select_combo(p.harness, dashboard.person_combo, "Pranav")
    p.harness.settle(0.5)

    fy = dashboard.fy_combo.currentText()
    person_id = dashboard.person_combo.currentData()
    account_id = dashboard.account_combo.currentData()

    balance_text = dashboard.kpi_balance._value_lbl.text()
    income_text = dashboard.kpi_income._value_lbl.text()
    expense_text = dashboard.kpi_expense._value_lbl.text()
    savings_text = dashboard.kpi_savings._value_lbl.text()
    interest_text = dashboard.kpi_interest._value_lbl.text()

    balance_val = parse_inr(balance_text)
    income_val = parse_inr(income_text)
    expense_val = parse_inr(expense_text)
    savings_val = parse_inr(savings_text)
    interest_val = parse_inr(interest_text)

    p.observe("H01", f"balance={balance_text} income={income_text} expense={expense_text}")

    fy_start = int(fy.split("-")[0])
    fy_end = fy_start + 1
    fy_date_start = f"{fy_start}-04-01"
    fy_date_end = f"{fy_end}-03-31"

    if account_id is None:
        sql_balance = p.sql(
            "SELECT SUM(current_balance) FROM BankAccount WHERE person_id=?",
            (person_id,)
        )[0][0] or 0.0
    else:
        sql_balance = p.sql(
            "SELECT current_balance FROM BankAccount WHERE account_id=?",
            (account_id,)
        )[0][0] if p.sql("SELECT current_balance FROM BankAccount WHERE account_id=?", (account_id,)) else 0.0

    sql_income = p.sql(
        "SELECT SUM(amount) FROM Transactions WHERE person_id=? AND transaction_type='Income' "
        "AND COALESCE(is_internal_transfer,0)=0 AND transaction_date BETWEEN ? AND ?"
        + ("" if account_id is None else " AND account_id=?"),
        (person_id, fy_date_start, fy_date_end, account_id) if account_id else (person_id, fy_date_start, fy_date_end)
    )[0][0] or 0.0

    sql_expense = p.sql(
        "SELECT SUM(amount) FROM Transactions WHERE person_id=? AND transaction_type='Expense' "
        "AND COALESCE(is_internal_transfer,0)=0 AND transaction_date BETWEEN ? AND ?"
        + ("" if account_id is None else " AND account_id=?"),
        (person_id, fy_date_start, fy_date_end, account_id) if account_id else (person_id, fy_date_start, fy_date_end)
    )[0][0] or 0.0

    sql_income_gross = p.sql(
        "SELECT SUM(amount) FROM Transactions WHERE person_id=? AND transaction_type='Income' "
        "AND transaction_date BETWEEN ? AND ?"
        + ("" if account_id is None else " AND account_id=?"),
        (person_id, fy_date_start, fy_date_end, account_id) if account_id else (person_id, fy_date_start, fy_date_end)
    )[0][0] or 0.0

    p.observe("H02", f"sql_balance={sql_balance} sql_income={sql_income} sql_expense={sql_expense}")

    ok_balance = balance_val is not None and abs(balance_val - sql_balance) < 0.01
    p.checks.check("KPI balance matches SQL", ok_balance,
                   f"ui={balance_val} sql={sql_balance}")

    ok_income = income_val is not None and abs(income_val - sql_income) < 0.01
    p.checks.check("KPI income matches SQL", ok_income,
                   f"ui={income_val} sql={sql_income}")

    ok_expense = expense_val is not None and abs(expense_val - sql_expense) < 0.01
    p.checks.check("KPI expense matches SQL", ok_expense,
                   f"ui={expense_val} sql={sql_expense}")

    ok_net = savings_val is not None and abs(savings_val - (sql_income - sql_expense)) < 0.01
    p.checks.check("KPI net savings = income - expense", ok_net,
                   f"ui={savings_val} calc={sql_income - sql_expense}")

    sql_fd_interest = p.sql(
        "SELECT SUM(r.interest_earned) FROM FDInterestRecord r JOIN FixedDeposit f ON f.fd_id=r.fd_id WHERE f.person_id=? AND r.financial_year=?",
        (person_id, fy)
    )[0][0] or 0.0

    sql_sav_interest = p.sql(
        "SELECT SUM(s.interest_earned) FROM SavingsInterestRecord s JOIN BankAccount b ON b.account_id=s.account_id WHERE b.person_id=? AND s.financial_year=?",
        (person_id, fy)
    )[0][0] or 0.0

    sql_total_interest = sql_fd_interest + sql_sav_interest

    p.observe("H03", f"sql_fd_interest={sql_fd_interest} sql_sav_interest={sql_sav_interest}")

    ok_interest = interest_val is not None and abs(interest_val - sql_total_interest) < 0.01
    p.checks.check("KPI interest matches SQL", ok_interest,
                   f"ui={interest_val} sql={sql_total_interest}")

    person_items = [dashboard.person_combo.itemText(i) for i in range(dashboard.person_combo.count())]
    p.observe("H04", f"person_combo_items={len(person_items)}")
    p.checks.check("Person combo has All Persons option", "All Persons" in person_items)
    ok_person = dashboard.person_combo.currentText() == "Pranav"
    p.checks.check("Person combo select to Pranav", ok_person)

    account_items = [dashboard.account_combo.itemText(i) for i in range(dashboard.account_combo.count())]
    p.observe("H05", f"account_combo_items={len(account_items)}")

    for acct_item in account_items:
        if acct_item != "All Accounts":
            os_select_combo(p.harness, dashboard.account_combo, acct_item)
            p.harness.settle(0.5)
            ok_item = dashboard.account_combo.currentText() == acct_item
            p.checks.check(f"Account combo select to {acct_item}", ok_item)
            break

    os_select_combo(p.harness, dashboard.account_combo, "All Accounts")
    p.harness.settle(0.5)

    ok_chart_income = hasattr(dashboard.chart_income_expense, "_last_call") and \
                      dashboard.chart_income_expense._last_call is not None
    p.checks.check("Chart income_expense has _last_call", ok_chart_income)

    ok_chart_dist = hasattr(dashboard.chart_distribution, "_last_call") and \
                    dashboard.chart_distribution._last_call is not None
    p.checks.check("Chart distribution has _last_call", ok_chart_dist)

    panel_interest_rows = dashboard.panel_interest._rows if hasattr(dashboard.panel_interest, "_rows") else {}
    p.observe("H06", f"panel_interest_rows={len(panel_interest_rows)}")

    tax_profile = p.sql(
        "SELECT COUNT(*) FROM TaxProfile WHERE person_id=?",
        (person_id,)
    )[0][0]
    has_tax_data = tax_profile > 0
    p.observe("H07", f"tax_profile_rows={tax_profile}")

    if not has_tax_data:
        panel_tax_label = dashboard.panel_tax._rows.get("gross", None) if hasattr(dashboard.panel_tax, "_rows") else None
        panel_tax_text = panel_tax_label.text() if panel_tax_label else ""
        p.checks.check("Tax panel shows 'No data' when empty", "No data" in str(panel_tax_text))

    check_western = False
    for kpi_text in [balance_text, income_text, expense_text, savings_text, interest_text]:
        if kpi_text and any(c.isdigit() for c in kpi_text):
            import re
            if re.search(r"\d{1,3}(,\d{3}){2,}", kpi_text):
                check_western = True
                break

    if check_western:
        p.observe("H23", "Western grouping detected in KPI texts")


def run_s(p):
    dashboard = p.dashboard
    p.nav("Overview")

    from core import auth
    original_privacy = auth.get_privacy_mode()
    p.observe("S01", f"original_privacy={original_privacy}")

    p.nav("Settings")
    settings_page = dashboard.settings_page
    p.harness.settle(0.5)

    from tools.real_ui_tests.rebuild_common import os_click
    os_click(p.harness, settings_page, "Privacy mode", wait=0.8)
    p.harness.settle(1.0)

    p.nav("Overview")
    p.harness.settle(0.5)

    balance_text_masked = dashboard.kpi_balance._value_lbl.text()
    ok_masked = "****" in balance_text_masked or "•" in balance_text_masked
    p.checks.check("Privacy mode masks KPI balance", ok_masked, f"text={balance_text_masked}")

    all_masked = all([
        "****" in dashboard.kpi_balance._value_lbl.text() or "•" in dashboard.kpi_balance._value_lbl.text(),
        "****" in dashboard.kpi_income._value_lbl.text() or "•" in dashboard.kpi_income._value_lbl.text(),
        "****" in dashboard.kpi_expense._value_lbl.text() or "•" in dashboard.kpi_expense._value_lbl.text(),
        "****" in dashboard.kpi_savings._value_lbl.text() or "•" in dashboard.kpi_savings._value_lbl.text(),
        "****" in dashboard.kpi_interest._value_lbl.text() or "•" in dashboard.kpi_interest._value_lbl.text()
    ])
    p.checks.check("Privacy mode masks all 5 KPI texts", all_masked)

    p.nav("Settings")
    p.harness.settle(0.5)
    os_click(p.harness, settings_page, "Privacy mode", wait=0.8)
    p.harness.settle(1.0)

    p.nav("Overview")
    p.harness.settle(0.5)

    balance_text_unmasked = dashboard.kpi_balance._value_lbl.text()
    ok_unmasked = "****" not in balance_text_unmasked
    p.checks.check("Privacy mode toggle off restores KPI", ok_unmasked, f"text={balance_text_unmasked}")

    final_privacy = auth.get_privacy_mode()
    ok_final = final_privacy == original_privacy
    p.checks.check("Privacy mode restored to original", ok_final,
                   f"original={original_privacy} final={final_privacy}")


if __name__ == "__main__":
    main_wrapper("00", "overview", run_r, run_s)
