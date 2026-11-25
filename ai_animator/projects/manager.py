"""Project management and project memory.

A project is a folder:

    <Project Name>/
        project.json      <- metadata + memory (characters, references, notes)
        references/       <- imported reference images (copies; originals untouched)
        characters/       <- per-character artwork (Phase 3)
        artwork/          <- illustrations, environments, props, ...
        animation/        <- timelines and frames (Phase 4)
        exports/          <- finished output
        chat/history.jsonl
        backups/          <- automatic zip snapshots

Nothing in here ever overwrites an existing file: imports get unique names
and a backup is taken before risky changes.
"""
from __future__ import annotations

import json
import shutil
import uuid
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ai_animator.core.fileio import read_json, slugify, unique_path, write_json_atomic

PROJECT_FILE = "project.json"
SUBDIRS = ["references", "characters", "artwork", "animation", "exports", "chat", "backups"]
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}

# What a reference image is *for*. The AI must not blend every reference into
# one design; each reference controls only the aspects the user assigned.
REFERENCE_ROLES = {
    "style": "Art style (linework, shading, palette, rendering)",
    "character": "Character design (shapes, features, costume)",
    "anatomy": "Anatomy / pose / proportions",
    "animation": "Animation (timing, motion, poses)",
    "composition": "Composition / framing / lighting",
    "environment": "Environment / background",
    "palette": "Color palette only",
    "general": "General inspiration (low priority)",
}

PROJECT_TYPES = {
    "general": "General creative project",
    "illustration": "Illustration / concept art",
    "character": "Character design",
    "animation_2d": "2D animation",
    "animation_3d": "3D animation workflow",
    "fnf": "Friday Night Funkin' character",
    "game_assets": "Game assets / sprites",
    "graphic_design": "Logo / graphic design",
    "comic": "Comic / manga / storyboard",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Reference:
    id: str
    file: str                     # path relative to the project folder
    roles: list[str] = field(default_factory=lambda: ["general"])
    notes: str = ""               # e.g. "only use the hair shading, not the face"
    character_id: str = ""        # optional link to a character
    added: str = field(default_factory=_now)


@dataclass
class Character:
    id: str
    name: str
    description: str = ""
    design_notes: str = ""        # locked details that must stay consistent
    reference_ids: list[str] = field(default_factory=list)
    created: str = field(default_factory=_now)
    updated: str = field(default_factory=_now)


class Project:
    def __init__(self, root: Path, data: dict):
        self.root = Path(root)
        self.data = data

    # ---- basic properties -------------------------------------------------
    @property
    def name(self) -> str:
        return self.data["name"]

    @property
    def id(self) -> str:
        return self.data["id"]

    @property
    def project_type(self) -> str:
        return self.data.get("type", "general")

    def save(self) -> None:
        self.data["updated"] = _now()
        write_json_atomic(self.root / PROJECT_FILE, self.data)

    # ---- characters --------------------------------------------------------
    def characters(self) -> list[Character]:
        return [Character(**c) for c in self.data.get("characters", [])]

    def add_character(self, name: str, description: str = "", design_notes: str = "") -> Character:
        if not name.strip():
            raise ValueError("Character name is required")
        ch = Character(id=uuid.uuid4().hex[:8], name=name.strip(),
                       description=description.strip(), design_notes=design_notes.strip())
        self.data.setdefault("characters", []).append(asdict(ch))
        self.save()
        return ch

    def update_character(self, char_id: str, **changes) -> Character:
        for c in self.data.get("characters", []):
            if c["id"] == char_id:
                for k, v in changes.items():
                    if k in ("name", "description", "design_notes", "reference_ids"):
                        c[k] = v
                c["updated"] = _now()
                self.save()
                return Character(**c)
        raise KeyError(char_id)

    def find_character(self, query: str) -> Character | None:
        """Resolve "him", "the clown", "Mr. Grin" style references by name."""
        q = query.strip().lower()
        if not q:
            return None
        chars = self.characters()
        for c in chars:
            if c.name.lower() == q:
                return c
        for c in chars:
            if q in c.name.lower() or c.name.lower() in q:
                return c
        return None

    # ---- references --------------------------------------------------------
    def references(self) -> list[Reference]:
        return [Reference(**r) for r in self.data.get("references", [])]

    def import_reference(self, src: Path, roles: list[str] | None = None,
                         notes: str = "", character_id: str = "") -> Reference:
        src = Path(src)
        if src.suffix.lower() not in IMAGE_EXTS:
            raise ValueError(f"Unsupported image type: {src.suffix}")
        roles = [r for r in (roles or ["general"]) if r in REFERENCE_ROLES] or ["general"]
        dest = unique_path(self.root / "references" / src.name)
        shutil.copy2(src, dest)  # copy - the user's original stays where it was
        ref = Reference(id=uuid.uuid4().hex[:8], file=dest.relative_to(self.root).as_posix(),
                        roles=roles, notes=notes, character_id=character_id)
        self.data.setdefault("references", []).append(asdict(ref))
        if character_id:
            for c in self.data.get("characters", []):
                if c["id"] == character_id:
                    c.setdefault("reference_ids", []).append(ref.id)
        self.save()
        return ref

    def update_reference(self, ref_id: str, **changes) -> Reference:
        for r in self.data.get("references", []):
            if r["id"] == ref_id:
                if "roles" in changes:
                    r["roles"] = [x for x in changes["roles"] if x in REFERENCE_ROLES] or ["general"]
                for k in ("notes", "character_id"):
                    if k in changes:
                        r[k] = changes[k]
                self.save()
                return Reference(**r)
        raise KeyError(ref_id)

    def reference_path(self, ref: Reference) -> Path:
        return self.root / ref.file

    # ---- memory notes ------------------------------------------------------
    def add_memory_note(self, text: str) -> None:
        if text.strip():
            self.data.setdefault("memory", []).append({"text": text.strip(), "added": _now()})
            self.save()

    def memory_summary(self) -> str:
        """Compact text the AI receives so it remembers this project."""
        lines = [f"Project: {self.name} (type: {PROJECT_TYPES.get(self.project_type, self.project_type)})"]
        if self.data.get("description"):
            lines.append(f"Description: {self.data['description']}")
        chars = self.characters()
        if chars:
            lines.append("Characters:")
            for c in chars:
                lines.append(f"  - {c.name} [id {c.id}]: {c.description}")
                if c.design_notes:
                    lines.append(f"    LOCKED DESIGN DETAILS: {c.design_notes}")
        refs = self.references()
        if refs:
            lines.append("Reference images (each controls ONLY its listed roles):")
            for r in refs:
                who = f", for character {r.character_id}" if r.character_id else ""
                note = f" - note: {r.notes}" if r.notes else ""
                lines.append(f"  - {r.file}: roles={','.join(r.roles)}{who}{note}")
        notes = self.data.get("memory", [])
        if notes:
            lines.append("Remembered decisions:")
            lines += [f"  - {n['text']}" for n in notes[-30:]]
        return "\n".join(lines)

    # ---- chat history ------------------------------------------------------
    @property
    def chat_file(self) -> Path:
        return self.root / "chat" / "history.jsonl"

    def append_chat(self, record: dict) -> None:
        self.chat_file.parent.mkdir(exist_ok=True)
        with open(self.chat_file, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def load_chat(self) -> list[dict]:
        out = []
        if self.chat_file.exists():
            for line in self.chat_file.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue  # a torn last line after a crash - skip it
        return out

    # ---- backups -----------------------------------------------------------
    def backup(self, reason: str = "manual") -> Path:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = unique_path(self.root / "backups" / f"{stamp}_{slugify(reason)}.zip")
        dest.parent.mkdir(exist_ok=True)
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in self.root.rglob("*"):
                if p.is_file() and "backups" not in p.relative_to(self.root).parts:
                    zf.write(p, p.relative_to(self.root).as_posix())
        return dest


class ProjectManager:
    def __init__(self, projects_dir: Path):
        self.projects_dir = Path(projects_dir)
        self.projects_dir.mkdir(parents=True, exist_ok=True)

    def list_projects(self) -> list[Project]:
        out = []
        for d in sorted(self.projects_dir.iterdir()):
            if d.is_dir() and (d / PROJECT_FILE).exists():
                try:
                    out.append(self.open_project(d))
                except Exception:
                    continue
        return sorted(out, key=lambda p: p.data.get("updated", ""), reverse=True)

    def create_project(self, name: str, description: str = "", project_type: str = "general") -> Project:
        if not name.strip():
            raise ValueError("Project name is required")
        root = unique_path(self.projects_dir / slugify(name))
        root.mkdir(parents=True)
        for sub in SUBDIRS:
            (root / sub).mkdir()
        data = {
            "format": 1, "id": uuid.uuid4().hex, "name": name.strip(),
            "description": description.strip(),
            "type": project_type if project_type in PROJECT_TYPES else "general",
            "created": _now(), "updated": _now(),
            "characters": [], "references": [], "memory": [],
            "settings": {"canvas": [1024, 1024], "fps": 24},
        }
        project = Project(root, data)
        project.save()
        return project

    def open_project(self, root: Path) -> Project:
        root = Path(root)
        data = read_json(root / PROJECT_FILE)
        if not data or "name" not in data:
            raise ValueError(f"Not an AI Animator project: {root}")
        for sub in SUBDIRS:
            (root / sub).mkdir(exist_ok=True)
        return Project(root, data)

    def delete_project(self, project: Project) -> Path:
        """Destructive. Only call after explicit user approval.
        A full zip is kept in <projects>/_deleted_backups first."""
        safe_dir = self.projects_dir / "_deleted_backups"
        safe_dir.mkdir(exist_ok=True)
        archive = unique_path(safe_dir / f"{project.root.name}_{datetime.now():%Y%m%d_%H%M%S}.zip")
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in project.root.rglob("*"):
                if p.is_file():
                    zf.write(p, p.relative_to(project.root).as_posix())
        shutil.rmtree(project.root)
        return archive
