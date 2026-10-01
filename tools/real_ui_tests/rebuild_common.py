r"""tools/real_ui_tests/rebuild_common.py — shared tooling for the DB rebuild
(Phase 0-2 of the rebuild plan). Not committed; untracked helper.

Interaction model: full OS-level input for every interaction (real pyautogui
mouse movement + click at the widget's actual physical screen coordinates,
real pyautogui keystrokes for typing), per the plan's Appendix os_click/
os_type/os_select_combo/os_set_date design. This is a course correction:
P2.0-P2.3 were originally driven via RealUIHarness.click()/type_into()
(QTest-driven, synthetic — no real cursor movement, no real OS hit-testing/
focus/event delivery). That is tracked as a known coverage gap for those
steps (see PROGRESS.md). Every step from P2.4 onward uses this OS-level path.
"""
import os
import sys
import re
import time
import json
import shutil
import sqlite3
import hashlib
import traceback
import faulthandler
import datetime as _dt
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE))

import pyautogui
import win32api
import win32con
import win32gui
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from tools.real_ui_test_harness import RealUIHarness, find_by_accessible_name, find_dialog_by_title

PDATA = BASE / "data" / "PersonalData" / "Pranav"
PWFILE = PDATA / "password.txt"
RUIH_DIR = BASE / "tools" / "real_ui_tests" / "screenshots" / "rebuild"
RUIH_DIR.mkdir(parents=True, exist_ok=True)
BACKUPS = BASE / "backups"
BACKUPS.mkdir(parents=True, exist_ok=True)
PROGRESS_MD = RUIH_DIR / "PROGRESS.md"
REAL_DB_PATH = BASE / "data" / "financial.db"

_SECRET_PATTERNS = []  # populated by read_secret() calls; masked in redacting_logger


# --------------------------------------------------------------------- secrets --

def read_secret(kind: str) -> str:
    """kind: 'master', 'ais_tis', 'equitas'. Reads password.txt at runtime.
    Never prints/logs the value. Raises if not found."""
    if not PWFILE.exists():
        raise RuntimeError(f"password file not found: {PWFILE}")
    prefix_map = {
        "master": ("master",),
        "ais_tis": ("ais", "tis"),
        "equitas": ("equitas",),
    }
    needles = prefix_map[kind]
    with open(PWFILE, "r", encoding="utf-8") as f:
        for line in f:
            low = line.lower()
            if all(n in low for n in needles) and ":" in line:
                val = line.split(":", 1)[-1].strip()
                if val:
                    _SECRET_PATTERNS.append(val)
                    return val
    raise RuntimeError(f"no '{kind}' line found in {PWFILE}")


def redact(text: str) -> str:
    for s in _SECRET_PATTERNS:
        if s:
            text = text.replace(s, "***")
    text = re.sub(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", "XXXXX9999X", text)
    text = re.sub(r"\d{9,}", lambda m: "9" * len(m.group(0)), text)
    return text


class RedactingLogger:
    def __init__(self, script_name: str):
        self.path = RUIH_DIR / f"{script_name}.log"
        self._fh = open(self.path, "a", encoding="utf-8")

    def log(self, *parts):
        msg = " ".join(str(p) for p in parts)
        msg = redact(msg)
        line = f"[{_dt.datetime.now().isoformat(timespec='seconds')}] {msg}"
        print(line)
        self._fh.write(line + "\n")
        self._fh.flush()

    def close(self):
        self._fh.close()


def redacting_logger(script_name: str) -> RedactingLogger:
    return RedactingLogger(script_name)


# ------------------------------------------------------------------ bootstrap --

def bootstrap_app():
    """Mirrors main.launch_app() minus app.exec(). Returns the QApplication."""
    from ui.logo import set_windows_app_user_model_id, set_app_icon, ensure_logo_assets
    from ui.messagebox_utils import install_copyable_error_dialogs
    from core.database import initialise_database
    from config import DATA_DIR, BACKUP_DIR, APP_NAME, APP_VERSION
    from PySide6.QtGui import QFont

    set_windows_app_user_model_id()
    ensure_logo_assets()
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    install_copyable_error_dialogs()
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    set_app_icon(app)
    app.setFont(QFont("Segoe UI", 10))

    from ui.theme import Theme, ThemeManager
    ThemeManager.load_and_apply()
    app.setStyleSheet(Theme.get_stylesheet())

    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)
    initialise_database()
    return app


# ---------------------------------------------------------------- focus/window --

def adopt_window(w):
    hwnd = int(w.winId())
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        try:
            import win32process
            fg_hwnd = win32gui.GetForegroundWindow()
            fg_thread, _ = win32process.GetWindowThreadProcessId(fg_hwnd)
            cur_thread = win32api.GetCurrentThreadId()
            win32process.AttachThreadInput(cur_thread, fg_thread, True)
            try:
                win32gui.SetForegroundWindow(hwnd)
            finally:
                win32process.AttachThreadInput(cur_thread, fg_thread, False)
        except Exception as e:
            print(f"WARNING: adopt_window focus fallback failed: {e!r}")
    win32gui.BringWindowToTop(hwnd)


def assert_foreground(w, retries=3):
    hwnd = int(w.winId())
    for _ in range(retries):
        if win32gui.GetForegroundWindow() == hwnd:
            return True
        adopt_window(w)
        time.sleep(0.3)
    raise RuntimeError("FOCUS failure: could not bring window to foreground")


# ------------------------------------------------------------------- clicking --
# Full OS-level path (Appendix design): real pyautogui mouse movement + click
# at the widget's actual physical screen coordinates, with a widgetAt/
# WindowFromPoint guard to confirm the click will land on the intended widget
# before firing it, and real pyautogui keystrokes for typing. This exercises
# genuine OS hit-testing, window focus and event delivery -- not just Qt's
# internal state.

def _verify_click_target(widget, global_pt, px, py):
    """Guard (Appendix step 4): confirm the OS click will actually land on the
    intended widget -- QApplication.widgetAt(logical_pt) must resolve to the
    widget or a descendant of it, AND win32gui.WindowFromPoint(physical) must
    belong to our own process. Returns the blocking widget's type name on
    failure (or None on success) instead of raising, so callers can decide
    whether a transient overlay (e.g. a fading toast) is worth retrying."""
    at = QApplication.widgetAt(global_pt)
    if at is None or not (at is widget or widget.isAncestorOf(at) or at.isAncestorOf(widget)):
        return type(at).__name__ if at is not None else "<nothing>"
    import win32process
    hwnd = win32gui.WindowFromPoint((px, py))
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    if pid != os.getpid():
        return f"foreign hwnd (pid {pid})"
    return None


def os_click(harness: RealUIHarness, root, accessible_name, wait=0.8, double=False):
    widget = find_by_accessible_name(root, accessible_name)
    if widget is None:
        raise LookupError(f"widget not found: {accessible_name!r}")
    harness.scroll_into_view(widget)
    if not widget.isVisible() or not widget.isEnabled():
        raise RuntimeError(f"widget not clickable: {accessible_name!r} visible={widget.isVisible()} enabled={widget.isEnabled()}")
    assert_foreground(widget.window())
    center = widget.mapToGlobal(widget.rect().center())
    px, py = harness.to_physical(center)
    # Real click delivery respects on-screen Z-order (unlike QTest, which
    # targets the widget object directly and never sees overlays). A toast
    # notification or similar transient overlay can sit over the target for a
    # couple of seconds; retry the guard briefly before failing for real.
    blocker = _verify_click_target(widget, center, px, py)
    if blocker is not None:
        # FINDING (Medium): ui/widgets/toast.py's ToastContainer and
        # toast_utils.init_toast_container() both call
        # setAttribute(WA_TransparentForMouseEvents, False) despite a comment
        # claiming click-through ("Allow mouse events to pass through") --
        # False means OPAQUE to mouse hit-testing, so the container (sized to
        # the full content area) blocks every OS-level click anywhere in the
        # window for as long as a toast is alive (default duration_ms=4000 +
        # fade_out). Retry budget below is sized to comfortably outlast that.
        for _ in range(16):
            harness.settle(0.5)
            blocker = _verify_click_target(widget, center, px, py)
            if blocker is None:
                break
        if blocker is not None:
            raise RuntimeError(
                f"widgetAt/WindowFromPoint guard failed for {accessible_name!r} at {center}: blocked by {blocker}"
            )
    pyautogui.moveTo(px, py, duration=0.2)
    if double:
        pyautogui.doubleClick()
    else:
        pyautogui.click()
    harness.settle(wait)
    print(f"os_click({accessible_name!r}) logical=({center.x()},{center.y()}) physical=({px},{py})")
    return widget


def os_click_widget(harness: RealUIHarness, widget, wait=0.8, double=False):
    """Same as os_click() but takes an already-resolved widget (e.g. one found
    by a property lookup rather than accessibleName())."""
    harness.scroll_into_view(widget)
    if not widget.isVisible() or not widget.isEnabled():
        raise RuntimeError(f"widget not clickable: {widget!r} visible={widget.isVisible()} enabled={widget.isEnabled()}")
    assert_foreground(widget.window())
    center = widget.mapToGlobal(widget.rect().center())
    px, py = harness.to_physical(center)
    blocker = _verify_click_target(widget, center, px, py)
    if blocker is not None:
        for _ in range(16):
            harness.settle(0.5)
            blocker = _verify_click_target(widget, center, px, py)
            if blocker is None:
                break
        if blocker is not None:
            raise RuntimeError(f"widgetAt/WindowFromPoint guard failed for {widget!r} at {center}: blocked by {blocker}")
    pyautogui.moveTo(px, py, duration=0.2)
    if double:
        pyautogui.doubleClick()
    else:
        pyautogui.click()
    harness.settle(wait)
    print(f"os_click_widget({widget!r}) logical=({center.x()},{center.y()}) physical=({px},{py})")
    return widget


def os_type_widget(harness: RealUIHarness, widget, text, secret=False, retries=3):
    """Direct widget version of os_type. Takes the widget directly (e.g. found
    by property lookup rather than accessibleName()), clears it, types text,
    and verifies readback. Retries on mismatch."""
    last_ok = None
    for attempt in range(1, retries + 1):
        os_click_widget(harness, widget, wait=0.3)
        pyautogui.hotkey("ctrl", "a")
        harness.settle(0.3)
        pyautogui.press("backspace")
        harness.settle(0.3)
        pyautogui.write(text, interval=0.05)
        harness.settle(0.8)
        # Readback: QLineEdit.text(), QDoubleSpinBox/QSpinBox.value(), QTextEdit.toPlainText()
        if hasattr(widget, "text") and callable(widget.text):
            ok = widget.text() == text
        elif hasattr(widget, "value") and callable(widget.value):
            try:
                ok = abs(widget.value() - float(text)) < 0.005
            except (ValueError, TypeError):
                ok = None
        elif hasattr(widget, "toPlainText") and callable(widget.toPlainText):
            ok = widget.toPlainText() == text
        else:
            ok = None
        last_ok = ok
        if ok is not False:
            break
        print(f"os_type_widget({widget!r}) attempt {attempt}/{retries} readback mismatch, retrying")
    if secret:
        print(f"os_type_widget({widget!r}) readback_ok={last_ok}")
    else:
        print(f"os_type_widget({widget!r}) = {text!r} readback_ok={last_ok}")
    if last_ok is False:
        raise RuntimeError(f"readback mismatch for {widget!r} after {retries} attempts")
    return widget


def os_type(harness: RealUIHarness, root, accessible_name, text, secret=False, wait=0.3, retries=3):
    # Real OS-level keystroke delivery is genuinely more fragile than QTest's
    # synthetic path -- it depends on actual Windows focus and message-queue
    # timing, which can occasionally drop or race (see the harness's own
    # click_via_os()/type_text_via_os() docstring). Retry the whole
    # click-clear-type sequence a few times on readback mismatch rather than
    # failing the entire script on one transient miss.
    widget = find_by_accessible_name(root, accessible_name)
    if widget is None:
        raise LookupError(f"widget not found: {accessible_name!r}")
    os_type_widget(harness, widget, text, secret=secret, retries=retries)
    if secret:
        print(f"os_type({accessible_name!r}) readback_ok=True")
    else:
        print(f"os_type({accessible_name!r}) = {text!r} readback_ok=True")
    return widget


def answer_message_box(harness: RealUIHarness, app, button, expect_title=None):
    """Prearm wrapper for QMessageBox. Asserts activeModalWidget() is a QMessageBox,
    stores its title and redacted text in .info dict, optionally asserts title matches
    expect_title, then clicks the button. If title mismatch, stores error and rejects.
    Call BEFORE the click that opens the box."""
    info = {"title": None, "text": None, "error": None}

    def cb():
        try:
            box = QApplication.activeModalWidget()
            if not isinstance(box, QMessageBox):
                raise AssertionError(f"expected QMessageBox, got {type(box).__name__}")
            info["title"] = box.windowTitle()
            info["text"] = redact(box.text())
            if expect_title is not None and box.windowTitle() != expect_title:
                info["error"] = f"title mismatch: expected {expect_title!r}, got {info['title']!r}"
                box.reject()
                return
            os_click_widget(harness, box.button(button), wait=0.6)
        except Exception as e:
            info["error"] = repr(e)
            box = QApplication.activeModalWidget()
            if isinstance(box, QMessageBox):
                box.reject()
            raise

    prearm_obj = prearm(app, cb)
    prearm_obj.info = info
    return prearm_obj


def answer_modal_dialog(harness: RealUIHarness, app, dialog_cls, title, fill_fn):
    """Prearm wrapper for a modal dialog. Asserts activeModalWidget() is dialog_cls
    with windowTitle()==title, then calls fill_fn(dlg). On exception, rejects the
    dialog and stores error in .info. Call BEFORE the click that opens the dialog."""
    info = {"error": None}

    def cb():
        try:
            dlg = QApplication.activeModalWidget()
            if not isinstance(dlg, dialog_cls):
                raise AssertionError(f"expected {dialog_cls.__name__}, got {type(dlg).__name__}")
            if dlg.windowTitle() != title:
                raise AssertionError(f"title mismatch: expected {title!r}, got {dlg.windowTitle()!r}")
            fill_fn(dlg)
        except Exception as e:
            info["error"] = repr(e)
            dlg = QApplication.activeModalWidget()
            if dlg is not None:
                dlg.reject()
            raise

    prearm_obj = prearm(app, cb)
    prearm_obj.info = info
    return prearm_obj


def toast_texts():
    """Return redacted texts of all visible Toast instances."""
    from ui.widgets.toast import Toast
    texts = []
    for w in QApplication.instance().allWidgets():
        if isinstance(w, Toast) and w.isVisible():
            if hasattr(w, "message_label") and w.message_label is not None:
                texts.append(redact(w.message_label.text()))
    return texts


def find_button(root, text):
    """Find first visible QAbstractButton in root with text().strip()==text.
    Raise LookupError if none found."""
    from PySide6.QtWidgets import QAbstractButton
    for btn in root.findChildren(QAbstractButton):
        if btn.isVisible() and btn.text().strip() == text:
            return btn
    raise LookupError(f"button not found: {text!r}")


def label_scan(root, words):
    """Return redacted texts of visible QLabels whose lowercase text contains
    any of the given words (case-insensitive search)."""
    from PySide6.QtWidgets import QLabel
    texts = []
    words_lower = [w.lower() for w in words]
    for label in root.findChildren(QLabel):
        if label.isVisible():
            label_text = label.text().lower()
            if any(w in label_text for w in words_lower):
                texts.append(redact(label.text()))
    return texts


def parse_inr(text):
    """Parse Indian rupee amount. Strips ₹, spaces, commas. Returns None for '****',
    '—' or empty string. Handles leading '-' before or after ₹. Returns float.
    Examples:
      parse_inr('₹ 1,23,456.78') == 123456.78
      parse_inr('-₹1,00,000.10') == -100000.10
      parse_inr('₹ ****') is None
    """
    if not text:
        return None
    text = text.strip()
    if not text or text == "****" or text == "—":
        return None
    is_negative = text.startswith("-")
    text = text.lstrip("-")
    text = text.strip()
    text = text.lstrip("₹").strip()
    if text.startswith("-"):
        is_negative = True
    text = text.lstrip("-").strip()
    if not text or text == "****" or text == "—":
        return None
    text = text.replace(",", "")
    try:
        val = float(text)
        return -val if is_negative else val
    except ValueError:
        return None


def close_all_windows():
    """Reject visible QDialogs and close top-level windows, then processEvents."""
    try:
        app = QApplication.instance()
        if not app:
            return
        for w in list(app.topLevelWidgets()):
            try:
                if isinstance(w, QDialog) and w.isVisible():
                    w.reject()
            except Exception:
                pass
        for w in list(app.topLevelWidgets()):
            try:
                w.close()
            except Exception:
                pass
        app.processEvents()
    except Exception:
        pass


def os_select_combo(harness: RealUIHarness, combo, text):
    idx = combo.findText(text)
    if idx < 0:
        raise LookupError(f"combo has no item {text!r}; items={[combo.itemText(i) for i in range(combo.count())]}")
    harness.click_via_os(combo, wait=0.3)
    view = combo.view()
    view.scrollTo(combo.model().index(idx, 0))
    harness.settle(0.2)
    rect = view.visualRect(combo.model().index(idx, 0))
    harness.click_at_via_os(view.viewport(), rect.center(), wait=0.4)
    if combo.currentText() != text:
        raise RuntimeError(f"combo select failed: wanted {text!r} got {combo.currentText()!r}")
    print(f"os_select_combo -> {text!r}")
    return combo


def os_set_date(harness: RealUIHarness, dateedit, qdate):
    harness.click_via_os(dateedit, wait=0.2)
    pyautogui.press("home")
    fmt = dateedit.displayFormat()
    date_str = qdate.toString(fmt)
    digits = re.sub(r"\D", "", date_str)
    pyautogui.write(digits, interval=0.05)
    harness.settle(0.3)
    ok = dateedit.date() == qdate
    print(f"os_set_date format={fmt} target={qdate.toString('yyyy-MM-dd')} ok={ok}")
    if not ok:
        # Documented fallback (Appendix): record as a finding and fall back to
        # setDate, explicitly labelled non-OS.
        print(f"FINDING: OS date entry failed for format {fmt!r}; falling back to setDate() (non-OS)")
        dateedit.setDate(qdate)
        harness.settle(0.3)
        ok = dateedit.date() == qdate
        if not ok:
            raise RuntimeError("date set failed even via setDate fallback")
    return ok


def nav_click(harness: RealUIHarness, dashboard, label):
    return os_click(harness, dashboard, f"Navigate to {label}")


# ---------------------------------------------------------- native file dialog --

import subprocess

TYPER = Path(__file__).resolve().parent / "os_file_dialog_typer.py"


def native_file_dialog(trigger_fn, path, timeout=30):
    """Spawns os_file_dialog_typer.py (separate process, unaffected by our GIL
    while trigger_fn() blocks inside the native QFileDialog's nested event
    loop), then calls trigger_fn() which must synchronously open the dialog
    (e.g. a QTest.mouseClick on a Browse control). Raises if the typer process
    fails/times out."""
    pid = os.getpid()
    proc = subprocess.Popen(
        [sys.executable, str(TYPER), "--pid", str(pid), "--path", str(path), "--timeout", str(timeout)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    trigger_fn()
    out, _ = proc.communicate(timeout=timeout + 10)
    if proc.returncode != 0:
        raise RuntimeError(f"native_file_dialog typer failed rc={proc.returncode} out={out!r}")
    return out


# --------------------------------------------------------------------- modals --

class Prearm:
    """QTimer.singleShot(0, cb) wrapper capturing exceptions."""
    def __init__(self, app, cb):
        self.app = app
        self.cb = cb
        self.done = False
        self.error = None

    def _run(self):
        try:
            self.cb()
        except Exception as e:
            self.error = e
        finally:
            self.done = True

    def arm(self):
        # Wait for the modal dialog to open before running the callback,
        # so the click that opens it can complete before we interact with it.
        self._timer = QTimer()
        self._timer.setInterval(200)
        deadline = time.time() + 120

        def tick():
            if self.done:
                return
            if time.time() > deadline:
                self._timer.stop()
                self.error = TimeoutError("no modal dialog appeared")
                self.done = True
                return
            if QApplication.activeModalWidget() is not None:
                self._timer.stop()
                self._run()

        self._timer.timeout.connect(tick)
        self._timer.start()
        return self


def prearm(app, cb):
    return Prearm(app, cb).arm()


def wait_until(harness: RealUIHarness, pred, timeout=30, interval=0.2):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if pred():
            return True
        harness.settle(interval)
    return False


def answer_password_dialog(harness, title, secret, tick_save=True, timeout=90):
    """In-process modal answerer for PasswordDialog.exec(); retries password entry up to 3 times."""
    from ui.dialogs.password_dialog import PasswordDialog

    state = {"done": False, "error": None, "typed_ok": None, "save_checked": None}
    deadline = time.time() + timeout
    timer = QTimer()
    timer.setInterval(200)

    def tick():
        if state["done"]:
            return
        if time.time() > deadline:
            timer.stop()
            dlg = QApplication.activeModalWidget()
            if isinstance(dlg, PasswordDialog) and dlg.windowTitle() == title and dlg.isVisible():
                dlg.reject()
            state.update(error="timeout", done=True)
            return
        dlg = QApplication.activeModalWidget()
        if not isinstance(dlg, PasswordDialog) or dlg.windowTitle() != title or not dlg.isVisible():
            return
        timer.stop()
        try:
            # Retry the clear+type sequence up to 3 times on readback mismatch, like os_type does
            last_typed_ok = None
            for attempt in range(1, 4):
                try:
                    adopt_window(dlg)
                    os_click_widget(harness, dlg.password_input, wait=0.3)
                    pyautogui.hotkey("ctrl", "a")
                    harness.settle(0.3)
                    pyautogui.press("backspace")
                    harness.settle(0.3)
                    pyautogui.write(secret, interval=0.05)
                    harness.settle(0.5)
                    last_typed_ok = dlg.password_input.text() == secret
                    if last_typed_ok:
                        break
                    print(f"answer_password_dialog attempt {attempt}/3 readback mismatch, retrying")
                except Exception as e:
                    if attempt < 3:
                        print(f"answer_password_dialog attempt {attempt}/3 failed: {repr(e)}, retrying")
                    else:
                        raise
            state["typed_ok"] = last_typed_ok
            if not state["typed_ok"]:
                raise RuntimeError("password readback mismatch")
            if tick_save and dlg.save_check is not None and not dlg.save_check.isChecked():
                os_click_widget(harness, dlg.save_check, wait=0.4)
            state["save_checked"] = bool(dlg.save_check is not None and dlg.save_check.isChecked())
            os_click(harness, dlg, "Confirm password", wait=0.5)
        except Exception as e:
            state["error"] = repr(e)
            dlg.reject()
        finally:
            state["done"] = True

    timer.timeout.connect(tick)
    timer.start()
    state["_timer"] = timer
    return state


# ------------------------------------------------------------------- login --

def login_to_dashboard(harness: RealUIHarness, master_pw=None, login_screen=None, otp=None):
    from core.auth import is_first_run
    if is_first_run():
        raise RuntimeError("is_first_run() is True; cannot log in yet")
    if master_pw is None:
        master_pw = read_secret("master")
    if login_screen is None:
        from ui.login_screen import LoginScreen
        login_screen = harness.launch(lambda: LoginScreen(), title="RUIH_LOGIN", maximized=False)
    adopt_window(login_screen)
    os_type(harness, login_screen, "Master password", master_pw, secret=True)
    if otp is not None:
        os_type(harness, login_screen, "One-time password", otp, secret=True)
    os_click(harness, login_screen, "Unlock account", wait=1.5)

    dashboard_ref = {}

    def _capture():
        # LoginScreen swaps to DashboardScreen internally; find it via emitted
        # attribute if present, else poll allWidgets for a visible DashboardScreen.
        pass

    from ui.dashboard_screen import DashboardScreen
    ok = wait_until(harness, lambda: any(
        isinstance(w, DashboardScreen) and w.isVisible() for w in QApplication.instance().allWidgets()
    ), timeout=90)
    if not ok:
        raise RuntimeError("dashboard did not appear within 90s after login")
    dashboard = next(w for w in QApplication.instance().allWidgets() if isinstance(w, DashboardScreen) and w.isVisible())
    adopt_window(dashboard)
    harness.window = dashboard
    return dashboard


def start_modal_watchdog(harness: RealUIHarness, log: RedactingLogger, expected_titles):
    """Start a 500ms QTimer watchdog that monitors for unexpected modal dialogs.
    For each visible activeModalWidget() whose title is not in expected_titles
    (a mutable set that the caller can edit), logs the title and redacted text.
    If the same widget persists >5s, takes a screenshot, rejects it, and appends
    to .failures list. Returns object with .timer and .failures."""

    class ModalWatchdog:
        def __init__(self):
            self.timer = QTimer()
            self.failures = []
            self.last_widget = None
            self.last_widget_time = None

        def tick(self):
            w = QApplication.activeModalWidget()
            if w is None:
                self.last_widget = None
                self.last_widget_time = None
                return
            title = w.windowTitle() if hasattr(w, "windowTitle") else "<no title>"
            if title not in expected_titles:
                text = redact(w.text()) if hasattr(w, "text") else "<no text>"
                log.log(f"WATCHDOG: unexpected modal: title={title!r} text={text!r}")
                if self.last_widget is w:
                    if self.last_widget_time is not None:
                        elapsed = time.time() - self.last_widget_time
                        if elapsed > 5:
                            harness.shot(f"WATCHDOG_{title}")
                            w.reject()
                            self.failures.append({"title": title, "text": text, "elapsed": elapsed})
                            self.last_widget = None
                            self.last_widget_time = None
                else:
                    self.last_widget = w
                    self.last_widget_time = time.time()

        def start_watching(self):
            self.timer.setInterval(500)
            self.timer.timeout.connect(self.tick)
            self.timer.start()
            return self

    wd = ModalWatchdog()
    return wd.start_watching()


def set_fy(harness: RealUIHarness, dashboard, fy="2025-26"):
    for attempt in range(1, 4):
        try:
            os_select_combo(harness, dashboard.fy_combo, fy)
            from core import session
            if session.session.selected_fy != fy:
                raise AssertionError(f"session.selected_fy is {session.session.selected_fy!r}, expected {fy!r}")
            return True
        except (RuntimeError, AssertionError) as e:
            if attempt < 3:
                print(f"set_fy attempt {attempt}/3 failed: {e!r}, retrying")
                harness.settle(0.5)
            else:
                raise


# ----------------------------------------------------------------------- DB --

def db_ro(path=None):
    if path is None:
        from config import DB_PATH
        path = DB_PATH
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def fingerprint_real_db(path=None):
    if path is None:
        from config import DB_PATH
        path = DB_PATH
    conn = db_ro(path)
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()]
    fp = {}
    for t in tables:
        rows = conn.execute(f"SELECT * FROM [{t}] ORDER BY rowid").fetchall()
        h = hashlib.sha256(repr(rows).encode("utf-8", errors="replace")).hexdigest()
        cnt = conn.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
        fp[t] = {"count": cnt, "sha256": h}
    conn.close()
    return fp


def require_scratch():
    from config import DB_PATH
    if Path(DB_PATH).resolve() == REAL_DB_PATH.resolve():
        raise RuntimeError("S-script must run via run_on_scratch.py")


def snapshot_db(tag: str):
    from config import DB_PATH
    is_scratch = Path(DB_PATH).resolve() != REAL_DB_PATH.resolve()
    if is_scratch:
        tag = f"scratch_{tag}"
    ts = _dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    dest = BACKUPS / f"rebuild_{ts}_{tag}.db"
    src_conn = sqlite3.connect(DB_PATH)
    dest_conn = sqlite3.connect(str(dest))
    with dest_conn:
        src_conn.backup(dest_conn)
    src_conn.close()
    dest_conn.close()
    assert dest.exists() and dest.stat().st_size > 0, f"snapshot {dest} missing/empty"
    check_conn = sqlite3.connect(f"file:{dest}?mode=ro", uri=True)
    integrity = check_conn.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        check_conn.close()
        raise RuntimeError(f"snapshot integrity_check failed: {integrity}")
    live_counts = {}
    snap_counts = {}
    live_conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    tables = [r[0] for r in live_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()]
    for t in tables:
        live_counts[t] = live_conn.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
        snap_counts[t] = check_conn.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
    live_conn.close()
    check_conn.close()
    if live_counts != snap_counts:
        raise RuntimeError(f"snapshot count mismatch: live={live_counts} snap={snap_counts}")
    print(f"snapshot OK: {dest} tables={len(tables)}")
    return str(dest)


def diff_fingerprints(before, after, allowed=()):
    changed = []
    for table in before.keys():
        if table not in after:
            continue
        if before[table]["count"] != after[table]["count"] or before[table]["sha256"] != after[table]["sha256"]:
            if table not in allowed:
                changed.append(table)
    return changed


def append_progress(line: str):
    with open(PROGRESS_MD, "a", encoding="utf-8") as f:
        f.write(f"- [{_dt.datetime.now().isoformat(timespec='seconds')}] {redact(line)}\n")


def read_theme_prefs():
    import core.session
    config_file = Path(core.session._CONFIG_FILE)
    if config_file.exists():
        return config_file.read_bytes()
    return None


def restore_theme_prefs(b):
    import core.session
    config_file = Path(core.session._CONFIG_FILE)
    if b is None:
        if config_file.exists():
            config_file.unlink()
    else:
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_bytes(b)


class Checks:
    def __init__(self, log: RedactingLogger):
        self.log = log
        self.results = []
        self.a11y = []

    def check(self, name, ok, detail=""):
        status = "PASS" if ok else "FAIL"
        self.log.log(f"[{status}] {name} {detail}")
        self.results.append({"name": name, "ok": ok, "detail": detail})

    def finish(self, json_path):
        path = Path(json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "results": self.results,
            "a11y": self.a11y,
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        has_fail = any(not r["ok"] for r in self.results)
        return 1 if has_fail else 0


def run_logged(main_fn, log_name):
    """Run main_fn with faulthandler enabled and exception logging."""
    faulthandler.enable()
    try:
        main_fn()
    except SystemExit:
        raise
    except BaseException:
        redacting_logger(log_name).log("UNCAUGHT EXCEPTION:\n" + traceback.format_exc())
        raise
