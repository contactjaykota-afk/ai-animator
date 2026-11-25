"""Screen capture (read-only). Screen *understanding* comes in Phase 2."""
from __future__ import annotations

import sys

from PIL import Image


def capture_screen(monitor: int = 1) -> Image.Image:
    import mss
    with mss.mss() as sct:
        monitors = sct.monitors
        if monitor >= len(monitors):
            monitor = 1 if len(monitors) > 1 else 0
        shot = sct.grab(monitors[monitor])
        return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")


def active_window_title() -> str:
    """Title of the foreground window (Windows only; '' elsewhere)."""
    if sys.platform != "win32":
        return ""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value
    except Exception:
        return ""
