"""core/settings.py — Simple JSON-backed settings helper."""
import json
import os
from threading import Lock
from typing import Any

from config import DATA_DIR

_LOCK = Lock()
_PATH = os.path.join(DATA_DIR, "settings.json")
_DEFAULTS = {
    "scheduled_backups_enabled": True,
    "scheduled_backups_interval_hours": 24,
    "show_onboarding_on_startup": True,
}


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def load_settings() -> dict:
    _ensure_dir()
    try:
        with _LOCK:
            if not os.path.exists(_PATH):
                return dict(_DEFAULTS)
            with open(_PATH, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            result = dict(_DEFAULTS)
            result.update(data or {})
            return result
    except Exception:
        return dict(_DEFAULTS)


def save_settings(d: dict) -> None:
    _ensure_dir()
    with _LOCK:
        try:
            cur = load_settings()
            cur.update(d or {})
            with open(_PATH, "w", encoding="utf-8") as fh:
                json.dump(cur, fh, indent=2)
        except Exception:
            pass


def get_setting(key: str, default: Any = None) -> Any:
    return load_settings().get(key, default)


def set_setting(key: str, value: Any) -> None:
    save_settings({key: value})
