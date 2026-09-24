r"""tools/real_ui_tests/rebuild_p2_3_accounts.py — Phase 2.3 Accounts.

Precondition: BankAccount = 0. If it is 4 and all rows match, skip.
At script start, verify BankFDConvention = 4 (seeded for existing banks at
initialise_database()); if it is 0, record a finding (do not block on it —
it is a documented pre-existing plan-acknowledged gap when banks are added
mid-session rather than at process start).
"""
import sys
import json
import sqlite3
import faulthandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from tools.real_ui_tests.rebuild_common import (
    bootstrap_app, adopt_window, os_click, os_type,
    login_to_dashboard, set_fy, snapshot_db, append_progress,
    redacting_logger, nav_click, prearm, wait_until,
)
from tools.real_ui_test_harness import RealUIHarness, find_by_accessible_name, find_dialog_by_title

faulthandler.dump_traceback_later(900, exit=True)
log = redacting_logger("P2_3_accounts")
RUIH_DIR = Path(__file__).resolve().parent / "screenshots" / "rebuild"

ORDER = ["Jana", "IDFC FIRST", "Ujjivan", "Equitas"]


def main():
    from config import DB_PATH
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QDialog

    seed = json.loads((RUIH_DIR / "P0_expectations.json").read_text(encoding="utf-8"))
    person_seed = json.loads((RUIH_DIR / "P0_person_seed.json").read_text(encoding="utf-8"))
    holder_name = person_seed["full_name"]

    accounts_spec = []
    for bank in ORDER:
        s = seed["statements"][bank]
        accounts_spec.append({
            "bank": bank,
            "masked": s["masked_account_number"],
            "ifsc": s["ifsc"],
            "opening_balance": round(s["opening_balance"], 2),
        })
    log.log(f"accounts_spec: {accounts_spec}")

    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    n_bankconv = conn.execute("SELECT COUNT(*) FROM BankFDConvention").fetchone()[0]
    n_acct = conn.execute("SELECT COUNT(*) FROM BankAccount").fetchone()[0]
    conn.close()
    log.log(f"BankFDConvention (pre-bootstrap check) = {n_bankconv}")

    if n_acct == 4:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        rows = conn.execute(
            "SELECT account_id, person_id, bank_name, account_type, opening_balance, interest_rate FROM BankAccount ORDER BY account_id"
        ).fetchall()
        conn.close()
        log.log(f"BankAccount already = 4: {rows}")
        skip_entry = True
    elif n_acct == 0:
        skip_entry = False
    else:
        log.log(f"STOP: unexpected BankAccount count = {n_acct} (partial state should be impossible)")
        sys.exit(1)

    app = bootstrap_app()

    from config import DB_PATH as DB_PATH2
    conn = sqlite3.connect(f"file:{DB_PATH2}?mode=ro", uri=True)
    n_bankconv_after = conn.execute("SELECT COUNT(*) FROM BankFDConvention").fetchone()[0]
    conn.close()
    log.log(f"BankFDConvention after fresh bootstrap_app() (re-runs initialise_database()) = {n_bankconv_after} "
            f"(expect 4; if this differs from the pre-bootstrap value of {n_bankconv}, that demonstrates the "
            f"finding: banks added mid-session via the UI do NOT get seeded into BankFDConvention until the "
            f"next process start / initialise_database() call)")
    if n_bankconv_after != 4:
        log.log("FINDING (Medium): BankFDConvention did not reach 4 even after a fresh initialise_database() call.")

    harness = RealUIHarness(screenshot_dir=str(RUIH_DIR))
    dashboard = login_to_dashboard(harness)
    set_fy(harness, dashboard, "2025-26")
    log.log("logged in, FY set to 2025-26")

    if not skip_entry:
        nav_click(harness, dashboard, "Settings")
        os_click(harness, dashboard, "Manage bank accounts", wait=1.0)

        from ui.manage_data_screen import ManageDataScreen
        wait_until(harness, lambda: find_dialog_by_title(QDialog, "Manage Data", timeout=0.1) is not None, timeout=5)
        dlg = find_dialog_by_title(QDialog, "Manage Data", timeout=1.0)
        assert dlg is not None
        manage_widget = dlg.findChild(ManageDataScreen)
        tabs = manage_widget.tabs
        tab_rect = tabs.tabBar().tabRect(2)  # Accounts tab
        QTest.mouseClick(tabs.tabBar(), Qt.MouseButton.LeftButton, pos=tab_rect.center())
        harness.settle(0.5)
        log.log(f"Accounts tab selected: currentIndex={tabs.currentIndex()}")
        assert tabs.currentIndex() == 2

        from ui.dialogs.account_dialog import AccountDialog

        for spec in accounts_spec:
            state = {}

            def fill(spec=spec, state=state):
                ad = find_dialog_by_title(AccountDialog, "Add Account", timeout=5.0)
                if ad is None:
                    state["error"] = f"AccountDialog not found for {spec['bank']}"
                    return
                person_combo = find_by_accessible_name(ad, "Person selector")
                idx = person_combo.findText("Pranav")
                assert idx >= 0, f"Pranav not in person_combo: {[person_combo.itemText(i) for i in range(person_combo.count())]}"
                person_combo.setCurrentIndex(idx)
                harness.settle(0.3)

                bank_combo = find_by_accessible_name(ad, "Bank selector")
                match_idx = None
                for i in range(bank_combo.count()):
                    txt = bank_combo.itemText(i)
                    if txt.startswith(spec["bank"] + " ") or txt == spec["bank"] or spec["bank"] in txt.split(" (")[0]:
                        match_idx = i
                        break
                # fall back: match on the actual full bank name we created in P2.2
                if match_idx is None:
                    for i in range(bank_combo.count()):
                        if bank_combo.itemData(i) and spec["bank"].split()[0].lower() in bank_combo.itemData(i).lower():
                            match_idx = i
                            break
                assert match_idx is not None, f"bank {spec['bank']!r} not found in combo: {[bank_combo.itemText(i) for i in range(bank_combo.count())]}"
                bank_combo.setCurrentIndex(match_idx)
                harness.settle(0.3)
                log.log(f"bank_combo selected index={match_idx} text={bank_combo.itemText(match_idx)!r} (list item, not typed)")

                os_type(harness, ad, "Account holder name", holder_name)

                type_combo = find_by_accessible_name(ad, "Account type")
                sidx = type_combo.findText("Savings")
                assert sidx >= 0
                type_combo.setCurrentIndex(sidx)
                harness.settle(0.3)

                if spec["masked"]:
                    os_type(harness, ad, "Masked account number", spec["masked"])

                ob_widget = find_by_accessible_name(ad, "Opening balance")
                ob_widget.setValue(spec["opening_balance"])
                harness.settle(0.3)
                log.log(f"opening_balance set via setValue() fallback (non-OS, QDoubleSpinBox prefix "
                        f"makes raw keystroke typing unreliable): value()={ob_widget.value()}")

                # IFSC lives on the "Bank Details" tab.
                if spec["ifsc"]:
                    inner_tabs = find_by_accessible_name(ad, "Account details tabs")
                    bank_tab_rect = inner_tabs.tabBar().tabRect(1)
                    QTest.mouseClick(inner_tabs.tabBar(), Qt.MouseButton.LeftButton, pos=bank_tab_rect.center())
                    harness.settle(0.4)
                    os_type(harness, ad, "IFSC code", spec["ifsc"])
                    # back to basic tab not required before save

                interest_widget = find_by_accessible_name(ad, "Interest rate")
                log.log(f"interest_rate left at dialog default = {interest_widget.value()} (user has no real rates yet)")

                os_click(harness, ad, "Save account", wait=1.2)
                state["saved"] = True

            prearm(app, fill)
            os_click(harness, manage_widget, "Add account", wait=2.0)
            harness.settle(0.8)
            log.log(f"account {spec['bank']!r} fill state={state}")
            assert state.get("saved"), state.get("error")

        dlg.close()
        harness.settle(0.5)

    # --- Verify ---
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    rows = conn.execute(
        "SELECT account_id, person_id, bank_name, account_type, opening_balance, interest_rate FROM BankAccount ORDER BY account_id"
    ).fetchall()
    log.log(f"BankAccount rows: {rows}")
    assert len(rows) == 4
    for r, spec in zip(rows, accounts_spec):
        account_id, person_id, bank_name, account_type, opening_balance, interest_rate = r
        assert person_id == 1
        assert account_type == "Savings"
        assert abs(opening_balance - spec["opening_balance"]) < 0.005, f"{bank_name} opening_balance {opening_balance} != {spec['opening_balance']}"
        log.log(f"account_id={account_id} bank={bank_name!r} opening_balance={opening_balance} interest_rate={interest_rate} OK")

    n_bank_final = conn.execute("SELECT COUNT(*) FROM Bank").fetchone()[0]
    log.log(f"Bank count after account creation = {n_bank_final} (expect still 4, no duplicates from get_or_create_bank)")
    assert n_bank_final == 4

    n_holders = conn.execute("SELECT COUNT(*) FROM AccountHolder").fetchone()[0]
    log.log(f"AccountHolder rows = {n_holders} (expect 4)")
    conn.close()

    snap = snapshot_db("P2_3")
    log.log(f"snapshot: {snap}")
    append_progress(f"P2.3 accounts complete. 4 accounts created. snapshot={snap}")
    log.log("P2.3 DONE")


if __name__ == "__main__":
    main()
