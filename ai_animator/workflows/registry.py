"""Creative workflows.

Different jobs need different pipelines. A workflow is an ordered list of
stages; the planner (Phase 3+) picks one from the request and adapts it.
FNF is one preset among many - not the core of the app.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Workflow:
    id: str
    name: str
    stages: tuple[str, ...]
    outputs: tuple[str, ...]
    keywords: tuple[str, ...] = field(default=())


WORKFLOWS: dict[str, Workflow] = {w.id: w for w in [
    Workflow("illustration", "Illustration / concept art",
             ("brief", "reference analysis", "thumbnails", "rough sketch", "refined sketch",
              "lineart", "flats", "shading & lighting", "texture & detail", "review", "export"),
             ("layered PSD/PNG", "flattened PNG"),
             ("draw", "illustration", "painting", "concept", "poster", "art")),
    Workflow("character", "Character design",
             ("brief", "reference analysis", "silhouettes", "design sketch", "expression sheet",
              "turnaround", "color callouts", "lock design notes", "export"),
             ("turnaround sheet", "layered body parts"),
             ("character", "oc", "turnaround", "design")),
    Workflow("environment", "Environment / background",
             ("brief", "perspective & composition", "value study", "color keys", "render",
              "parallax layer split", "export"),
             ("layered background", "parallax layers"),
             ("background", "environment", "landscape", "building", "scene")),
    Workflow("logo", "Logo / graphic design",
             ("brief", "concept sketches", "vector build", "typography", "color variants",
              "small-size test", "export"),
             ("SVG", "PNG set"),
             ("logo", "icon", "graphic", "emblem")),
    Workflow("frame_by_frame", "Frame-by-frame 2D animation",
             ("brief", "key poses", "timing chart", "breakdowns", "in-betweens",
              "cleanup", "color", "consistency review", "preview", "export"),
             ("PNG sequence", "GIF/MP4", "sprite sheet"),
             ("animate", "animation", "walk", "run", "cycle", "idle", "lip", "fight")),
    Workflow("cutout", "Cutout / rig animation",
             ("separate parts", "pivot setup", "rig", "keyframes", "easing", "secondary motion",
              "preview", "export"),
             ("rigged project", "PNG sequence"),
             ("cutout", "rig", "puppet", "bones")),
    Workflow("motion_graphics", "Motion graphics / logo animation",
             ("brief", "styleframes", "animatic", "animate", "polish", "export"),
             ("MP4", "GIF", "Lottie"), ("motion graphics", "logo animation", "title")),
    Workflow("storyboard", "Storyboard / animatic",
             ("script breakdown", "shot list", "thumbnails", "panels", "timing", "animatic"),
             ("panel sheet", "animatic MP4"), ("storyboard", "comic", "manga", "panel", "shot")),
    Workflow("pixel_art", "Pixel art & sprites",
             ("palette", "silhouette", "pixel pass", "shading", "animation frames", "sheet export"),
             ("PNG sprite sheet", "Aseprite file"), ("pixel", "sprite", "8-bit", "16-bit")),
    Workflow("fnf_character", "FNF character package",
             ("character design lock", "idle", "singLEFT", "singDOWN", "singUP", "singRIGHT",
              "extra anims", "offsets", "Sparrow atlas + XML", "Psych Engine JSON"),
             ("Sparrow PNG/XML", "character JSON"), ("fnf", "friday night funkin", "psych engine")),
    Workflow("3d_animation", "3D animation workflow (via Blender)",
             ("concept", "model/blockout", "rig", "animate", "light", "render", "export"),
             ("Blender file", "render sequence"), ("3d", "blender", "model", "render")),
]}


def suggest_workflow(request: str) -> Workflow:
    """Simple keyword guess; Claude refines the choice in the planner."""
    text = request.lower()
    best, score = WORKFLOWS["illustration"], 0
    for wf in WORKFLOWS.values():
        s = sum(len(k) for k in wf.keywords if k in text)
        if s > score:
            best, score = wf, s
    return best
