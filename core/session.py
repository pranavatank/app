"""
core/session.py — Global session state for the logged-in app instance.
Holds AES key, selected person, account, financial year, and privacy flag.
"""

import json
import os
from config import get_current_financial_year

_CONFIG_DIR  = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_CONFIG_FILE = os.path.join(_CONFIG_DIR, "theme_prefs.json")


class Session:
    """Singleton-style session object. Import and use `session` instance."""

    def __init__(self):
        self.aes_key:          bytes | None = None
        self.is_authenticated: bool         = False
        self.selected_person_id:   int | None  = None   # None = All persons
        self.selected_account_id:  int | None  = None   # None = All accounts
        self.selected_fy:          str          = get_current_financial_year()
        self.privacy_mode:         bool         = False
        self.theme:                str          = "light"  # light or dark
        self.sidebar_open:        bool         = self._load_sidebar_pref()

    # ── Auth ─────────────────────────────────────────────────────────────────

    def login(self, aes_key: bytes) -> None:
        self.aes_key          = aes_key
        self.is_authenticated = True

    def logout(self) -> None:
        self.aes_key          = None
        self.is_authenticated = False
        self.selected_person_id  = None
        self.selected_account_id = None
        self.selected_fy         = get_current_financial_year()
        self.privacy_mode        = False

    # ── Selectors ────────────────────────────────────────────────────────────

    def set_person(self, person_id: int | None) -> None:
        self.selected_person_id  = person_id
        self.selected_account_id = None  # reset account when person changes

    def set_account(self, account_id: int | None) -> None:
        self.selected_account_id = account_id

    def set_financial_year(self, fy: str) -> None:
        self.selected_fy = fy

    def set_privacy_mode(self, enabled: bool) -> None:
        self.privacy_mode = enabled

    def set_theme(self, theme: str) -> None:
        """Set theme (light or dark)."""
        self.theme = theme

    def set_sidebar_open(self, open_: bool) -> None:
        """Persist sidebar expanded/collapsed state for the session."""
        self.sidebar_open = bool(open_)
        self._save_sidebar_pref()

    def is_sidebar_open(self) -> bool:
        return bool(self.sidebar_open)

    def get_theme(self) -> str:
        """Get current theme."""
        return self.theme

    @staticmethod
    def _load_sidebar_pref() -> bool:
        """Load saved sidebar state from theme_prefs.json. Default to True (expanded) on first run."""
        try:
            if os.path.exists(_CONFIG_FILE):
                with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data.get("sidebar_open", True)
        except Exception:
            pass
        return True  # Default to expanded on first run

    def _save_sidebar_pref(self) -> None:
        """Save sidebar state to theme_prefs.json alongside theme preference."""
        try:
            os.makedirs(_CONFIG_DIR, exist_ok=True)
            data = {}
            # Preserve existing theme preference if it exists
            if os.path.exists(_CONFIG_FILE):
                with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            # Update sidebar_open with current instance state
            data["sidebar_open"] = self.sidebar_open
            with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    # ── Helpers ───────────────────────────────────────────────────────────────

    def mask(self, value: float) -> str:
        """Return '****' if privacy mode is on, else formatted currency."""
        if self.privacy_mode:
            return "₹ ****"
        return f"₹ {value:,.2f}"

    def __repr__(self):
        return (
            f"Session(authenticated={self.is_authenticated}, "
            f"person={self.selected_person_id}, "
            f"account={self.selected_account_id}, "
            f"fy={self.selected_fy}, "
            f"privacy={self.privacy_mode})"
        )


# Global session instance — import this everywhere
session = Session()
