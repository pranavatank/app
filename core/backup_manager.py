"""core/backup_manager.py — Simple scheduled backup helper."""
import os
import threading
from datetime import datetime, timezone
from typing import Optional

from config import BACKUP_DIR, DB_PATH
from core.database import backup_database

# Preserve a live scheduler when this module is reloaded (for example by the
# app's hard-refresh path). importlib.reload reuses the module dictionary, so
# unconditional assignments here would orphan its daemon thread.
if "_scheduler_thread" not in globals():
    _scheduler_thread: threading.Thread | None = None
if "_stop_event" not in globals():
    _stop_event: threading.Event | None = None
if "_current_interval_hours" not in globals():
    _current_interval_hours: float = 24.0

# A completed thread is no longer an active handle. Clear stale state on reload
# while retaining the event/thread pair for any worker that is still running.
if _scheduler_thread is not None and not _scheduler_thread.is_alive():
    _scheduler_thread = None
    _stop_event = None


def _ensure_backup_dir():
    os.makedirs(BACKUP_DIR, exist_ok=True)


def create_backup() -> Optional[str]:
    """Create a timestamped copy of the database in BACKUP_DIR. Returns path or None."""
    try:
        _ensure_backup_dir()
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        base = os.path.basename(DB_PATH)
        dest = os.path.join(BACKUP_DIR, f"{ts}-{base}")
        backup_database(dest)
        return dest
    except Exception:
        return None


def schedule_periodic_backups(interval_hours: float = 24.0) -> threading.Thread:
    """Start a daemon thread that creates backups every interval_hours.

    Returns the Thread object.
    """
    global _scheduler_thread, _stop_event, _current_interval_hours
    # Stop existing scheduler if running
    stop_scheduler()
    stop_event = threading.Event()
    interval = float(interval_hours or 24.0)
    _stop_event = stop_event
    _current_interval_hours = interval

    def _loop():
        # Each worker owns its event and interval. A replacement schedule may
        # update module globals while this daemon is still exiting.
        while not stop_event.wait(interval * 3600):
            create_backup()

    _scheduler_thread = threading.Thread(target=_loop, daemon=True, name="BackupScheduler")
    _scheduler_thread.start()
    return _scheduler_thread


def stop_scheduler() -> None:
    """Stop the periodic backup scheduler if running."""
    global _scheduler_thread, _stop_event
    try:
        if _stop_event is not None:
            _stop_event.set()
    finally:
        _stop_event = None
        _scheduler_thread = None


def is_scheduler_running() -> bool:
    return _scheduler_thread is not None and _scheduler_thread.is_alive()


def get_scheduler_interval_hours() -> float:
    return float(_current_interval_hours)
