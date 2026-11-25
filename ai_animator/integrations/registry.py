"""Creative-application integrations.

Each external app gets an adapter describing how we can control it, in
order of reliability: official scripting > file-based exchange > UI
automation (mouse/keyboard, always behind approval). Phase 1 only detects
installed apps; the adapters are implemented in Phase 6.
"""
from __future__ import annotations

import glob
import os
import shutil
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class AppIntegration:
    id: str
    name: str
    good_for: str
    control_methods: tuple[str, ...]
    exe_globs: tuple[str, ...]          # Windows install locations
    path_names: tuple[str, ...] = ()    # executables on PATH

    def find_executable(self) -> str | None:
        for name in self.path_names:
            found = shutil.which(name)
            if found:
                return found
        if sys.platform != "win32":
            return None
        for pattern in self.exe_globs:
            pattern = os.path.expandvars(pattern)
            hits = sorted(glob.glob(pattern))
            if hits:
                return hits[-1]
        return None


PF = r"%ProgramFiles%"
INTEGRATIONS: dict[str, AppIntegration] = {a.id: a for a in [
    AppIntegration("animate", "Adobe Animate", "frame-by-frame & symbol animation, FLA projects",
                   ("JSFL scripts", "file import/export", "UI automation"),
                   (PF + r"\Adobe\Adobe Animate*\Animate.exe",)),
    AppIntegration("photoshop", "Adobe Photoshop", "painting, layered PSD, photo-style edits",
                   ("ExtendScript/UXP scripts", "PSD files", "UI automation"),
                   (PF + r"\Adobe\Adobe Photoshop*\Photoshop.exe",)),
    AppIntegration("illustrator", "Adobe Illustrator", "vector art, logos",
                   ("ExtendScript", "SVG/AI files", "UI automation"),
                   (PF + r"\Adobe\Adobe Illustrator*\Support Files\Contents\Windows\Illustrator.exe",)),
    AppIntegration("blender", "Blender", "3D, 2D Grease Pencil animation, rendering",
                   ("Python API (headless)", "file import/export"),
                   (PF + r"\Blender Foundation\Blender*\blender.exe",), ("blender",)),
    AppIntegration("krita", "Krita", "painting, frame-by-frame animation (free)",
                   ("Python scripting", ".kra/PNG files", "UI automation"),
                   (PF + r"\Krita (x64)\bin\krita.exe",), ("krita",)),
    AppIntegration("aseprite", "Aseprite", "pixel art and sprite animation",
                   ("command-line + Lua scripts", ".aseprite/PNG sheets"),
                   (PF + r"\Aseprite\Aseprite.exe", r"%ProgramFiles(x86)%\Steam\steamapps\common\Aseprite\Aseprite.exe"),
                   ("aseprite",)),
]}


def detect_installed() -> dict[str, str | None]:
    return {app_id: app.find_executable() for app_id, app in INTEGRATIONS.items()}
