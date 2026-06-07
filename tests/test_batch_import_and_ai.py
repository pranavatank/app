import json
import sqlite3
from pathlib import Path

import core.database as database
import config
from engines.statement_parser import LocalAIStatementParser, parse_statement_with_debug
from models.transaction import add_transactions_batch


def _init_temp_db(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(database, "DB_PATH", str(db_path))
    monkeypatch.setattr(config, "DB_PATH", str(db_path))
    database.initialise_database()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("INSERT INTO Person(full_name) VALUES (?)", ("Tester",))
    person_id = conn.execute("SELECT person_id FROM Person LIMIT 1").fetchone()[0]
    conn.execute(
        "INSERT INTO BankAccount(person_id, bank_name, account_type, opening_balance, current_balance, interest_rate) VALUES (?,?,?,?,?,?)",
        (person_id, "Test Bank", "Savings", 0, 0, 0),
    )
    account_id = conn.execute("SELECT account_id FROM BankAccount LIMIT 1").fetchone()[0]
    conn.commit()
    conn.close()
    return db_path, person_id, account_id


def test_batch_import_rolls_back_on_error(tmp_path, monkeypatch):
    _db_path, person_id, account_id = _init_temp_db(tmp_path, monkeypatch)

    good = {
        "transaction_date": "2026-06-01",
        "transaction_type": "Income",
        "amount": 100.0,
        "category": "Salary",
        "mode": "Bank Transfer",
        "description": "Salary credit",
        "reference_no": "REF1",
        "balance_after": 100.0,
    }
    bad = {
        "transaction_date": "2026-06-02",
        "transaction_type": "Expense",
        "amount": None,
        "category": "Food & Dining",
        "mode": "UPI",
        "description": "Bad row",
        "reference_no": "REF2",
        "balance_after": 0.0,
    }

    try:
        add_transactions_batch(account_id, person_id, [good, bad])
        assert False, "Expected batch insert to fail"
    except Exception:
        pass

    conn = sqlite3.connect(database.DB_PATH)
    count = conn.execute("SELECT COUNT(*) FROM Transactions").fetchone()[0]
    conn.close()
    assert count == 0


def test_ai_fallback_and_mapping_suggestion(monkeypatch, tmp_path):
    _db_path, _person_id, _account_id = _init_temp_db(tmp_path, monkeypatch)

    # Rule parser fails, AI returns a parsed transaction.
    monkeypatch.setattr("engines.statement_parser.GenericExcelParser.parse_excel", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        "engines.statement_parser.LocalAIStatementParser.parse_statement",
        lambda *args, **kwargs: [
            {
                "transaction_date": "2026-06-03",
                "description": "AI parsed",
                "amount": 250.0,
                "transaction_type": "Income",
                "category": "Other Income",
                "mode": "Bank Transfer",
                "balance_after": 250.0,
            }
        ],
    )

    txns, debug = parse_statement_with_debug("dummy.xlsx", "Excel", "Generic")
    assert len(txns) == 1
    assert debug["mode_used"] == "ai"

    # Mapping suggestion response from Ollama.
    class _Resp:
        def __init__(self, payload: dict):
            self._payload = payload

        def read(self):
            return json.dumps(self._payload).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def _fake_urlopen(*args, **kwargs):
        return _Resp({"response": json.dumps({"date_col": "TxnDate", "desc_col": "Narr"})})

    monkeypatch.setattr("engines.statement_parser._read_excel_with_password", lambda *args, **kwargs: __import__("pandas").DataFrame([{ "TxnDate": "01-06-2026", "Narr": "Salary" }]))
    monkeypatch.setattr("engines.statement_parser.url_request.urlopen", _fake_urlopen)

    parser = LocalAIStatementParser()
    suggestion = parser.suggest_excel_mapping("dummy.xlsx")
    assert suggestion == {"date_col": "TxnDate", "desc_col": "Narr"}