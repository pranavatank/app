"""Scheduler reload and replacement must not redirect an old worker."""

import importlib

import core.backup_manager as backup_manager


class FakeEvent:
    def __init__(self):
        self.is_stopped = False
        self.waits = []

    def set(self):
        self.is_stopped = True

    def wait(self, timeout=None):
        self.waits.append(timeout)
        return self.is_stopped


class FakeThread:
    instances = []

    def __init__(self, target, daemon, name):
        self.target = target
        self.daemon = daemon
        self.name = name
        self.alive = False
        self.instances.append(self)

    def start(self):
        self.alive = True

    def is_alive(self):
        return self.alive


def _fake_scheduler(monkeypatch):
    backup_manager.stop_scheduler()
    FakeThread.instances.clear()
    monkeypatch.setattr(backup_manager.threading, "Event", FakeEvent)
    monkeypatch.setattr(backup_manager.threading, "Thread", FakeThread)


def test_old_worker_uses_its_own_stop_event_after_restart(monkeypatch):
    _fake_scheduler(monkeypatch)
    backups = []
    monkeypatch.setattr(backup_manager, "create_backup", lambda: backups.append("created"))

    old_thread = backup_manager.schedule_periodic_backups(1)
    old_event = backup_manager._stop_event
    new_thread = backup_manager.schedule_periodic_backups(2)
    new_event = backup_manager._stop_event

    assert old_event.is_stopped
    assert not new_event.is_stopped
    old_thread.target()

    assert old_event.waits == [3600.0]
    assert new_event.waits == []
    assert backups == []
    assert backup_manager._scheduler_thread is new_thread
    assert backup_manager.get_scheduler_interval_hours() == 2.0


def test_module_reload_preserves_live_scheduler_handles(monkeypatch):
    _fake_scheduler(monkeypatch)
    thread = backup_manager.schedule_periodic_backups(3.5)
    stop_event = backup_manager._stop_event

    reloaded = importlib.reload(backup_manager)

    assert reloaded is backup_manager
    assert backup_manager._scheduler_thread is thread
    assert backup_manager._stop_event is stop_event
    assert backup_manager.is_scheduler_running()
    assert backup_manager.get_scheduler_interval_hours() == 3.5

    backup_manager.stop_scheduler()
    assert stop_event.is_stopped
