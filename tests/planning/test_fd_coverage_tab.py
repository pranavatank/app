import pytest
from PySide6.QtGui import QColor

import ui.dialogs.fd_coverage_tab as coverage_module
from ui.dialogs.fd_coverage_tab import CoverageTab
from ui.theme import Theme
from ui.widgets.money_label import format_inr
from engines.fd_allocation_engine import COVERAGE_OVER, COVERAGE_NEAR, COVERAGE_OK

LIMIT = 500000
ASHA = {"person_id": 1, "full_name": "Asha"}
RAVI = {"person_id": 2, "full_name": "Ravi"}


def _row(total: float, status: str, bank_name: str = "Bank A", person_name: str = "Asha") -> dict:
    return {
        "person_name": person_name,
        "bank_name": bank_name,
        "savings_amount": 0.0,
        "fd_amount": total,
        "total": total,
        "headroom": max(LIMIT - total, 0),
        "used_pct": round(total / LIMIT * 100, 1),
        "status": status,
    }


def _stub_report(monkeypatch, rows: list[dict]) -> None:
    monkeypatch.setattr(coverage_module, "get_coverage_report", lambda persons, per_bank_limit: rows)


@pytest.fixture
def tab(qapp):
    return CoverageTab()


def test_mixed_statuses_show_rows_summary_and_status_color(tab, monkeypatch):
    _stub_report(monkeypatch, [
        _row(520000, COVERAGE_OVER, "Bank A"),
        _row(460000, COVERAGE_NEAR, "Bank B"),
        _row(100000, COVERAGE_OK, "Bank C"),
    ])

    tab.refresh([ASHA], LIMIT)

    assert tab.table.rowCount() == 3
    assert tab.table.isColumnHidden(0)
    assert "1 bank above the insured limit and 1 bank close to it" in tab.summary_lbl.text()
    assert format_inr(20000) in tab.summary_lbl.text()
    assert tab.table.item(0, 7).foreground().color().name() == QColor(Theme.DANGER).name()


def test_two_persons_show_person_column(tab, monkeypatch):
    _stub_report(monkeypatch, [_row(100000, COVERAGE_OK, "Bank A", "Asha")])

    tab.refresh([ASHA, RAVI], LIMIT)

    assert not tab.table.isColumnHidden(0)


def test_only_ok_row_summary_says_all_within_limit(tab, monkeypatch):
    _stub_report(monkeypatch, [_row(100000, COVERAGE_OK)])

    tab.refresh([ASHA], LIMIT)

    assert tab.summary_lbl.text() == "All your deposits are within the insured limit."


def test_only_near_row_summary_says_close_to_limit(tab, monkeypatch):
    _stub_report(monkeypatch, [_row(460000, COVERAGE_NEAR)])

    tab.refresh([ASHA], LIMIT)

    assert tab.summary_lbl.text().startswith("1 bank close to the insured limit")


def test_no_rows_shows_empty_message_and_hides_table_and_summary(tab, monkeypatch):
    _stub_report(monkeypatch, [])

    tab.refresh([ASHA], LIMIT)

    assert tab.table.isHidden()
    assert not tab.empty_lbl.isHidden()
    assert tab.summary_lbl.isHidden()
