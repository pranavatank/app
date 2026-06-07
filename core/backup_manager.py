"""core/backup_manager.py — Simple scheduled backup helper."""
import os
import threading
from datetime import datetime
import shutil
from typing import Optional

from config import BACKUP_DIR, DB_PATH

# Scheduler globals
_scheduler_thread: threading.Thread | None = None
_stop_event: threading.Event | None = None
_current_interval_hours: float = 24.0


def _ensure_backup_dir():
    os.makedirs(BACKUP_DIR, exist_ok=True)


def create_backup() -> Optional[str]:
    """Create a timestamped copy of the database in BACKUP_DIR. Returns path or None."""
    try:
        _ensure_backup_dir()
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        base = os.path.basename(DB_PATH)
        dest = os.path.join(BACKUP_DIR, f"{ts}-{base}")
        shutil.copy2(DB_PATH, dest)
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
    _stop_event = threading.Event()
    _current_interval_hours = float(interval_hours or 24.0)

    def _loop():
        while not _stop_event.wait(_current_interval_hours * 3600):
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
