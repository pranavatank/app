"""Route simple message boxes to non-blocking cards, preserving decisions."""
from PySide6.QtWidgets import QApplication, QMessageBox
from ui.widgets.toast_utils import show_info, show_warning, show_danger

_ORIGINALS = {}

def _is_simple(buttons):
    return buttons in (QMessageBox.StandardButton.Ok, QMessageBox.StandardButton.NoButton)

def _route(kind, parent, title, text, buttons=QMessageBox.StandardButton.Ok, defaultButton=QMessageBox.StandardButton.NoButton):
    if not _is_simple(buttons): return _ORIGINALS[kind](parent, title, text, buttons, defaultButton)
    msg = str(text or title or "")
    if kind == "critical": show_danger(msg, title=title, parent=parent)
    elif kind == "warning": show_warning(msg, title=title, parent=parent)
    else: show_info(msg, title=title, parent=parent)
    return QMessageBox.StandardButton.Ok

def _critical(parent, title, text, buttons=QMessageBox.StandardButton.Ok, defaultButton=QMessageBox.StandardButton.NoButton):
    return _route("critical", parent, title, text, buttons, defaultButton)
def _warning(parent, title, text, buttons=QMessageBox.StandardButton.Ok, defaultButton=QMessageBox.StandardButton.NoButton):
    return _route("warning", parent, title, text, buttons, defaultButton)
def _information(parent, title, text, buttons=QMessageBox.StandardButton.Ok, defaultButton=QMessageBox.StandardButton.NoButton):
    return _route("information", parent, title, text, buttons, defaultButton)

def install_copyable_error_dialogs():
    """Idempotently route simple notices and retain copyable critical failures."""
    if _ORIGINALS: return
    _ORIGINALS.update(critical=QMessageBox.critical, warning=QMessageBox.warning, information=QMessageBox.information)
    QMessageBox.critical = _critical
    QMessageBox.warning = _warning
    QMessageBox.information = _information
