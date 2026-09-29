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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from tools.real_ui_tests.rebuild_common import (
    bootstrap_app, os_click_widget,
    login_to_dashboard, set_fy, snapshot_db, append_progress,
    redacting_logger, nav_click, wait_until, native_file_dialog,
    read_secret, db_ro, answer_password_dialog, run_logged,
)
from tools.real_ui_test_harness import RealUIHarness, find_by_accessible_name

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
        os_click_widget(harness, tax_page.zone_26as, wait=1.5)

    native_file_dialog(trigger_26as, path_26as, timeout=30)
    ok = wait_until(harness, lambda: tax_page.zone_26as.pdf_data is not None, timeout=180)
    log.log(f"26AS: pdf_data loaded={ok}")
    if not ok:
        raise RuntimeError("26AS did not load pdf_data within 180s")

    n_26as_after = table_count("Form26ASImport")
    n_26as_rec_after = table_count("Form26ASRecord")
    log.log(f"26AS: Form26ASImport={n_26as_after} Form26ASRecord={n_26as_rec_after} "
            f"(expected 1 / {seed['form26as']['record_count']})")

    # --- AIS (password-protected) ---
    path_ais = str((PDATA / "AIS.pdf").resolve())
    assert Path(path_ais).exists(), path_ais

    def trigger_ais():
        os_click_widget(harness, tax_page.zone_ais, wait=1.5)

    st_ais = answer_password_dialog(harness, "Enter AIS Password", read_secret("ais_tis"), tick_save=True)
    native_file_dialog(trigger_ais, path_ais, timeout=30)
    wait_until(harness, lambda: st_ais["done"], 90)
    log.log(f"AIS password: typed_ok={st_ais.get('typed_ok')} save_checked={st_ais.get('save_checked')} error={st_ais.get('error')}")
    assert st_ais.get("error") is None, st_ais.get("error")

    ok = wait_until(harness, lambda: tax_page.zone_ais.pdf_data is not None, timeout=180)
    log.log(f"AIS: pdf_data loaded={ok}")
    if not ok:
        raise RuntimeError("AIS did not load pdf_data within 180s")

    # --- TIS (password-protected) ---
    path_tis = str((PDATA / "TIS.pdf").resolve())
    assert Path(path_tis).exists(), path_tis

    def trigger_tis():
        os_click_widget(harness, tax_page.zone_tis, wait=1.5)

    st_tis = answer_password_dialog(harness, "Enter TIS Password", read_secret("ais_tis"), tick_save=True)
    native_file_dialog(trigger_tis, path_tis, timeout=30)
    wait_until(harness, lambda: st_tis["done"], 90)
    log.log(f"TIS password: typed_ok={st_tis.get('typed_ok')} save_checked={st_tis.get('save_checked')} error={st_tis.get('error')}")
    assert st_tis.get("error") is None, st_tis.get("error")

    ok = wait_until(harness, lambda: tax_page.zone_tis.pdf_data is not None, timeout=180)
    log.log(f"TIS: pdf_data loaded={ok}")
    if not ok:
        raise RuntimeError("TIS did not load pdf_data within 180s")

    ok = wait_until(harness, lambda: tax_page.merge_result is not None, timeout=30)
    log.log(f"merge_result set={ok}")

    # --- Verify UI state ---
    if tax_page.merge_result is None:
        log.log("FINDING(High): merge_result is still None after merge attempt")
    if hasattr(tax_page, "fd_table"):
        fd_rowcount = tax_page.fd_table.rowCount()
        log.log(f"UI: fd_table.rowCount()={fd_rowcount}")

    # --- Verify independent SQL (not trusting the app's own success toasts) ---
    conn = db_ro()

    # Form26ASImport: exactly 1 row with correct values
    n_26as_import = conn.execute("SELECT COUNT(*) FROM Form26ASImport").fetchone()[0]
    assert n_26as_import == 1, f"Form26ASImport count {n_26as_import} != 1"

    form26as_row = conn.execute(
        "SELECT financial_year, total_tds FROM Form26ASImport"
    ).fetchone()
    fy_26as, total_tds_26as = form26as_row
    assert fy_26as == "2025-26", f"Form26ASImport fy {fy_26as} != 2025-26"
    assert abs(total_tds_26as - 13367.00) <= 0.005, f"Form26ASImport total_tds {total_tds_26as} != 13367.00 (tolerance 0.005)"
    log.log(f"Form26ASImport: fy={fy_26as} total_tds={total_tds_26as}")

    # Form26ASRecord: exactly seed's record_count rows
    expected_form26as_count = seed.get("form26as", {}).get("record_count", 158)
    n_26as_rec = conn.execute("SELECT COUNT(*) FROM Form26ASRecord").fetchone()[0]
    assert n_26as_rec == expected_form26as_count, f"Form26ASRecord count {n_26as_rec} != {expected_form26as_count}"
    log.log(f"Form26ASRecord count={n_26as_rec}")

    # Per-deductor totals (no hard-coded deductor names)
    deductor_rows = conn.execute("""
        SELECT deductor_name, SUM(amount_paid) as gross, SUM(tds_deducted) as tds
        FROM Form26ASRecord
        GROUP BY deductor_name
        ORDER BY deductor_name
    """).fetchall()

    for deductor_name, actual_gross, actual_tds in deductor_rows:
        log.log(f"Form26AS deductor: gross={actual_gross:.2f}, tds={actual_tds:.2f}")

    # AISTISImport: exactly 2 rows (one AIS, one TIS)
    ais_tis_rows = conn.execute("""
        SELECT source_type, financial_year, fd_interest, savings_interest, dividend_income, tds_deducted
        FROM AISTISImport
        ORDER BY source_type
    """).fetchall()

    assert len(ais_tis_rows) == 2, f"AISTISImport count {len(ais_tis_rows)} != 2"
    log.log(f"AISTISImport count={len(ais_tis_rows)}")
    for source_type, fy, fd_int, savings_int, div_inc, tds_ded in ais_tis_rows:
        log.log(f"AISTISImport {source_type}: fy={fy} fd_interest={fd_int} savings_interest={savings_int} dividend={div_inc} tds={tds_ded}")
        if fy != "2025-26":
            log.log("FINDING(High): AIS/TIS FY regression")

    # Check saved AIS/TIS password
    person_row = conn.execute(
        "SELECT ais_tis_password_enc IS NOT NULL FROM Person WHERE person_id=1"
    ).fetchone()
    if person_row:
        has_pwd_enc = person_row[0]
        log.log(f"Person.ais_tis_password_enc IS NOT NULL: {bool(has_pwd_enc)}")
        if has_pwd_enc:
            from models.person import get_ais_tis_password
            from core.session import session
            pwd = get_ais_tis_password(1, session.aes_key)
            pwd_matches = pwd == read_secret("ais_tis")
            log.log(f"get_ais_tis_password(1) matches stored: {pwd_matches}")

    conn.close()

    snap = snapshot_db("P2_5_7")
    log.log(f"snapshot: {snap}")
    append_progress(
        f"P2.5-2.7 tax documents complete. snapshot={snap}"
    )
    log.log("P2.5-2.7 DONE")


if __name__ == "__main__":
    run_logged(main, "P2_5_7_crash")
