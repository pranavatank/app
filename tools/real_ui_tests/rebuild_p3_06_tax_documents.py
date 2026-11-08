r"""tools/real_ui_tests/rebuild_p3_06_tax_documents.py — Phase 3.06 Tax Documents.

Tests tax document import with R-mode reconciliation checking and S-mode AIS import.

Usage: python rebuild_p3_06_tax_documents.py --env R|S
"""
import sys
import json
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QLabel, QWidget

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.real_ui_tests.rebuild_p3_common import P3Run, main_wrapper
from tools.real_ui_tests.rebuild_common import (
    os_click_widget, native_file_dialog, answer_password_dialog,
    label_scan, parse_inr, read_secret, wait_until, set_fy, redact,
)
from tools.real_ui_test_harness import RealUIHarness, find_by_accessible_name
from tools.private_sources import get_personal_data_dir


PDATA = get_personal_data_dir()


def run_r(p):
    """Read-only: verify position table and FD reconciliation."""
    p.log.log("=== TAX DOCUMENTS R-MODE ===")

    dashboard = p.dashboard
    tax_page = p.nav("Tax Documents")
    p.harness.settle(1.5)

    if not hasattr(tax_page, "position_table"):
        p.checks.check("tax_page has position_table", False, "")
        return

    pos_table = tax_page.position_table
    pos_row_count = pos_table.rowCount()
    pos_visible = tax_page.position_frame.isVisible()
    p.log.log(f"Position table rows: {pos_row_count}, visible: {pos_visible}")
    p.observe("R06.tables_empty", f"position_frame.isVisible={pos_visible}, position_table.rowCount={pos_row_count}")

    fy = "2025-26"

    try:
        ais_data = p.sql(
            "SELECT fd_interest, savings_interest FROM AISTISImport WHERE person_id=1 AND financial_year=? AND source_type='AIS'",
            (fy,)
        )
        if ais_data:
            fd_interest, savings_interest = ais_data[0]
            p.log.log(f"AIS data: fd_interest={fd_interest}, savings_interest={savings_interest}")
        else:
            p.log.log("No AIS data found in DB")
    except Exception as e:
        p.log.log(f"AIS query failed: {e}")
        p.checks.check("ais_query success", False, str(e))

    try:
        tds_data = p.sql(
            "SELECT SUM(r.tds_deducted) FROM AISTISImportRecord r JOIN AISTISImport i USING(import_id) WHERE i.person_id=1 AND i.financial_year=? AND i.source_type='26AS'",
            (fy,)
        )
        if tds_data and tds_data[0][0] is not None:
            tds_deducted = tds_data[0][0]
            p.log.log(f"TDS data: tds_deducted={tds_deducted}")
        else:
            p.log.log("No TDS data found in DB")
    except Exception as e:
        p.log.log(f"TDS query failed: {e}")
        p.checks.check("tds_query success", False, str(e))

    if hasattr(tax_page, "fd_table"):
        fd_table = tax_page.fd_table
        fd_row_count = fd_table.rowCount()
        fd_visible = tax_page.fd_frame.isVisible()
        p.log.log(f"FD table rows: {fd_row_count}, visible: {fd_visible}")
        p.observe("R06.fd_table_empty", f"fd_frame.isVisible={fd_visible}, fd_table.rowCount={fd_row_count}")

        matched_count = 0
        not_in_app_count = 0

        for i in range(fd_row_count):
            status_item = fd_table.item(i, 3)
            if status_item:
                status = status_item.text().strip()
                if "Matched" in status:
                    matched_count += 1
                elif "Not in App" in status:
                    not_in_app_count += 1
                    account_item = fd_table.item(i, 0)
                    if account_item:
                        acc_no = account_item.text().strip()
                        last_4 = acc_no[-4:] if len(acc_no) >= 4 else acc_no
                        p.log.log(f"Not in App account: ...{last_4}")

        p.log.log(f"FD reconciliation: Matched={matched_count} Not in App={not_in_app_count}")

    try:
        import pyautogui
        for zone_name, zone in [("26AS", tax_page.zone_26as), ("AIS", tax_page.zone_ais), ("TIS", tax_page.zone_tis)]:
            if zone and zone.isVisible():
                center = zone.mapToGlobal(zone.rect().center())
                px, py = p.harness.to_physical(center)
                pyautogui.moveTo(px, py, duration=0.3)
                p.harness.settle(0.2)
                pyautogui.scroll(3)
                p.harness.settle(0.2)
                p.log.log(f"Hovered and scrolled {zone_name} zone")
    except Exception as e:
        p.log.log(f"Hover/scroll error: {e}")

    errors = label_scan(tax_page, ["gap", "mismatch", "error"])
    p.log.log(f"Label scan results (gap/mismatch/error): {errors}")
    if errors:
        for err in errors:
            p.observe("label_scan", err)

    p.nav("Accounts")
    p.harness.settle(1.0)

    set_fy(p.harness, dashboard, "2024-25")
    p.harness.settle(1.0)

    tax_page_2 = p.nav("Tax Documents")
    p.harness.settle(1.0)

    if hasattr(tax_page_2, "position_table"):
        pos_table_2 = tax_page_2.position_table
        row_count_2 = pos_table_2.rowCount()
        p.log.log(f"Position table after FY change to 2024-25: {row_count_2} rows")
        p.observe("fy_change", f"Changed to 2024-25, position table has {row_count_2} rows")

    set_fy(p.harness, dashboard, "2025-26")
    p.harness.settle(1.0)
    p.log.log("Restored to 2025-26")


def run_s(p):
    """Scratch: import AIS with password, verify financial year."""
    p.log.log("=== TAX DOCUMENTS S-MODE ===")

    dashboard = p.dashboard
    set_fy(p.harness, dashboard, "2026-27")
    p.harness.settle(1.0)
    tax_page = p.nav("Tax Documents")
    p.harness.settle(1.5)

    if not hasattr(tax_page, "zone_ais"):
        p.checks.check("tax_page has zone_ais", False, "")
        return

    ais_path = PDATA / "AIS.pdf"
    if not ais_path.exists():
        p.checks.check("AIS.pdf exists", False, str(ais_path))
        return

    ais_secret = read_secret("ais_tis")
    p.log.log("Read AIS/TIS password")
    previous_imports = p.sql("SELECT import_id FROM AISTISImport WHERE source_type='AIS' AND person_id=1")
    previous_ids = {row[0] for row in previous_imports}

    def trigger():
        os_click_widget(p.harness, tax_page.zone_ais, wait=1.5)

    # These two dialogs are expected parts of this flow; allow the watchdog to
    # observe them without generating noise or rejecting the native picker.
    p.expected_titles.update({"Select File", "Enter AIS Password"})

    # Observe QDialog.accepted directly so a completed helper callback cannot
    # be mistaken for a successful password-dialog acceptance.
    from ui.dialogs.password_dialog import PasswordDialog
    password_acceptance = {"seen": False, "accepted": False}
    acceptance_probe = QTimer()
    acceptance_probe.setInterval(20)

    def probe_password_dialog():
        dlg = QApplication.activeModalWidget()
        if (isinstance(dlg, PasswordDialog) and dlg.windowTitle() == "Enter AIS Password"
                and not password_acceptance["seen"]):
            password_acceptance["seen"] = True
            dlg.accepted.connect(lambda: password_acceptance.update(accepted=True))

    acceptance_probe.timeout.connect(probe_password_dialog)
    acceptance_probe.start()
    pwd_state = answer_password_dialog(p.harness, "Enter AIS Password", ais_secret, tick_save=True)
    native_file_dialog(trigger, str(ais_path), timeout=30)
    wait_until(p.harness, lambda: pwd_state["done"], timeout=90)
    acceptance_probe.stop()

    p.log.log(f"AIS password: done={pwd_state['done']} typed_ok={pwd_state.get('typed_ok')} error={pwd_state.get('error')}")
    p.checks.check("ais_password done", pwd_state["done"], "")
    p.checks.check("ais_password error", pwd_state.get("error") is None, pwd_state.get("error", ""))
    p.checks.check("ais_password accepted", password_acceptance["accepted"],
                   "PasswordDialog did not emit accepted" if not password_acceptance["accepted"] else "")

    def ais_terminal_or_loaded():
        return (tax_page.zone_ais.pdf_data is not None or
                tax_page.zone_ais.title_label.text().strip().lower().startswith("error:"))

    ok = wait_until(p.harness, ais_terminal_or_loaded, timeout=180, interval=0.5)
    zone_status = redact(tax_page.zone_ais.title_label.text().strip())[:240]
    toast_text = []
    for card in tax_page.findChildren(QWidget, "ToastCard"):
        labels = [label.text().strip() for label in card.findChildren(QLabel) if label.text().strip()]
        if labels:
            toast_text.append(redact(" | ".join(labels))[:240])
    diagnostic = f"zone_status={zone_status!r}; toast={toast_text[:3]!r}"
    loaded = tax_page.zone_ais.pdf_data is not None
    p.checks.check("ais_pdf_data loaded", loaded, diagnostic if not loaded else "")
    p.harness.settle(2.0)

    latest_row = p.sql(
        "SELECT financial_year, import_id FROM AISTISImport WHERE source_type='AIS' AND person_id=1 ORDER BY import_id DESC LIMIT 1"
    )
    if latest_row:
        fy = latest_row[0][0]
        p.checks.check("AIS import persisted a fresh row", latest_row[0][1] not in previous_ids,
                       f"import_id={latest_row[0][1]}; previous_ids={sorted(previous_ids)}")
        p.log.log(f"Latest AIS financial_year from DB: {fy}")
        p.observe("H3 import_fy", f"AIS financial_year: {fy}")

        seed_path = Path(__file__).parent / "screenshots" / "rebuild" / "P0_expectations.json"
        expected_fy = json.loads(seed_path.read_text(encoding="utf-8"))["ais"]["financial_year"]
        p.checks.check("ais_fy matches source document", fy == expected_fy,
                       f"expected {expected_fy}, got {fy}; selected FY is 2026-27")
    else:
        p.checks.check("ais_import record exists", False, "no AISTISImport row for AIS")


if __name__ == "__main__":
    main_wrapper("06", "tax_documents", run_r, run_s)
