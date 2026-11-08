"""Keep Income Expectation dialog actions visible on short displays."""

import pytest
from PySide6.QtCore import QPoint, QRect
from PySide6.QtWidgets import QPushButton

from ui.dialogs.income_expectation_dialog import IncomeExpectationDialog


@pytest.mark.parametrize("available_height", [720, 540])
def test_edit_income_dialog_scrolls_content_and_keeps_footer_visible(qapp, available_height):
    dialog = IncomeExpectationDialog(
        persons=[{"person_id": 1, "full_name": "Test Person"}],
        existing={
            "expectation_id": 71,
            "person_id": 1,
            "account_id": 1,
            "income_type": "Salary",
            "expected_amount": 50000,
            "expected_date": "2025-06-15",
            "frequency": "One-Time",
            "financial_year": "2025-26",
            "actual_transaction_id": None,
            "notes": "Geometry fixture",
        },
    )
    dialog._fit_content_to_available_screen(available_height)
    dialog.show()
    qapp.processEvents()

    assert dialog.height() + 48 <= available_height
    assert dialog.form_scroll_area.isVisible()
    assert dialog.button_layout is not None
    buttons = [w for w in dialog.findChildren(QPushButton)
               if w.accessibleName() in {"Cancel income expectation dialog", "Save income expectation"}]
    assert len(buttons) == 2
    for button in buttons:
        rect = QRect(button.mapTo(dialog, QPoint(0, 0)), button.size())
        assert dialog.rect().contains(rect)

    scrollbar = dialog.form_scroll_area.verticalScrollBar()
    if available_height <= 540:
        assert scrollbar.maximum() > 0
    if scrollbar.maximum() > 0:
        scrollbar.setValue(scrollbar.maximum())
    qapp.processEvents()
    for widget in (dialog.notes_edit, dialog.link_panel):
        rect = QRect(widget.mapTo(dialog.form_scroll_area.viewport(), QPoint(0, 0)), widget.size())
        assert dialog.form_scroll_area.viewport().rect().contains(rect)

    dialog.close()
