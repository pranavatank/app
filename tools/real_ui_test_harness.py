"""
tools/real_ui_test_harness.py — Reusable helpers for REAL (not headless) UI testing.

WHY THIS FILE EXISTS
---------------------
Every prior round of "verification" in this project's redesign work used PySide6's
QTest.mouseClick()/keyClick() under QT_QPA_PLATFORM=offscreen. That approach
INJECTS events directly into Qt's internal event queue — it never goes through the
real OS input pipeline. It is fast and fine for pure logic checks, but it produces
false confidence: code can appear fully correct in an offscreen QTest run while a
real mouse click on a real Windows desktop does nothing, because the two paths
diverge exactly at the layer offscreen testing skips (window focus, DPI-scaled
screen coordinates, scroll position, real compositor repaint timing).

This module runs the app in a REAL, visible, on-screen window (never offscreen) —
that part was always right. What changed is HOW it clicks things.

HISTORY: coordinate-based clicking was tried first and replaced
----------------------------------------------------------------
The first version of this harness sent OS-level clicks via `pyautogui` at
`widget.mapToGlobal(widget.rect().center())`, converted to physical pixels. That
requires the OS to have already given our window real foreground input focus, and
requires the DPI conversion to be exactly right, and requires nothing else to have
moved on screen between computing the coordinate and the click landing. In practice
this produced real, reproducible failures on this machine: Windows' focus-stealing
prevention silently refused `SetForegroundWindow` (no exception in some cases,
outright `pywintypes.error` in others), and — independent of that — clicks
occasionally landed on the wrong control (e.g. closing a dialog instead of opening
one), because a coordinate is only correct at the instant it's computed and this
harness had no way to confirm what was actually under the cursor before clicking.

Since this app is a normal on-screen (non-offscreen) PySide6 window running in the
same process as the test script, there is a strictly more reliable option that
doesn't go through OS input at all: **find the target widget by its accessible
name (this codebase already calls `setAccessibleName()` on essentially every
interactive control — see ui/dialogs/person_dialog.py, ui/manage_data_screen.py,
etc.) and drive it directly via `QTest.mouseClick()`/`keyClicks()` on the widget
object itself.** This still goes through Qt's real event loop and produces a real
repaint (this was never an offscreen/QT_QPA_PLATFORM=offscreen setup), it just
skips the OS input queue — which is exactly the layer where DPI math and
focus-stealing prevention live. The tradeoff: it does not prove that a real user's
literal mouse click would land correctly (e.g. if a widget were visually obscured
by another real OS window, QTest wouldn't catch that). For that reason this harness
keeps `pyautogui` for what it's uniquely good at — real screenshots for visual
evidence, and an explicit, opt-in real-OS-click path (`click_via_os`) for the rare
case where you specifically need to prove OS-level input delivery (e.g. a
focus-dependent modal). Default to `click()`/`type_into()` (QTest-based, by
accessible name); reach for `click_via_os()` only when that's insufficient.

See docs/VISUAL_TESTING_GUIDE.md for the full writeup, including the specific
misclick/focus-stealing incidents that motivated this design.

INSTALLED PACKAGES (already in .venv — see VISUAL_TESTING_GUIDE.md for the "why"):
    pyautogui   — real OS mouse/keyboard control + screenshot(); used now only for
                  screenshots and the explicit click_via_os()/type_via_os() escape
                  hatch, not for everyday interaction
    pygetwindow — window enumeration (lighter-weight alternative to pywin32 for
                  simple cases; not strictly required once pywin32 is available)
    pywin32     — win32gui/win32con: used to raise/focus the window for
                  screenshots and for the click_via_os() escape hatch
    mss         — fast multi-monitor screenshot library (alternative to
                  pyautogui.screenshot(); not used by default here but installed)
    pywinauto   — Windows UI Automation (uia backend). Available as a second,
                  independent way to prove a control is really reachable via OS
                  accessibility APIs (see find_via_uia()) — useful as a
                  cross-check, since it inspects the OS accessibility tree rather
                  than Qt's own object tree, so it can catch cases where a widget
                  is registered in Qt but not actually exposed to assistive tech /
                  OS automation.

USAGE
-----
    from tools.real_ui_test_harness import RealUIHarness

    harness = RealUIHarness()
    dashboard = harness.launch(lambda: DashboardScreen(), maximized=True)

    # Preferred: find + interact by accessible name, driven via QTest (no OS
    # coordinates, no DPI math, no focus-stealing risk).
    harness.click(dashboard, "Settings nav")                  # by accessibleName
    harness.click(dashboard._nav_buttons[8])                  # or pass a widget directly
    harness.type_into(dialog, "Nickname", "Jane Doe")
    harness.settle()                                          # pump for a real repaint
    harness.shot("settings_screen")                           # real screenshot

    # Escape hatch: a genuine OS-level click, only when you specifically need to
    # prove real input delivery (e.g. a focus-dependent modal).
    harness.click_via_os(some_widget)

    harness.close()
"""
import os
import sys
import time

os.environ.setdefault("QT_API", "pyside6")

import pyautogui
import win32api
import win32con
import win32gui
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QScrollArea, QWidget

pyautogui.FAILSAFE = True   # slam mouse to a screen corner to abort a runaway script
pyautogui.PAUSE = 0.15


def find_by_accessible_name(root: QWidget, name: str) -> QWidget | None:
    """Walk root's widget tree (including root itself) looking for a child whose
    accessibleName() matches exactly. This is the primary way this harness locates
    controls — it relies on the app already calling setAccessibleName() on its
    interactive widgets (confirmed extensive throughout ui/), not on coordinates."""
    if root.accessibleName() == name:
        return root
    for w in root.findChildren(QWidget):
        if w.accessibleName() == name:
            return w
    return None


def find_dialog_by_title(dialog_cls, title: str | None = None, timeout: float = 3.0,
                          poll_interval: float = 0.1):
    """Poll QApplication.allWidgets() for a visible instance of dialog_cls (and
    optionally matching windowTitle()). Polling matters because a modal
    QDialog.exec() call spins up a nested Qt event loop that can take a beat to
    fully register — a single immediate snapshot has been observed to miss a
    dialog that is genuinely open and visible on screen a moment later.

    Uses allWidgets(), not topLevelWidgets(): a QDialog(parent) was observed NOT
    to appear in topLevelWidgets() at all in this app, even while visibly open on
    screen, but it does appear in allWidgets()."""
    app = QApplication.instance()
    deadline = time.time() + timeout
    while time.time() < deadline:
        for w in app.allWidgets():
            if isinstance(w, dialog_cls) and w.isVisible():
                if title is None or w.windowTitle() == title:
                    return w
        app.processEvents()
        time.sleep(poll_interval)
    return None


class RealUIHarness:
    def __init__(self, screenshot_dir: str | None = None):
        self.app = QApplication.instance() or QApplication([])
        # Kept for the OS-level escape hatch (click_via_os) and for converting
        # Qt logical-pixel coordinates to physical screen pixels when a real OS
        # click is specifically requested. Not used by the default click()/
        # type_into() path, which never leaves Qt's own coordinate space.
        self.dpr = self.app.primaryScreen().devicePixelRatio()
        self.screenshot_dir = screenshot_dir or os.getcwd()
        self._shot_n = 0
        self.window = None

    # ------------------------------------------------------------------ window --

    def launch(self, widget_factory, title="RUIH_TARGET", maximized=True, resize=None, move=None):
        """Construct widget_factory() as a real top-level window. Returns the
        constructed widget.

        maximized=True (default) is the safe choice: it sidesteps a real gotcha
        (see below) by never risking a window geometry that doesn't fit the
        physical screen — this only matters for click_via_os()/screenshots, since
        default click()/type_into() never computes screen coordinates at all.
        """
        widget = widget_factory()
        widget.setWindowTitle(title)
        if maximized:
            widget.showMaximized()
        else:
            # A window requested at 1600x900 positioned at (50,50) becomes
            # PHYSICALLY 2000x1125 at (62,62) under 125% scaling. On a
            # 1920x1080 physical screen, the bottom ~45 physical pixels of that
            # window are off-screen. Qt still returns a perfectly valid
            # mapToGlobal() coordinate for a widget in that clipped region.
            # This only matters for click_via_os()/screenshots.
            if resize:
                widget.resize(*resize)
            if move:
                widget.move(*move)
            widget.show()
        self.app.processEvents()
        self.settle(0.8)

        # Raise/focus the window for screenshots and for click_via_os(). This is
        # NOT required for the default click()/type_into() path (QTest talks to
        # the widget object directly, regardless of OS focus) — it's only here so
        # screenshots show the right window on top and click_via_os() has a
        # chance of working.
        hwnd = win32gui.FindWindow(None, title)
        if hwnd:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            try:
                win32gui.SetForegroundWindow(hwnd)
            except win32gui.error:
                # Windows' focus-stealing prevention can outright refuse this
                # call (pywintypes.error, "No error message is available") when
                # our thread isn't already attached to the foreground thread's
                # input queue. Standard workaround: temporarily attach thread
                # input so Windows treats us as if we already own focus.
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
                    print(f"WARNING: SetForegroundWindow fallback also failed: {e!r} "
                          f"— screenshots may show the wrong window on top, but "
                          f"click()/type_into() are unaffected (they don't need OS focus).")
            win32gui.BringWindowToTop(hwnd)
        self.settle(0.5)
        self.window = widget
        return widget

    def close(self):
        if self.window:
            self.window.close()

    # ----------------------------------------------------------- widget lookup --

    def find(self, root: QWidget, accessible_name: str) -> QWidget | None:
        return find_by_accessible_name(root, accessible_name)

    def find_dialog(self, dialog_cls, title: str | None = None, timeout: float = 3.0):
        return find_dialog_by_title(dialog_cls, title, timeout)

    def scroll_into_view(self, widget) -> bool:
        """A widget's mapToGlobal() position is a real number even when it's
        scrolled completely out of view inside a QScrollArea — Qt doesn't refuse
        to answer just because it isn't currently visible. Always scroll a widget
        into view before interacting with it if there's any chance it lives
        inside a scroll area — this walks up the parent chain looking for one and
        calls ensureWidgetVisible() if found. Cheap and harmless to call even for
        QTest-driven interaction (it doesn't affect coordinates, but some widgets
        skip layout/paint work until scrolled into view, which can matter for
        screenshot evidence)."""
        parent = widget.parent()
        while parent is not None:
            if isinstance(parent, QScrollArea):
                parent.ensureWidgetVisible(widget)
                self.settle(0.3)
                return True
            parent = parent.parent()
        return False

    # ------------------------------------------------------------------ timing --

    def settle(self, seconds=1.2):
        """A widget's internal Qt state (label text, checked state, current
        index) updates immediately and synchronously when you trigger an action —
        but the PIXELS actually presented to the Windows compositor can lag
        behind that by a second or more when the event loop is driven by
        occasional manual processEvents() calls instead of a real, continuous
        app.exec() loop. A screenshot taken right after an action can show STALE
        pixels even though querying the widget directly already shows the correct
        new state. Always pump for a real second or two after any interaction
        before treating a screenshot as ground truth, and prefer confirming BOTH
        the screenshot AND a direct widget-state query (label.text(),
        button.isChecked(), a DB row) before concluding whether something worked.
        """
        end = time.time() + seconds
        while time.time() < end:
            self.app.processEvents()
            QTest.qWait(50)

    # ----------------------------------------------------- primary interaction --
    # QTest-driven: finds by accessible name (or takes a widget directly), acts
    # on the real widget object through Qt's real event loop. No OS coordinates,
    # no DPI math, no dependency on window focus.

    def click(self, target, accessible_name: str | None = None, wait=0.8, button=Qt.MouseButton.LeftButton):
        """Click a widget. Pass either a widget directly, or a root widget plus
        accessible_name to look it up first."""
        widget = self._resolve(target, accessible_name)
        self.scroll_into_view(widget)
        QTest.mouseClick(widget, button)
        self.settle(wait)
        return widget

    def double_click(self, target, accessible_name: str | None = None, wait=0.8):
        widget = self._resolve(target, accessible_name)
        self.scroll_into_view(widget)
        QTest.mouseDClick(widget, Qt.MouseButton.LeftButton)
        self.settle(wait)
        return widget

    def type_into(self, target, accessible_name: str | None = None, text: str = "", wait=0.3, clear_first=True):
        """Focus a widget (typically a QLineEdit) and type real key events into it
        via QTest.keyClicks(). This still exercises the widget's real keyPressEvent
        handling, validators, etc. — it just doesn't go through the OS input queue."""
        widget = self._resolve(target, accessible_name)
        self.scroll_into_view(widget)
        widget.setFocus(Qt.FocusReason.MouseFocusReason)
        if clear_first and hasattr(widget, "clear"):
            widget.clear()
        QTest.keyClicks(widget, text)
        self.settle(wait)
        return widget

    def key(self, target, accessible_name: str | None, qt_key, wait=0.4):
        """Send a single real Qt key event (e.g. Qt.Key.Key_Return) to a widget."""
        widget = self._resolve(target, accessible_name)
        QTest.keyClick(widget, qt_key)
        self.settle(wait)
        return widget

    def _resolve(self, target, accessible_name):
        if accessible_name is None:
            if target is None:
                raise ValueError("must pass either a widget or (root, accessible_name)")
            return target
        widget = find_by_accessible_name(target, accessible_name)
        if widget is None:
            raise LookupError(f"no widget with accessibleName() == {accessible_name!r} "
                               f"found under {target!r}")
        return widget

    # --------------------------------------------------- OS-level escape hatch --
    # Genuine OS-level input via pyautogui, going through real screen coordinates
    # and the real OS input queue. Requires the window to actually have OS
    # foreground focus (see launch()'s focus-forcing, and its warning if that
    # failed). Use only when you specifically need to prove real OS input
    # delivery — e.g. a focus-stealing-sensitive modal, or as a final
    # cross-check after the primary QTest-driven path. Subject to the DPI/focus
    # issues documented in docs/VISUAL_TESTING_GUIDE.md.

    def to_physical(self, qpoint):
        """Convert a Qt logical-pixel global point to physical screen pixels."""
        return int(qpoint.x() * self.dpr), int(qpoint.y() * self.dpr)

    def click_via_os(self, widget, wait=0.8, button="left"):
        self.scroll_into_view(widget)
        center = widget.mapToGlobal(widget.rect().center())
        px, py = self.to_physical(center)
        pyautogui.moveTo(px, py, duration=0.15)
        if button == "left":
            pyautogui.click()
        elif button == "right":
            pyautogui.rightClick()
        self.settle(wait)

    def double_click_via_os(self, widget, wait=0.8):
        self.scroll_into_view(widget)
        center = widget.mapToGlobal(widget.rect().center())
        px, py = self.to_physical(center)
        pyautogui.moveTo(px, py, duration=0.15)
        pyautogui.doubleClick()
        self.settle(wait)

    def type_text_via_os(self, text, wait=0.3):
        pyautogui.typewrite(text, interval=0.02)
        self.settle(wait)

    def find_via_uia(self, window_title: str, control_name: str, control_type: str = "Button"):
        """Look up a control via Windows UI Automation (pywinauto's uia backend),
        independent of Qt's own object tree. Useful as a cross-check that a
        control is genuinely exposed to OS accessibility (not just present in
        Qt's widget tree) — e.g. to confirm a screen-reader / other assistive
        tech would actually be able to reach it. Returns the pywinauto wrapper, or
        raises if not found. Requires pywinauto (already in this project's venv).
        """
        from pywinauto import Application
        app = Application(backend="uia").connect(title=window_title)
        window = app.window(title=window_title)
        return window.child_window(title=control_name, control_type=control_type)

    # -------------------------------------------------------------- artifacts --

    def shot(self, name):
        self._shot_n += 1
        path = os.path.join(self.screenshot_dir, f"{self._shot_n:02d}_{name}.png")
        pyautogui.screenshot(path)
        print(f"[screenshot] {path}")
        return path
