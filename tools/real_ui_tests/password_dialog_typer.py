r"""tools/real_ui_tests/password_dialog_typer.py — answers a modal
ui/dialogs/password_dialog.py PasswordDialog from a SEPARATE OS process.

Why a separate process: PasswordDialog.exec() is a genuinely blocking modal
(unlike the app's other non-modal "Manage Data" dialogs, which use .show()).
Once our main test process's own event-pump call is the one that delivers the
real OS click which enters exec(), that call does not return until the dialog
closes -- so nothing scheduled from *inside* the same process/thread (a
QTimer.singleShot prearm callback included) can reliably win the race against
real-world OS input latency to interact with it first. A second process,
independent of the main process's GIL and event loop, sidesteps this
entirely -- the same pattern already used for the native Windows file-open
dialog (os_file_dialog_typer.py).

Usage:
    python password_dialog_typer.py --pid <pid> --title "Enter Statement Password"
        --password <pw> [--save-toggle] [--timeout 30]
Exit 0 on success, 2 on timeout / dialog or control not found.
"""
import sys
import time
import argparse

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import win32gui
import win32process
import win32con
import pyautogui

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05


def find_dialog_hwnd(pid, title, timeout):
    deadline = time.time() + timeout
    while time.time() < deadline:
        found = []

        def cb(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return
            if win32gui.GetWindowText(hwnd) != title:
                return
            _, whwnd_pid = win32process.GetWindowThreadProcessId(hwnd)
            if whwnd_pid == pid:
                found.append(hwnd)

        win32gui.EnumWindows(cb, None)
        if found:
            return found[0]
        time.sleep(0.15)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--save-toggle", action="store_true")
    ap.add_argument("--timeout", type=float, default=30)
    args = ap.parse_args()

    hwnd = find_dialog_hwnd(args.pid, args.title, args.timeout)
    if hwnd is None:
        print("TIMEOUT: no window titled", args.title, "found for pid", args.pid)
        sys.exit(2)

    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception as e:
        print(f"WARNING: SetForegroundWindow failed: {e!r}")
    time.sleep(0.5)

    from pywinauto import Application
    uia_app = Application(backend="uia").connect(handle=hwnd)
    window = uia_app.window(handle=hwnd)

    pw_field = window.child_window(title="Password input", control_type="Edit")
    pw_field.wait("visible", timeout=10)
    rect = pw_field.rectangle()
    cx, cy = rect.mid_point()
    pyautogui.moveTo(cx, cy, duration=0.2)
    pyautogui.click()
    time.sleep(0.2)
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.1)
    pyautogui.press("backspace")
    time.sleep(0.1)
    pyautogui.write(args.password, interval=0.05)
    time.sleep(0.3)
    print("OK: password typed")

    if args.save_toggle:
        try:
            toggle = window.child_window(title="Save password toggle", control_type="CheckBox")
            if not toggle.get_toggle_state():
                trect = toggle.rectangle()
                tcx, tcy = trect.mid_point()
                pyautogui.moveTo(tcx, tcy, duration=0.2)
                pyautogui.click()
                time.sleep(0.3)
            print("OK: save toggle checked =", toggle.get_toggle_state())
        except Exception as e:
            # Non-fatal: the dialog defaults save_checked=True already: this is
            # a belt-and-braces confirmation, not required for the confirm click.
            print(f"WARNING: save toggle step failed (non-fatal): {e!r}")

    try:
        confirm_btn = window.child_window(title="Confirm password", control_type="Button")
        brect = confirm_btn.rectangle()
        bcx, bcy = brect.mid_point()
        pyautogui.moveTo(bcx, bcy, duration=0.2)
        pyautogui.click()
        time.sleep(0.3)
        print("OK: confirm clicked")
    except Exception as e:
        # If the window is already gone here, something upstream (e.g. a stray
        # Enter) already closed it -- verify by re-checking window liveness
        # rather than assuming success.
        still_open = win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd)
        print(f"confirm click step raised {e!r}; dialog still open={still_open}")
        if still_open:
            sys.exit(2)
        print("OK: dialog already closed (treated as answered)")
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e!r}")
        sys.exit(2)
