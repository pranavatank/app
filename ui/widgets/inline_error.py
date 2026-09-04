"""
ui/widgets/inline_error.py — Helper for inline field-level error messages.

Displays and clears error messages next to a form field.
"""

from PyQt6.QtWidgets import QLabel, QWidget, QHBoxLayout, QVBoxLayout
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt

from ui.theme.theme import Theme


def setup_field_error_label(field: QWidget) -> QLabel:
    """
    Create and setup an error label to appear below a form field.

    The label is hidden by default and styled to show validation errors.

    Args:
        field: The input field (QLineEdit, QSpinBox, QComboBox, etc.)

    Returns:
        The error label, positioned and ready to use.
    """
    error_label = QLabel()
    error_label.setObjectName("fieldErrorLabel")
    error_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Normal))
    error_label.setStyleSheet(
        f"color: {Theme.DANGER}; font-size: 10px; margin-top: 2px;"
    )
    error_label.setWordWrap(True)
    error_label.hide()
    return error_label


def show_field_error(error_label: QLabel, message: str):
    """
    Show an error message in the label.

    Args:
        error_label: The label created by setup_field_error_label()
        message: The error message to display
    """
    error_label.setText(message)
    error_label.show()


def clear_field_error(error_label: QLabel):
    """
    Clear and hide the error label.

    Args:
        error_label: The label to clear
    """
    error_label.setText("")
    error_label.hide()


def setup_field_with_error(parent: QWidget, field: QWidget, label_text: str = None) -> tuple[QVBoxLayout, QLabel]:
    """
    Create a vertical layout with a field and its error label.

    This is a convenience for simple field + error label layouts.

    Args:
        parent: The parent widget to attach the layout to
        field: The input field
        label_text: Optional label text to display above the field

    Returns:
        (layout, error_label) tuple for use in building forms
    """
    layout = QVBoxLayout()
    layout.setSpacing(4)
    layout.setContentsMargins(0, 0, 0, 0)

    if label_text:
        field_label = QLabel(label_text)
        field_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Normal))
        layout.addWidget(field_label)

    layout.addWidget(field)

    error_label = setup_field_error_label(field)
    layout.addWidget(error_label)

    return layout, error_label
