"""Income transaction picker respects FY boundaries and linked-row exclusions."""

from ui.dialogs import income_expectation_dialog as income_dialog_module
from ui.dialogs.income_expectation_dialog import LinkActualDialog


def test_link_picker_keeps_fy_boundary_dates_and_excludes_outside_or_linked(qapp, monkeypatch):
    seen = {}

    def fake_get_transactions(**kwargs):
        seen["transactions"] = kwargs
        return [
            {"transaction_id": 10, "transaction_date": "2025-04-01", "category": "Salary", "amount": 100},
            {"transaction_id": 11, "transaction_date": "2026-03-31", "category": "Salary", "amount": 101},
            {"transaction_id": 12, "transaction_date": "2025-03-31", "category": "Salary", "amount": 102},
            {"transaction_id": 13, "transaction_date": "2025-06-15", "category": "Salary", "amount": 103},
            {"transaction_id": 14, "transaction_date": "2026-04-01", "category": "Salary", "amount": 104},
            {"transaction_id": 15, "transaction_date": "not-a-date", "category": "Salary", "amount": 105},
            {"transaction_id": 16, "transaction_date": None, "category": "Salary", "amount": 106},
        ]

    def fake_get_expectations(**kwargs):
        seen["expectations"] = kwargs
        return [{"actual_transaction_id": 13}]

    monkeypatch.setattr(income_dialog_module, "get_transactions", fake_get_transactions)
    monkeypatch.setattr(income_dialog_module, "get_income_expectations", fake_get_expectations)

    dialog = LinkActualDialog(
        expectation={"financial_year": "2025-26"}, person_id=7, account_id=9
    )
    ids = [int(dialog.table.item(row, 4).text()) for row in range(dialog.table.rowCount())]

    assert ids == [10, 11]
    assert seen["transactions"] == {
        "person_id": 7,
        "account_id": 9,
        "transaction_type": "Income",
    }
    assert seen["expectations"] == {"person_id": 7, "financial_year": "2025-26"}
    dialog.close()
