"""P3.14 S gate: change the scratch master password and verify secret access."""
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tests.native.rebuild_p3_common import P3Run, main_wrapper
from tests.native.rebuild_common import (
    _SECRET_PATTERNS, login_to_dashboard, os_click, os_type_widget,
    answer_message_box, wait_until, snapshot_db, native_file_dialog,
)
from PySide6.QtWidgets import QApplication, QMessageBox


def run_r(p):
    # This release gate is intentionally S-only; the wrapper rejects R runs.
    raise RuntimeError("P3.14 password-change gate must run with --env S")


def run_s(p):
    from core.auth import verify_login
    from core.database import get_connection
    from core.encryption import decrypt_field, encrypt_field
    from core import session

    old_password = None
    new_password = None
    try:
        from tests.native.rebuild_common import read_secret
        old_password = read_secret("master")
        if not old_password:
            raise RuntimeError("scratch master password was not available")

        conn = get_connection()
        person_id = conn.execute(
            "INSERT INTO Person (full_name, ais_tis_password_enc) VALUES (?, NULL)",
            ("RUIH_P3_14_password_fixture",),
        ).lastrowid
        conn.commit()
        conn.close()
        dashboard = p.dashboard
        bank_secret = "RUIH-bank-" + secrets.token_urlsafe(20)
        tax_secret = "RUIH-tax-" + secrets.token_urlsafe(20)
        _SECRET_PATTERNS.extend([bank_secret, tax_secret])
        original_key = session.session.aes_key
        conn = get_connection()
        account_id = conn.execute(
            "INSERT INTO BankAccount (person_id, bank_name, account_type, statement_password_enc) VALUES (?, ?, ?, ?)",
            (person_id, "RUIH_P3_14_fixture", "Savings", encrypt_field(bank_secret, original_key)),
        ).lastrowid
        conn.execute(
            "UPDATE Person SET ais_tis_password_enc=? WHERE person_id=?",
            (encrypt_field(tax_secret, original_key), person_id),
        )
        conn.commit()
        conn.close()
        before_change_backup = snapshot_db("p3_14_before_password_change")
        p.observe("P3.14_pre_change_snapshot", before_change_backup)

        settings_page = p.nav("Settings")
        new_password = "RUIH-" + secrets.token_urlsafe(24)
        _SECRET_PATTERNS.append(new_password)
        os_type_widget(p.harness, settings_page.current_pwd, old_password, retries=1, secret=True)
        os_type_widget(p.harness, settings_page.new_pwd, new_password, retries=1, secret=True)
        os_type_widget(p.harness, settings_page.confirm_pwd, new_password, retries=1, secret=True)
        os_click(p.harness, settings_page, "Change password", wait=1.0)
        p.harness.settle(1.0)
        new_key = session.session.aes_key
        p.checks.check("password change accepted", bool(new_key) and new_key != original_key)

        logout_confirm = answer_message_box(
            p.harness, p.app, QMessageBox.StandardButton.Yes, expect_title="Logout"
        )
        os_click(p.harness, dashboard, "Logout", wait=0.5)
        p.harness.settle(1.0)
        p.checks.check("password change logout confirmed", logout_confirm.done and logout_confirm.error is None)
        from ui.login_screen import LoginScreen
        wait_until(p.harness, lambda: any(
            isinstance(w, LoginScreen) and w.isVisible() for w in QApplication.instance().allWidgets()
        ), timeout=15)
        login_screen = next((w for w in QApplication.instance().allWidgets()
                             if isinstance(w, LoginScreen) and w.isVisible()), None)
        dashboard = login_to_dashboard(
            p.harness, master_pw=new_password, login_screen=login_screen
        )
        p.dashboard = dashboard
        p.harness.window = dashboard
        ok, _, verified_key = verify_login(new_password)
        old_ok, _, _ = verify_login(old_password)
        p.checks.check("new password login succeeds and old password fails", ok and not old_ok)

        conn = get_connection()
        bank_enc = conn.execute("SELECT statement_password_enc FROM BankAccount WHERE account_id=?", (account_id,)).fetchone()[0]
        tax_enc = conn.execute("SELECT ais_tis_password_enc FROM Person WHERE person_id=?", (person_id,)).fetchone()[0]
        conn.close()
        try:
            bank_ok = decrypt_field(bank_enc, verified_key) == bank_secret
            tax_ok = decrypt_field(tax_enc, verified_key) == tax_secret
        except Exception:
            bank_ok = tax_ok = False
        p.checks.check("bank and tax secrets decrypt after relogin", bank_ok and tax_ok)

        # Restore the pre-change scratch snapshot through the same UI handoff
        # users see, then prove the backup's old credential and key are active.
        p.expected_titles.add("Confirm Restore")
        p.expected_titles.add("Select Backup File")
        settings_page = p.nav("Settings")
        restore_confirm = answer_message_box(
            p.harness, p.app, QMessageBox.StandardButton.Yes, expect_title="Confirm Restore"
        )
        native_file_dialog(
            lambda: os_click(p.harness, settings_page, "Restore database from backup", wait=0.5),
            before_change_backup,
            timeout=30,
        )
        p.harness.settle(1.0)
        p.checks.check("pre-change snapshot restore confirmed",
                       restore_confirm.done and restore_confirm.error is None)
        login_screen = next((w for w in QApplication.instance().allWidgets()
                             if type(w).__name__ == "LoginScreen" and w.isVisible()), None)
        from core import session as app_session
        p.checks.check("restore clears changed session", not app_session.session.is_authenticated
                       and app_session.session.aes_key is None)
        old_ok, _, old_key = verify_login(old_password)
        new_ok, _, _ = verify_login(new_password)
        p.checks.check("restored snapshot requires old master password", old_ok and not new_ok)
        if login_screen is None:
            raise RuntimeError("login screen did not appear after snapshot restore")
        dashboard = login_to_dashboard(
            p.harness, master_pw=old_password, login_screen=login_screen
        )
        p.dashboard = dashboard
        p.harness.window = dashboard
        conn = get_connection()
        restored_bank = conn.execute(
            "SELECT statement_password_enc FROM BankAccount WHERE account_id=?", (account_id,)
        ).fetchone()[0]
        restored_tax = conn.execute(
            "SELECT ais_tis_password_enc FROM Person WHERE person_id=?", (person_id,)
        ).fetchone()[0]
        conn.close()
        try:
            restored_secrets_ok = (
                decrypt_field(restored_bank, old_key) == bank_secret
                and decrypt_field(restored_tax, old_key) == tax_secret
            )
        except Exception:
            restored_secrets_ok = False
        p.checks.check("restored snapshot secrets decrypt with old key", restored_secrets_ok)
        try:
            decrypt_field(restored_bank, verified_key)
            new_key_fails = False
        except Exception:
            new_key_fails = True
        p.checks.check("changed master key fails on restored secret", new_key_fails)
    except Exception as exc:
        p.checks.check("password change release gate completed", False, type(exc).__name__)
    finally:
        # The scratch credential changes as part of the UI roundtrip.
        if new_password:
            p.observe("P3.14_scratch_master_restored", "scratch master restored to its pre-change credential through the UI")


if __name__ == "__main__":
    main_wrapper("14", "PasswordChange", run_r, run_s)
