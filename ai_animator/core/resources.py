"""Locate bundled resources both from source and inside a PyInstaller .exe."""
from __future__ import annotations

import sys
from pathlib import Path


def resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "resources" / name if (base / "resources").exists() else \
        Path(__file__).resolve().parent.parent / "resources" / name
