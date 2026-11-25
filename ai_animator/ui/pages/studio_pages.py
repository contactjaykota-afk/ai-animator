"""Drawing / Animation / FNF studios.

These are honest placeholders: they show the planned features and the phase
in which each arrives, instead of pretending to work.
"""
from __future__ import annotations

from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget

from ai_animator.workflows.registry import WORKFLOWS

STUDIOS = {
    "drawing": ("Drawing Studio", "Phase 3", [
        "Layered canvas (sketch / lineart / flats / shading / highlights / FX)",
        "Rough sketch → refine → clean lineart → shade pipeline",
        "Redraw only a selected area (masked edits) - the rest stays locked",
        "Transparent backgrounds, PNG/PSD/SVG export",
        "Version history and side-by-side comparison",
        "Any subject & technique: characters, environments, props, logos, pixel art, painterly…",
    ], ["illustration", "character", "environment", "logo", "pixel_art", "storyboard"]),
    "animation": ("Animation Studio", "Phase 4", [
        "Timeline with per-frame inspection, onion skin and holds",
        "Key poses → breakdowns → in-betweens with timing charts",
        "Frame-by-frame, cutout/rig, motion graphics and VFX workflows",
        "Loops, previews at any FPS, PNG sequences / GIF / MP4 / sprite sheets",
        "3D workflows through Blender (Phase 6)",
    ], ["frame_by_frame", "cutout", "motion_graphics", "3d_animation"]),
    "fnf": ("FNF Studio", "Phase 5", [
        "Presets: idle, singLEFT, singDOWN, singUP, singRIGHT (+ miss and custom anims)",
        "Configurable frame counts per animation",
        "Sparrow atlas (PNG + XML) export with offsets",
        "Psych Engine character JSON generation",
        "Organized export folder ready to drop into a mod",
    ], ["fnf_character"]),
}


class StudioPage(QWidget):
    def __init__(self, key: str):
        super().__init__()
        title, phase, features, wfs = STUDIOS[key]
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 12)
        t = QLabel(title)
        t.setObjectName("H1")
        root.addWidget(t)
        badge = QLabel(f"Not built yet — arrives in {phase}. Use Studio Chat to plan this work now.")
        badge.setObjectName("Badge")
        root.addWidget(badge)
        card = QFrame()
        card.setObjectName("Card")
        cl = QVBoxLayout(card)
        h = QLabel("Planned features")
        h.setObjectName("H2")
        cl.addWidget(h)
        for f in features:
            lbl = QLabel("•  " + f)
            lbl.setWordWrap(True)
            cl.addWidget(lbl)
        root.addWidget(card)
        card2 = QFrame()
        card2.setObjectName("Card")
        g = QGridLayout(card2)
        h = QLabel("Workflows this studio will run")
        h.setObjectName("H2")
        g.addWidget(h, 0, 0, 1, 2)
        for i, wid in enumerate(wfs):
            wf = WORKFLOWS[wid]
            lbl = QLabel(f"<b>{wf.name}</b><br><span style='color:#8b8b99'>"
                         f"{' → '.join(wf.stages)}</span>")
            lbl.setWordWrap(True)
            g.addWidget(lbl, 1 + i // 2, i % 2)
        root.addWidget(card2)
        root.addStretch()
