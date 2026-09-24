r"""tools/real_ui_tests/os_file_dialog_typer.py — types a file path into a
native Windows "Open" file dialog (QFileDialog.getOpenFileName), as a separate
process so it isn't blocked by the GIL of the process whose Qt event loop is
inside the modal file dialog.

Usage: python os_file_dialog_typer.py --pid <pid> --path <path> [--timeout 30]
Exit 0 on success, 2 on timeout / dialog not found.
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


def find_dialog_hwnd(pid, timeout):
    deadline = time.time() + timeout
    while time.time() < deadline:
        found = []

        def cb(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return
            cls = win32gui.GetClassName(hwnd)
            if cls != "#32770":
                return
            _, whwnd_pid = win32process.GetWindowThreadProcessId(hwnd)
            if whwnd_pid == pid:
                found.append(hwnd)

        win32gui.EnumWindows(cb, None)
        if found:
            return found[0]
        time.sleep(0.2)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, required=True)
    ap.add_argument("--path", required=True)
    ap.add_argument("--timeout", type=float, default=30)
    args = ap.parse_args()

    hwnd = find_dialog_hwnd(args.pid, args.timeout)
    if hwnd is None:
        print("TIMEOUT: no #32770 dialog found for pid", args.pid)
        sys.exit(2)

    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception as e:
        print(f"WARNING: SetForegroundWindow failed: {e!r}")
    time.sleep(0.7)

    pyautogui.hotkey("alt", "n")
    time.sleep(0.3)
    pyautogui.write(args.path, interval=0.01)
    time.sleep(0.2)
    pyautogui.press("enter")
    time.sleep(0.3)
    print("OK: typed path into dialog", hwnd)
    sys.exit(0)


if __name__ == "__main__":
    main()
