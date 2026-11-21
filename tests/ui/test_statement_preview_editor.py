"""Validate the compact transaction editor used by statement previews."""

from PySide6.QtWidgets import QDialog, QPushButton

from ui.dialogs.transaction_edit_dialog import TransactionEditDialog


def test_preview_editor_preserves_precision_and_focuses_the_first_error(qapp):
    original = {"amount": 123.45000000001, "balance_after": 0.0}
    dialog = TransactionEditDialog(transaction_data=original, is_preview=True)
    dialog.show()
    qapp.processEvents()
    try:
        assert dialog.amount_edit.text() == "123.45"
        assert dialog.balance_edit.text() == "0.00"
        assert dialog.get_data()["amount"] == original["amount"]

        dialog.amount_edit.setText("nan")
        dialog.balance_edit.setText("invalid")
        save = next(btn for btn in dialog.findChildren(QPushButton) if btn.text() == "Save")
        save.click()
        qapp.processEvents()
        assert dialog.amount_error.isVisible() and dialog.balance_error.isVisible()
        assert dialog.amount_edit.hasFocus()
        assert dialog.result() != QDialog.DialogCode.Accepted

        dialog.amount_edit.setText("10.25")
        dialog.balance_edit.clear()
        save.click()
        assert dialog.result() == QDialog.DialogCode.Accepted
        assert dialog.get_data()["balance_after"] is None
        assert dialog.get_data()["amount"] == 10.25
    finally:
        dialog.close()
