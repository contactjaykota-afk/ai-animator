"""Executes computer-toolset members on the real (or fake) desktop.

Input validation is strict: wrong or missing fields raise ValueError, which the
agent returns to Claude as an error result instead of guessing.
"""
from __future__ import annotations

import time
from typing import Callable

from ai_animator.desktop.frames import Frame, png_block
from ai_animator.desktop.input_backend import InputBackend, parse_combo

MEMBERS = {"screenshot", "zoom", "left_click", "right_click", "middle_click", "double_click",
           "triple_click", "left_click_drag", "mouse_move", "left_mouse_down", "left_mouse_up",
           "cursor_position", "scroll", "type", "key", "hold_key", "wait"}
CLICKS = {"left_click": ("left", 1), "right_click": ("right", 1), "middle_click": ("middle", 1),
          "double_click": ("left", 2), "triple_click": ("left", 3)}
MAX_WAIT = 300


def _coord(inp: dict, key: str, frame: Frame, required: bool = True):
    val = inp.get(key)
    if val is None:
        if required:
            raise ValueError(f"missing {key}")
        return None
    if not (isinstance(val, (list, tuple)) and len(val) == 2 and all(isinstance(v, (int, float)) for v in val)):
        raise ValueError(f"{key} must be [x, y]")
    if not frame.in_bounds(*val):
        raise ValueError(f"{key} {list(val)} is outside the screenshot "
                         f"({frame.image.width}x{frame.image.height})")
    return frame.to_screen(*val)


class ActionExecutor:
    def __init__(self, backend: InputBackend, capture: Callable[[], Frame],
                 before_pointer: Callable[[int, int], None] = lambda x, y: None,
                 checkpoint: Callable[[], None] = lambda: None):
        self.backend = backend
        self.capture = capture
        self.before_pointer = before_pointer   # animates the visible AI cursor
        self.checkpoint = checkpoint           # raises if STOP pressed / waits while paused
        self.frame: Frame | None = None

    def current_frame(self) -> Frame:
        if self.frame is None:
            self.frame = self.capture()
        return self.frame

    def _point(self, x: int, y: int) -> None:
        self.before_pointer(x, y)
        self.checkpoint()
        self.backend.move(x, y)

    def _sleep(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.checkpoint()
            time.sleep(min(0.1, max(0.0, end - time.monotonic())))

    def run(self, name: str, inp: dict):
        """Returns a tool_result content (str or list of blocks)."""
        if name not in MEMBERS:
            raise ValueError(f"unsupported action: {name}")
        inp = inp or {}
        b = self.backend
        frame = self.current_frame()

        if name == "screenshot":
            self.frame = self.capture()
            return [png_block(self.frame.image)]
        if name == "zoom":
            region = inp.get("region")
            if not (isinstance(region, (list, tuple)) and len(region) == 4):
                raise ValueError("region must be [x0, y0, x1, y1]")
            self.frame = self.capture()  # zoom must show the screen as it is now
            return [png_block(self.frame.crop_zoom(region))]
        if name == "cursor_position":
            x, y = frame.to_frame(*b.cursor_position())
            return f"X={x},Y={y}"
        if name == "wait":
            self._sleep(min(float(inp.get("duration", 1)), MAX_WAIT))
            return "OK"

        if name in CLICKS:
            button, count = CLICKS[name]
            pt = _coord(inp, "coordinate", frame, required=False)
            if pt:
                self._point(*pt)
            self.checkpoint()
            b.click(button, count, parse_combo(inp["text"]) if inp.get("text") else None)
            time.sleep(0.15)  # give the clicked app time to take keyboard focus
        elif name == "mouse_move":
            self._point(*_coord(inp, "coordinate", frame))
        elif name == "left_click_drag":
            start = _coord(inp, "start_coordinate", frame)
            end = _coord(inp, "coordinate", frame)
            mods = parse_combo(inp["text"]) if inp.get("text") else []
            self._point(*start)
            for m in mods:
                b.key(m, True)
            try:
                b.button("left", True)
                steps = 12
                for i in range(1, steps + 1):  # move in steps so apps see a real drag
                    self.checkpoint()
                    x = start[0] + (end[0] - start[0]) * i // steps
                    y = start[1] + (end[1] - start[1]) * i // steps
                    self.before_pointer(x, y)
                    b.move(x, y)
                    time.sleep(0.015)
            finally:
                b.button("left", False)
                for m in reversed(mods):
                    b.key(m, False)
        elif name == "left_mouse_down":
            b.button("left", True)
        elif name == "left_mouse_up":
            b.button("left", False)
        elif name == "scroll":
            direction = inp.get("scroll_direction")
            amount = int(inp.get("scroll_amount", 3))
            if direction not in ("up", "down", "left", "right"):
                raise ValueError("scroll_direction must be up/down/left/right")
            if not 1 <= amount <= 50:
                raise ValueError("scroll_amount must be 1..50")
            pt = _coord(inp, "coordinate", frame, required=False)
            if pt:
                self._point(*pt)
            mods = parse_combo(inp["text"]) if inp.get("text") else []
            for m in mods:
                b.key(m, True)
            try:
                dy = {"up": amount, "down": -amount}.get(direction, 0)
                dx = {"right": amount, "left": -amount}.get(direction, 0)
                b.scroll(dx, dy)
            finally:
                for m in reversed(mods):
                    b.key(m, False)
        elif name == "type":
            text = inp.get("text")
            if not isinstance(text, str):
                raise ValueError("text must be a string")
            for i in range(0, len(text), 50):  # chunks so STOP can interrupt long typing
                self.checkpoint()
                b.type_text(text[i:i + 50])
        elif name == "key":
            text = inp.get("text")
            if not isinstance(text, str) or not text.strip():
                raise ValueError("text must name a key, e.g. Return or ctrl+s")
            repeat = int(inp.get("repeat", 1))
            if not 1 <= repeat <= 100:
                raise ValueError("repeat must be 1..100")
            for _ in range(repeat):
                self.checkpoint()
                b.press_combo(text)
        elif name == "hold_key":
            text = inp.get("text")
            duration = float(inp.get("duration", 1))
            if not isinstance(text, str) or not 0 < duration <= MAX_WAIT:
                raise ValueError("hold_key needs text and 0 < duration <= 300")
            keys = parse_combo(text)
            for k in keys:
                b.key(k, True)
            try:
                self._sleep(duration)
            finally:
                for k in reversed(keys):
                    b.key(k, False)
        return "OK"
