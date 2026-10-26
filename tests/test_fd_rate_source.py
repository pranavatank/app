"""
tests/test_fd_rate_source.py — Tests for bank FD rate fetching, parsing and caching
"""

import pytest
from datetime import date

import config
from engines.fd_rate_source import (
    COMMERCIAL_BANK,
    SMALL_FINANCE_BANK,
    classify_bank_type,
    extract_as_of_date,
    fetch_rates,
    is_stale,
    load_cached_rates,
    parse_rates_html,
    save_cached_rates,
    _parse_rate,
)

SAMPLE_HTML = """
<html><head><script type="application/ld+json">{"dateModified": "2026-10-07 18:56:12"}</script></head><body>
<table><tr><th>Bonds</th><th>Types</th></tr><tr><td>A</td><td>B</td></tr></table>
<table>
<tr><th>Banks</th><th>Highest FD rate (% p.a.)</th><th>1-year FD rate (% p.a.)</th><th>3-year FD rate (% p.a.)</th><th>5-year FD rate (% p.a.)</th><th>Additional interest rate for senior citizens (% p.a.)</th></tr>
<tr><td>Suryoday Small Finance Bank</td><td>8.25</td><td>7.25</td><td>7.25</td><td>8.25</td><td>0.15</td></tr>
<tr><td>Bandhan Bank</td><td>7.45</td><td>7.00</td><td>7.25</td><td>5.85</td><td>0.50-0.75</td></tr>
<tr><td></td><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td></tr>
</table></body></html>
"""


class _FakeHeaders:
    def get_content_charset(self):
        return "utf-8"


class _FakeResponse:
    headers = _FakeHeaders()

    def __init__(self, body: bytes):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def test_parse_rates_html_reads_rate_table():
    banks = parse_rates_html(SAMPLE_HTML)

    assert len(banks) == 2
    suryoday, bandhan = banks
    assert suryoday["bank_name"] == "Suryoday Small Finance Bank"
    assert suryoday["rate_1y"] == 7.25
    assert suryoday["rate_5y"] == 8.25
    assert suryoday["senior_extra"] == 0.15
    assert suryoday["bank_type"] == SMALL_FINANCE_BANK
    assert bandhan["senior_extra"] is None
    assert bandhan["bank_type"] == COMMERCIAL_BANK


def test_parse_rates_html_without_rate_table_raises():
    with pytest.raises(ValueError):
        parse_rates_html("<html><table><tr><th>Name</th></tr><tr><td>x</td></tr></table></html>")


@pytest.mark.parametrize("text, expected", [
    ("8.25%", 8.25),
    ("7.10 p.a.", 7.10),
    ("—", None),
    ("0.25-0.50", None),
])
def test_parse_rate(text, expected):
    assert _parse_rate(text) == expected


def test_extract_as_of_date():
    assert extract_as_of_date(SAMPLE_HTML) == "2026-10-07"
    assert extract_as_of_date("<html></html>") is None


@pytest.mark.parametrize("bank_name, expected", [
    ("AU Small Finance Bank", SMALL_FINANCE_BANK),
    ("HDFC Bank", COMMERCIAL_BANK),
])
def test_classify_bank_type(bank_name, expected):
    assert classify_bank_type(bank_name) == expected


def test_load_cached_rates_returns_bundled_snapshot_when_no_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))

    snapshot = load_cached_rates()

    assert snapshot["is_bundled"] is True
    assert len(snapshot["banks"]) == 19


def test_save_then_load_returns_cached_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    custom_snapshot = {
        "source_url": "https://example.com/fd-rates",
        "as_of": "2026-10-01",
        "fetched_at": "2026-10-01T09:00:00",
        "is_bundled": False,
        "banks": [{
            "bank_name": "Test Bank",
            "bank_type": COMMERCIAL_BANK,
            "highest_rate": 7.0,
            "rate_1y": 6.5,
            "rate_3y": 6.75,
            "rate_5y": 6.8,
            "senior_extra": 0.5,
        }],
    }

    save_cached_rates(custom_snapshot)

    assert load_cached_rates() == custom_snapshot


def test_corrupt_cache_falls_back_to_bundled_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    (tmp_path / "fd_rates_cache.json").write_text("not json", encoding="utf-8")

    snapshot = load_cached_rates()

    assert snapshot["is_bundled"] is True


def test_fetch_rates_parses_saves_and_returns_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        "engines.fd_rate_source.urllib.request.urlopen",
        lambda request, timeout: _FakeResponse(SAMPLE_HTML.encode("utf-8")),
    )

    snapshot = fetch_rates("https://example.com/fd-rates")

    assert len(snapshot["banks"]) == 2
    assert snapshot["as_of"] == "2026-10-07"
    assert snapshot["is_bundled"] is False
    assert (tmp_path / "fd_rates_cache.json").exists()


def test_is_stale_within_window_is_false():
    assert is_stale({"as_of": "2026-10-07"}, today=date(2026, 10, 12)) is False


def test_is_stale_after_window_is_true():
    assert is_stale({"as_of": "2026-10-07"}, today=date(2026, 12, 1)) is True


def test_is_stale_invalid_as_of_is_true():
    assert is_stale({"as_of": "bad"}) is True


def test_page_date_is_not_invented_when_aggregator_has_no_date(monkeypatch,tmp_path):
    import config
    import engines.fd_rate_source as source
    monkeypatch.setattr(config,'DATA_DIR',str(tmp_path))
    html=b'<table><tr><th>Bank</th><th>1 year</th></tr><tr><td>A</td><td>7.5</td></tr></table>'
    class Response:
        class headers:
            @staticmethod
            def get_content_charset():return 'utf-8'
        def read(self):return html
        def __enter__(self):return self
        def __exit__(self,*args):pass
    monkeypatch.setattr(source.urllib.request,'urlopen',lambda *args,**kwargs:Response())
    snapshot=source.fetch_rates('https://comparison.example/rates')
    assert snapshot['as_of'] is None
    assert source.is_stale(snapshot)
