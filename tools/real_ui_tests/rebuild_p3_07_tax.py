r"""tools/real_ui_tests/rebuild_p3_07_tax.py — Phase 3.07 Tax screen test

R: Validates pre-filled read-only interest inputs, data source switches, FY changes.
S: Validates tax calculation against engine, vector loop with various income values.
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.real_ui_tests.rebuild_p3_common import P3Run, main_wrapper
from tools.real_ui_tests.rebuild_common import (
    os_select_combo, os_click_widget, os_type_widget, parse_inr, set_fy
)
from engines.tax_engine import calculate_new_regime_tax, calculate_gross_total_income
from models.fd_interest_record import get_total_fd_interest
from models.savings_interest import get_total_savings_interest
from models.tax_profile import get_tax_profile


def run_r(p):
    tax_page = p.nav("Tax")

    os_select_combo(p.harness, tax_page.person_combo, "Pranav")
    p.harness.settle(0.5)

    os_select_combo(p.harness, tax_page.source_combo, "AIS/TIS Data")
    p.harness.settle(0.8)

    ais_row = p.sql(
        "SELECT fd_interest, savings_interest FROM AISTISImport WHERE person_id=1 AND financial_year='2025-26' ORDER BY import_date DESC LIMIT 1"
    )
    expected_ais_fd = ais_row[0][0] if ais_row else 0
    expected_ais_savings = ais_row[0][1] if ais_row else 0

    fd_val = tax_page.fd_interest_input.value()
    ok_fd = abs(fd_val - expected_ais_fd) < 0.01
    p.checks.check("tax AIS FD interest matches", ok_fd, f"got {fd_val} expected {expected_ais_fd}")

    savings_val = tax_page.savings_interest_input.value()
    ok_savings = abs(savings_val - expected_ais_savings) < 0.01
    p.checks.check("tax AIS savings interest matches", ok_savings, f"got {savings_val} expected {expected_ais_savings}")

    p.observe("P3.07_R_ais_fd_interest", str(expected_ais_fd))
    p.observe("P3.07_R_ais_savings_interest", str(expected_ais_savings))

    other_val = tax_page.other_income_input.value()
    dividend_val = tax_page.dividend_income.value()
    p.log.log(f"AIS other_income={other_val} dividend={dividend_val}")

    os_select_combo(p.harness, tax_page.source_combo, "App Actual Data")
    p.harness.settle(0.8)

    app_fd = tax_page.fd_interest_input.value()
    app_savings = tax_page.savings_interest_input.value()
    app_other = tax_page.other_income_input.value()

    expected_fd = get_total_fd_interest('2025-26', 1)
    expected_savings = get_total_savings_interest('2025-26', 1)
    tax_profile = get_tax_profile(1, '2025-26')
    expected_other = (tax_profile or {}).get('other_income', 0)

    ok_app_fd = abs(app_fd - expected_fd) < 0.01
    ok_app_savings = abs(app_savings - expected_savings) < 0.01
    ok_app_other = abs(app_other - expected_other) < 0.01

    p.checks.check("tax app FD interest matches", ok_app_fd, f"got {app_fd} expected {expected_fd}")
    p.checks.check("tax app savings interest matches", ok_app_savings, f"got {app_savings} expected {expected_savings}")
    p.checks.check("tax app other income matches", ok_app_other, f"got {app_other} expected {expected_other}")

    set_fy(p.harness, p.dashboard, "2024-25")
    p.harness.settle(0.5)

    fd_2425 = tax_page.fd_interest_input.value()
    savings_2425 = tax_page.savings_interest_input.value()

    set_fy(p.harness, p.dashboard, "2025-26")
    p.harness.settle(0.5)

    fd_back = tax_page.fd_interest_input.value()
    savings_back = tax_page.savings_interest_input.value()

    ok_fd_stable = abs(fd_back - app_fd) < 0.01
    ok_savings_stable = abs(savings_back - app_savings) < 0.01
    p.checks.check("tax FY switch FD stable", ok_fd_stable, f"before {app_fd} after {fd_back}")
    p.checks.check("tax FY switch savings stable", ok_savings_stable, f"before {app_savings} after {savings_back}")

    os_select_combo(p.harness, tax_page.person_combo, "All Persons")
    p.harness.settle(0.5)

    os_select_combo(p.harness, tax_page.person_combo, "Pranav")
    p.harness.settle(0.5)

    fd_after_person = tax_page.fd_interest_input.value()
    ok_person_stable = abs(fd_after_person - app_fd) < 0.01
    p.checks.check("tax person switch FD stable", ok_person_stable, f"before {app_fd} after {fd_after_person}")


def run_s(p):
    tax_page = p.nav("Tax")

    os_select_combo(p.harness, tax_page.person_combo, "Pranav")
    p.harness.settle(0.5)

    os_select_combo(p.harness, tax_page.source_combo, "AIS/TIS Data")
    p.harness.settle(0.8)

    os_click_widget(p.harness, tax_page.btn_calc, wait=1.2)
    p.harness.settle(0.8)

    waterfall_total_val = tax_page.waterfall_total.value
    ok_total_computed = waterfall_total_val is not None
    p.checks.check("tax waterfall total computed", ok_total_computed, f"value={waterfall_total_val}")

    waterfall_total_text = tax_page.waterfall_total.value_label.text()
    waterfall_parsed = parse_inr(waterfall_total_text)
    ok_waterfall_parse = abs(waterfall_parsed - waterfall_total_val) < 0.01 if (waterfall_total_val and waterfall_parsed) else False
    p.checks.check("tax waterfall parse matches value", ok_waterfall_parse, f"text={waterfall_total_text} parsed={waterfall_parsed} value={waterfall_total_val}")

    tax_profile_row = p.sql(
        "SELECT total_tax_new FROM TaxProfile WHERE person_id=1 AND financial_year='2025-26' ORDER BY rowid DESC LIMIT 1"
    )

    db_total = None
    if tax_profile_row:
        db_total = tax_profile_row[0][0]
        ok_db_match = abs(db_total - waterfall_total_val) < 0.01 if waterfall_total_val else False
        p.checks.check("tax DB total equals waterfall", ok_db_match, f"db={db_total} waterfall={waterfall_total_val}")
    else:
        p.checks.check("tax DB total equals waterfall", False, "no TaxProfile row found")

    salary_base = tax_page.gross_salary.value()
    exemption_10 = tax_page.exemption_10.value()
    deduction_16ii = tax_page.deduction_16ii.value()
    deduction_16iii = tax_page.deduction_16iii.value()
    salary = max(0, salary_base - exemption_10 - deduction_16ii - deduction_16iii)

    pension = max(0, tax_page.pension_income.value())

    stcg_normal = max(0, tax_page.stcg_normal.value())
    stcg_111a = max(0, tax_page.stcg_111a.value())
    ltcg_112 = max(0, tax_page.ltcg_20.value())
    ltcg_112a = max(0, tax_page.ltcg_112a.value())

    business_income = max(0, tax_page.manufacturing_income.value()) + max(0, tax_page.other_business_income.value())
    presumptive_income = max(0, tax_page.presumptive_income.value())

    other_income = (max(0, tax_page.rental_income.value()) + max(0, tax_page.lottery_winnings.value()) +
                    max(0, tax_page.online_game_winnings.value()) + max(0, tax_page.other_income_input.value()))

    fd_interest = max(0, tax_page.fd_interest_input.value())
    savings_interest = max(0, tax_page.savings_interest_input.value())
    other_interest = max(0, tax_page.other_interest.value())
    dividend = max(0, tax_page.dividend_income.value())

    total_business_income = business_income + presumptive_income

    gross, special_rate = calculate_gross_total_income(
        salary_income=salary,
        pension_income=pension,
        business_income=total_business_income,
        house_property_income=0,
        capital_gains_normal=stcg_normal,
        capital_gains_stcg_111a=stcg_111a,
        capital_gains_ltcg_112=ltcg_112,
        capital_gains_ltcg_112a=ltcg_112a,
        interest_income=fd_interest + savings_interest + other_interest,
        dividend_income=dividend,
        other_income=other_income,
    )

    engine_result = calculate_new_regime_tax(
        gross_income=gross,
        salary_income=salary,
        pension_income=pension,
        special_rate_income=special_rate,
        financial_year='2025-26'
    )
    engine_total = engine_result.get('total_tax', 0)

    ok_engine_match = abs(engine_total - waterfall_total_val) < 0.01 if waterfall_total_val else False
    p.checks.check("tax engine result matches waterfall", ok_engine_match, f"engine={engine_total} waterfall={waterfall_total_val}")

    vectors = [
        {"other": 1200000, "salary": 1275000},
        {"other": 1210000, "salary": 350458},
        {"other": 1300000, "salary": 6000000},
    ]

    for idx, vec in enumerate(vectors):
        os_type_widget(p.harness, tax_page.other_income_input, "0", retries=2)
        p.harness.settle(0.3)
        os_type_widget(p.harness, tax_page.gross_salary, "0", retries=2)
        p.harness.settle(0.3)

        os_type_widget(p.harness, tax_page.other_income_input, str(vec["other"]), retries=2)
        p.harness.settle(0.3)
        os_type_widget(p.harness, tax_page.gross_salary, str(vec["salary"]), retries=2)
        p.harness.settle(0.5)

        os_click_widget(p.harness, tax_page.btn_calc, wait=1.2)
        p.harness.settle(0.8)

        vec_waterfall_val = tax_page.waterfall_total.value

        vec_salary = max(0, vec["salary"] - tax_page.exemption_10.value() - tax_page.deduction_16ii.value() - tax_page.deduction_16iii.value())

        vec_fd = max(0, tax_page.fd_interest_input.value())
        vec_savings = max(0, tax_page.savings_interest_input.value())
        vec_other_int = max(0, tax_page.other_interest.value())
        vec_dividend = max(0, tax_page.dividend_income.value())

        vec_business = max(0, tax_page.manufacturing_income.value()) + max(0, tax_page.other_business_income.value())
        vec_presumptive = max(0, tax_page.presumptive_income.value())
        vec_total_business = vec_business + vec_presumptive

        vec_gross, vec_special = calculate_gross_total_income(
            salary_income=vec_salary,
            pension_income=max(0, tax_page.pension_income.value()),
            business_income=vec_total_business,
            house_property_income=0,
            capital_gains_normal=max(0, tax_page.stcg_normal.value()),
            capital_gains_stcg_111a=max(0, tax_page.stcg_111a.value()),
            capital_gains_ltcg_112=max(0, tax_page.ltcg_20.value()),
            capital_gains_ltcg_112a=max(0, tax_page.ltcg_112a.value()),
            interest_income=vec_fd + vec_savings + vec_other_int,
            dividend_income=vec_dividend,
            other_income=vec["other"],
        )

        vec_engine = calculate_new_regime_tax(
            gross_income=vec_gross,
            salary_income=vec_salary,
            pension_income=max(0, tax_page.pension_income.value()),
            special_rate_income=vec_special,
            financial_year='2025-26'
        )
        vec_engine_total = vec_engine.get('total_tax', 0)

        ok_vec = abs(vec_engine_total - vec_waterfall_val) < 0.01 if vec_waterfall_val else False
        p.checks.check(f"tax vector {idx} matches engine", ok_vec, f"engine={vec_engine_total} waterfall={vec_waterfall_val}")

    p.observe("H24", "plan tax vectors include prefilled AIS interest so pure vectors are unreachable")


if __name__ == "__main__":
    main_wrapper("07", "Tax", run_r, run_s)
