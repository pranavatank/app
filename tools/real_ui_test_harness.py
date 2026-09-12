"""
tools/real_ui_test_harness.py — Reusable helpers for REAL (not headless) UI testing.

WHY THIS FILE EXISTS
---------------------
Every prior round of "verification" in this project's redesign work used PyQt6's
QTest.mouseClick()/keyClick() under QT_QPA_PLATFORM=offscreen. That approach
INJECTS events directly into Qt's internal event queue — it never goes through the
real OS input pipeline. It is fast and fine for pure logic checks, but it produces
false confidence: code can appear fully correct in an offscreen QTest run while a
real mouse click on a real Windows desktop does nothing, because the two paths
diverge exactly at the layer offscreen testing skips (window focus, DPI-scaled
screen coordinates, scroll position, real compositor repaint timing).

This module drives a REAL, visible window with `pyautogui` (genuine OS-level mouse
and keyboard events) and captures REAL screenshots with `pyautogui.screenshot()`.
It exists so that "I clicked it and it worked" means what it says.

See docs/VISUAL_TESTING_GUIDE.md for the full writeup of why each helper below is
shaped the way it is — every one of them exists because a naive version of it
silently failed at least once during real testing on this machine.

INSTALLED PACKAGES (already in .venv — see VISUAL_TESTING_GUIDE.md for the "why"):
    pyautogui   — real OS mouse/keyboard control + screenshot()
    pygetwindow — window enumeration (lighter-weight alternative to pywin32 for
                  simple cases; not strictly required once pywin32 is available)
    pywin32     — win32gui/win32con: the ONLY thing that reliably forces a
                  script-launched window into real OS foreground focus on Windows
    mss         — fast multi-monitor screenshot library (alternative to
                  pyautogui.screenshot(); not used by default here but installed)

USAGE
-----
    from tools.real_ui_test_harness import RealUIHarness

    harness = RealUIHarness()
    dashboard = harness.launch(DashboardScreen, resize=None)  # None -> maximized
    harness.click(dashboard._nav_buttons[8])       # real click, DPI-correct, auto-scrolls
    harness.settle()                               # pump events long enough for a real repaint
    harness.shot("settings_screen")                # real screenshot, saved + path printed
    harness.type_text("hello")                     # real keyboard typing
    harness.close()
"""
import os
import time

import pyautogui
import win32con
import win32gui
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QScrollArea

pyautogui.FAILSAFE = True   # slam mouse to a screen corner to abort a runaway script
pyautogui.PAUSE = 0.15


class RealUIHarness:
    def __init__(self, screenshot_dir: str | None = None):
        self.app = QApplication.instance() or QApplication([])
        # THE #1 GOTCHA: Qt widget geometry (mapToGlobal, resize, move, rect()) is
        # always in LOGICAL pixels. pyautogui always operates in PHYSICAL screen
        # pixels. On any machine where Windows display scaling != 100% (this dev
        # machine is 125%), passing a raw Qt coordinate straight to pyautogui lands
        # the click at the wrong physical spot — scaled down by 1/DPR, consistently
        # up and to the left of the real target. Every coordinate that crosses from
        # Qt-space into pyautogui-space MUST go through self.to_physical().
        self.dpr = self.app.primaryScreen().devicePixelRatio()
        self.screenshot_dir = screenshot_dir or os.getcwd()
        self._shot_n = 0
        self.window = None

    # ------------------------------------------------------------------ window --

    def launch(self, widget_factory, title="RUIH_TARGET", maximized=True, resize=None, move=None):
        """Construct widget_factory() as a real top-level window and force real OS
        foreground focus onto it. Returns the constructed widget.

        maximized=True (default) is the safe choice: it sidesteps the SECOND
        gotcha entirely (see below) by never risking a window geometry that
        doesn't fit the physical screen.
        """
        widget = widget_factory()
        widget.setWindowTitle(title)
        if maximized:
            widget.showMaximized()
        else:
            # THE #2 GOTCHA: resize()/move() are also logical-pixel calls. A window
            # requested at 1600x900 positioned at (50,50) becomes PHYSICALLY
            # 2000x1125 at (62,62) under 125% scaling — taller than a 1080px-high
            # physical screen. Everything below the clipped edge still has a valid
            # (but useless) mapToGlobal() position: Qt will happily report a
            # coordinate for it, and a click sent there lands off-screen or on
            # whatever's behind our window, with zero error or feedback. If you
            # must use a fixed size instead of maximized, verify explicitly that
            # (position + size) * dpr stays within QApplication.primaryScreen()
            # .geometry() before trusting any click inside it.
            if resize:
                widget.resize(*resize)
            if move:
                widget.move(*move)
            widget.show()
        self.app.processEvents()
        self.settle(0.8)

        # THE #3 GOTCHA: Windows' focus-stealing prevention silently blocks a
        # background/scripted process's window from becoming the real input-
        # focused window even after Qt's own activateWindow()/raise_() — both
        # return normally and the window LOOKS focused (drawn on top), but a real
        # OS click can still be delivered to whatever window Windows actually
        # considers foreground. There is no exception, no error: the click just
        # does nothing, which looks identical to "the button doesn't work". Only
        # win32gui's SetForegroundWindow (plus ShowWindow/BringWindowToTop) reliably
        # forces it.
        hwnd = win32gui.FindWindow(None, title)
        if hwnd:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            win32gui.BringWindowToTop(hwnd)
        self.settle(0.5)
        actually_foreground = win32gui.GetForegroundWindow() == hwnd
        if not actually_foreground:
            print(f"WARNING: could not force real foreground focus onto '{title}' — "
                  f"clicks below may silently miss. Foreground is currently: "
                  f"{win32gui.GetWindowText(win32gui.GetForegroundWindow())!r}")
        self.window = widget
        return widget

    def close(self):
        if self.window:
            self.window.close()

    # ------------------------------------------------------------- coordinates --

    def to_physical(self, qpoint):
        """Convert a Qt logical-pixel global point to physical screen pixels."""
        return int(qpoint.x() * self.dpr), int(qpoint.y() * self.dpr)

    def scroll_into_view(self, widget) -> bool:
        """THE #4 GOTCHA: a widget's mapToGlobal() position is a real number even
        when it's scrolled out of view inside a QScrollArea — Qt does not refuse to
        answer just because the widget isn't currently visible. Clicking that
        coordinate hits whatever IS visible there instead (often another control
        entirely), silently. Always scroll a widget into view before clicking it if
        there's any chance it lives inside a scroll area — this walks up the
        parent chain looking for one and calls ensureWidgetVisible() if found.
        """
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
        """THE #5 GOTCHA: a widget's internal Qt state (label text, checked state,
        current index) updates immediately and synchronously when you trigger an
        action — but the PIXELS actually presented to the Windows compositor can
        lag behind that by a second or more when the event loop is being driven by
        occasional manual processEvents() calls instead of a real, continuous
        app.exec() loop. A screenshot taken right after a click can show STALE
        pixels (the previous screen) even though querying the widget directly
        already shows the correct new state. This is very likely an artifact of
        driving Qt from a script rather than something a real running app
        (main.py's real app.exec() loop) exhibits to an actual user — but it means
        a screenshot alone, taken too early, is not trustworthy evidence either way.
        Always pump for a real second or two after any interaction before treating
        a screenshot as ground truth, and prefer confirming BOTH the screenshot AND
        a direct widget-state query (label.text(), button.isChecked(), a DB row)
        before concluding whether something worked.
        """
        end = time.time() + seconds
        while time.time() < end:
            self.app.processEvents()
            QTest.qWait(50)

    # ----------------------------------------------------------------- actions --

    def click(self, widget, wait=0.8, button="left"):
        self.scroll_into_view(widget)
        center = widget.mapToGlobal(widget.rect().center())
        px, py = self.to_physical(center)
        pyautogui.moveTo(px, py, duration=0.15)
        if button == "left":
            pyautogui.click()
        elif button == "right":
            pyautogui.rightClick()
        self.settle(wait)

    def double_click(self, widget, wait=0.8):
        """THE #6 GOTCHA: QTest.mouseDClick does NOT reliably fire doubleClicked at
        all — confirmed by connecting a bare lambda directly to the signal with
        zero application logic involved, under BOTH offscreen and real platforms.
        pyautogui.doubleClick() (a genuine OS double-click with real timing) is the
        only way tested so far that's actually credible for verifying
        double-click-driven behaviour. If you need to verify a double-click-to-edit
        interaction and this still doesn't fire the expected signal, do not
        conclude the app is broken from that alone — cross-check with the
        equivalent keyboard path (e.g. select the row, press Enter) if the code
        treats them equivalently, and note the ambiguity explicitly.
        """
        self.scroll_into_view(widget)
        center = widget.mapToGlobal(widget.rect().center())
        px, py = self.to_physical(center)
        pyautogui.moveTo(px, py, duration=0.15)
        pyautogui.doubleClick()
        self.settle(wait)

    def key(self, qt_key_or_str, wait=0.4):
        """Send a real key press. Accepts a pyautogui key name string (e.g. 'enter',
        'tab', 'esc') for simple keys."""
        pyautogui.press(qt_key_or_str)
        self.settle(wait)

    def type_text(self, text, wait=0.3):
        pyautogui.typewrite(text, interval=0.02)
        self.settle(wait)

    # -------------------------------------------------------------- artifacts --

    def shot(self, name):
        self._shot_n += 1
        path = os.path.join(self.screenshot_dir, f"{self._shot_n:02d}_{name}.png")
        pyautogui.screenshot(path)
        print(f"[screenshot] {path}")
        return path
