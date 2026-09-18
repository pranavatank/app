"""
tools/real_ui_tests/test_button_size_audit.py — Real-render size audit.

Covers guide §5 step 2: "Measure its rendered height/width ... against the design
system's scale - flag any button that visually looks bigger/smaller than
sm=28/md=36/lg=44 or wider than 280px." Prior rounds only asserted these in code;
this measures what Qt actually laid out, on a real maximized window.

Walks every nav screen, builds it for real, and reports each visible QPushButton /
QToolButton whose rendered height is off the {28, 36, 44} scale (tolerance below)
or whose width exceeds the 280px cap.

REPORTS ONLY - it changes no code and writes nothing to the database.

Run with:
    .venv/Scripts/python tools/real_ui_tests/test_button_size_audit.py
"""
import os
import sys

os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from PySide6.QtWidgets import QApplication, QDialog, QPushButton, QToolButton

from tools.real_ui_test_harness import RealUIHarness
from ui.dashboard_screen import DashboardScreen, _NAV_ITEMS
from ui.theme.theme_manager import ThemeManager

SHOT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(SHOT_DIR, exist_ok=True)

HEIGHT_SCALE = (28, 36, 44)
HEIGHT_TOLERANCE = 2      # Qt rounds; 2px either side is not a design violation
MAX_WIDTH = 280

# Nav items are square icon buttons on a fixed rail, not content controls, and
# the sidebar toggle is deliberately small. They are not part of this scale.
EXEMPT_OBJECT_NAMES = {"sidebarToggle"}


def height_ok(h):
    return any(abs(h - target) <= HEIGHT_TOLERANCE for target in HEIGHT_SCALE)


def audit_screen(screen, screen_name):
    """Return (violations, measured_count) for one built screen."""
    violations = []
    measured = 0
    # PySide6's findChildren takes a single type, not a tuple (PyQt6 allowed one).
    buttons = list(screen.findChildren(QPushButton)) + list(screen.findChildren(QToolButton))
    for btn in buttons:
        if not btn.isVisible():
            continue
        if btn.objectName() in EXEMPT_OBJECT_NAMES:
            continue
        if btn.property("nav_item"):
            continue

        h, w = btn.height(), btn.width()
        measured += 1
        label = (btn.text() or btn.accessibleName() or btn.objectName()
                 or type(btn).__name__).strip()

        if not height_ok(h):
            violations.append((screen_name, label, f"height {h}px off scale {HEIGHT_SCALE}"))
        if w > MAX_WIDTH:
            violations.append((screen_name, label, f"width {w}px exceeds {MAX_WIDTH}px cap"))
    return violations, measured


def main():
    ThemeManager.apply("Aurora", save=False, notify=False)
    harness = RealUIHarness(screenshot_dir=SHOT_DIR)
    dashboard = harness.launch(lambda: DashboardScreen(), maximized=True)

    print(f"[dpr] {QApplication.primaryScreen().devicePixelRatio()}", flush=True)
    print(f"[scale] heights {HEIGHT_SCALE} (+/-{HEIGHT_TOLERANCE}px), max width {MAX_WIDTH}px\n",
          flush=True)

    all_violations = []
    total_measured = 0

    for index, (label, _key) in enumerate(_NAV_ITEMS):
        dashboard._navigate(index)
        harness.settle(1.0)

        if index in getattr(dashboard, "_screen_errors", {}):
            print(f"--- {label}: SCREEN FAILED TO BUILD, skipped", flush=True)
            all_violations.append((label, "(screen)", "failed to build"))
            continue

        screen = dashboard.stack.currentWidget()
        violations, measured = audit_screen(screen, label)
        total_measured += measured
        all_violations.extend(violations)

        status = "clean" if not violations else f"{len(violations)} off-scale"
        print(f"--- {label}: {measured} visible buttons, {status}", flush=True)
        for _s, btn_label, problem in violations:
            print(f"      {btn_label[:46]:48s} {problem}", flush=True)

    harness.shot("button_size_audit_final")

    print("\n===== SUMMARY =====", flush=True)
    print(f"Measured {total_measured} visible buttons across {len(_NAV_ITEMS)} screens.",
          flush=True)
    if all_violations:
        print(f"{len(all_violations)} off-scale control(s) found:", flush=True)
        for screen_name, btn_label, problem in all_violations:
            print(f"  [{screen_name}] {btn_label[:40]} - {problem}", flush=True)
    else:
        print("All measured controls conform to the design scale.", flush=True)

    try:
        harness.close()
    except Exception:
        pass
    # An audit reports; it does not fail a build.
    return 0


def _close_all_windows():
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


if __name__ == "__main__":
    try:
        rc = main()
    except BaseException:
        import traceback
        traceback.print_exc()
        rc = 1
    finally:
        _close_all_windows()
    sys.exit(rc)
