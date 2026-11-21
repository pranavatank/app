"""Focused synthetic checks for the FD ledger audit affordances."""

from ui.fixed_deposits_screen import FixedDepositsScreen
from core.session import session


def _fd(fd_id, status):
    return {
        "fd_id": fd_id, "person_name": "Synthetic Person", "bank_name": "Synthetic Bank",
        "fd_reference_no": f"S-{fd_id}", "principal_amount": 1000, "interest_rate": 7.5,
        "tenure_years": 1, "tenure_months": 0, "tenure_days": 0,
        "compounding_type": "Quarterly", "start_date": "2025-01-01",
        "maturity_date": "2026-01-01", "maturity_amount": 1077,
        "expected_interest_amount": 77, "actual_interest_amount": None,
        "maturity_calc_method": "Formula", "status": status,
    }


def _quiet_charts(monkeypatch):
    monkeypatch.setattr("ui.fixed_deposits_screen.get_all_financial_years", lambda since_year=2020: [])
    monkeypatch.setattr("ui.fixed_deposits_screen.get_total_fd_interest", lambda fy, pid: 0)
    monkeypatch.setattr("ui.fixed_deposits_screen.get_total_savings_interest", lambda fy, pid: 0)


def test_status_counts_and_filter_keep_storage_statuses(qapp, monkeypatch):
    _quiet_charts(monkeypatch)
    rows = [_fd(1, "Pending Details"), _fd(2, "Active"), _fd(3, "Matured")]
    monkeypatch.setattr("ui.fixed_deposits_screen.get_all_fds", lambda person_id=None: rows)
    screen = FixedDepositsScreen()
    screen.refresh()
    assert screen.table.rowCount() == 3
    assert "Pending Details: 1" in screen.status_counts.text()
    screen.status_filters.setCurrentText("Pending Details")
    assert screen.table.rowCount() == 1
    assert screen.table.item(0, 14).text() == "Pending Details"
    screen.close()


def test_filter_switch_is_blocked_with_unsaved_inline_edits(qapp, monkeypatch):
    _quiet_charts(monkeypatch)
    monkeypatch.setattr("ui.fixed_deposits_screen.get_all_fds", lambda person_id=None: [_fd(1, "Active")])
    monkeypatch.setattr("ui.fixed_deposits_screen.QMessageBox.information", lambda *args: None)
    screen = FixedDepositsScreen()
    screen.refresh()
    screen.table.item(0, 4).setText("1200")
    screen.status_filters.setCurrentText("Active")
    assert screen._has_unsaved_edits
    assert screen.status_filters.currentText() == "All"
    screen.close()


def test_interest_trend_privacy_clears_plot_and_accessible_data(qapp, monkeypatch):
    _quiet_charts(monkeypatch)
    screen = FixedDepositsScreen()
    old = session.privacy_mode
    try:
        session.privacy_mode = True
        monkeypatch.setattr("ui.fixed_deposits_screen.get_all_financial_years", lambda since_year=2020: ["2025-26"])
        monkeypatch.setattr("ui.fixed_deposits_screen.get_total_fd_interest", lambda fy, pid: 123456)
        monkeypatch.setattr("ui.fixed_deposits_screen.get_total_savings_interest", lambda fy, pid: 654321)
        screen._refresh_interest_chart()
        assert screen.interest_chart._data_rows == ()
        assert "hidden in privacy mode" in screen.interest_chart.accessibleDescription()
    finally:
        session.privacy_mode = old
        screen.close()


def test_refresh_restores_inline_draft_without_disclosing_it_in_privacy_mode(qapp, monkeypatch):
    _quiet_charts(monkeypatch)
    monkeypatch.setattr("ui.fixed_deposits_screen.get_all_fds", lambda person_id=None: [_fd(1, "Active")])
    monkeypatch.setattr(session, "privacy_mode", False)
    screen = FixedDepositsScreen()
    try:
        screen.refresh()
        screen.table.item(0, 4).setText("34567.89")
        screen.refresh()
        assert screen.table.item(0, 4).text() == "34567.89"
        assert screen._dirty_fd_ids == {1}
        session.privacy_mode = True
        screen.refresh()
        assert "34567.89" not in screen.table.item(0, 4).text()
        assert not screen._dirty_fd_ids
        session.privacy_mode = False
        screen.refresh()
        assert screen.table.item(0, 4).text() == "34567.89"
    finally:
        screen.close()


def test_ledger_viewport_fits_five_rows(qapp):
    screen = FixedDepositsScreen()
    assert screen.table.minimumHeight() >= 5 * 32
    screen.close()


def test_interest_trend_is_yearly_and_chronological(qapp, monkeypatch):
    _quiet_charts(monkeypatch)
    screen = FixedDepositsScreen()
    try:
        monkeypatch.setattr("ui.fixed_deposits_screen.get_all_financial_years", lambda since_year=2020: ["2026-27", "2024-25", "2025-26"])
        monkeypatch.setattr("ui.fixed_deposits_screen.get_total_fd_interest", lambda fy, pid: int(fy[:4]))
        monkeypatch.setattr("ui.fixed_deposits_screen.get_total_savings_interest", lambda fy, pid: int(fy[:4]) * 2)
        screen._refresh_interest_chart()
        assert [row[0] for row in screen.interest_chart._data_rows] == ["2024-25", "2025-26", "2026-27"]
        assert screen.interest_chart._data_rows[0][1:] == (2024, 4048)
    finally:
        screen.close()


def test_edit_dialog_shows_basename_provenance_and_bank_reported_kind(qapp):
    from models.person import add_person
    from models.bank_account import add_account
    from models.fixed_deposit import add_fd
    from ui.dialogs.fd_dialog import FDDialog

    person_id = add_person("Synthetic provenance holder")
    account_id = add_account(person_id, "Synthetic provenance bank", "Savings")
    fd_id = add_fd(
        account_id, person_id, 1000, "2025-01-01", 12, 7.5, None,
        "2026-01-01", 1077, maturity_calc_method="BankReported",
        tenure_years=1, fd_reference_no="S-PROV", status="Pending Details",
        source_statement_file=r"C:\private\source\advice.pdf",
    )
    dialog = FDDialog(None, mode="edit", fd_id=fd_id)
    text = dialog.provenance_label.text()
    assert "Bank reported (advice)" in text
    assert "advice.pdf" in text
    assert "C:\\private" not in text
    dialog.close()


def test_focused_action_label_tracks_selected_status(qapp, monkeypatch):
    _quiet_charts(monkeypatch)
    rows = [_fd(10, "Pending Details"), _fd(11, "Active")]
    monkeypatch.setattr("ui.fixed_deposits_screen.get_all_fds", lambda person_id=None: rows)
    screen = FixedDepositsScreen()
    screen.refresh()
    screen._update_edit_details_action(0)
    assert screen.edit_details_button.text() == "Complete details"
    screen._update_edit_details_action(1)
    assert screen.edit_details_button.text() == "Edit details"
    screen.close()


def test_failed_save_keeps_inline_value_and_dirty_state(qapp, monkeypatch):
    from models.person import add_person
    from models.bank_account import add_account
    from models.fixed_deposit import add_fd

    _quiet_charts(monkeypatch)
    person_id = add_person("Synthetic failed save holder")
    account_id = add_account(person_id, "Synthetic failed save bank", "Savings")
    fd_id = add_fd(account_id, person_id, 1000, "2025-01-01", 12, 7.5, "Quarterly",
                   "2026-01-01", 1077, tenure_years=1, fd_reference_no="S-FAIL")
    from models.fixed_deposit import get_fd
    fd = get_fd(fd_id)
    fd.update(person_name="Synthetic failed save holder", bank_name="Synthetic failed save bank")
    monkeypatch.setattr("ui.fixed_deposits_screen.get_all_fds", lambda person_id=None: [fd])
    monkeypatch.setattr("ui.fixed_deposits_screen.update_fd", lambda *args: (_ for _ in ()).throw(RuntimeError("synthetic failure")))
    monkeypatch.setattr("ui.fixed_deposits_screen.show_warning", lambda *args: None)
    screen = FixedDepositsScreen()
    screen.refresh()
    screen.table.item(0, 4).setText("1200")
    screen.table.getCheckedRows = lambda: [0]
    screen._on_save_changes()
    assert screen.table.rowCount() == 1
    assert screen.table.item(0, 4).text() == "1200"
    assert fd_id in screen._dirty_fd_ids
    screen.close()
