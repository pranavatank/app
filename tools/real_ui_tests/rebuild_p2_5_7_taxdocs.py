r"""tools/real_ui_tests/rebuild_p2_5_7_taxdocs.py — Phase 2.5-2.7 Tax Documents
(Form 26AS -> AIS -> TIS), one TaxDocumentsScreen instance, in that fixed
order (26AS sets self._itr_financial_year, which AIS/TIS persistence reads).

Note: all three DropZone widgets on this screen share the SAME
accessibleName ("File drop zone" -- set unconditionally in
ui/widgets/drop_zone.py's _build_ui()), so they cannot be told apart by
accessible name. Each is clicked by direct widget reference
(tax_page.zone_26as / .zone_ais / .zone_tis) via os_click_widget().

26AS is never password-prompted by the app (parse_form26as_pdf() is always
called with password=None; only AIS and TIS check is_pdf_encrypted() and
show a PasswordDialog). Passwords come from password.txt via read_secret().
"""
import sys
import json
import faulthandler
from pathlib import Path
from PySide6.QtWidgets import QDialog

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from tools.real_ui_tests.rebuild_common import (
    bootstrap_app, adopt_window, os_click, os_click_widget, os_type,
    login_to_dashboard, set_fy, snapshot_db, append_progress,
    redacting_logger, nav_click, prearm, wait_until, native_file_dialog,
    read_secret, db_ro,
)
from tools.real_ui_test_harness import RealUIHarness, find_by_accessible_name, find_dialog_by_title

faulthandler.dump_traceback_later(900, exit=True)
log = redacting_logger("P2_5_7_taxdocs")
RUIH_DIR = Path(__file__).resolve().parent / "screenshots" / "rebuild"
PDATA = Path(__file__).resolve().parent.parent.parent / "data" / "PersonalData" / "Pranav"


def table_count(table):
    conn = db_ro()
    n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    conn.close()
    return n


def main():
    seed = json.loads((RUIH_DIR / "P0_expectations.json").read_text(encoding="utf-8"))

    n_26as = table_count("Form26ASImport")
    n_aistis = table_count("AISTISImport")
    n_26as_rec = table_count("Form26ASRecord")
    log.log(f"pre-run: Form26ASImport={n_26as} Form26ASRecord={n_26as_rec} AISTISImport={n_aistis}")

    if n_26as == 1 and n_aistis == 2:
        log.log("Form26ASImport=1 and AISTISImport=2 already; SKIP entire P2.5-2.7")
        append_progress("P2.5-2.7 tax documents: already complete (skip). "
                         f"Form26ASImport={n_26as} Form26ASRecord={n_26as_rec} AISTISImport={n_aistis}")
        log.log("P2.5-2.7 DONE (skip)")
        return
    if not (n_26as == 0 and n_aistis == 0):
        log.log(f"STOP: unexpected partial state Form26ASImport={n_26as} AISTISImport={n_aistis} "
                 "(neither 0/0 nor 1/2)")
        sys.exit(1)

    app = bootstrap_app()
    harness = RealUIHarness(screenshot_dir=str(RUIH_DIR))
    dashboard = login_to_dashboard(harness)
    set_fy(harness, dashboard, "2025-26")
    log.log("logged in, FY set to 2025-26")

    nav_click(harness, dashboard, "Tax Documents")
    tax_page = dashboard.tax_documents_page

    # --- 26AS (no password) ---
    path_26as = str((PDATA / "26AS.pdf").resolve())
    assert Path(path_26as).exists(), path_26as

    def trigger_26as():
        os_click_widget(harness, tax_page.zone_26as, wait=0.3)

    native_file_dialog(trigger_26as, path_26as, timeout=30)
    ok = wait_until(harness, lambda: tax_page.zone_26as.pdf_data is not None, timeout=60)
    log.log(f"26AS: pdf_data loaded={ok}")
    if not ok:
        raise RuntimeError("26AS did not load pdf_data within 60s")

    n_26as_after = table_count("Form26ASImport")
    n_26as_rec_after = table_count("Form26ASRecord")
    log.log(f"26AS: Form26ASImport={n_26as_after} Form26ASRecord={n_26as_rec_after} "
            f"(expected 1 / {seed['form26as']['record_count']})")

    # --- AIS (password-protected) ---
    ais_pw_state = {}

    def fill_ais_password():
        dlg = find_dialog_by_title(QDialog, "Enter AIS Password", timeout=5.0)
        if dlg is None:
            ais_pw_state["error"] = "AIS PasswordDialog not found"
            return
        pw = read_secret("ais_tis")
        os_type(harness, dlg, "Password input", pw, secret=True)
        os_click(harness, dlg, "Confirm password", wait=1.0)
        ais_pw_state["submitted"] = True

    path_ais = str((PDATA / "AIS.pdf").resolve())
    assert Path(path_ais).exists(), path_ais

    def trigger_ais():
        os_click_widget(harness, tax_page.zone_ais, wait=0.3)

    prearm(app, fill_ais_password)
    native_file_dialog(trigger_ais, path_ais, timeout=30)
    assert ais_pw_state.get("submitted"), ais_pw_state.get("error")

    ok = wait_until(harness, lambda: tax_page.zone_ais.pdf_data is not None, timeout=60)
    log.log(f"AIS: pdf_data loaded={ok}")
    if not ok:
        raise RuntimeError("AIS did not load pdf_data within 60s")

    # --- TIS (password-protected) ---
    tis_pw_state = {}

    def fill_tis_password():
        dlg = find_dialog_by_title(QDialog, "Enter TIS Password", timeout=5.0)
        if dlg is None:
            tis_pw_state["error"] = "TIS PasswordDialog not found"
            return
        pw = read_secret("ais_tis")
        os_type(harness, dlg, "Password input", pw, secret=True)
        os_click(harness, dlg, "Confirm password", wait=1.0)
        tis_pw_state["submitted"] = True

    path_tis = str((PDATA / "TIS.pdf").resolve())
    assert Path(path_tis).exists(), path_tis

    def trigger_tis():
        os_click_widget(harness, tax_page.zone_tis, wait=0.3)

    prearm(app, fill_tis_password)
    native_file_dialog(trigger_tis, path_tis, timeout=30)
    assert tis_pw_state.get("submitted"), tis_pw_state.get("error")

    ok = wait_until(harness, lambda: tax_page.zone_tis.pdf_data is not None, timeout=60)
    log.log(f"TIS: pdf_data loaded={ok}")
    if not ok:
        raise RuntimeError("TIS did not load pdf_data within 60s")

    ok = wait_until(harness, lambda: tax_page.merge_result is not None, timeout=30)
    log.log(f"merge_result set={ok}")

    # --- Verify (independent SQL, not trusting the app's own success toasts) ---
    n_26as_final = table_count("Form26ASImport")
    n_26as_rec_final = table_count("Form26ASRecord")
    n_aistis_final = table_count("AISTISImport")
    log.log(f"final: Form26ASImport={n_26as_final} Form26ASRecord={n_26as_rec_final} AISTISImport={n_aistis_final} "
            f"(expected 1 / {seed['form26as']['record_count']} / 2)")

    assert n_26as_final == 1, n_26as_final
    assert n_26as_rec_final == seed["form26as"]["record_count"], n_26as_rec_final
    assert n_aistis_final == 2, n_aistis_final

    snap = snapshot_db("P2_5_7")
    log.log(f"snapshot: {snap}")
    append_progress(
        f"P2.5-2.7 tax documents complete. Form26ASImport={n_26as_final} "
        f"Form26ASRecord={n_26as_rec_final} AISTISImport={n_aistis_final}. snapshot={snap}"
    )
    log.log("P2.5-2.7 DONE")


if __name__ == "__main__":
    main()
