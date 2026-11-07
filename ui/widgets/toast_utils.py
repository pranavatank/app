"""Thread-safe, backwards-compatible global toast helpers."""
from PySide6.QtCore import QObject, Signal, Qt, QTimer
from PySide6.QtWidgets import QApplication, QWidget
import weakref
import shiboken6
import threading
from .toast import ToastContainer

_toast_container = None
_containers = {}
_orphaned = []
_default_host = None


def _is_visible_host(candidate, source=None):
    if candidate is None or candidate is source or not shiboken6.isValid(candidate): return False
    try:
        if not candidate.isVisible(): return False
        return candidate.isWindow()
    except RuntimeError:
        return False


def _resolve_host(source=None):
    app = QApplication.instance()
    if source is not None and shiboken6.isValid(source):
        try:
            parent = source.parentWidget()
            while parent is not None:
                top = parent.window()
                if _is_visible_host(top, source): return top
                parent = parent.parentWidget()
        except RuntimeError:
            pass
    default = _default_host() if _default_host else None
    if _is_visible_host(default, source): return default
    if app is None: return None
    for candidate in (app.activeModalWidget(), app.activeWindow()):
        if _is_visible_host(candidate, source): return candidate
    for candidate in app.topLevelWidgets():
        if not _is_visible_host(candidate, source): continue
        try:
            if candidate.windowType() in (Qt.WindowType.Popup, Qt.WindowType.ToolTip, Qt.WindowType.Tool): continue
        except RuntimeError:
            continue
        return candidate
    return None


class _ToastDispatcher(QObject):
    requested = Signal(object, str, object, object, object)
    def __init__(self):
        super().__init__(); self.requested.connect(self._show, Qt.ConnectionType.QueuedConnection)
    def _show(self, message, variant, duration_ms, title, preferred):
        self.show_for(message, variant, duration_ms, title, preferred)
    def show_for(self, message, variant, duration_ms, title, preferred, avoid=None):
        global _toast_container
        app = QApplication.instance()
        if app is None: return
        modal = app.activeModalWidget()
        host = modal if _is_visible_host(modal, avoid) else None
        if host is None and preferred is not None and shiboken6.isValid(preferred):
            host = preferred.window()
        if not _is_visible_host(host, avoid): host = _resolve_host(avoid)
        if host is None and _toast_container is not None and shiboken6.isValid(_toast_container):
            candidate = _toast_container.content_area
            if _is_visible_host(candidate, avoid): host = candidate.window()
        if host is None:
            _orphaned.append((str(message), variant, duration_ms, title)); return
        key = id(host); entry = _containers.get(key)
        container = entry[1] if entry and entry[0]() is host and shiboken6.isValid(entry[1]) else None
        if container is None:
            container = ToastContainer(host); _containers[key] = (weakref.ref(host), container)
            container.host_unavailable.connect(lambda requests, source, source_key=key: self._handoff_requests(requests, source_key, source))
            container.host_destroyed.connect(lambda requests, source, source_key=key: self._handoff_requests(requests, source_key, source))
            container.host_available.connect(lambda target=host: self._deliver_orphans(target))
            host.destroyed.connect(lambda _=None, k=key, c=container, h=host: self._host_destroyed(k, c, h))
        _toast_container = container
        if _orphaned:
            queued = list(_orphaned); _orphaned.clear()
            for item in queued: container.show_toast(*item[:3], title=item[3])
        container.show_toast(str(message), variant, duration_ms, title)
    def _handoff(self, source):
        global _toast_container
        app = QApplication.instance()
        if not shiboken6.isValid(source): return
        requests = source.drain_requests()
        if not requests: return
        host = _resolve_host(source.content_area)
        if host is None and _toast_container is not source:
            host = _toast_container.content_area if _toast_container and shiboken6.isValid(_toast_container) else None
        if host is None:
            _orphaned.extend(requests); return
        for msg, variant, remaining, title in requests:
            self.show_for(msg, variant, remaining, title, host, avoid=source.content_area)
    def _deliver_orphans(self, host):
        if not _orphaned or not shiboken6.isValid(host): return
        queued = list(_orphaned); _orphaned.clear()
        for msg, variant, duration, title in queued:
            self.show_for(msg, variant, duration, title, host)
    def _host_destroyed(self, key, container, host):
        requests = container.drain_requests() if shiboken6.isValid(container) else []
        _containers.pop(key, None)
        self._handoff_requests(requests, key, host)
    def _handoff_requests(self, requests, source_key, source_host=None):
        if not requests: return
        host = _resolve_host(source_host)
        if host is None:
            _orphaned.extend(requests); return
        for msg, variant, remaining, title in requests:
            self.show_for(msg, variant, remaining, title, host, avoid=source_host)

_dispatcher = None
_dispatcher_lock = threading.Lock()
def _get_dispatcher():
    global _dispatcher
    if _dispatcher is None:
        with _dispatcher_lock:
            if _dispatcher is None:
                _dispatcher = _ToastDispatcher()
                app = QApplication.instance()
                if app: _dispatcher.moveToThread(app.thread())
    return _dispatcher

def init_toast_container(content_area):
    """Initialize or replace the default host used when no window is active."""
    global _toast_container, _default_host
    _get_dispatcher()
    key = id(content_area); entry = _containers.get(key)
    old = entry[1] if entry and entry[0]() is content_area and shiboken6.isValid(entry[1]) else None
    if old is None:
        old = ToastContainer(content_area); _containers[key] = (weakref.ref(content_area), old)
        old.host_unavailable.connect(lambda requests, source, source_key=key: _get_dispatcher()._handoff_requests(requests, source_key, source))
        old.host_destroyed.connect(lambda requests, source, source_key=key: _get_dispatcher()._handoff_requests(requests, source_key, source))
        old.host_available.connect(lambda target=content_area: _get_dispatcher()._deliver_orphans(target))
        content_area.destroyed.connect(lambda _=None, k=key, c=old, h=content_area: _get_dispatcher()._host_destroyed(k, c, h))
    _toast_container = old
    _default_host = weakref.ref(content_area)
    return old

def show_toast(message: str, variant: str = "info", duration_ms=None, title=None, parent=None):
    """Queue a toast on the active host; calls are safe from worker threads."""
    _get_dispatcher().requested.emit(message, variant, duration_ms, title, parent)

def show_success(message, duration_ms=None, title=None, parent=None): show_toast(message, "success", duration_ms, title, parent)
def show_info(message, duration_ms=None, title=None, parent=None): show_toast(message, "info", duration_ms, title, parent)
def show_warning(message, duration_ms=None, title=None, parent=None): show_toast(message, "warning", duration_ms, title, parent)
def show_danger(message, duration_ms=None, title=None, parent=None): show_toast(message, "danger", duration_ms, title, parent)
