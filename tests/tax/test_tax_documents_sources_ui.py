from core.session import session
from models.ais_tis_import import save_ais_tis_data
from models.form26as import save_form26as_import
from models.person import add_person
from ui.tax_documents_screen import TaxDocumentsScreen


def test_source_statuses_follow_person_and_financial_year(qapp, monkeypatch):
    people = [add_person(f"Synthetic Person {index}") for index in range(1, 4)]
    fy = "2025-26"
    # Complete, partial, and missing datasets in the same synthetic database.
    save_form26as_import(people[0], fy, [], source_file="synthetic-26as.pdf")
    save_ais_tis_data(people[0], fy, "AIS", "{}", {})
    save_ais_tis_data(people[0], fy, "TIS", "{}", {})
    save_form26as_import(people[1], fy, [], source_file="synthetic-26as.pdf")
    save_ais_tis_data(people[1], fy, "TIS", "{}", {})
    monkeypatch.setattr(TaxDocumentsScreen, "_try_merge", lambda self, person_id: None)

    screen = TaxDocumentsScreen()
    monkeypatch.setattr(session, "selected_person_id", people[0])
    monkeypatch.setattr(session, "selected_fy", fy)
    screen.refresh()
    assert "Synthetic Person 1" in screen.context_label.text()
    assert [screen.source_zones[key].title_label.text() for key in ("26as", "ais", "tis")] == [
        "Form 26AS · Saved", "AIS · Saved", "TIS · Saved"
    ]
    assert all("Replace" in screen.replace_buttons[key].text() for key in screen.replace_buttons)

    monkeypatch.setattr(session, "selected_person_id", people[1])
    screen.refresh()
    assert [screen.source_zones[key].title_label.text() for key in ("26as", "ais", "tis")] == [
        "Form 26AS · Saved", "AIS · Missing", "TIS · Saved"
    ]
    assert "Browse" in screen.replace_buttons["ais"].text()
    assert "Replace" in screen.replace_buttons["26as"].text()

    monkeypatch.setattr(session, "selected_person_id", people[2])
    screen.refresh()
    assert all(screen.source_zones[key].title_label.text().endswith("Missing") for key in screen.source_zones)
    assert all("Browse" in screen.replace_buttons[key].text() for key in screen.replace_buttons)
    assert not screen.empty_state.isHidden()

    monkeypatch.setattr(session, "selected_person_id", people[0])
    monkeypatch.setattr(session, "selected_fy", "2026-27")
    screen.refresh()
    assert "FY 2026-27" in screen.context_label.text()
    assert all(screen.source_zones[key].title_label.text().endswith("Missing") for key in screen.source_zones)
    assert all("Browse" in screen.replace_buttons[key].text() for key in screen.replace_buttons)
    screen.close()


def test_import_completion_reloads_the_returned_to_context(qapp, monkeypatch):
    first = add_person("Synthetic Import Owner")
    second = add_person("Synthetic Other Owner")
    fy = "2025-26"
    monkeypatch.setattr(session, "selected_person_id", first)
    monkeypatch.setattr(session, "selected_fy", fy)
    screen = TaxDocumentsScreen()
    request, owner, request_fy, lock = screen._begin_source_request("ais", screen.zone_ais)
    monkeypatch.setattr(session, "selected_person_id", second)
    screen.refresh()
    monkeypatch.setattr(session, "selected_person_id", first)
    screen.refresh()
    assert screen.zone_ais.pdf_data is None
    save_ais_tis_data(first, fy, "AIS", "{}", {})

    assert not screen._complete_source_request("ais", request, owner, request_fy, lock, fy)
    assert screen.zone_ais.pdf_data is not None
    assert "Saved" in screen.zone_ais.title_label.text()
    screen.close()


def test_bank_ledger_column_excludes_family_transfers(qapp, monkeypatch):
    from models.bank_account import add_account
    from models.transaction import add_transaction, link_internal_transfer

    first = add_person("Synthetic tax owner")
    second = add_person("Synthetic transfer sender")
    source = add_account(second, "Test Bank A", "Savings")
    target = add_account(first, "Test Bank B", "Savings")
    debit = add_transaction(source, second, "2025-04-20", "Expense", 120)
    credit = add_transaction(target, first, "2025-04-20", "Income", 120, category="Savings Interest")
    add_transaction(target, first, "2025-04-21", "Income", 30, category="Savings Interest")
    link_internal_transfer(debit, credit)

    monkeypatch.setattr(session, "selected_person_id", first)
    monkeypatch.setattr(session, "selected_fy", "2025-26")
    screen = TaxDocumentsScreen()
    screen.merge_result = {
        "financial_position": {"savings_interest": 150},
        "income_variance": {"savings_interest": {"tis": 150, "ais": 150, "difference": 0}},
    }
    screen._render_position_table(first)

    assert screen.position_table.horizontalHeaderItem(5).text() == "Bank Ledger"
    assert "150" in screen.position_table.item(0, 4).text()
    assert "30" in screen.position_table.item(0, 5).text()
    assert screen.position_table.item(0, 6).text() == "Ledger differs"
    screen.close()
