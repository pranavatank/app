"""Shared layout rules for scrollable editors and their fixed action rows."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFormLayout, QHBoxLayout, QScrollArea


def configure_editor_form(form: QFormLayout) -> None:
    form.setSpacing(12)
    form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)


def editor_footer() -> QHBoxLayout:
    footer = QHBoxLayout()
    footer.setSpacing(8)
    footer.addStretch()
    return footer


def focus_editor_field(field) -> None:
    parent = field.parentWidget()
    while parent is not None:
        if isinstance(parent, QScrollArea):
            parent.ensureWidgetVisible(field)
            break
        parent = parent.parentWidget()
    field.setFocus(Qt.FocusReason.OtherFocusReason)
