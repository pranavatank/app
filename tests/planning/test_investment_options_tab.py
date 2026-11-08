"""
tests/test_investment_options_tab.py — Tests for the FD planner investment options tab
"""

from ui.dialogs.investment_options_tab import InvestmentOptionsTab

SSY = "Sukanya Samriddhi Yojana (SSY)"
SCSS = "Senior Citizens Savings Scheme (SCSS)"
NSC = "National Savings Certificate (NSC)"
FRSB = "RBI Floating Rate Savings Bond"


def _row_names(tab: InvestmentOptionsTab) -> list[str]:
    return [tab.table.item(row, 0).text() for row in range(tab.table.rowCount())]


def _cell(tab: InvestmentOptionsTab, row: int, column: int) -> str:
    return tab.table.item(row, column).text()


def test_non_senior_hides_scss_and_lists_highest_rate_first(qapp):
    tab = InvestmentOptionsTab()
    tab.refresh(1_000_000, False)

    assert tab.table.rowCount() == 10
    assert not any("SCSS" in name for name in _row_names(tab))
    assert _cell(tab, 0, 0) == SSY


def test_senior_lists_scss_before_ssy_for_equal_rates(qapp):
    tab = InvestmentOptionsTab()
    tab.refresh(1_000_000, True)

    assert tab.table.rowCount() == 11
    assert _row_names(tab)[:2] == [SCSS, SSY]


def test_zero_amount_shows_placeholders_and_prompt(qapp):
    tab = InvestmentOptionsTab()
    tab.refresh(0, False)

    assert _cell(tab, 0, 6) == "—"
    assert tab.amount_lbl.text().startswith("Enter an amount")


def test_table_has_eight_columns_without_notes(qapp):
    tab = InvestmentOptionsTab()

    assert tab.table.columnCount() == 8


def test_amount_above_scheme_limit_marks_note_as_capped(qapp):
    tab = InvestmentOptionsTab()
    tab.refresh(5_000_000, True)

    scss_row = _row_names(tab).index(SCSS)
    assert tab.table.item(scss_row, 0).toolTip().endswith("Capped at the scheme limit.")

    tab.table.setCurrentCell(scss_row, 0)
    assert tab.details_lbl.text().startswith(f"{SCSS}:")
    assert tab.details_lbl.text().endswith("Capped at the scheme limit.")


def test_rates_beating_best_bank_rate_are_bold(qapp):
    tab = InvestmentOptionsTab()
    tab.refresh(1_000_000, False, best_bank_rate=8.0)

    names = _row_names(tab)
    assert tab.table.item(names.index(FRSB), 0).font().bold()
    assert not tab.table.item(names.index(NSC), 0).font().bold()
