"""Check the Settings shortcut and compact Manage Data workflow."""

from pathlib import Path
import os

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QGroupBox, QPushButton
from shiboken6 import isValid

import ui.manage_data_screen as manage_data
import ui.settings_screen as settings_module
from ui.settings_screen import SettingsScreen
from ui.theme.theme_manager import ThemeManager


@pytest.mark.parametrize("theme", ThemeManager.theme_names())
def test_settings_shortcuts_open_readable_manage_data_tabs(qapp, monkeypatch, theme):
    monkeypatch.setattr(manage_data, "get_all_persons", lambda: [])
    monkeypatch.setattr(manage_data, "get_all_banks", lambda: [])
    monkeypatch.setattr(manage_data, "get_all_accounts", lambda: [{
        "account_id": 1, "person_name": "Example Person", "bank_name": "Example Small Finance Bank",
        "account_type": "Savings", "account_number_masked": "XXXX1234",
        "opening_balance": 1000, "current_balance": 2500,
    }])
    previous_theme = ThemeManager.current_name()
    ThemeManager.apply(theme, save=False, notify=False)
    settings = SettingsScreen()
    settings.resize(1200, 720)
    settings.show()
    buttons = {btn.text(): btn for btn in settings.findChildren(QPushButton)}
    routes = [
        ("Manage People", "People", "person"),
        ("Manage Banks", "Banks", "bank"),
        ("Manage Bank Accounts", "Accounts", "account"),
    ]
    dialog = None
    try:
        for caption, tab, entity in routes:
            buttons[caption].click()
            current = settings._manage_data_dialog
            assert isinstance(current, QDialog) and not current.isModal()
            assert dialog is None or current is dialog
            dialog = current
            dialog.resize(640, 410)
            qapp.processEvents()
            tabs = settings._manage_data_widget.tabs
            assert tabs.tabText(tabs.currentIndex()) == tab
            actions = {b.accessibleName(): b for b in tabs.currentWidget().findChildren(QPushButton)}
            for action in ("Add", "Edit", "Delete"):
                assert actions[f"{action} {entity}"].isVisible()

            if output := os.getenv("FINMGR_BATCH5_CAPTURES"):
                target = Path(output) / f"{theme.lower()}-manage-{tab.lower()}-compact.png"
                target.parent.mkdir(parents=True, exist_ok=True)
                assert dialog.grab().save(str(target))

        table = settings._manage_data_widget.accounts_table
        header = table.horizontalHeader()
        for column in (1, 4, 6, 7):
            caption = table.horizontalHeaderItem(column).text()
            assert header.sectionSize(column) >= header.fontMetrics().horizontalAdvance(caption)
        assert table.horizontalScrollBar().maximum() > 0

        dialog.close()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert settings._manage_data_dialog is None
        assert not isValid(dialog)
        buttons["Manage Banks"].click()
        assert settings._manage_data_widget.tabs.currentWidget() is settings._manage_data_widget.tabs.widget(1)
    finally:
        settings.close()
        settings.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        ThemeManager.apply(previous_theme, save=False, notify=False)


def test_appearance_cards_can_be_selected_with_the_keyboard(qapp, monkeypatch):
    monkeypatch.setattr(settings_module, "_device_info", lambda: {
        "device_id": "Example", "platform": "Windows", "hostname": "Example desktop",
    })
    previous_theme = ThemeManager.current_name()
    ThemeManager.apply("Aurora", save=False, notify=False)
    settings = SettingsScreen()
    settings.resize(1200, 720)
    settings.show()
    try:
        groups = {box.title() for box in settings.findChildren(QGroupBox)}
        assert {"People and banks", "Security and privacy", "Backup and diagnostics"} <= groups
        card = settings._theme_cards["Nova"]
        card.setFocus(Qt.FocusReason.TabFocusReason)
        qapp.processEvents()
        assert card.hasFocus() and card.accessibleName() == "Nova theme"
        QTest.keyClick(card, Qt.Key.Key_Space)
        assert ThemeManager.current_name() == "Nova"
        assert [name for name, card in settings._theme_cards.items() if card.isChecked()] == ["Nova"]
    finally:
        settings.close()
        settings.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        ThemeManager.apply(previous_theme, save=False, notify=False)
