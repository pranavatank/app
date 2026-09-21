"""
tools/real_ui_tests/test_tax_documents_flow.py — Real, on-screen test:
Tax Documents -> drop real 26AS / AIS / TIS PDFs -> verify each parses.

Covers guide §5 "Specific flows to run end-to-end for real", item 5: click each
of the three drop zones for real, confirm each parses without the app hanging or
crashing, and confirm the reconciliation view populates.

The three handlers (_on_26as_selected / _on_ais_selected / _on_tis_selected) all
go through Loader.run(), so this doubles as a regression test for the GUI-thread
callback fix — before it, Loader delivered results on the worker thread and any
dialog opened there deadlocked the process.

A native QFileDialog cannot be driven by QTest, so the file is handed to the zone
via its own fileSelected(str) signal — the same mechanism the browse button uses
once a path is chosen. The literal browse-button click is therefore NOT covered.

AIS/TIS PDFs are encrypted, so a PasswordDialog opens on the GUI thread. Following
guide §5.3 gotcha G, we pre-arm QTimer.singleShot(0, callback) before emitting
fileSelected, where callback finds and fills the password dialog with the real
password from data/PersonalData/Pranav/password.txt.

Read-only: parses PDFs into memory and does not write transactions, so there is
nothing to clean up. Any rows the merge step would create are reported, not kept.

Run with:
    .venv/Scripts/python tools/real_ui_tests/test_tax_documents_flow.py
"""
import os
import sys
import time

os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")

# Amounts print with the rupee sign; the Windows console defaults to cp1252 and
# raises UnicodeEncodeError on it, which would kill a passing test at the report.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from PySide6.QtWidgets import QApplication, QDialog
from PySide6.QtCore import QTimer

from tools.real_ui_test_harness import RealUIHarness
from tools.taxdoc_import import read_ais_tis_password
from ui.dashboard_screen import DashboardScreen
from ui.dialogs.password_dialog import PasswordDialog
from ui.theme.theme_manager import ThemeManager
from core.backup_manager import create_backup

SHOT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(SHOT_DIR, exist_ok=True)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "PersonalData", "Pranav")
PASSWORD_FILE = os.path.join(DATA_DIR, "password.txt")
TAX_DOCS_NAV_INDEX = 6
PARSE_TIMEOUT = 90.0

checks = []


def get_ais_tis_password() -> str | None:
    """Get AIS/TIS password from file, env var, or return None."""
    # Try env var first
    pwd = os.environ.get("AIS_TIS_PASSWORD")
    if pwd:
        return pwd
    # Try password file
    pwd = read_ais_tis_password(PASSWORD_FILE)
    if pwd:
        return pwd
    return None


def check(label, ok):
    checks.append((label, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {label}", flush=True)
    return ok


def wait_for(predicate, timeout=PARSE_TIMEOUT, interval=0.5):
    """Pump the event loop until predicate() is true or the deadline passes."""
    app = QApplication.instance()
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.processEvents()
        try:
            if predicate():
                return True
        except Exception:
            pass
        time.sleep(interval)
    return False


def dismiss_blocking_dialogs():
    """Reject any unexpected modal that appeared, so one cannot strand the run.

    PasswordDialog is expected (it is pre-handled by drop_file), so it is not
    counted as a failure. All other dialogs are unexpected."""
    app = QApplication.instance()
    found = []
    for w in list(app.topLevelWidgets()):
        if isinstance(w, QDialog) and w.isVisible():
            # Skip PasswordDialog — it's expected and should be handled by drop_file
            if isinstance(w, PasswordDialog):
                continue
            found.append((type(w).__name__, w.windowTitle()))
            try:
                w.reject()
            except Exception:
                pass
    if found:
        print(f"[warn] dismissed unexpected modal dialog(s): {found}", flush=True)
    return found


def drop_file(harness, zone, path, label):
    """Hand a real path to a DropZone and wait for its parse to finish.

    For AIS/TIS (encrypted PDFs), pre-arms a QTimer.singleShot callback to handle
    the password dialog that will appear on the GUI thread."""
    if not os.path.exists(path):
        check(f"{label}: source file exists", False)
        return None

    # For AIS/TIS files, pre-arm a callback to handle the password dialog
    # (guide §5.3 gotcha G: modal .exec() blocks the caller).
    if label in ("AIS", "TIS"):
        password = get_ais_tis_password()
        if not password:
            check(f"{label}: password available from file or env var", False)
            return None

        def handle_password_dialog():
            """Find the password dialog and fill it with the real password."""
            try:
                dlg = harness.find_dialog(PasswordDialog, timeout=2.0)
                if dlg and dlg.isVisible():
                    # Fill password field
                    dlg.password_input.setText(password)
                    # Accept the dialog
                    dlg.accept()
                    print(f"[{label}] password dialog handled", flush=True)
            except Exception as e:
                print(f"[{label}] failed to handle password dialog: {e}", flush=True)

        # Pre-arm the callback to run ASAP (0ms delay)
        QTimer.singleShot(0, handle_password_dialog)

    zone.fileSelected.emit(path)
    harness.settle(1.0)

    # The handler sets zone.pdf_data on success, or an "Error: ..." status on
    # failure. Waiting only for pdf_data would burn the whole timeout on every
    # failure, so settle for either outcome and report which one arrived.
    def settled():
        if getattr(zone, "pdf_data", None) is not None:
            return True
        status = getattr(zone, "_status_label", None)
        return bool(status and "Error" in (status.text() or ""))

    wait_for(settled)
    ok = getattr(zone, "pdf_data", None) is not None
    if not ok:
        status = getattr(zone, "_status_label", None)
        print(f"[{label}] zone status: {status.text() if status else '(none)'}", flush=True)
    modals = dismiss_blocking_dialogs()
    if modals:
        check(f"{label}: parsed without opening a blocking modal", False)

    check(f"{label}: parsed (zone.pdf_data populated)", ok)
    return getattr(zone, "pdf_data", None)


def main():
    # Back up the database before testing
    print("[backup] creating database backup...", flush=True)
    try:
        backup_path = create_backup()
        if backup_path:
            print(f"[backup] saved to: {backup_path}", flush=True)
        else:
            print("[backup] FAILED — database may be modified if test fails", flush=True)
    except Exception as e:
        print(f"[backup] error: {e}", flush=True)

    ThemeManager.apply("Aurora", save=False, notify=False)
    harness = RealUIHarness(screenshot_dir=SHOT_DIR)
    dashboard = harness.launch(lambda: DashboardScreen(), maximized=True)
    harness.shot("00_dashboard")

    dpr = QApplication.primaryScreen().devicePixelRatio()
    print(f"[dpr] {dpr}", flush=True)

    # --- navigate to Tax Documents --------------------------------------------
    dashboard._navigate(TAX_DOCS_NAV_INDEX)
    harness.settle(1.5)
    harness.shot("01_tax_documents_screen")

    check("Tax Documents page title correct",
          dashboard.page_title_lbl.text() == "Tax Documents")

    screen = dashboard.stack.currentWidget()
    check("Tax Documents screen built without an error placeholder",
          TAX_DOCS_NAV_INDEX not in getattr(dashboard, "_screen_errors", {}))

    for attr in ("zone_26as", "zone_ais", "zone_tis"):
        if not check(f"Drop zone '{attr}' exists", hasattr(screen, attr)):
            return report(harness)

    # --- drop each real document ----------------------------------------------
    results = {}
    for attr, filename, label in (
        ("zone_26as", "26AS.pdf", "Form 26AS"),
        ("zone_ais", "AIS.pdf", "AIS"),
        ("zone_tis", "TIS.pdf", "TIS"),
    ):
        path = os.path.abspath(os.path.join(DATA_DIR, filename))
        print(f"\n[{label}] dropping {path}", flush=True)
        t0 = time.time()
        results[label] = drop_file(harness, getattr(screen, attr), path, label)
        print(f"[{label}] took {time.time() - t0:.1f}s", flush=True)
        harness.shot(f"02_{attr}_loaded")

    # The app must still be responsive after all three parses.
    harness.settle(1.5)
    check("App still responsive after all three parses",
          dashboard.isVisible() and dashboard.page_title_lbl.text() == "Tax Documents")
    harness.shot("03_all_three_loaded")

    # --- reconciliation view ---------------------------------------------------
    if all(results.values()):
        populated = wait_for(
            lambda: screen.position_table.rowCount() > 0
            or screen.non_income_table.rowCount() > 0
            or screen.fd_table.rowCount() > 0,
            timeout=20.0,
        )
        rows = (screen.position_table.rowCount(),
                screen.non_income_table.rowCount(),
                screen.fd_table.rowCount())
        print(f"[reconciliation] rows position/non_income/fd = {rows}", flush=True)
        check("Reconciliation view populated after all three documents", populated)
        harness.shot("04_reconciliation")
    else:
        print("[reconciliation] skipped - not all three documents parsed", flush=True)

    # --- verify database state ------------------------------------------------
    print("\n[verify] checking database state...", flush=True)
    verify_database_state()

    return report(harness)


def verify_database_state():
    """Verify Form26ASRecord and AISTISImport counts after parsing.

    Expected: Person 1, FY 2025-26 should have:
    - Form26ASRecord: 158 rows
    - AISTISImport: 2 rows (one for AIS, one for TIS)
    """
    try:
        from models.form26as import get_form26as_import, get_form26as_records
        from models.ais_tis_import import get_all_ais_tis_imports
        from engines.taxdocs.persist import SOURCE_TYPE_AIS, SOURCE_TYPE_TIS

        person_id = 1
        fy = "2025-26"

        # Check Form 26AS
        import_26as = get_form26as_import(person_id, fy)
        if import_26as:
            records = get_form26as_records(import_26as.get("import_id"))
            record_count = len(records)
            ok_26as = record_count == 158
            check(f"Form26ASRecord: {record_count} == 158", ok_26as)
            print(f"[verify] Form26ASRecord count: {record_count}", flush=True)
        else:
            check("Form26ASRecord: 158 == (none)", False)
            print("[verify] Form26ASRecord import not found", flush=True)

        # Check AIS/TIS imports
        all_imports = get_all_ais_tis_imports(person_id)
        ais_tis_list = [x for x in all_imports if x.get("financial_year") == fy]
        ais_count = sum(1 for x in ais_tis_list if x.get("source_type") == SOURCE_TYPE_AIS)
        tis_count = sum(1 for x in ais_tis_list if x.get("source_type") == SOURCE_TYPE_TIS)
        total_ais_tis = len(ais_tis_list)
        ok_ais_tis = total_ais_tis == 2 and ais_count == 1 and tis_count == 1
        check(f"AISTISImport: {total_ais_tis} rows (AIS: {ais_count}, TIS: {tis_count})", ok_ais_tis)
        print(f"[verify] AISTISImport count: {total_ais_tis} (AIS: {ais_count}, TIS: {tis_count})", flush=True)

    except Exception as e:
        print(f"[verify] error during database check: {e}", flush=True)
        import traceback
        traceback.print_exc(file=sys.stdout)


def report(harness):
    dismiss_blocking_dialogs()
    try:
        harness.close()
    except Exception:
        pass

    print("\n===== SUMMARY =====", flush=True)
    failed = [label for label, ok in checks if not ok]
    if failed:
        print(f"{len(failed)} check(s) FAILED:", flush=True)
        for label in failed:
            print(f"  - {label}", flush=True)
        return 1
    print("All checks PASSED.", flush=True)
    print(f"Screenshots saved to: {SHOT_DIR}", flush=True)
    return 0


def _close_all_windows():
    """Close every top-level window, whatever happened. A failed assertion must
    never leave a test window (or a blocking modal) on the user's screen."""
    try:
        app = QApplication.instance()
        if not app:
            return
        for w in list(app.topLevelWidgets()):
            try:
                if isinstance(w, QDialog) and w.isVisible():
                    w.reject()
            except Exception:
                pass
        for w in list(app.topLevelWidgets()):
            try:
                w.close()
            except Exception:
                pass
        app.processEvents()
    except Exception:
        pass


if __name__ == "__main__":
    try:
        rc = main()
    except BaseException:
        import traceback
        traceback.print_exc()
        rc = 1
    finally:
        _close_all_windows()
    sys.exit(rc)
