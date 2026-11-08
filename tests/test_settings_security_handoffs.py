"""Security settings must hand off enrollment and restored authentication safely."""

import secrets
import hmac

from PySide6.QtWidgets import QApplication, QMainWindow, QWidget

import core.session as app_session
import core.database as database
import ui.settings_screen as settings_module
from ui.settings_screen import SettingsScreen, TOTPEnrollmentDialog, RestoreRecoveryDialog


class ImmediateLoader:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def _settings_window(qapp):
    dashboard = QMainWindow()
    settings = SettingsScreen(dashboard)
    dashboard.setCentralWidget(settings)
    dashboard.show()
    qapp.processEvents()
    return dashboard, settings


def test_totp_enable_opens_persistent_copyable_enrollment_dialog(qapp, monkeypatch):
    dashboard, settings = _settings_window(qapp)
    uri = f"otpauth://totp/FinanceApp?secret={secrets.token_urlsafe(24)}"
    opened = {}
    monkeypatch.setattr(settings_module, "enable_totp", lambda: uri)

    def hold_dialog(dialog):
        opened["dialog"] = dialog
        return 0

    monkeypatch.setattr(TOTPEnrollmentDialog, "exec", hold_dialog)
    settings._on_totp_toggle(2)

    dialog = opened["dialog"]
    assert dialog.isModal()
    assert dialog.uri_input.isReadOnly()
    assert hmac.compare_digest(dialog.uri_input.text(), uri)

    dialog.show()
    qapp.processEvents()
    dialog.copy_button.click()
    assert hmac.compare_digest(QApplication.clipboard().text(), uri)
    assert dialog.isVisible()
    dialog.close()
    dashboard.close()


def test_restore_success_clears_session_and_shows_login(qapp, monkeypatch):
    import ui.widgets.loader as loader_module

    dashboard, settings = _settings_window(qapp)
    monkeypatch.setattr(loader_module, "Loader", ImmediateLoader)
    restored = []
    monkeypatch.setattr(database, "restore_database", lambda path: restored.append(path))
    app_session.session.login(b"old-session-key")

    assert settings._restore_from_path("temporary-backup.sqlite") is True

    assert restored == ["temporary-backup.sqlite"]
    assert not app_session.session.is_authenticated
    assert app_session.session.aes_key is None
    assert not dashboard.isVisible()
    login = qapp._restore_login_screen
    assert login.isVisible()

    login.close()
    del qapp._restore_login_screen
    qapp.processEvents()
    app_session.session.logout()


def test_failed_restore_preserves_current_session_and_dashboard(qapp, monkeypatch):
    import ui.widgets.loader as loader_module

    dashboard, settings = _settings_window(qapp)
    monkeypatch.setattr(loader_module, "Loader", ImmediateLoader)
    monkeypatch.setattr(database, "restore_database", lambda _: (_ for _ in ()).throw(ValueError("invalid backup")))
    monkeypatch.setattr(settings_module.QMessageBox, "critical", lambda *args: None)
    app_session.session.login(b"still-valid-key")

    assert settings._restore_from_path("invalid-backup.sqlite") is False

    assert app_session.session.is_authenticated
    assert app_session.session.aes_key == b"still-valid-key"
    assert dashboard.isVisible()
    assert not hasattr(qapp, "_restore_login_screen")
    dashboard.close()
    qapp.processEvents()
    app_session.session.logout()


def test_unrecoverable_restore_locks_session_and_shows_recovery_snapshot(qapp, monkeypatch):
    import ui.widgets.loader as loader_module

    dashboard, settings = _settings_window(qapp)
    monkeypatch.setattr(loader_module, "Loader", ImmediateLoader)
    recovery_path = "B:/temporary/.restore_rollback_test.sqlite"
    monkeypatch.setattr(
        database, "restore_database",
        lambda _: (_ for _ in ()).throw(database.RestoreRecoveryError(recovery_path)),
    )
    app_session.session.login(b"uncertain-session-key")

    assert settings._restore_from_path("backup.sqlite") is False

    assert not app_session.session.is_authenticated
    assert app_session.session.aes_key is None
    assert not dashboard.isVisible()
    dialog = qapp._restore_recovery_dialog
    assert isinstance(dialog, RestoreRecoveryDialog)
    assert dialog.isVisible() and dialog.isModal()
    assert dialog.recovery_path == recovery_path
    assert dialog.path_input.text() == recovery_path
    assert not hasattr(qapp, "_restore_login_screen")

    dialog.close()
    del qapp._restore_recovery_dialog
    qapp.processEvents()
    app_session.session.logout()


def test_restore_is_rejected_while_page_has_active_work(qapp, monkeypatch):
    import ui.widgets.loader as loader_module

    dashboard, settings = _settings_window(qapp)
    busy_page = QWidget(dashboard)
    busy_page._busy = True
    called = []
    monkeypatch.setattr(loader_module, "Loader", ImmediateLoader)
    monkeypatch.setattr(database, "restore_database", lambda path: called.append(path))
    monkeypatch.setattr(settings_module.QMessageBox, "warning", lambda *args: None)
    app_session.session.login(b"busy-session-key")

    assert settings._restore_from_path("backup.sqlite") is False

    assert called == []
    assert app_session.session.aes_key == b"busy-session-key"
    assert dashboard.isVisible()
    dashboard.close()
    qapp.processEvents()
    app_session.session.logout()
