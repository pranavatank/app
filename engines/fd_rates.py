"""Validated FD quote metadata shared by the official-bank rate adapters."""
from dataclasses import dataclass
from datetime import date,datetime,timedelta,timezone
from urllib.parse import urlparse


@dataclass(frozen=True)
class RateCard:
    id: str
    bank: str
    min_days: int
    max_days: int
    rate: float
    customer: str
    effective_from: str
    checked_at: str
    source_url: str
    min_amount: float = 1000
    max_amount: float = 29_999_999
    compounding: int = 4
    day_basis: str = "actual"
    verified: bool = False
    origin: str = "manual"
    evidence_hash: str = ""
    tenure_label: str = ""
    bank_insured: bool = False
    simple_until_days: int = 0

    def __post_init__(self):
        from math import isfinite
        if not isinstance(self.verified, bool) or not isinstance(self.bank_insured, bool):
            raise ValueError("Verification and insurance flags must be boolean values.")
        if not isinstance(self.min_days,int) or not isinstance(self.max_days,int):
            raise ValueError("Tenure endpoints must be whole days.")
        if not isinstance(self.simple_until_days,int) or not 0<=self.simple_until_days<=3653:
            raise ValueError("Invalid simple-interest tenure boundary.")
        if (not self.id.strip() or not self.bank.strip() or self.customer not in ("general", "senior")
                or not 1 <= self.min_days <= self.max_days <= 3653
                or not isfinite(self.rate) or not 0 < self.rate <= 20
                or not isfinite(self.min_amount) or not isfinite(self.max_amount)
                or not 0 < self.min_amount <= self.max_amount
                or self.compounding not in (1, 2, 4, 12)
                or self.day_basis not in ("actual", "365")
                or self.origin not in ("manual", "official_page")):
            raise ValueError("Invalid rate card fields; review tenure, rate, amounts and customer category.")
        date.fromisoformat(self.effective_from)
        stamp = datetime.fromisoformat(self.checked_at)
        if stamp.tzinfo is None:
            raise ValueError("Verification timestamp must include timezone.")
        parsed = urlparse(self.source_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("A public HTTPS bank source URL is required.")

    def status(self, as_of: date, now: datetime | None = None) -> str:
        now = now or datetime.now(timezone.utc)
        stamp = datetime.fromisoformat(self.checked_at)
        if date.fromisoformat(self.effective_from) > as_of:
            return "Not effective yet"
        if stamp > now + timedelta(minutes=5):
            return "Invalid future timestamp"
        # Calendar-date as well as wall-clock checks prevent using a snapshot
        # in a backdated/future plan, or relabelling old cached data as fresh.
        if as_of != now.astimezone().date():
            return "Refresh on the booking date"
        if now - stamp > timedelta(hours=24):
            return "Expired — refresh / reconfirm"
        if not self.verified:
            return "Terms review required"
        return "Bank-confirmed" if self.origin == "manual" else "Official page · reviewed"

    def usable(self, as_of: date) -> bool:
        return self.status(as_of) in ("Bank-confirmed", "Official page · reviewed")
