import pytest

from engines.taxdocs.period import extract_tax_period, extract_tax_period_from_pages
from engines.taxdocs import persist


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Assessment Year: 2026-27", {"financial_year": "2025-26", "assessment_year": "2026-27"}),
        ("Financial Year 2025-26", {"financial_year": "2025-26", "assessment_year": None}),
        ("Financial Year 2025-2026", {"financial_year": "2025-26", "assessment_year": None}),
        ("Assessment Year 2026-2027", {"financial_year": "2025-26", "assessment_year": "2026-27"}),
        ("FY 2025-26; AY 2026-27", {"financial_year": "2025-26", "assessment_year": "2026-27"}),
    ],
)
def test_extract_tax_period(text, expected):
    assert extract_tax_period(text) == expected


def test_extract_tax_period_rejects_conflicting_source_labels():
    with pytest.raises(ValueError, match="conflicts"):
        extract_tax_period("Financial Year 2025-26; Assessment Year 2025-26")
    with pytest.raises(ValueError, match="conflicting tax document years"):
        extract_tax_period("Financial Year 2024-25; Financial Year 2025-26")


def test_report_period_ignores_historical_labeled_years_on_detail_pages():
    pages = [
        "Annual Information Statement\nFinancial Year 2025-26\nAssessment Year 2026-27",
        "Transaction history\nFinancial Year 2022-23\nFinancial Year 2023-24",
    ]
    assert extract_tax_period_from_pages(pages) == {
        "financial_year": "2025-26",
        "assessment_year": "2026-27",
    }


def test_report_period_still_rejects_conflicting_header_labels():
    with pytest.raises(ValueError, match="conflicting tax document years"):
        extract_tax_period_from_pages([
            "Financial Year 2024-25\nFinancial Year 2025-26",
            "Financial Year 2026-27",
        ])


@pytest.mark.parametrize("source_type", [persist.SOURCE_TYPE_AIS, persist.SOURCE_TYPE_TIS])
def test_ais_tis_persist_uses_source_year(monkeypatch, source_type):
    writes = {}

    def save_summary(person_id, financial_year, saved_type, raw_json, payload):
        writes["summary"] = (financial_year, saved_type)
        return 17

    def save_records(import_id, records):
        writes["records"] = (import_id, records)

    monkeypatch.setattr(persist, "save_ais_tis_data", save_summary)
    monkeypatch.setattr(persist, "save_ais_tis_records", save_records)

    result = persist.persist_ais_tis(
        1,
        {"assessment_year": "2026-27", "details": []},
        source_type,
    )

    assert result["financial_year"] == "2025-26"
    assert writes["summary"] == ("2025-26", source_type)
    assert writes["records"] == (17, [])


def test_ais_tis_persist_rejects_conflicting_caller_year(monkeypatch):
    monkeypatch.setattr(persist, "save_ais_tis_data", lambda *args: pytest.fail("unexpected write"))
    with pytest.raises(ValueError, match="conflicts with source year"):
        persist.persist_ais_tis(
            1,
            {"financial_year": "2025-26"},
            persist.SOURCE_TYPE_AIS,
            financial_year="2026-27",
        )


def test_ais_tis_persist_rejects_missing_source_period_before_write(monkeypatch):
    monkeypatch.setattr(persist, "save_ais_tis_data", lambda *args: pytest.fail("unexpected write"))
    with pytest.raises(ValueError, match="no financial year or assessment year"):
        persist.persist_ais_tis(1, {"details": []}, persist.SOURCE_TYPE_AIS)


def test_26as_assessment_year_maps_to_matching_financial_year(monkeypatch):
    captured = {}

    def save(person_id, financial_year, records, source_file="", raw_text=""):
        captured["financial_year"] = financial_year
        return 3

    monkeypatch.setattr(persist, "save_form26as_import", save)
    result = persist.persist_form26as(1, {"assessment_year": "2026-27", "records": []})
    assert result["financial_year"] == "2025-26"
    assert captured["financial_year"] == "2025-26"
