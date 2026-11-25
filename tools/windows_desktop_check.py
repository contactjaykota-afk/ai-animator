"""Real-desktop integration check (Windows only). Used by CI; safe to run on your own PC
(it opens Notepad, types a test line, and closes Notepad without saving).

Checks:
  1. real cursor movement (SetCursorPos/GetCursorPos)
  2. real screenshot -> frame scaling -> click inside Notepad via the agent's executor
  3. typing (Unicode) and key combos, verified by reading the clipboard
  4. global Shift+Esc STOP hotkey fires on a real key press
  5. overlay windows are excluded from screen capture
"""
from __future__ import annotations

import ctypes
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ai_animator.desktop.actions import ActionExecutor  # noqa: E402
from ai_animator.desktop.frames import capture_frame  # noqa: E402
from ai_animator.desktop.input_backend import WindowsInput  # noqa: E402
from ai_animator.desktop.watchers import GlobalHotkey  # noqa: E402

user32 = ctypes.windll.user32
results: dict[str, str] = {}


def ok(name, msg=""):
    results[name] = "ok " + msg
    print(f"[ok]   {name} {msg}", flush=True)


def find_window(substr: str, timeout=15):
    found = []
    end = time.time() + timeout
    proto = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    while time.time() < end:
        found.clear()

        def cb(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                n = user32.GetWindowTextLengthW(hwnd)
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                if substr.lower() in buf.value.lower():
                    found.append(hwnd)
            return True
        user32.EnumWindows(proto(cb), 0)
        if found:
            return found[0]
        time.sleep(0.3)
    raise RuntimeError(f"window containing {substr!r} not found")


def clipboard() -> str:
    """Read Unicode text straight from the Windows clipboard (no console encoding involved)."""
    k32 = ctypes.windll.kernel32
    user32.GetClipboardData.restype = wintypes.HANDLE
    k32.GlobalLock.restype = ctypes.c_void_p
    k32.GlobalLock.argtypes = (wintypes.HGLOBAL,)
    k32.GlobalUnlock.argtypes = (wintypes.HGLOBAL,)
    for _ in range(20):
        if user32.OpenClipboard(None):
            break
        time.sleep(0.1)
    else:
        raise RuntimeError("could not open clipboard")
    try:
        handle = user32.GetClipboardData(13)  # CF_UNICODETEXT
        if not handle:
            return ""
        ptr = k32.GlobalLock(handle)
        try:
            return ctypes.wstring_at(ptr)
        finally:
            k32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def main() -> int:
    inp = WindowsInput()

    # 1. cursor
    inp.move(321, 234)
    assert inp.cursor_position() == (321, 234), inp.cursor_position()
    ok("cursor_move", str(inp.cursor_position()))

    # 2. screenshot + click into Notepad via the executor (exercises scaling)
    proc = subprocess.Popen(["notepad.exe"])
    try:
        hwnd = find_window("Notepad")
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        ex = ActionExecutor(inp, capture_frame)
        ex.run("screenshot", {})
        f = ex.frame
        cx, cy = (rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2 + 40
        fx, fy = f.to_frame(cx, cy)
        ex.run("left_click", {"coordinate": [fx, fy]})
        time.sleep(0.5)
        rx, ry = inp.cursor_position()
        assert abs(rx - cx) <= 3 and abs(ry - cy) <= 3, ((rx, ry), (cx, cy))
        ok("screenshot_and_click", f"frame {f.image.size}, scale {f.scale:.3f}, clicked ({rx},{ry})")

        # 3. typing + shortcuts, verified through the clipboard
        text = "AI Animator input test 123 - äöü ✓"
        ex.run("type", {"text": text})
        time.sleep(0.3)
        ex.run("key", {"text": "ctrl+a"})
        ex.run("key", {"text": "ctrl+c"})
        time.sleep(0.5)
        got = clipboard()
        assert got == text, f"clipboard was {got!r}"
        ok("type_and_shortcuts", repr(got))
    finally:
        proc.kill()

    # 4. global STOP hotkey on a real key press
    fired = []
    hk = GlobalHotkey(lambda: fired.append(1))
    hk.start()
    assert not hk.failed, hk.failed
    inp.press_combo("shift+Escape")
    end = time.time() + 3
    while not fired and time.time() < end:
        time.sleep(0.05)
    hk.stop()
    assert fired, "Shift+Esc hotkey did not fire"
    ok("global_stop_hotkey")

    # 5. overlays excluded from capture
    from PySide6.QtWidgets import QApplication
    from ai_animator.ui.overlay import AICursor, ControlBar, ControlBorder
    app = QApplication.instance() or QApplication([])
    widgets = [ControlBorder(), AICursor(), ControlBar()]
    for w in widgets:
        w.show()
    app.processEvents()
    aff = wintypes.DWORD()
    for w in widgets:
        user32.GetWindowDisplayAffinity(int(w.winId()), ctypes.byref(aff))
        assert aff.value == 0x11, f"{type(w).__name__} affinity {aff.value:#x}"
        w.close()
    ok("overlay_hidden_from_capture")

    print("ALL DESKTOP CHECKS PASSED", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}", flush=True)
        sys.exit(1)
