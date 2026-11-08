import copy
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

import ui.dialogs.fd_planner_dialog as planner_module
from ui.dialogs.fd_planner_dialog import FDPlannerDialog, _EXCLUDED_BANKS_SETTING

ALPHA = "Alpha Small Finance Bank"
BETA = "Beta Bank"
GAMMA = "Gamma Bank"

SNAPSHOT = {
    "source_url": "https://example.com/rates",
    "as_of": "2026-10-07",
    "fetched_at": "2026-10-12T00:00:00",
    "is_bundled": False,
    "banks": [
        {"bank_name": ALPHA, "bank_type": "Small Finance Bank", "highest_rate": 8.0,
         "rate_1y": 8.0, "rate_3y": 7.5, "rate_5y": 7.0, "senior_extra": 0.5},
        {"bank_name": BETA, "bank_type": "Bank", "highest_rate": 7.5,
         "rate_1y": 7.5, "rate_3y": 7.2, "rate_5y": None, "senior_extra": 0.5},
        {"bank_name": GAMMA, "bank_type": "Bank", "highest_rate": 7.0,
         "rate_1y": 7.0, "rate_3y": 7.0, "rate_5y": 7.0, "senior_extra": 0.5},
    ],
}


@pytest.fixture(autouse=True)
def recorded(monkeypatch):
    calls = SimpleNamespace(settings=[], warnings=[], successes=[])
    monkeypatch.setattr(planner_module, "load_cached_rates", lambda: copy.deepcopy(SNAPSHOT))
    monkeypatch.setattr(planner_module, "get_setting", lambda key, default=None: default)
    monkeypatch.setattr(planner_module, "set_setting", lambda key, value: calls.settings.append((key, value)))
    monkeypatch.setattr(planner_module, "show_warning", lambda message, **_: calls.warnings.append(message))
    monkeypatch.setattr(planner_module, "show_success", lambda message, **_: calls.successes.append(message))
    monkeypatch.setattr(planner_module, "get_all_persons", lambda: [])
    return calls


@pytest.fixture
def make_dialog(qapp):
    return lambda: FDPlannerDialog(None, person_id=None)


@pytest.fixture
def dialog(make_dialog):
    return make_dialog()


def _bank_names(dialog) -> list[str]:
    return [dialog.results_table.item(row, 1).text() for row in range(dialog.results_table.rowCount())]


def _suggest(dialog, amount: str, tenure_key: str) -> None:
    dialog.amount_edit.setText(amount)
    dialog.tenure_combo.setCurrentIndex(dialog.tenure_combo.findData(tenure_key))
    dialog._on_suggest()


def test_rates_table_lists_banks_with_use_checked(dialog):
    assert dialog.rates_table.rowCount() == 3
    for row in range(3):
        assert dialog.rates_table.item(row, 0).checkState() == Qt.CheckState.Checked
    assert "example.com" in dialog.rates_info_lbl.text()


def test_suggest_split_fills_results_for_one_year(dialog):
    dialog.existing_check.setChecked(False)
    _suggest(dialog, "1200000", "rate_1y")

    assert dialog.results_table.rowCount() == 3
    assert _bank_names(dialog)[0] == ALPHA
    assert dialog.warning_banner.isHidden()


def test_empty_amount_warns_and_shows_no_results(dialog, recorded):
    dialog._on_suggest()

    assert recorded.warnings
    assert dialog.results_table.rowCount() == 0


def test_unchecking_small_finance_banks_excludes_them(dialog):
    dialog.existing_check.setChecked(False)
    dialog.sfb_check.setChecked(False)
    _suggest(dialog, "1200000", "rate_1y")

    assert ALPHA not in _bank_names(dialog)


def test_unchecking_bank_persists_exclusion_and_excludes_it_from_split(dialog, recorded):
    dialog.existing_check.setChecked(False)
    dialog.rates_table.item(0, 0).setCheckState(Qt.CheckState.Unchecked)

    assert recorded.settings == [(_EXCLUDED_BANKS_SETTING, [ALPHA])]

    _suggest(dialog, "1200000", "rate_1y")
    assert ALPHA not in _bank_names(dialog)


def test_amount_above_insured_room_shows_warning_banner(dialog):
    dialog.existing_check.setChecked(False)
    dialog.max_banks_spin.setValue(2)
    _suggest(dialog, "5000000", "rate_1y")

    assert not dialog.warning_banner.isHidden()


def test_bank_without_rate_for_tenure_is_not_suggested(dialog):
    dialog.existing_check.setChecked(False)
    _suggest(dialog, "1200000", "rate_5y")

    assert BETA not in _bank_names(dialog)


def test_household_mode_splits_across_family_members(make_dialog, monkeypatch):
    monkeypatch.setattr(planner_module, "get_all_persons", lambda: [
        {"person_id": 1, "full_name": "Asha"},
        {"person_id": 2, "full_name": "Ravi"},
    ])
    monkeypatch.setattr(planner_module, "get_existing_exposure", lambda person_id: {})
    monkeypatch.setattr(planner_module, "_is_senior_citizen_in_fy", lambda person_id, fy: False)
    dlg = make_dialog()

    assert dlg.person_combo.itemText(0) == "All family members"
    assert not dlg.senior_check.isEnabled()

    dlg.max_banks_spin.setValue(1)
    _suggest(dlg, "1500000", "rate_1y")

    assert dlg.results_table.rowCount() == 2
    assert {dlg.results_table.item(row, 0).text() for row in range(2)} == {"Asha", "Ravi"}
    assert all(dlg.results_table.item(row, 1).text() == ALPHA for row in range(2))
    assert not dlg.results_table.isColumnHidden(0)
    assert not dlg.warning_banner.isHidden()


def test_use_my_savings_fills_amount_above_keep_aside(make_dialog, monkeypatch, recorded):
    monkeypatch.setattr(planner_module, "get_all_persons", lambda: [{"person_id": 1, "full_name": "Asha"}])
    monkeypatch.setattr(planner_module, "get_savings_total", lambda person_ids: 600000.0)
    dlg = make_dialog()
    dlg._on_use_savings()

    assert dlg.amount_edit.text() == "500000"

    monkeypatch.setattr(planner_module, "get_savings_total", lambda person_ids: 50000.0)
    dlg.amount_edit.setText("123")
    dlg._on_use_savings()

    assert recorded.warnings
    assert dlg.amount_edit.text() == "123"


def test_rates_table_sorts_by_highest_rate_then_by_column(dialog):
    assert dialog.rates_table.item(0, 1).text() == ALPHA
    assert dialog.rates_table.item(dialog.rates_table.rowCount() - 1, 1).text() == GAMMA

    dialog.rates_table.sortItems(4, Qt.SortOrder.AscendingOrder)

    assert dialog.rates_table.item(0, 1).text() == GAMMA


def test_best_rate_per_tenure_is_highlighted(dialog):
    rows = {dialog.rates_table.item(row, 1).text(): row for row in range(dialog.rates_table.rowCount())}

    assert dialog.rates_table.item(rows[ALPHA], 4).font().bold()
    assert not dialog.rates_table.item(rows[GAMMA], 4).font().bold()


def test_overflow_suggests_government_backed_option(dialog):
    dialog.existing_check.setChecked(False)
    dialog.max_banks_spin.setValue(2)
    _suggest(dialog, "5000000", "rate_1y")

    assert "Post Office Time Deposit – 1 year" in dialog.warning_lbl.text()


def test_copy_plan_puts_visible_columns_and_total_on_clipboard(dialog):
    dialog.existing_check.setChecked(False)
    _suggest(dialog, "1200000", "rate_1y")
    dialog._on_copy_plan()

    copied = QApplication.clipboard().text()
    assert ALPHA in copied
    assert "Total:" in copied
    assert dialog.btn_copy.isEnabled()


def test_tabs_refresh_the_selected_tab(dialog):
    coverage_calls = []
    options_calls = []
    dialog.coverage_tab.refresh = lambda persons, per_bank_limit: coverage_calls.append(per_bank_limit)
    dialog.options_tab.refresh = lambda amount, is_senior, best_rate: options_calls.append(
        (amount, is_senior, best_rate)
    )
    assert dialog.tabs.count() == 3

    dialog.tabs.setCurrentIndex(1)
    assert coverage_calls == [500000]

    dialog.amount_edit.setText("100000")
    dialog.tenure_combo.setCurrentIndex(dialog.tenure_combo.findData("rate_1y"))
    dialog.tabs.setCurrentIndex(2)
    assert options_calls == [(100000.0, False, 8.0)]
