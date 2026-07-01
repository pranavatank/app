import json

from engines.statement_parser import (
    DEFAULT_OLLAMA_MODEL,
    LocalAIStatementParser,
    unload_ollama_model,
    validate_transactions,
    is_ollama_available,
)


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


def test_is_ollama_available_checks_configured_model(monkeypatch):
    captured = {}

    class _Resp:
        status = 200

        def read(self):
            return json.dumps({"models": [{"name": "qwen2.5vl:7b"}]}).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def _fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        return _Resp()

    monkeypatch.setattr("engines.statement_parser.url_request.urlopen", _fake_urlopen)

    assert is_ollama_available(model="qwen2.5vl:7b")
    assert captured["url"] == "http://127.0.0.1:11434/api/tags"


def test_local_ai_defaults_to_qwen_vl(monkeypatch):
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)

    parser = LocalAIStatementParser()

    assert parser.model == DEFAULT_OLLAMA_MODEL
    assert parser.keep_alive == -1


def test_unload_ollama_model_sends_keep_alive_zero(monkeypatch):
    captured = {}

    class _Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def _fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["timeout"] = timeout
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        return _Resp()

    monkeypatch.setattr("engines.statement_parser.url_request.urlopen", _fake_urlopen)

    assert unload_ollama_model(model="qwen2.5vl:7b", endpoint="http://127.0.0.1:11434")
    assert captured["url"] == "http://127.0.0.1:11434/api/generate"
    assert captured["payload"]["model"] == "qwen2.5vl:7b"
    assert captured["payload"]["keep_alive"] == 0
