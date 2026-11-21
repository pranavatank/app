"""Reconcile ruled Ujjivan tables, including blank cells at zero balance."""

from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from engines.bank_parsers import ujjivan_statement_parser
from engines.parser_registry import get
from engines.statement_parser import parse_statement_with_debug


@pytest.mark.parametrize("closing, reverse_same_day, expected_count", [
    ("8.50", False, 3), ("8.50", True, 3), ("9.50", False, 0),
])
def test_ujjivan_requires_verified_summary_for_blank_zero_balance(monkeypatch, closing, reverse_same_day, expected_count):
    header = ["Tran Date", "Value Date", "Particular", "Debit", "Credit", "Balance\nAmount"]
    first = [
        header,
        ["02/04/2026", "03/04/2026", "Interest", "", "2.00", "22.00"],
        ["03/04/2026", "03/04/2026", "Debit\ncontinued", "22.00", "", ""],
    ]
    second = [
        header,
        ["04/04/2026", "04/04/2026", "Deposit", "", "8.50", "8.50"],
    ]
    footer = [
        ["31/03/2026", "", "", "", "", ""],
        ["Opening Balance", "Debit Count", "Credit Count", "Total Debit", "Total Credit", "Closing Balance"],
        ["20.00", "1", "2", "22.00", "10.50", closing],
    ]
    tables = [[first], [second], [footer]]
    if reverse_same_day:
        entries = list(reversed(first[1:] + second[1:]))
        for entry in entries:
            entry[0] = "02/04/2026"
        tables = [[header_and_rows] for header_and_rows in ([header, *entries], footer)]
    pages = [SimpleNamespace(extract_tables=lambda tables=group: tables) for group in tables]
    monkeypatch.setattr(ujjivan_statement_parser, "ensure_pdf_password", lambda *_: None)
    monkeypatch.setattr(ujjivan_statement_parser.pdfplumber, "open", lambda *_, **__: nullcontext(SimpleNamespace(pages=pages)))

    rows = get("Ujjivan Small Finance Bank").parse_pdf("fixture.pdf")

    assert len(rows) == expected_count
    if rows:
        assert [row["transaction_type"] for row in rows] == ["Income", "Expense", "Income"]
        assert [row["balance_after"] for row in rows] == [22.0, 0.0, 8.5]
        assert rows[0]["transaction_date"] == "2026-04-02"
        assert rows[1]["description"] == "Debit continued"
    else:
        rows, debug = parse_statement_with_debug("fixture.pdf", "PDF", "Ujjivan")
        assert rows == []
        assert debug["reconciliation_failed"]
        assert len(debug["attempts"]) == 1
