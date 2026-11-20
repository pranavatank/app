"""Actual income stays distinct from expectation matching and projections."""

from ui.income_management_screen import IncomeManagementScreen


def test_actual_income_includes_linked_and_unmatched_ledger_entries(qapp, monkeypatch):
    rows = [
        {"amount": 1000, "category": "Professional Fees"},
        {"amount": 500, "category": "Interest"},
        {"amount": 9000, "category": "Other Income", "is_internal_transfer": 1},
    ]
    monkeypatch.setattr(
        "ui.income_management_screen.get_transactions",
        lambda **kwargs: rows,
    )
    screen = IncomeManagementScreen()

    screen._populate_actual_income(1, "2025-26")

    assert "2" in screen.actual_income_summary.text()
    assert "1,500" in screen.actual_income_summary.text()
    assert "FY 2025-26" in screen.actual_income_summary.text()
    assert "ledger" in screen.actual_income_note.text().lower()


def test_private_actual_income_clears_exact_chart_data(qapp, monkeypatch):
    from core.session import session

    monkeypatch.setattr(session, "privacy_mode", False)
    monkeypatch.setattr(
        "ui.income_management_screen.get_transactions",
        lambda **kwargs: [{"amount": 950, "category": "Interest"}],
    )
    screen = IncomeManagementScreen()
    screen._populate_actual_income(1, "2025-26")
    assert screen.chart_actual_income._data_rows == (("Interest", 950.0),)

    session.set_privacy_mode(True)
    screen._populate_actual_income(1, "2025-26")

    assert "****" in screen.actual_income_summary.text()
    assert "950" not in screen.actual_income_summary.text()
    assert screen.chart_actual_income._data_rows == ()


def test_actual_income_zero_records_is_explicit(qapp, monkeypatch):
    monkeypatch.setattr(
        "ui.income_management_screen.get_transactions",
        lambda **kwargs: [],
    )
    screen = IncomeManagementScreen()

    screen._populate_actual_income(None, "2025-26")

    assert "No income transactions recorded" in screen.actual_income_summary.text()


def test_expected_income_zero_does_not_erase_actual_summary(qapp, monkeypatch):
    monkeypatch.setattr(
        "ui.income_management_screen.get_transactions",
        lambda **kwargs: [{"amount": 250, "category": "Other"}],
    )
    screen = IncomeManagementScreen()
    screen._populate_table_expectations([])
    screen._populate_actual_income(1, "2025-26")

    assert not screen.empty_state_expectations.isHidden()
    assert "250" in screen.actual_income_summary.text()


def test_actual_summary_refreshes_for_person_and_fy_context(qapp, monkeypatch):
    def transactions(*, person_id, financial_year, transaction_type):
        amount = 100 if person_id == 1 else 700
        return [{"amount": amount, "category": "Fees"}]

    monkeypatch.setattr("ui.income_management_screen.get_transactions", transactions)
    screen = IncomeManagementScreen()
    screen._populate_actual_income(1, "2024-25")
    first = screen.actual_income_summary.text()
    screen._populate_actual_income(2, "2025-26")
    second = screen.actual_income_summary.text()

    assert "100" in first and "FY 2024-25" in first
    assert "700" in second and "FY 2025-26" in second


def test_expected_chart_uses_only_linked_actual_amounts(qapp, monkeypatch):
    screen = IncomeManagementScreen()
    captured = {}
    monkeypatch.setattr(
        screen.chart_vs_actual,
        "plot_comparison",
        lambda **kwargs: captured.update(kwargs),
    )
    screen._populate_chart_1(
        [
            {"expected_date": "2025-04-10", "expected_amount": 500,
             "actual_transaction_id": 10, "actual_amount": 450},
            {"expected_date": "2025-04-20", "expected_amount": 300,
             "actual_transaction_id": None, "actual_amount": 0},
        ],
        "2025-26",
    )

    assert captured["values2"][0] == 450
    assert sum(captured["values2"]) == 450
