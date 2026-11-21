"""Read Ujjivan's ruled transaction table and reconcile its printed summary."""

import re

import pdfplumber

from engines.parser_utils import _extract_reference_no, infer_statement_category
from engines.statement.assemble import _guess_mode, normalize_account_no, parse_amount, parse_date
from engines.statement.validate import normalise_order
from engines.statement_passwords import ensure_pdf_password


_TRANSACTION_HEADER = ("tran date", "value date", "particular", "debit", "credit", "balance amount")


def _label(value):
    return " ".join((value or "").casefold().split())


def _cents(value):
    text = (value or "").strip()
    if not re.fullmatch(r"-?\d[\d,]*(?:\.\d{1,2})?", text):
        return None
    return round(parse_amount(text) * 100)


class UjjivanStatementParser:
    def parse_pdf(self, file_path, password=None, debug=None):
        ensure_pdf_password(file_path, password)
        with pdfplumber.open(file_path, password=password) as pdf:
            tables = [table for page in pdf.pages for table in page.extract_tables()]
        rows = []
        summaries = set()
        found_transactions = False
        for table in tables:
            if not table or len(table[0]) != 6:
                continue
            headers = tuple(map(_label, table[0]))
            if headers != _TRANSACTION_HEADER:
                for header, values in zip(table, table[1:]):
                    if (
                        len(header) == len(values) == 6
                        and _label(header[0]) == "opening balance"
                        and _label(header[-1]) == "closing balance"
                    ):
                        summaries.add(tuple(map(_cents, values)))
                continue
            found_transactions = True
            for entry in table[1:]:
                if not any(_label(value) for value in entry):
                    continue
                row = self._parse_row(entry)
                if row is None:
                    return self._reject(debug)
                rows.append(row)

        rows = normalise_order(rows)
        if len(summaries) != 1 or not rows:
            return self._reject(debug) if found_transactions else []
        summary = next(iter(summaries))
        if not self._reconcile(rows, summary):
            if any(row["transaction_date"] != rows[0]["transaction_date"] for row in rows):
                return self._reject(debug)
            # Booking dates cannot disambiguate the printed order on a single day.
            rows.reverse()
            if not self._reconcile(rows, summary):
                return self._reject(debug)
        if debug is not None:
            debug.update(rows_extracted=len(rows), rows_scanned=len(rows))
        return rows

    @staticmethod
    def _reject(debug):
        if debug is not None:
            debug["reconciliation_failed"] = True
            debug.setdefault("issues", []).append(
                "Ujjivan transaction rows do not reconcile with the printed statement summary."
            )
        return []

    @staticmethod
    def _parse_row(entry):
        if len(entry) != len(_TRANSACTION_HEADER):
            return None
        booking_day, value_day, narration, debit, credit, balance = entry
        day = parse_date(booking_day or "")
        if not day or not parse_date(value_day or ""):
            return None
        amounts = [_cents(value) for value in (debit, credit)]
        if any(_label(cell) and value is None for cell, value in zip((debit, credit), amounts)):
            return None
        withdrawals, deposits = (value or 0 for value in amounts)
        if min(withdrawals, deposits) < 0 or bool(withdrawals) == bool(deposits):
            return None
        after = _cents(balance)
        if after is None and _label(balance):
            return None
        kind = "Expense" if withdrawals else "Income"
        description = " ".join((narration or "").split()) or "Transaction"
        return {
            "transaction_date": day,
            "transaction_type": kind,
            "description": description[:200],
            "description_raw": description,
            "reference_no": _extract_reference_no(description),
            "deposit_account_no": normalize_account_no(description),
            "mode": _guess_mode(description),
            "category": infer_statement_category(description, kind) or f"Other {kind}",
            "amount": (withdrawals or deposits) / 100,
            # Blank cells are tested as zero against every movement and both printed totals.
            "balance_after": (after or 0) / 100,
        }

    @staticmethod
    def _reconcile(rows, summary):
        if not rows or any(value is None for value in summary):
            return False
        opening, debit_count, credit_count, total_debit, total_credit, closing = summary
        expected = opening
        counts = {"Expense": 0, "Income": 0}
        totals = {"Expense": 0, "Income": 0}
        for row in rows:
            kind = row["transaction_type"]
            amount = round(row["amount"] * 100)
            counts[kind] += 1
            totals[kind] += amount
            expected += amount if kind == "Income" else -amount
            if expected != round(row["balance_after"] * 100):
                return False
        return (
            expected == closing
            and counts["Expense"] * 100 == debit_count
            and counts["Income"] * 100 == credit_count
            and totals["Expense"] == total_debit
            and totals["Income"] == total_credit
        )
