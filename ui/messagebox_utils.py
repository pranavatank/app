from __future__ import annotations

from typing import Callable

from PyQt6.QtWidgets import QApplication, QMessageBox


_ORIGINAL_CRITICAL: Callable | None = None
_ORIGINAL_WARNING: Callable | None = None


def _with_copy_button(
    parent,
    icon: QMessageBox.Icon,
    title: str,
    text: str,
    buttons: QMessageBox.StandardButton,
    default_button: QMessageBox.StandardButton,
) -> QMessageBox.StandardButton:
    box = QMessageBox(parent)
    box.setIcon(icon)
    box.setWindowTitle(title or "Error")
    box.setText(text or "An error occurred.")

    if buttons == QMessageBox.StandardButton.NoButton:
        buttons = QMessageBox.StandardButton.Ok

    box.setStandardButtons(buttons)
    copy_btn = box.addButton("Copy Error", QMessageBox.ButtonRole.ActionRole)
    if default_button != QMessageBox.StandardButton.NoButton:
        box.setDefaultButton(default_button)

    box.exec()

    if box.clickedButton() is copy_btn:
        QApplication.clipboard().setText(f"{title}\n{text}".strip())
        return QMessageBox.StandardButton.Ok

    clicked = box.standardButton(box.clickedButton())
    if clicked == QMessageBox.StandardButton.NoButton:
        return QMessageBox.StandardButton.Ok
    return clicked


def _patched_critical(
    parent,
    title,
    text,
    buttons=QMessageBox.StandardButton.Ok,
    defaultButton=QMessageBox.StandardButton.NoButton,
):
    # Keep default behavior for complex dialogs using multiple decision buttons.
    if buttons not in (QMessageBox.StandardButton.Ok, QMessageBox.StandardButton.NoButton):
        return _ORIGINAL_CRITICAL(parent, title, text, buttons, defaultButton)

    return _with_copy_button(
        parent=parent,
        icon=QMessageBox.Icon.Critical,
        title=title,
        text=text,
        buttons=buttons,
        default_button=defaultButton,
    )


def _patched_warning(
    parent,
    title,
    text,
    buttons=QMessageBox.StandardButton.Ok,
    defaultButton=QMessageBox.StandardButton.NoButton,
):
    if buttons not in (QMessageBox.StandardButton.Ok, QMessageBox.StandardButton.NoButton):
        return _ORIGINAL_WARNING(parent, title, text, buttons, defaultButton)

    lower_title = (title or "").lower()
    lower_text = (text or "").lower()
    error_like = any(k in lower_title for k in ("error", "failed", "exception")) or any(
        k in lower_text for k in ("error", "failed", "exception")
    )

    if not error_like:
        return _ORIGINAL_WARNING(parent, title, text, buttons, defaultButton)

    return _with_copy_button(
        parent=parent,
        icon=QMessageBox.Icon.Warning,
        title=title,
        text=text,
        buttons=buttons,
        default_button=defaultButton,
    )


def install_copyable_error_dialogs() -> None:
    global _ORIGINAL_CRITICAL, _ORIGINAL_WARNING
    if _ORIGINAL_CRITICAL is not None:
        return

    _ORIGINAL_CRITICAL = QMessageBox.critical
    _ORIGINAL_WARNING = QMessageBox.warning

    QMessageBox.critical = _patched_critical
    QMessageBox.warning = _patched_warning
