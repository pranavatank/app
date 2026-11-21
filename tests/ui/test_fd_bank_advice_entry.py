"""Ensure bank advice can be recorded without guessed compounding."""

import pytest

from PySide6.QtWidgets import QDialog

from core.database import get_connection
from models.bank_account import add_account
from models.person import add_person
from ui.dialogs.fd_dialog import FDDialog


@pytest.mark.parametrize("reported_amount,stored_amount", [("1071.25", 1071.25), ("", None)])
def test_bank_advice_keeps_reported_values_and_unknown_compounding(qapp, reported_amount, stored_amount):
    person_id = add_person("Synthetic deposit holder")
    account_id = add_account(person_id, "Synthetic advice bank", "Savings")
    dialog = FDDialog(None)
    dialog.person_combo.setCurrentIndex(dialog.person_combo.findData(person_id))
    dialog.account_combo.setCurrentIndex(dialog.account_combo.findData(account_id))
    dialog.principal_input.setText("1000")
    dialog.rate_input.setText("7.5")
    dialog.tenure_months_input.setText("12")
    dialog.amount_method_combo.setCurrentIndex(dialog.amount_method_combo.findData("BankReported"))
    dialog.compounding_combo.setCurrentText("Unknown")
    dialog.reported_start_input.setText("2025-07-02")
    dialog.reported_date_input.setText("2026-07-03")
    dialog.reported_amount_input.setText(reported_amount)
    dialog._on_save()

    assert dialog.result() == QDialog.DialogCode.Accepted
    db = get_connection()
    try:
        row = db.execute(
            "SELECT * FROM FixedDeposit WHERE account_id = ?", (account_id,),
        ).fetchone()
        assert row["maturity_date"] == "2026-07-03"
        assert row["maturity_amount"] == stored_amount
        assert row["maturity_calc_method"] == "BankReported"
        assert row["maturity_amount_formula"] is None
        assert row["compounding_type"] is None
        assert row["status"] == "Pending Details"
        assert db.execute("SELECT COUNT(*) FROM FDInterestRecord WHERE fd_id = ?", (row["fd_id"],)).fetchone()[0] == 0
    finally:
        db.close()
