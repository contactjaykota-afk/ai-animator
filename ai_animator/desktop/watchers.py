"""Extra STOP / takeover protections that work even when AI Animator is not focused.

  * GlobalHotkey   - Shift+Esc anywhere -> emergency stop (Windows RegisterHotKey)
  * MouseWatcher   - you push the mouse into the top-left screen corner -> emergency stop;
                     you move the mouse away from where the AI left it -> auto-pause
                     ("you took over"), resume when ready.
"""
from __future__ import annotations

import logging
import sys
import threading
from typing import Callable

log = logging.getLogger(__name__)


class GlobalHotkey:  # pragma: no cover - Windows only, exercised in Windows CI
    MOD_SHIFT, MOD_NOREPEAT, VK_ESCAPE, WM_HOTKEY, WM_QUIT = 0x4, 0x4000, 0x1B, 0x0312, 0x0012

    def __init__(self, on_trigger: Callable[[], None]):
        self.on_trigger = on_trigger
        self._thread: threading.Thread | None = None
        self._tid = 0
        self.registered = threading.Event()
        self.failed = ""

    def start(self) -> None:
        if sys.platform != "win32" or self._thread:
            return
        self._thread = threading.Thread(target=self._loop, name="stop-hotkey", daemon=True)
        self._thread.start()
        self.registered.wait(2)

    def _loop(self) -> None:
        import ctypes
        from ctypes import wintypes
        user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
        self._tid = kernel32.GetCurrentThreadId()
        if not user32.RegisterHotKey(None, 1, self.MOD_SHIFT | self.MOD_NOREPEAT, self.VK_ESCAPE):
            self.failed = "Shift+Esc is already used by another program"
            log.warning("Global STOP hotkey unavailable: %s", self.failed)
            self.registered.set()
            return
        self.registered.set()
        msg = wintypes.MSG()
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == self.WM_HOTKEY:
                    log.warning("Shift+Esc pressed - emergency stop")
                    self.on_trigger()
        finally:
            user32.UnregisterHotKey(None, 1)

    def stop(self) -> None:
        if self._thread and self._tid:
            import ctypes
            ctypes.windll.user32.PostThreadMessageW(self._tid, self.WM_QUIT, 0, 0)
            self._thread.join(2)
        self._thread = None


class MouseWatcher:
    """Polls the real cursor. `expected()` returns where the AI last put it (or None)."""

    def __init__(self, get_pos: Callable[[], tuple[int, int]], expected: Callable[[], tuple[int, int] | None],
                 on_corner: Callable[[], None], on_takeover: Callable[[], None],
                 corner: tuple[int, int] = (0, 0), tolerance: int = 40, interval: float = 0.05):
        self.get_pos, self.expected = get_pos, expected
        self.on_corner, self.on_takeover = on_corner, on_takeover
        self.corner, self.tolerance, self.interval = corner, tolerance, interval
        self.enabled_takeover = True
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._was_in_corner: bool | None = None  # only ENTERING the corner stops

    def check_once(self) -> str:
        x, y = self.get_pos()
        exp = self.expected()
        near_corner = abs(x - self.corner[0]) <= 2 and abs(y - self.corner[1]) <= 2
        ai_at_corner = exp is not None and abs(exp[0] - self.corner[0]) <= 2 and abs(exp[1] - self.corner[1]) <= 2
        entered = near_corner and self._was_in_corner is False
        self._was_in_corner = near_corner
        if entered and not ai_at_corner:
            self.on_corner()
            return "corner"
        if self.enabled_takeover and exp is not None and \
                (abs(x - exp[0]) > self.tolerance or abs(y - exp[1]) > self.tolerance):
            self.on_takeover()
            return "takeover"
        return ""

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                self.check_once()
            except Exception:
                pass

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="mouse-watch", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(1)
        self._thread = None
