"""Regression coverage for monetary field and reference parsing."""

from contextlib import nullcontext
from types import SimpleNamespace

import pdfplumber

from engines.bank_parsers import hdfc_statement_parser, sbi_statement_parser, yes_bank_statement_parser
from engines.parser_registry import get


def _mock_pdf(monkeypatch, module, text):
    monkeypatch.setattr(module, "ensure_pdf_password", lambda *args: None)
    page = SimpleNamespace(extract_text=lambda: text)
    monkeypatch.setattr(pdfplumber, "open", lambda *args, **kwargs: nullcontext(SimpleNamespace(pages=[page])))


def test_hdfc_parses_alphanumeric_reference_and_uses_balance_direction(monkeypatch):
    _mock_pdf(monkeypatch, hdfc_statement_parser, """
31/03/25 ATM WDL 000000000000000 31/03/25 100.00 2,000.00
01/04/25 UPI TRANSFER IMPSR123456789012 02/04/25 500.00 2,500.00
WRAPPED NARRATION
""")

    rows = hdfc_statement_parser.HDFCStatementParser().parse_pdf("fixture.pdf")

    assert len(rows) == 2
    assert rows[1]["transaction_date"] == "2025-04-01"
    assert rows[1]["reference_no"] == "IMPSR123456789012"
    assert rows[1]["description"] == "UPI TRANSFER WRAPPED NARRATION"
    assert rows[1]["transaction_type"] == "Income"


def test_sbi_preserves_printed_amount_when_running_balance_does_not_tie(monkeypatch):
    _mock_pdf(monkeypatch, sbi_statement_parser, """
31/03/2025 31/03/2025 DEP TFR - 1000.00 10000.00
01/04/2025 02/04/2025 ATM WDL 1250.00 - 8000.00
02/04/2025 02/04/2025 TRANSFER - 2000.00 10000.00
""")

    rows = sbi_statement_parser.parse_sbi_pdf("fixture.pdf")

    assert [row["amount"] for row in rows] == [1000.0, 1250.0, 2000.0]
    assert [row["transaction_type"] for row in rows] == ["Income", "Expense", "Income"]
    assert rows[1]["transaction_date"] == "2025-04-01"
    assert rows[1]["balance_after"] == 8000.0


def test_sbi_handles_newest_first_and_blank_money_columns(monkeypatch):
    _mock_pdf(monkeypatch, sbi_statement_parser, """
02/04/2026 02/04/2026 - - 5000.00 17000.00
01/04/2026 01/04/2026 ATM WDL 1000.00 - 12000.00
""")

    rows = sbi_statement_parser.parse_sbi_pdf("fixture.pdf")

    assert [row["transaction_date"] for row in rows] == ["2026-04-01", "2026-04-02"]
    assert rows[1]["amount"] == 5000
    assert rows[1]["transaction_type"] == "Income"


def test_sbi_resolves_full_bank_name():
    assert get("State Bank of India") is sbi_statement_parser.parse_sbi_pdf


def test_yes_reads_booking_date_and_both_supported_table_shapes():
    parser = yes_bank_statement_parser.YESBankStatementParser()
    seven = parser._parse_row(
        ["31 Mar 2025", "01 Apr 2025", "123456789012", "Card payment", "100.00", "", "0.00"],
        {}, 1,
    )
    six = parser._parse_row(["01-Apr-2026", "NA", "Bank transfer", "", "100.00", "100.00"], {}, 1)

    assert seven["transaction_date"] == "2025-03-31"
    assert seven["transaction_type"] == "Expense"
    assert seven["balance_after"] == 0
    assert six["transaction_date"] == "2026-04-01"
    assert six["transaction_type"] == "Income"


def test_empty_coordinate_parse_falls_back_to_rule_parser(monkeypatch):
    from ui import statement_import_screen_modern as screen

    rows = [{"transaction_date": "2026-04-30", "transaction_type": "Income", "amount": 100}]
    result = rows, {"mode_used": "rule-pdf"}
    monkeypatch.setattr(screen, "parse_statement_pdf", lambda *args, **kwargs: [])
    monkeypatch.setattr(screen, "parse_statement_with_debug", lambda *args, **kwargs: result)

    assert screen._StatementParseWorker("fixture.pdf", "PDF", "Jana", None, None).run() == result


def test_incomplete_coordinate_parse_uses_balance_tied_rule_result(monkeypatch):
    from ui import statement_import_screen_modern as screen

    rows = [
        {"transaction_date": f"2026-04-{i:02}", "transaction_type": "Income",
         "amount": 100, "balance_after": 1000 + i * 100}
        for i in (1, 2, 3)
    ]
    monkeypatch.setattr(screen, "parse_statement_pdf", lambda *args, **kwargs: [rows[0], rows[2]])
    result = rows, {"mode_used": "rule-pdf"}
    monkeypatch.setattr(screen, "parse_statement_with_debug", lambda *args, **kwargs: result)

    assert screen._StatementParseWorker("fixture.pdf", "PDF", "Ujjivan", None, None).run() == result
