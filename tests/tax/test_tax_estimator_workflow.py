"""Synthetic coverage for Tax estimator context and compact workflow state."""

from ui import tax_screen as tax_ui
from core.session import session


def test_estimator_keeps_context_and_distinguishes_source_and_manual_state(qapp, monkeypatch):
    people = {
        11: {"person_id": 11, "full_name": "Asha Synthetic", "pan_number": "—"},
        22: {"person_id": 22, "full_name": "Dev Synthetic", "pan_number": "—"},
    }
    saved = {(11, "2025-26"): {"salary_income": 900000, "tds_deducted": 20000}}
    monkeypatch.setattr(tax_ui, "get_all_persons", lambda: list(people.values()))
    monkeypatch.setattr(tax_ui, "get_person", lambda pid: people.get(pid))
    monkeypatch.setattr(tax_ui, "get_ais_tis_data", lambda pid, fy, source_type="AIS": saved.get((pid, fy)))
    monkeypatch.setattr(tax_ui, "get_tax_profile", lambda pid, fy: None)
    monkeypatch.setattr(tax_ui, "get_total_fd_interest", lambda fy, pid: 0)
    monkeypatch.setattr(tax_ui, "get_total_savings_interest", lambda fy, pid: 0)
    monkeypatch.setattr(tax_ui, "project_next_year_income", lambda pid, fy: {
        "next_fy": "2026-27", "assessment_year": "2027-28", "income_source": "expectations",
        "expected_income": 0, "fd_interest": 0, "savings_interest": 0, "gross_total_income": 0,
        "taxable_income": 0, "projected_tax": 0,
        "slab": {"current_rate": 0, "is_top_slab": False, "amount_to_next_slab": 1,
                 "next_rate": 5, "slab_ceiling": 400000},
    })
    original_person, original_fy = session.selected_person_id, session.selected_fy
    session.set_person(11)
    session.set_financial_year("2025-26")
    screen = tax_ui.TaxScreen()
    screen.resize(1200, 720)
    screen.show()
    qapp.processEvents()
    try:
        screen.refresh()
        assert screen.workflow_scroll.widget() is not None
        assert "Asha Synthetic" in screen.estimate_status.text()
        assert "saved AIS/TIS values" in screen.estimate_status.text()
        assert screen.gross_salary.value() == 900000

        # Person selection is the shared session selection used by the rest of the app.
        screen.person_combo.setCurrentIndex(screen.person_combo.findData(22))
        assert session.selected_person_id == 22
        assert "Dev Synthetic" in screen.estimate_status.text()
        assert "no saved AIS/TIS document" in screen.estimate_status.text()

        session.set_financial_year("2024-25")
        screen.refresh()
        assert "FY 2024-25" in screen.estimate_status.text()
        assert "no saved AIS/TIS document" in screen.estimate_status.text()

        screen.gross_salary.setValue(123456)
        assert "Manual edits" in screen.estimate_status.text()
        assert "out of date" in screen.estimate_status.text()

        tax_result = tax_ui.calculate_new_regime_tax(123456, salary_income=123456, financial_year="2024-25")
        monkeypatch.setattr(tax_ui, "calculate_and_save_tax", lambda **kwargs: {
            "new_regime": tax_result, "gross_total_income": 123456, "taxes_paid": 0,
        })
        monkeypatch.setattr(tax_ui, "show_success", lambda *args, **kwargs: None)
        screen._on_calculate()
        qapp.processEvents()
        assert "Estimate calculated" in screen.estimate_status.text()
        assert screen.workflow_scroll.verticalScrollBar().value() > 0

        session.set_person(9999)
        screen.refresh()
        assert session.selected_person_id is None
        assert not screen.btn_calc.isEnabled()
        assert screen.taxpayer_label.text() == "—"
        assert screen.pan_label.text() == "—"
        assert screen.ay_label.text() == "—"
    finally:
        screen.close()
        session.set_person(original_person)
        session.set_financial_year(original_fy)


def test_app_saved_summary_is_not_presented_as_fresh_estimate(qapp, monkeypatch):
    person = {"person_id": 31, "full_name": "Ravi Synthetic", "pan_number": "—"}
    monkeypatch.setattr(tax_ui, "get_all_persons", lambda: [person])
    monkeypatch.setattr(tax_ui, "get_person", lambda pid: person if pid == 31 else None)
    monkeypatch.setattr(tax_ui, "get_ais_tis_data", lambda *args, **kwargs: None)
    monkeypatch.setattr(tax_ui, "get_total_fd_interest", lambda fy, pid: 0)
    monkeypatch.setattr(tax_ui, "get_total_savings_interest", lambda fy, pid: 0)
    monkeypatch.setattr(tax_ui, "get_tax_profile", lambda pid, fy: {
        "salary_income": 500000, "gross_total_income": 510000, "tds_deducted": 1000,
        "tcs_collected": 0, "advance_tax_paid": 0, "self_assessment_tax": 0,
    })
    monkeypatch.setattr(tax_ui, "project_next_year_income", lambda pid, fy: {
        "next_fy": "2026-27", "assessment_year": "2027-28", "income_source": "expectations",
        "expected_income": 0, "fd_interest": 0, "savings_interest": 0, "gross_total_income": 0,
        "taxable_income": 0, "projected_tax": 0,
        "slab": {"current_rate": 0, "is_top_slab": False, "amount_to_next_slab": 1,
                 "next_rate": 5, "slab_ceiling": 400000},
    })
    original_person, original_fy = session.selected_person_id, session.selected_fy
    session.set_person(31)
    screen = tax_ui.TaxScreen()
    try:
        screen.source_combo.setCurrentIndex(1)
        assert "Stored profile summary" in screen.estimate_status.text()
        assert "may differ from visible inputs" in screen.estimate_status.text()
        screen.gross_salary.setValue(600000)
        assert "out of date" in screen.estimate_status.text()
    finally:
        screen.close()
        session.set_person(original_person)
        session.set_financial_year(original_fy)
