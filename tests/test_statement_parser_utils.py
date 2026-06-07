from engines.statement_parser import validate_transactions, is_ollama_available


def test_validate_transactions_filters_invalid():
    txns = [
        {"transaction_date": "2024-01-01", "amount": 100.0, "transaction_type": "Income"},
        {"transaction_date": "", "amount": 50.0, "transaction_type": "Expense"},
        {"transaction_date": "2024-02-01", "amount": 0, "transaction_type": "Expense"},
        {"transaction_date": "2024-03-01", "amount": 20.0},
    ]

    valid, errors = validate_transactions(txns)
    # Only the first should be valid
    assert len(valid) == 1
    assert len(errors) >= 1


def test_is_ollama_available_returns_bool():
    val = is_ollama_available()
    assert isinstance(val, bool)
