"""Mouse and keyboard control.

`WindowsInput` drives the real mouse/keyboard with the Win32 SendInput API
(no extra packages, works inside the packaged .exe). `FakeInput` records
calls so the agent can be tested without touching a real desktop.

Coordinates here are always REAL screen pixels. Scaling from screenshot
space happens in desktop/actions.py.
"""
from __future__ import annotations

import sys
import time
from abc import ABC, abstractmethod

MODIFIERS = {"ctrl", "control", "alt", "shift", "super", "win", "cmd", "meta"}


def parse_combo(combo: str) -> list[str]:
    """'ctrl+shift+s' -> ['ctrl', 'shift', 's'] (keeps a literal '+' key)."""
    combo = (combo or "").strip()
    if combo == "+":
        return ["+"]
    parts = [p.strip() for p in combo.split("+")]
    if combo.endswith("++"):
        parts = parts[:-2] + ["+"]
    return [p for p in parts if p]


class InputBackend(ABC):
    @abstractmethod
    def move(self, x: int, y: int) -> None: ...
    @abstractmethod
    def button(self, button: str, down: bool) -> None: ...
    @abstractmethod
    def scroll(self, dx: int, dy: int) -> None: ...
    @abstractmethod
    def key(self, name: str, down: bool) -> None: ...
    @abstractmethod
    def type_text(self, text: str) -> None: ...
    @abstractmethod
    def cursor_position(self) -> tuple[int, int]: ...

    # ---- composed actions ------------------------------------------------
    def click(self, button: str = "left", count: int = 1, modifiers: list[str] | None = None) -> None:
        mods = modifiers or []
        for m in mods:
            self.key(m, True)
        try:
            for _ in range(count):
                self.button(button, True)
                self.button(button, False)
                time.sleep(0.04)
        finally:
            for m in reversed(mods):
                self.key(m, False)

    def press_combo(self, combo: str, repeat: int = 1, hold: float = 0.0) -> None:
        keys = parse_combo(combo)
        if not keys:
            raise ValueError("empty key combination")
        for _ in range(max(1, repeat)):
            for k in keys:
                self.key(k, True)
            if hold:
                time.sleep(hold)
            for k in reversed(keys):
                self.key(k, False)
            time.sleep(0.02)


class FakeInput(InputBackend):
    """Records every call; used in tests and as a dry-run backend."""

    def __init__(self, width: int = 1920, height: int = 1080):
        self.calls: list[tuple] = []
        self.pos = (0, 0)
        self.size = (width, height)

    def move(self, x, y):
        self.pos = (x, y)
        self.calls.append(("move", x, y))

    def button(self, button, down):
        self.calls.append(("button", button, down))

    def scroll(self, dx, dy):
        self.calls.append(("scroll", dx, dy))

    def key(self, name, down):
        self.calls.append(("key", name, down))

    def type_text(self, text):
        self.calls.append(("type", text))

    def cursor_position(self):
        return self.pos


# ---------------------------------------------------------------------------
# Windows implementation
# ---------------------------------------------------------------------------
VK = {
    "return": 0x0D, "enter": 0x0D, "kp_enter": 0x0D, "tab": 0x09, "escape": 0x1B, "esc": 0x1B,
    "backspace": 0x08, "delete": 0x2E, "del": 0x2E, "insert": 0x2D, "home": 0x24, "end": 0x23,
    "page_up": 0x21, "pageup": 0x21, "prior": 0x21, "page_down": 0x22, "pagedown": 0x22, "next": 0x22,
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28, "space": 0x20,
    "ctrl": 0x11, "control": 0x11, "control_l": 0x11, "control_r": 0x11,
    "alt": 0x12, "alt_l": 0x12, "alt_r": 0x12, "shift": 0x10, "shift_l": 0x10, "shift_r": 0x10,
    "super": 0x5B, "super_l": 0x5B, "win": 0x5B, "cmd": 0x5B, "meta": 0x5B,
    "caps_lock": 0x14, "num_lock": 0x90, "scroll_lock": 0x91, "print": 0x2C, "pause": 0x13,
    "menu": 0x5D, "apps": 0x5D,
    "minus": 0xBD, "plus": 0xBB, "equal": 0xBB, "comma": 0xBC, "period": 0xBE, "slash": 0xBF,
    "semicolon": 0xBA, "apostrophe": 0xDE, "bracketleft": 0xDB, "bracketright": 0xDD,
    "backslash": 0xDC, "grave": 0xC0,
}
VK.update({f"f{i}": 0x6F + i for i in range(1, 25)})
EXTENDED = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x5B, 0x5D}


class WindowsInput(InputBackend):  # pragma: no cover - exercised by Windows CI
    def __init__(self):
        if sys.platform != "win32":
            raise RuntimeError("WindowsInput only works on Windows")
        import ctypes
        from ctypes import wintypes
        self.ctypes, self.wt = ctypes, wintypes
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        ULONG_PTR = ctypes.c_size_t

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                        ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                        ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

        class HARDWAREINPUT(ctypes.Structure):
            _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]

        class _U(ctypes.Union):
            _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]

        class INPUT(ctypes.Structure):
            _anonymous_ = ("u",)
            _fields_ = [("type", wintypes.DWORD), ("u", _U)]

        self.MOUSEINPUT, self.KEYBDINPUT, self.INPUT = MOUSEINPUT, KEYBDINPUT, INPUT
        self.user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
        self.user32.VkKeyScanW.argtypes = (wintypes.WCHAR,)
        self.user32.VkKeyScanW.restype = ctypes.c_short

    def _send(self, *inputs) -> None:
        arr = (self.INPUT * len(inputs))(*inputs)
        sent = self.user32.SendInput(len(inputs), arr, self.ctypes.sizeof(self.INPUT))
        if sent != len(inputs):
            raise OSError(f"SendInput blocked (error {self.ctypes.get_last_error()}). "
                          "Windows blocks input into apps running as administrator "
                          "unless AI Animator also runs as administrator.")

    def _mouse(self, flags, data=0):
        inp = self.INPUT(type=0)
        inp.mi = self.MOUSEINPUT(0, 0, data & 0xFFFFFFFF, flags, 0, 0)
        return inp

    def move(self, x, y):
        if not self.user32.SetCursorPos(int(x), int(y)):
            raise OSError("SetCursorPos failed")

    def button(self, button, down):
        flags = {"left": (0x0002, 0x0004), "right": (0x0008, 0x0010), "middle": (0x0020, 0x0040)}[button]
        self._send(self._mouse(flags[0] if down else flags[1]))

    def scroll(self, dx, dy):
        if dy:
            self._send(self._mouse(0x0800, int(dy) * 120))   # MOUSEEVENTF_WHEEL (+ = up)
        if dx:
            self._send(self._mouse(0x1000, int(dx) * 120))   # MOUSEEVENTF_HWHEEL (+ = right)

    def _vk(self, name: str) -> tuple[int, bool]:
        """Returns (virtual key, needs_shift)."""
        low = name.lower()
        if low in VK:
            return VK[low], False
        if len(name) == 1:
            res = self.user32.VkKeyScanW(name)
            if res == -1:
                raise ValueError(f"no key for character {name!r}")
            return res & 0xFF, bool(res & 0x100)
        raise ValueError(f"unknown key name: {name}")

    def key(self, name, down):
        vk, _ = self._vk(name)
        flags = (0 if down else 0x0002) | (0x0001 if vk in EXTENDED else 0)
        inp = self.INPUT(type=1)
        inp.ki = self.KEYBDINPUT(vk, 0, flags, 0, 0)
        self._send(inp)

    def type_text(self, text):
        for ch in text:
            if ch == "\n":
                self.press_combo("Return")
                continue
            if ch == "\r":
                continue
            data = ch.encode("utf-16-le")
            units = [int.from_bytes(data[i:i + 2], "little") for i in range(0, len(data), 2)]
            events = []
            for u in units:  # KEYEVENTF_UNICODE: types any character, any keyboard layout
                for up in (0, 0x0002):
                    inp = self.INPUT(type=1)
                    inp.ki = self.KEYBDINPUT(0, u, 0x0004 | up, 0, 0)
                    events.append(inp)
            self._send(*events)
            time.sleep(0.005)

    def cursor_position(self):
        pt = self.wt.POINT()
        self.user32.GetCursorPos(self.ctypes.byref(pt))
        return pt.x, pt.y


def default_backend() -> InputBackend:
    if sys.platform == "win32":
        return WindowsInput()
    raise RuntimeError("Desktop control is only supported on Windows.")
