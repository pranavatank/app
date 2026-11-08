"""Ensure transaction dialog actions remain reachable on short displays."""

import pytest
from PySide6.QtCore import QPoint, QRect
from PySide6.QtWidgets import QDialogButtonBox

from ui.dialogs.transaction_dialog import TransactionDialog


@pytest.mark.parametrize("available_height", [720, 540])
def test_transaction_dialog_scrolls_form_and_keeps_footer_visible(qapp, available_height):
    dialog = TransactionDialog(
        persons=[{"person_id": 1, "full_name": "Test Person"}],
        accounts=[{"account_id": 1, "person_id": 1, "bank_name": "Test Bank", "account_type": "Savings"}],
    )
    dialog._fit_form_to_available_screen(available_height)
    dialog.show()
    qapp.processEvents()

    assert dialog.height() + 48 <= available_height
    assert dialog.button_box.isVisible()
    ok_button = dialog.button_box.button(QDialogButtonBox.StandardButton.Ok)
    button_rect = QRect(ok_button.mapTo(dialog, QPoint(0, 0)), ok_button.size())
    assert dialog.rect().contains(button_rect)

    # ensureWidgetVisible(widget) only promises the widget's top-left point is
    # visible, which can leave the rest clipped. Move to the actual scroll end.
    scrollbar = dialog.form_scroll_area.verticalScrollBar()
    assert scrollbar.maximum() > 0
    scrollbar.setValue(scrollbar.maximum())
    qapp.processEvents()
    desc_rect = QRect(
        dialog.desc_edit.mapTo(dialog.form_scroll_area.viewport(), QPoint(0, 0)),
        dialog.desc_edit.size(),
    )
    assert dialog.form_scroll_area.viewport().rect().contains(desc_rect)

    dialog.close()
