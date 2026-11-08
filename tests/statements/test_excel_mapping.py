import os
import tempfile
import pandas as pd

from engines.statement_parser import GenericExcelParser


def test_excel_mapping_applies_and_parses():
    # Create a small DataFrame with non-standard headers
    df = pd.DataFrame([
        {"TxnDate": "01-06-2026", "Narr": "Salary June", "InAmt": 50000.00, "Bal": 150000.00},
        {"TxnDate": "05-06-2026", "Narr": "Grocery Store", "OutAmt": -2500.00, "Bal": 147500.00},
    ])

    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp.close()
    try:
        df.to_excel(tmp.name, index=False)

        # Mapping from expected field names to source columns
        column_mapping = {
            "transaction_date": "TxnDate",
            "description": "Narr",
            "credit": "InAmt",
            "debit": "OutAmt",
            "balance": "Bal",
        }

        parser = GenericExcelParser()
        txns = parser.parse_excel(tmp.name, debug={}, password=None, column_mapping=column_mapping)

        assert isinstance(txns, list)
        assert len(txns) >= 1
        # Basic sanity checks
        for t in txns:
            assert "transaction_date" in t
            assert "amount" in t
            assert "description" in t

    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass
