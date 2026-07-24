"""
core/session.py — Global session state for the logged-in app instance.
Holds AES key, selected person, account, financial year, and privacy flag.
"""

from config import get_current_financial_year


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
        self.sidebar_open:        bool         = False

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

    def is_sidebar_open(self) -> bool:
        return bool(self.sidebar_open)

    def get_theme(self) -> str:
        """Get current theme."""
        return self.theme

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
