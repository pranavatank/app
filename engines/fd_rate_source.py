"""engines/fd_rate_source.py — Fetch current bank FD rates from a public web page and cache them locally."""

import copy
import json
import os
import re
import urllib.request
from datetime import date, datetime, timezone
import math
from html.parser import HTMLParser

import config
from core.settings import get_setting, set_setting

DEFAULT_FD_RATES_URL = "https://www.paisabazaar.com/fixed-deposit/scheduled-banks-fd-interest-rates/"
RATES_STALE_AFTER_DAYS = 30
SMALL_FINANCE_BANK = "Small Finance Bank"
COMMERCIAL_BANK = "Bank"
_SETTINGS_KEY_URL = "fd_rates_source_url"
_CACHE_FILENAME = "fd_rates_cache.json"
_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


def classify_bank_type(bank_name: str) -> str:
    if "small finance" in bank_name.lower():
        return SMALL_FINANCE_BANK
    return COMMERCIAL_BANK


def _row(bank_name: str, highest_rate: float, rate_1y: float, rate_3y: float,
         rate_5y: float, senior_extra: float) -> dict:
    return {
        "bank_name": bank_name,
        "bank_type": classify_bank_type(bank_name),
        "highest_rate": highest_rate,
        "rate_1y": rate_1y,
        "rate_3y": rate_3y,
        "rate_5y": rate_5y,
        "senior_extra": senior_extra,
    }


_BUNDLED_SNAPSHOT = {
    "source_url": DEFAULT_FD_RATES_URL,
    "as_of": "2026-10-07",
    "fetched_at": "2026-10-12T00:00:00",
    "is_bundled": True,
    "banks": [
        _row("Suryoday Small Finance Bank", 8.25, 7.25, 7.25, 8.25, 0.15),
        _row("Jana Small Finance Bank", 8.00, 7.00, 8.00, 7.77, 0.50),
        _row("ESAF Small Finance Bank", 8.00, 6.00, 6.00, 5.75, 0.50),
        _row("Utkarsh Small Finance Bank", 8.10, 6.00, 7.50, 7.00, 0.50),
        _row("Ujjivan Small Finance Bank", 7.80, 7.25, 7.25, 7.20, 0.50),
        _row("Shivalik Small Finance Bank", 8.00, 6.00, 7.50, 6.25, 0.50),
        _row("Equitas Small Finance Bank", 8.00, 7.10, 7.10, 7.00, 0.50),
        _row("Bandhan Bank", 7.45, 7.00, 7.25, 5.85, 0.50),
        _row("DCB Bank", 7.50, 6.90, 7.00, 7.50, 0.25),
        _row("RBL Bank", 7.00, 6.90, 7.00, 6.70, 0.50),
        _row("Capital Small Finance Bank", 7.15, 7.00, 7.00, 6.90, 0.50),
        _row("SBM Bank", 7.30, 7.10, 7.10, 7.00, 0.50),
        _row("AU Small Finance Bank", 7.40, 6.35, 7.40, 6.75, 0.50),
        _row("Central Bank of India", 6.75, 6.10, 6.00, 6.00, 0.50),
        _row("YES Bank", 7.25, 6.65, 7.00, 6.75, 0.50),
        _row("IndusInd Bank", 7.00, 6.75, 7.00, 6.65, 0.50),
        _row("Unity Small Finance Bank", 7.50, 7.50, 6.75, 6.75, 0.50),
        _row("Federal Bank", 6.70, 6.25, 6.50, 6.40, 0.50),
        _row("Bank of India", 6.85, 6.50, 6.70, 6.00, 0.50),
    ],
}


def get_rates_source_url() -> str:
    return get_setting(_SETTINGS_KEY_URL) or DEFAULT_FD_RATES_URL


def set_rates_source_url(url: str) -> None:
    set_setting(_SETTINGS_KEY_URL, (url or "").strip())


def _parse_rate(text: str) -> float | None:
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*%?\s*(?:p\.?a\.?)?\s*", text, re.I)
    if not match:
        return None
    value = float(match[1])
    return value if math.isfinite(value) and 0 <= value <= 20 else None


class _TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._table = None
        self._row = None
        self._cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._end_row()
            self._table = []
            self.tables.append(self._table)
        elif tag == "tr":
            self._end_row()
            if self._table is not None:
                self._row = []
        elif tag in ("td", "th"):
            self._end_cell()
            if self._row is not None:
                self._cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self._end_cell()
        elif tag == "tr":
            self._end_row()
        elif tag == "table":
            self._end_row()
            self._table = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def _end_cell(self):
        if self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None

    def _end_row(self):
        self._end_cell()
        if self._row is not None and self._table is not None:
            self._table.append(self._row)
        self._row = None


def _column_index(headers: list[str], *keywords: str) -> int | None:
    for index, header in enumerate(headers):
        if any(keyword in header for keyword in keywords):
            return index
    return None


def _find_columns(header_row: list[str]) -> dict | None:
    headers = [header.lower() for header in header_row]
    columns = {
        "bank": _column_index(headers, "bank"),
        "highest": _column_index(headers, "highest"),
        "1y": _column_index(headers, "1-year", "1 year"),
        "3y": _column_index(headers, "3-year", "3 year"),
        "5y": _column_index(headers, "5-year", "5 year"),
        "senior": next(
            (i for i, h in enumerate(headers) if "senior" in h and ("additional" in h or "extra" in h)),
            None,
        ),
    }
    has_rate_column = any(columns[key] is not None for key in ("1y", "3y", "5y"))
    if columns["bank"] is None or not has_rate_column:
        return None
    return columns


def _cell(row: list[str], index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    return row[index]


def _banks_from_rows(rows: list[list[str]], columns: dict) -> list[dict]:
    banks = []
    for row in rows:
        name = _cell(row, columns["bank"])
        if not name:
            continue
        rate_1y = _parse_rate(_cell(row, columns["1y"]))
        rate_3y = _parse_rate(_cell(row, columns["3y"]))
        rate_5y = _parse_rate(_cell(row, columns["5y"]))
        if rate_1y is None and rate_3y is None and rate_5y is None:
            continue
        banks.append({
            "bank_name": name,
            "bank_type": classify_bank_type(name),
            "highest_rate": _parse_rate(_cell(row, columns["highest"])),
            "rate_1y": rate_1y,
            "rate_3y": rate_3y,
            "rate_5y": rate_5y,
            "senior_extra": _parse_rate(_cell(row, columns["senior"])),
        })
    return banks


def parse_rates_html(html: str) -> list[dict]:
    parser = _TableParser()
    parser.feed(html)
    banks = []
    for table in parser.tables:
        columns = _find_columns(table[0]) if len(table) >= 2 else None
        if columns:
            banks = _banks_from_rows(table[1:], columns)
            break
    if not banks:
        raise ValueError("No FD rate table found on the page.")
    return banks


def extract_as_of_date(html: str) -> str | None:
    match = re.search(r'"dateModified"\s*:\s*"(\d{4}-\d{2}-\d{2})', html)
    return match.group(1) if match else None


def _cache_path() -> str:
    return os.path.join(config.DATA_DIR, _CACHE_FILENAME)


def save_cached_rates(snapshot: dict) -> None:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(_cache_path(), "w", encoding="utf-8") as fh:
        json.dump(snapshot, fh, indent=2)


def load_cached_rates() -> dict:
    try:
        with open(_cache_path(), "r", encoding="utf-8") as fh:
            snapshot = json.load(fh)
        if isinstance(snapshot, dict) and isinstance(snapshot.get("banks"), list) and snapshot["banks"]:
            return snapshot
    except Exception:
        pass
    return copy.deepcopy(_BUNDLED_SNAPSHOT)


def fetch_rates(url: str | None = None, timeout: int = 20) -> dict:
    url = url or get_rates_source_url()
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "text/html"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        html = response.read().decode(charset, errors="replace")

    snapshot = {
        "source_url": url,
        "as_of": extract_as_of_date(html),  # Page metadata, never proof of a bank rate
        "date_kind": "page_modified",
        "fetched_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "is_bundled": False,
        "banks": parse_rates_html(html),
    }
    save_cached_rates(snapshot)
    return snapshot


def is_stale(snapshot: dict, today: date | None = None) -> bool:
    try:
        as_of = date.fromisoformat(snapshot["as_of"])
        age = ((today or date.today()) - as_of).days
        return age < 0 or age > RATES_STALE_AFTER_DAYS
    except (KeyError, TypeError, ValueError):
        return True
