r"""tools/real_ui_tests/rebuild_p3_08_income_prediction.py — Phase 3.08 Income Prediction test (R only)

Validates prediction data, TDS risk tables, income comparison, and FY stability.
"""
import sys
from datetime import date

sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent.parent.parent))

from tools.real_ui_tests.rebuild_p3_common import P3Run, main_wrapper
from tools.real_ui_tests.rebuild_common import (
    label_scan, wait_until, set_fy
)
from engines.prediction_engine import get_prediction_summary


def run_r(p):
    prediction_page = p.nav("Income Prediction")

    ok_load = wait_until(
        p.harness,
        lambda: prediction_page._prediction_data.get('financial_year') == '2025-26',
        timeout=60
    )
    p.checks.check("income prediction data loaded FY 2025-26", ok_load)

    if not prediction_page._prediction_data:
        p.checks.check("income prediction data exists", False, "empty dict")
        return

    p.observe("P3.08_R_prediction_keys", str(list(prediction_page._prediction_data.keys())))

    summary = get_prediction_summary(1, '2025-26')
    p.observe("P3.08_R_summary_keys", str(list(summary.keys())))

    fy_income = prediction_page._prediction_data.get('fy_income', {})
    fy_projected = fy_income.get('projected_income_total', 0)
    fy_limit = fy_income.get('annual_income_limit', 0)
    fy_headroom = fy_income.get('income_headroom', 0)

    summary_projected = summary.get('projected_income_total', 0)
    summary_limit = summary.get('annual_income_limit', 0)
    summary_headroom = summary.get('income_headroom', 0)

    ok_projected = abs(fy_projected - summary_projected) < 0.01
    ok_limit = abs(fy_limit - summary_limit) < 0.01
    ok_headroom = abs(fy_headroom - summary_headroom) < 0.01

    p.checks.check("income prediction projected total matches", ok_projected,
                   f"page={fy_projected} summary={summary_projected}")
    p.checks.check("income prediction annual limit matches", ok_limit,
                   f"page={fy_limit} summary={summary_limit}")
    p.checks.check("income prediction headroom matches", ok_headroom,
                   f"page={fy_headroom} summary={summary_headroom}")

    page_tds_risk = prediction_page._prediction_data.get('tds_risk', {})
    page_by_bank = page_tds_risk.get('by_bank', [])

    summary_tds = summary.get('tds_risk', {})
    summary_by_bank = summary_tds.get('by_bank', [])

    ok_tds_banks = len(page_by_bank) == len(summary_by_bank)
    p.checks.check("income prediction TDS risk bank count matches", ok_tds_banks,
                   f"page={len(page_by_bank)} summary={len(summary_by_bank)}")

    page_comparison = prediction_page._prediction_data.get('comparison', {})
    summary_comparison = summary.get('comparison', {})

    page_comp_rows = page_comparison.get('rows', [])
    summary_comp_rows = summary_comparison.get('rows', [])

    ok_comp_rows = len(page_comp_rows) == len(summary_comp_rows)
    p.checks.check("income prediction comparison rows match", ok_comp_rows,
                   f"page={len(page_comp_rows)} summary={len(summary_comp_rows)}")

    error_labels = label_scan(prediction_page, ['gap', 'mismatch', 'error'])
    ok_no_errors = len(error_labels) == 0
    p.checks.check("income prediction no error labels", ok_no_errors,
                   detail=str(error_labels) if error_labels else "")

    set_fy(p.harness, p.dashboard, "2026-27")
    p.harness.settle(0.5)

    ok_fy_change = wait_until(
        p.harness,
        lambda: prediction_page._prediction_data.get('financial_year') == '2026-27',
        timeout=60
    )
    p.checks.check("income prediction FY changed to 2026-27", ok_fy_change)
    p.observe("P3.08_R_fy_2627_data", prediction_page._prediction_data.get('financial_year', 'not set'))

    nav_away = p.nav("Accounts")
    p.harness.settle(0.5)

    nav_back = p.nav("Income Prediction")
    p.harness.settle(1.0)

    ok_fy_persist = wait_until(
        p.harness,
        lambda: prediction_page._prediction_data.get('financial_year') == '2026-27',
        timeout=60
    )
    p.checks.check("income prediction FY persists after nav", ok_fy_persist)

    set_fy(p.harness, p.dashboard, "2025-26")
    p.harness.settle(0.5)

    ok_restore = wait_until(
        p.harness,
        lambda: prediction_page._prediction_data.get('financial_year') == '2025-26',
        timeout=60
    )
    p.checks.check("income prediction FY restored to 2025-26", ok_restore)


def run_s(p):
    p.checks.check("S mode unused", True, "n/a")


if __name__ == "__main__":
    main_wrapper("08", "Income Prediction", run_r, run_s)
