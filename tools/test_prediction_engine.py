#!/usr/bin/env python3
"""
tools/test_prediction_engine.py — Standalone test suite for prediction_engine.py

Tests internal consistency of prediction_engine against real DB with fixed values.
Read-only, deterministic, runnable from project root with:
    .venv\Scripts\python.exe tools/test_prediction_engine.py
"""

import sys
import os
import sqlite3
from pathlib import Path
from datetime import date

# Ensure UTF-8 output on Windows (rupee sign killed cp1252 before)
import codecs
sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Ensure we can import from the project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from engines.prediction_engine import (
    get_prediction_summary, build_strategies,
    STRATEGY_DECLARATION, STRATEGY_REDISTRIBUTION, STRATEGY_NEW_BANK,
    STRATEGY_DEFER_MATURITY, STRATEGY_HEADROOM_INVESTMENT, STRATEGY_DATA_QUALITY,
)
from config import DB_PATH


def get_db_connection():
    """Open read-only connection to the database."""
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)


def count_table_rows(table_name: str) -> int:
    """Count rows in a given table."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cur.fetchone()[0]
    conn.close()
    return count


def get_db_snapshot(label: str) -> dict:
    """Capture row counts for critical tables."""
    return {
        "label": label,
        "Transactions": count_table_rows("Transactions"),
        "FixedDeposit": count_table_rows("FixedDeposit"),
        "IncomeExpectation": count_table_rows("IncomeExpectation"),
        "BankAccount": count_table_rows("BankAccount"),
        "Form26ASImport": count_table_rows("Form26ASImport"),
        "Form26ASRecord": count_table_rows("Form26ASRecord"),
        "AISTISImport": count_table_rows("AISTISImport"),
    }


def assert_equal(actual, expected, tolerance=0.0, label=""):
    """Assert actual equals expected (with optional float tolerance)."""
    if isinstance(expected, float) and isinstance(actual, float):
        if abs(actual - expected) <= tolerance:
            print(f"PASS: {label} == {actual}")
            return True
        else:
            print(f"FAIL: {label} expected {expected}, got {actual} (diff: {actual - expected})")
            return False
    else:
        if actual == expected:
            print(f"PASS: {label} == {actual}")
            return True
        else:
            print(f"FAIL: {label} expected {expected}, got {actual}")
            return False


def assert_greater(actual, expected, label=""):
    """Assert actual > expected."""
    if actual > expected:
        print(f"PASS: {label} > {expected} (got {actual})")
        return True
    else:
        print(f"FAIL: {label} expected > {expected}, got {actual}")
        return False


def assert_false(actual, label=""):
    """Assert actual is False."""
    if actual is False:
        print(f"PASS: {label} is False")
        return True
    else:
        print(f"FAIL: {label} expected False, got {actual}")
        return False


def assert_is_list(actual, label=""):
    """Assert actual is a list."""
    if isinstance(actual, list):
        print(f"PASS: {label} is list with {len(actual)} items")
        return True
    else:
        print(f"FAIL: {label} expected list, got {type(actual)}")
        return False


def assert_len_equal(actual, expected, label=""):
    """Assert len(actual) == expected."""
    if len(actual) == expected:
        print(f"PASS: {label} len == {expected}")
        return True
    else:
        print(f"FAIL: {label} expected len {expected}, got {len(actual)}")
        return False


def assert_string_not_empty(actual, label=""):
    """Assert actual is a non-empty string."""
    if isinstance(actual, str) and len(actual) > 0:
        print(f"PASS: {label} is non-empty string (len {len(actual)})")
        return True
    else:
        print(f"FAIL: {label} expected non-empty string, got {repr(actual)}")
        return False


def run_tests():
    """Run all test assertions."""
    passed = 0
    failed = 0

    print("\n" + "="*80)
    print("TEST: Prediction Engine Internal Consistency")
    print("="*80)

    # Capture before snapshot
    before = get_db_snapshot("BEFORE")
    print(f"\nDB snapshot BEFORE:")
    for k, v in before.items():
        if k != "label":
            print(f"  {k}: {v}")

    # Fixed test parameters
    person_id = 1
    financial_year = "2025-26"
    as_of = date(2026, 3, 31)

    print(f"\nCalling get_prediction_summary(person_id={person_id}, financial_year='{financial_year}', as_of={as_of})")

    # Get the prediction summary
    try:
        result = get_prediction_summary(person_id, financial_year, as_of)
    except Exception as e:
        print(f"\nFAIL: get_prediction_summary raised exception: {e}")
        return 0, 1

    # Test 1: Realised income - taxable component
    test = assert_equal(
        result["realised_income"]["taxable"],
        95591.00,
        tolerance=0.01,
        label="realised_income['taxable']"
    )
    passed += test
    failed += not test

    # Test 2: Realised income - non_taxable component
    test = assert_equal(
        result["realised_income"]["non_taxable"],
        6400091.21,
        tolerance=0.01,
        label="realised_income['non_taxable']"
    )
    passed += test
    failed += not test

    # CRITICAL GUARD: The engine must classify by category, not sum all income
    # A naive implementation would report ~6.49M as taxable, which breaks the whole screen
    test = (
        assert_greater(
            result["realised_income"]["non_taxable"],
            5_000_000,
            label="realised_income['non_taxable'] > 5_000_000"
        )
        and
        assert_greater(
            200_000,
            result["realised_income"]["taxable"],
            label="realised_income['taxable'] < 200_000"
        )
    )
    if test:
        print("  ^ CRITICAL GUARD PASS: Engine correctly classifies by category, not naive sum.")
        passed += 1
    else:
        print("  ^ CRITICAL GUARD FAIL: Engine may be summing all income as taxable!")
        failed += 1

    # Test 3: Projected FD interest - estimated_fd_count
    test = assert_equal(
        result["projected_fd_interest"]["estimated_fd_count"],
        19,
        label="projected_fd_interest['estimated_fd_count']"
    )
    passed += test
    failed += not test

    # Test 4: Projected FD interest - known_fd_count
    test = assert_equal(
        result["projected_fd_interest"]["known_fd_count"],
        1,
        label="projected_fd_interest['known_fd_count']"
    )
    passed += test
    failed += not test

    # Test 5: Projected FD interest - total
    test = assert_equal(
        result["projected_fd_interest"]["total"],
        121507.00,
        tolerance=0.01,
        label="projected_fd_interest['total']"
    )
    passed += test
    failed += not test

    # INVARIANT 1: estimated_fd_count + known_fd_count == total FD count from DB
    total_fds_in_db = count_table_rows("FixedDeposit")
    fd_sum = result["projected_fd_interest"]["estimated_fd_count"] + result["projected_fd_interest"]["known_fd_count"]
    test = assert_equal(
        fd_sum,
        total_fds_in_db,
        label="estimated_fd_count + known_fd_count == total FD count"
    )
    passed += test
    failed += not test

    # INVARIANT 2: is_estimated == (estimated_fd_count > 0)
    expected_is_estimated = result["projected_fd_interest"]["estimated_fd_count"] > 0
    actual_is_estimated = result["projected_fd_interest"]["is_estimated"]
    test = assert_equal(
        actual_is_estimated,
        expected_is_estimated,
        label="is_estimated == (estimated_fd_count > 0)"
    )
    passed += test
    failed += not test

    # Test 6: FY Income - projected_total
    test = assert_equal(
        result["fy_income"]["projected_total"],
        217098.00,
        tolerance=0.01,
        label="fy_income['projected_total']"
    )
    passed += test
    failed += not test

    # Test 7: FY Income - limit
    test = assert_equal(
        result["fy_income"]["limit"],
        1200000.00,
        tolerance=0.01,
        label="fy_income['limit']"
    )
    passed += test
    failed += not test

    # Test 8: FY Income - headroom
    test = assert_equal(
        result["fy_income"]["headroom"],
        982902.00,
        tolerance=0.01,
        label="fy_income['headroom']"
    )
    passed += test
    failed += not test

    # Test 9: FY Income - is_over_limit
    test = assert_false(
        result["fy_income"]["is_over_limit"],
        label="fy_income['is_over_limit']"
    )
    passed += test
    failed += not test

    # Test 10: TDS Risk - threshold
    test = assert_equal(
        result["tds_risk"]["threshold"],
        50000.00,
        tolerance=0.01,
        label="tds_risk['threshold']"
    )
    passed += test
    failed += not test

    # Test 11: Timeline - months length
    test = assert_len_equal(
        result["timeline"]["months"],
        12,
        label="len(timeline['months'])"
    )
    passed += test
    failed += not test

    # Test 12: Timeline - final cumulative matches projected_total
    if result["timeline"]["months"]:
        test = assert_equal(
            result["timeline"]["months"][-1]["cumulative_projected"],
            result["fy_income"]["projected_total"],
            tolerance=0.01,
            label="timeline['months'][-1]['cumulative_projected'] == fy_income['projected_total']"
        )
        passed += test
        failed += not test

    # STRUCTURAL ASSERTION 2: Headroom calculation
    test = assert_equal(
        result["fy_income"]["headroom"],
        result["fy_income"]["limit"] - result["fy_income"]["projected_total"],
        tolerance=0.01,
        label="fy_income['headroom'] == limit - projected_total"
    )
    passed += test
    failed += not test

    # STRUCTURAL ASSERTION 3: Per-bank TDS interest sums correctly
    test = assert_is_list(
        result["tds_risk"]["by_bank"],
        label="tds_risk['by_bank']"
    )
    passed += test
    failed += not test

    if isinstance(result["tds_risk"]["by_bank"], list):
        per_bank_total = sum(bank["projected_interest"] for bank in result["tds_risk"]["by_bank"])
        test = assert_equal(
            per_bank_total,
            result["projected_fd_interest"]["total"],
            tolerance=0.01,
            label="sum(tds_risk['by_bank'][*]['projected_interest']) ~= projected_fd_interest['total']"
        )
        passed += test
        failed += not test

    # STRUCTURAL ASSERTION 4: Known + estimated total = total
    test = assert_equal(
        result["projected_fd_interest"]["known_total"] + result["projected_fd_interest"]["estimated_total"],
        result["projected_fd_interest"]["total"],
        tolerance=0.01,
        label="known_total + estimated_total == total"
    )
    passed += test
    failed += not test

    # STRUCTURAL ASSERTION 5: is_estimated flags present
    test = True
    if isinstance(result["tds_risk"]["by_bank"], list):
        for bank in result["tds_risk"]["by_bank"]:
            if "is_estimated" not in bank:
                test = False
                break
    if test and "is_estimated" in result["projected_fd_interest"]:
        print(f"PASS: Every dict that reports money carries is_estimated key")
        passed += 1
    else:
        print(f"FAIL: Some dict missing is_estimated key")
        failed += 1

    # STRUCTURAL ASSERTION 6: Advisory structure
    test = assert_is_list(
        result["advisory"]["warnings"],
        label="advisory['warnings']"
    )
    passed += test
    failed += not test

    test = assert_string_not_empty(
        result["advisory"]["disclaimer"],
        label="advisory['disclaimer']"
    )
    passed += test
    failed += not test

    # ========== E2: New assertions for ITR, comparison, and strategies ==========

    # BLOCK 1: ITR actuals stored (6 assertions)
    print("\n--- ITR actuals ---")
    test = (
        result["itr_actuals"]["has_data"] is True
    )
    if test:
        print(f"PASS: itr_actuals['has_data'] is True")
        passed += 1
    else:
        print(f"FAIL: itr_actuals['has_data'] expected True, got {result['itr_actuals']['has_data']}")
        failed += 1

    if result["itr_actuals"]["form26as"]:
        test = assert_equal(
            result["itr_actuals"]["form26as"]["total_tds"],
            13367.00,
            tolerance=0.01,
            label="itr_actuals['form26as']['total_tds']"
        )
        passed += test
        failed += not test
    else:
        print(f"FAIL: itr_actuals['form26as'] is None")
        failed += 1

    if result["itr_actuals"]["ais"]:
        test = assert_equal(
            result["itr_actuals"]["ais"]["fd_interest"],
            256642.00,
            tolerance=0.01,
            label="itr_actuals['ais']['fd_interest']"
        )
        passed += test
        failed += not test

        test = assert_equal(
            result["itr_actuals"]["ais"]["savings_interest"],
            46183.00,
            tolerance=0.01,
            label="itr_actuals['ais']['savings_interest']"
        )
        passed += test
        failed += not test

        test = assert_equal(
            result["itr_actuals"]["ais"]["total_interest"],
            302825.00,
            tolerance=0.01,
            label="itr_actuals['ais']['total_interest']"
        )
        passed += test
        failed += not test

        test = assert_equal(
            result["itr_actuals"]["ais"]["tds_deducted"],
            12073.00,
            tolerance=0.01,
            label="itr_actuals['ais']['tds_deducted']"
        )
        passed += test
        failed += not test
    else:
        print(f"FAIL: itr_actuals['ais'] is None")
        failed += 4

    # BLOCK 2: Comparison shape and framing (4 assertions)
    print("\n--- Comparison shape ---")
    test = assert_len_equal(
        result["comparison"]["rows"],
        4,
        label="len(comparison['rows'])"
    )
    passed += test
    failed += not test

    # Check FD Interest row has our_under_reports == True
    fd_interest_row = next((r for r in result["comparison"]["rows"] if r.get("label") == "FD Interest"), None)
    if fd_interest_row:
        test = fd_interest_row.get("our_under_reports") is True
        if test:
            print(f"PASS: FD Interest row our_under_reports is True")
            passed += 1
        else:
            print(f"FAIL: FD Interest row our_under_reports expected True, got {fd_interest_row.get('our_under_reports')}")
            failed += 1
    else:
        print(f"FAIL: FD Interest row not found in comparison")
        failed += 1

    # Check TDS row has our_value == 0.0
    tds_row = next((r for r in result["comparison"]["rows"] if r.get("label") == "TDS Deducted"), None)
    if tds_row:
        test = assert_equal(
            tds_row.get("our_value"),
            0.0,
            tolerance=0.01,
            label="TDS Deducted row our_value"
        )
        passed += test
        failed += not test
    else:
        print(f"FAIL: TDS Deducted row not found in comparison")
        failed += 1

    # Text guard: no "gap", "mismatch", "error" in comparison rows and strategies
    forbidden_words = ["gap", "mismatch", "error"]
    forbidden_found = []
    for row in result["comparison"]["rows"]:
        text = (row.get("label", "") + " " +
                (row.get("our_under_reports") and "Our data under-reports this figure" or "Our data covers this figure")).lower()
        for word in forbidden_words:
            if word in text:
                forbidden_found.append(word)

    strategies = result.get("advisory", {}).get("strategies", [])
    for strat in strategies:
        text = (strat.get("title", "") + " " + strat.get("detail", "") + " " + strat.get("action", "")).lower()
        for word in forbidden_words:
            if word in text:
                forbidden_found.append(word)

    if not forbidden_found:
        print(f"PASS: No forbidden words (gap/mismatch/error) in comparison or strategies")
        passed += 1
    else:
        print(f"FAIL: Found forbidden words: {set(forbidden_found)}")
        failed += 1

    # BLOCK 3: Strategies (6 assertions)
    print("\n--- Strategies ---")
    test = assert_is_list(
        result["advisory"]["strategies"],
        label="advisory['strategies']"
    )
    passed += test
    failed += not test

    test = assert_equal(
        result["advisory"]["context"]["limit"],
        result["fy_income"]["limit"],
        tolerance=0.01,
        label="context['limit'] == fy_income['limit']"
    )
    passed += test
    failed += not test

    test = assert_equal(
        result["advisory"]["context"]["tds_threshold"],
        result["tds_risk"]["threshold"],
        tolerance=0.01,
        label="context['tds_threshold'] == tds_risk['threshold']"
    )
    passed += test
    failed += not test

    # Every strategy has all 9 documented keys
    strategy_keys = {"id", "category", "priority", "title", "detail", "action", "amount", "bank_name", "is_estimated"}
    all_keys_present = True
    for strat in strategies:
        if not strategy_keys.issubset(set(strat.keys())):
            all_keys_present = False
            print(f"FAIL: Strategy missing keys: expected {strategy_keys}, got {set(strat.keys())}")
            break
    if all_keys_present:
        print(f"PASS: Every strategy has all 9 documented keys")
        passed += 1
    else:
        failed += 1

    # Every priority is int >= 1 and strategies sorted by priority
    all_priorities_valid = True
    priorities_sorted = True
    if strategies:
        prev_priority = 0
        for strat in strategies:
            pri = strat.get("priority")
            if not isinstance(pri, int) or pri < 1:
                all_priorities_valid = False
                print(f"FAIL: Strategy priority invalid: {pri}")
                break
            if pri < prev_priority:
                priorities_sorted = False
            prev_priority = pri
    else:
        # No strategies is OK
        all_priorities_valid = True
        priorities_sorted = True

    if all_priorities_valid:
        print(f"PASS: All strategy priorities are int >= 1")
        passed += 1
    else:
        failed += 1

    if priorities_sorted or not strategies:
        print(f"PASS: Strategies sorted by priority")
        passed += 1
    else:
        print(f"FAIL: Strategies not sorted by priority")
        failed += 1

    # BLOCK 4: Strategy coverage of crossing banks (1 assertion)
    print("\n--- Crossing banks coverage ---")
    crossing_banks_need_declaration = []
    if not result["fy_income"]["is_over_limit"]:
        for bank in result["tds_risk"]["by_bank"]:
            if bank.get("will_cross"):
                crossing_banks_need_declaration.append(bank.get("bank_name"))

    all_crossing_covered = True
    if crossing_banks_need_declaration:
        strategy_declarations = [s for s in strategies if s.get("category") == STRATEGY_DECLARATION]
        declared_banks = [s.get("bank_name") for s in strategy_declarations]
        for bank_name in crossing_banks_need_declaration:
            if bank_name not in declared_banks:
                all_crossing_covered = False
                print(f"FAIL: Crossing bank {bank_name} not covered by STRATEGY_DECLARATION")
                break

    if all_crossing_covered:
        print(f"PASS: All crossing banks have STRATEGY_DECLARATION (when under limit)")
        passed += 1
    else:
        failed += 1

    # BLOCK 5: build_strategies purity (2 assertions)
    print("\n--- build_strategies purity ---")
    strategies1 = build_strategies(person_id, financial_year, as_of)
    strategies2 = build_strategies(person_id, financial_year, as_of)

    test = strategies1["strategies"] == strategies2["strategies"]
    if test:
        print(f"PASS: build_strategies returns same strategies on two calls")
        passed += 1
    else:
        print(f"FAIL: build_strategies returned different results on two calls")
        print(f"  Call 1: {len(strategies1.get('strategies', []))} strategies")
        print(f"  Call 2: {len(strategies2.get('strategies', []))} strategies")
        failed += 1

    # Verify no row count changes across pure function calls
    snapshot_mid = get_db_snapshot("MID (after build_strategies)")
    test = True
    for table in ["Transactions", "FixedDeposit", "IncomeExpectation", "BankAccount", "Form26ASImport", "Form26ASRecord", "AISTISImport"]:
        if before[table] != snapshot_mid[table]:
            test = False
            print(f"FAIL: {table} changed during build_strategies ({before[table]} -> {snapshot_mid[table]})")
            break
    if test:
        print(f"PASS: All table counts unchanged during build_strategies calls")
        passed += 1
    else:
        failed += 1

    # ========== End E2 assertions ==========

    # EDGE CASE 1: FY with no data
    print("\n--- Edge case: FY with no data (2019-20) ---")
    try:
        edge_result = get_prediction_summary(1, "2019-20", as_of=date(2020, 3, 31))
        print(f"PASS: get_prediction_summary(1, '2019-20') did not raise (returned summary)")
        passed += 1
    except Exception as e:
        print(f"FAIL: get_prediction_summary(1, '2019-20') raised {e}")
        failed += 1

    # EDGE CASE 2: Person who does not exist
    print("\n--- Edge case: Person who does not exist (99999) ---")
    try:
        edge_result = get_prediction_summary(99999, "2025-26", as_of=date(2026, 3, 31))
        print(f"PASS: get_prediction_summary(99999, '2025-26') did not raise (returned summary)")
        passed += 1
    except Exception as e:
        print(f"FAIL: get_prediction_summary(99999, '2025-26') raised {e}")
        failed += 1

    # EDGE CASE 3: financial_year=None (derive current FY)
    print("\n--- Edge case: financial_year=None (derive current) ---")
    try:
        edge_result = get_prediction_summary(1, None, as_of=date(2026, 3, 31))
        if edge_result.get("financial_year"):
            print(f"PASS: get_prediction_summary(1, None) derived FY: {edge_result['financial_year']}")
            passed += 1
        else:
            print(f"FAIL: get_prediction_summary(1, None) returned no financial_year")
            failed += 1
    except Exception as e:
        print(f"FAIL: get_prediction_summary(1, None) raised {e}")
        failed += 1

    # EDGE CASE 4: Idempotency
    print("\n--- Edge case: Idempotency (call twice) ---")
    try:
        result1 = get_prediction_summary(1, "2025-26", as_of=date(2026, 3, 31))
        result2 = get_prediction_summary(1, "2025-26", as_of=date(2026, 3, 31))
        if (result1["fy_income"]["projected_total"] == result2["fy_income"]["projected_total"] and
            result1["realised_income"]["taxable"] == result2["realised_income"]["taxable"]):
            print(f"PASS: Idempotent (two calls return same fy_income['projected_total'])")
            passed += 1
        else:
            print(f"FAIL: Results differ between calls")
            failed += 1
    except Exception as e:
        print(f"FAIL: Idempotency test raised {e}")
        failed += 1

    # Capture after snapshot
    after = get_db_snapshot("AFTER")
    print(f"\nDB snapshot AFTER:")
    for k, v in after.items():
        if k != "label":
            print(f"  {k}: {v}")

    # Also show BEFORE snapshot with ITR tables
    print(f"\nDB snapshot BEFORE (full):")
    for k, v in before.items():
        if k != "label":
            print(f"  {k}: {v}")

    # Zero side-effect proof
    print("\n--- Zero-side-effect proof ---")
    # Check original 4 tables as formal assertions
    for table in ["Transactions", "FixedDeposit", "IncomeExpectation", "BankAccount"]:
        before_count = before[table]
        after_count = after[table]
        if before_count == after_count:
            print(f"PASS: {table} count unchanged ({before_count} -> {after_count})")
            passed += 1
        else:
            print(f"FAIL: {table} count changed ({before_count} -> {after_count})")
            failed += 1

    # Check new ITR tables as formal assertions
    for table in ["Form26ASImport", "Form26ASRecord", "AISTISImport"]:
        before_count = before.get(table, 0)
        after_count = after.get(table, 0)
        test = assert_equal(
            after_count,
            before_count,
            label=f"{table} count unchanged"
        )
        passed += test
        failed += not test

    # Summary
    print("\n" + "="*80)
    total = passed + failed
    print(f"SUMMARY: {passed} passed, {failed} failed out of {total} assertions")
    print("="*80)

    return passed, failed


if __name__ == "__main__":
    passed, failed = run_tests()
    sys.exit(0 if failed == 0 else 1)
