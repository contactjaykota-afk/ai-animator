"""Screenshots sized for Claude, and coordinate mapping back to the real screen.

The API rejects oversized images (it does not shrink them), and Claude's
coordinates are in the pixel space of the screenshot we send. So we downscale
each capture and keep the factor to map clicks back.
"""
from __future__ import annotations

import base64
import io
import math
from dataclasses import dataclass
from typing import Callable

from PIL import Image

# Conservative limits from the computer-use docs (fit every supported model and keep
# screenshots cheap). The docs recommend staying at or below ~1920x1080 anyway.
MAX_LONG_EDGE = 1568
MAX_PIXELS = 1_150_000


def scale_factor(width: int, height: int) -> float:
    return min(1.0, MAX_LONG_EDGE / max(width, height), math.sqrt(MAX_PIXELS / (width * height)))


@dataclass
class Frame:
    image: Image.Image        # what Claude sees (downscaled)
    scale: float              # sent_pixels = real_pixels * scale
    origin: tuple[int, int]   # top-left of the captured monitor in real screen pixels
    real_size: tuple[int, int]

    def to_screen(self, x: float, y: float) -> tuple[int, int]:
        """Claude's screenshot coordinate -> real screen pixel (clamped to the monitor)."""
        rx = int(round(x / self.scale)) + self.origin[0]
        ry = int(round(y / self.scale)) + self.origin[1]
        rx = min(max(rx, self.origin[0]), self.origin[0] + self.real_size[0] - 1)
        ry = min(max(ry, self.origin[1]), self.origin[1] + self.real_size[1] - 1)
        return rx, ry

    def to_frame(self, rx: int, ry: int) -> tuple[int, int]:
        return (int(round((rx - self.origin[0]) * self.scale)),
                int(round((ry - self.origin[1]) * self.scale)))

    def in_bounds(self, x: float, y: float) -> bool:
        return 0 <= x < self.image.width and 0 <= y < self.image.height

    def crop_zoom(self, region: list[float]) -> Image.Image:
        """Zoom: region in screenshot coords -> that area at higher detail, same size budget."""
        return self.zoom_source(region)

    zoom_source: Callable = None  # set by the capturer (needs the full-resolution image)


def png_block(img: Image.Image) -> dict:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "PNG", optimize=True)
    return {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                        "data": base64.standard_b64encode(buf.getvalue()).decode()}}


def make_frame(full: Image.Image, origin: tuple[int, int] = (0, 0)) -> Frame:
    w, h = full.size
    s = scale_factor(w, h)
    small = full.resize((max(1, int(w * s)), max(1, int(h * s))), Image.LANCZOS) if s < 1 else full.copy()
    frame = Frame(image=small, scale=s, origin=origin, real_size=(w, h))

    def zoom(region):
        x0, y0, x1, y1 = [float(v) for v in region]
        if x1 <= x0 or y1 <= y0:
            raise ValueError("zoom region must be [x0, y0, x1, y1] with x1>x0 and y1>y0")
        box = (int(x0 / s), int(y0 / s), int(math.ceil(x1 / s)), int(math.ceil(y1 / s)))
        box = (max(0, box[0]), max(0, box[1]), min(w, box[2]), min(h, box[3]))
        crop = full.crop(box)
        zs = scale_factor(*crop.size)
        if zs < 1:
            crop = crop.resize((max(1, int(crop.width * zs)), max(1, int(crop.height * zs))), Image.LANCZOS)
        return crop
    frame.zoom_source = zoom
    return frame


def capture_frame(monitor: int = 1) -> Frame:
    import mss
    with mss.mss() as sct:
        mons = sct.monitors
        mon = mons[monitor] if monitor < len(mons) else mons[1 if len(mons) > 1 else 0]
        shot = sct.grab(mon)
        full = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    return make_frame(full, (mon["left"], mon["top"]))
