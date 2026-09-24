r"""tools/real_ui_tests/rebuild_p2_4_statement.py — Phase 2.4 Statements.

Usage: python rebuild_p2_4_statement.py --bank Jana|IDFC FIRST|Ujjivan|Equitas

Run once per statement in the order Jana -> IDFC FIRST -> Ujjivan -> Equitas
(reprocess_internal_transfers runs after each import, across accounts).

Full OS-level interaction throughout (real pyautogui mouse movement + click,
real keystrokes) -- this is the first script written after the course
correction away from QTest-driven clicks; see rebuild_common.py docstring.
"""
import sys
import json
import time
import sqlite3
import argparse
import subprocess
import faulthandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from tools.real_ui_tests.rebuild_common import (
    bootstrap_app, adopt_window, os_click, os_type, read_secret,
    login_to_dashboard, set_fy, snapshot_db, append_progress,
    redacting_logger, nav_click, prearm, wait_until, assert_foreground,
)
from tools.real_ui_test_harness import RealUIHarness, find_by_accessible_name, find_dialog_by_title

faulthandler.dump_traceback_later(900, exit=True)
RUIH_DIR = Path(__file__).resolve().parent / "screenshots" / "rebuild"
STATEMENT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "PersonalData" / "Pranav" / "Statement"
FILE_TYPER = Path(__file__).resolve().parent / "os_file_dialog_typer.py"

BANK_ORDER = ["Jana", "IDFC FIRST", "Ujjivan", "Equitas"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", required=True, choices=BANK_ORDER)
    args = ap.parse_args()
    bank = args.bank

    log = redacting_logger(f"P2_4_{bank.replace(' ', '_')}")
    seed = json.loads((RUIH_DIR / "P0_expectations.json").read_text(encoding="utf-8"))
    spec = seed["statements"][bank]
    pdf_path = STATEMENT_DIR / spec["file"]
    if not pdf_path.exists():
        log.log(f"STOP: statement file not found: {pdf_path}")
        sys.exit(1)

    from config import DB_PATH

    def get_account_id_and_count():
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        row = conn.execute(
            "SELECT account_id FROM BankAccount WHERE bank_name LIKE ? ORDER BY account_id LIMIT 1",
            (f"%{bank.split()[0]}%",),
        ).fetchone()
        if row is None:
            conn.close()
            return None, None
        account_id = row[0]
        n = conn.execute("SELECT COUNT(*) FROM Transactions WHERE account_id=?", (account_id,)).fetchone()[0]
        conn.close()
        return account_id, n

    account_id, n_tx = get_account_id_and_count()
    if account_id is None:
        log.log(f"STOP: no BankAccount row matching bank={bank!r}")
        sys.exit(1)
    log.log(f"account_id={account_id} existing Transactions={n_tx} expected={spec['count']}")

    if n_tx == spec["count"]:
        log.log("Already imported for this account; skipping entry, verify only.")
        skip_entry = True
    elif n_tx == 0:
        skip_entry = False
    else:
        log.log(f"STOP: partial state ({n_tx} of {spec['count']}) -- batch insert should be all-or-nothing")
        sys.exit(1)

    app = bootstrap_app()
    harness = RealUIHarness(screenshot_dir=str(RUIH_DIR))
    dashboard = login_to_dashboard(harness)
    set_fy(harness, dashboard, "2025-26")
    log.log("logged in, FY set to 2025-26")

    if not skip_entry:
        nav_click(harness, dashboard, "Statement Import")
        import_screen = dashboard.import_page
        assert import_screen is not None, "import_page not found on dashboard"
        # Real OS-level clicking finding: a toast notification overlay can sit on
        # top of the navigated-to screen for a couple of seconds after nav and
        # will intercept a real click at that screen point (QTest's click()
        # never hit this, since it targets the widget object directly,
        # bypassing Z-order / overlay hit-testing entirely). Let it fade first.
        harness.settle(2.5)

        def click_card_checked(accessible_name, max_attempts=3):
            """isChecked() can lag a real OS click by a frame or two (or, rarely,
            miss entirely per the harness's own fragility note). Poll briefly and
            re-click on a genuine miss rather than asserting once."""
            for attempt in range(1, max_attempts + 1):
                os_click(harness, import_screen, accessible_name, wait=0.8)
                card = find_by_accessible_name(import_screen, accessible_name)
                if wait_until(harness, lambda: card.isChecked(), timeout=2.0, interval=0.2):
                    return card
                print(f"click_card_checked({accessible_name!r}) attempt {attempt}/{max_attempts} not checked, retrying")
            raise RuntimeError(f"card never became checked after OS click: {accessible_name!r}")

        click_card_checked("Select person: Pranav")

        # The account card label uses bank_display_name, which is the Bank's
        # nickname (e.g. "Jana"), not the full bank_name ("Jana Small Finance
        # Bank") -- confirmed by dumping accessible names live.
        account_label = f"{bank} — Savings"
        click_card_checked(f"Select account: {account_label}")

        os_click(harness, import_screen, "Select PDF format", wait=0.6)
        assert import_screen.btn_format_pdf.isChecked()

        pid = app.applicationPid() if hasattr(app, "applicationPid") else None
        import os as _os
        pid = _os.getpid()
        typer_proc = subprocess.Popen(
            [sys.executable, str(FILE_TYPER), "--pid", str(pid), "--path", str(pdf_path), "--timeout", "30"],
        )
        os_click(harness, import_screen, "File drop zone", wait=1.0)
        rc = typer_proc.wait(timeout=35)
        assert rc == 0, f"os_file_dialog_typer exit code {rc}"
        wait_until(harness, lambda: import_screen.selected_file is not None, timeout=10)
        # QFileDialog normalises to forward slashes on Windows; compare by resolved Path,
        # not raw string, to avoid a false mismatch on separator style alone.
        assert import_screen.selected_file is not None and Path(import_screen.selected_file).resolve() == pdf_path.resolve(), (
            f"selected_file={import_screen.selected_file!r} expected {str(pdf_path)!r}"
        )
        log.log(f"file selected: {pdf_path.name}")

        if bank == "Equitas":
            # PasswordDialog.exec() is a genuine blocking modal (unlike the
            # non-modal "Manage Data" dialogs elsewhere). With real OS-level
            # input, a QTimer.singleShot(0) prearm callback in *this* process
            # races the real-world latency of the OS click actually being
            # delivered and can end up running its own dialog-search loop
            # before the dialog exists, deadlocking against the very
            # processEvents() call that would go on to enter exec(). A
            # separate process -- independent of this process's GIL/event
            # loop, using Windows UI Automation to find the dialog's controls
            # by their accessible name -- sidesteps this entirely, the same
            # way the native file-open dialog is already handled.
            import os as _os2
            pw = read_secret("equitas")
            pw_typer = Path(__file__).resolve().parent / "password_dialog_typer.py"
            pwproc = subprocess.Popen(
                [sys.executable, str(pw_typer), "--pid", str(_os2.getpid()),
                 "--title", "Enter Statement Password", "--password", pw,
                 "--save-toggle", "--timeout", "30"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            os_click(harness, import_screen, "Next button", wait=2.0)
            out, _ = pwproc.communicate(timeout=40)
            log.log(f"password_dialog_typer exit={pwproc.returncode} output={out.strip()!r}")
            assert pwproc.returncode == 0, f"password_dialog_typer failed rc={pwproc.returncode}"
        else:
            os_click(harness, import_screen, "Next button", wait=2.0)

        log.log("parsing started; waiting up to 180s for preview table")
        ok = wait_until(harness, lambda: import_screen.preview_table.rowCount() > 0, timeout=180, interval=0.5)
        if not ok:
            debug = import_screen.debug_output.toPlainText() if hasattr(import_screen, "debug_output") else ""
            log.log(f"STOP: preview table never populated. debug_output={debug[:500]}")
            sys.exit(1)

        n_preview = import_screen.preview_table.rowCount()
        log.log(f"preview rowCount={n_preview} expected={spec['count']}")
        assert n_preview == spec["count"], f"preview count {n_preview} != expected {spec['count']}"

        for idx in [0, n_preview // 2, n_preview - 1]:
            row_vals = [
                import_screen.preview_table.item(idx, c).text() if import_screen.preview_table.item(idx, c) else ""
                for c in range(import_screen.preview_table.columnCount())
            ]
            log.log(f"preview row {idx}: {row_vals}")

        os_click(harness, import_screen, "Select all new transactions", wait=1.0)
        os_click(harness, import_screen, "Next button", wait=2.0)

        log.log("importing; waiting up to 180s for return to person selection")
        ok2 = wait_until(
            harness,
            lambda: import_screen.person_cards_container.isVisible(),
            timeout=180, interval=0.5,
        )
        if not ok2:
            log.log("STOP: import did not return to person selection within 180s")
            sys.exit(1)
        harness.settle(1.5)
        log.log("import complete")

    # --- Verify ---
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    row = conn.execute(
        "SELECT COUNT(*), MIN(transaction_date), MAX(transaction_date), "
        "SUM(CASE WHEN transaction_type='Income' THEN amount ELSE 0 END), "
        "SUM(CASE WHEN transaction_type='Expense' THEN amount ELSE 0 END) "
        "FROM Transactions WHERE account_id=?",
        (account_id,),
    ).fetchone()
    log.log(f"Transactions summary: count={row[0]} min_date={row[1]} max_date={row[2]} "
            f"income_sum={row[3]} expense_sum={row[4]}")
    assert row[0] == spec["count"], f"count {row[0]} != {spec['count']}"
    assert row[1] == spec["min_date"], f"min_date {row[1]} != {spec['min_date']}"
    assert row[2] == spec["max_date"], f"max_date {row[2]} != {spec['max_date']}"
    assert abs((row[3] or 0) - spec["income_sum"]) < 0.01, f"income_sum {row[3]} != {spec['income_sum']}"
    assert abs((row[4] or 0) - spec["expense_sum"]) < 0.01, f"expense_sum {row[4]} != {spec['expense_sum']}"

    n_not_stmt = conn.execute(
        "SELECT COUNT(*) FROM Transactions WHERE account_id=? AND source != 'Statement Import'", (account_id,)
    ).fetchone()[0]
    log.log(f"non-'Statement Import' source rows = {n_not_stmt} (expect 0)")
    assert n_not_stmt == 0

    fd_rows = conn.execute(
        "SELECT fd_id, status, principal_amount, start_date, source_transaction_id FROM FixedDeposit WHERE account_id=?",
        (account_id,),
    ).fetchall()
    log.log(f"FixedDeposit rows for account: {fd_rows}")

    n_internal = conn.execute(
        "SELECT COUNT(*) FROM Transactions WHERE account_id=? AND is_internal_transfer=1", (account_id,)
    ).fetchone()[0]
    log.log(f"is_internal_transfer=1 rows for account = {n_internal}")

    if bank == "Equitas":
        pw_enc_row = conn.execute(
            "SELECT statement_password_enc FROM BankAccount WHERE account_id=?", (account_id,)
        ).fetchone()
        has_enc = pw_enc_row[0] is not None
        log.log(f"Equitas statement_password_enc is set = {has_enc}")
        assert has_enc

    conn.close()

    snap = snapshot_db(f"P2_4_{bank.replace(' ', '_')}")
    log.log(f"snapshot: {snap}")
    append_progress(f"P2.4 statement import complete for {bank}. {row[0]} transactions. snapshot={snap}")
    log.log("P2.4 (bank) DONE")


if __name__ == "__main__":
    main()
