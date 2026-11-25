"""Application settings and secure API-key storage.

Settings (model, folders, preferences) are plain JSON in the per-user app
data folder. API keys are NEVER written to that JSON or to project files:
they go to the operating system's credential vault (Windows Credential
Manager via `keyring`). An ANTHROPIC_API_KEY environment variable also works.
"""
from __future__ import annotations

import logging
import os
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from ai_animator.core.fileio import read_json, write_json_atomic

log = logging.getLogger(__name__)

KEYRING_SERVICE = "AI Animator"
KEYRING_ANTHROPIC = "anthropic_api_key"

AVAILABLE_MODELS = {
    "claude-opus-5-5": "Claude Opus 5.5 (best quality - default)",
    "claude-sonnet-5-5": "Claude Sonnet 5.5 (faster, cheaper)",
    "claude-haiku-5-5": "Claude Haiku 5.5 (fastest, cheapest)",
}
EFFORT_LEVELS = ["low", "medium", "high", "xhigh", "max"]


def app_data_dir() -> Path:
    """Per-user folder for settings and logs.

    Windows: %APPDATA%\\AI Animator   Other: ~/.config/ai_animator
    AI_ANIMATOR_HOME overrides both (used by tests and portable installs).
    """
    override = os.environ.get("AI_ANIMATOR_HOME")
    if override:
        base = Path(override)
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home())) / "AI Animator"
    else:
        base = Path.home() / ".config" / "ai_animator"
    base.mkdir(parents=True, exist_ok=True)
    return base


def default_projects_dir() -> Path:
    override = os.environ.get("AI_ANIMATOR_HOME")
    if override:
        return Path(override) / "Projects"
    return Path.home() / "Documents" / "AI Animator Projects"


@dataclass
class Settings:
    model: str = "claude-opus-5-5"
    effort: str = "medium"
    max_tokens: int = 64000
    projects_dir: str = field(default_factory=lambda: str(default_projects_dir()))
    last_project: str = ""
    image_provider: str = "none"
    require_approval: bool = True  # cannot be turned off from the UI
    agent_profile: dict = field(default_factory=dict)
    agent_consent: bool = False

    @classmethod
    def path(cls) -> Path:
        return app_data_dir() / "settings.json"

    @classmethod
    def load(cls) -> "Settings":
        raw = read_json(cls.path(), default={}) or {}
        known = {f.name for f in fields(cls)}
        s = cls(**{k: v for k, v in raw.items() if k in known})
        if s.model not in AVAILABLE_MODELS:
            s.model = "claude-opus-5-5"
        if s.effort not in EFFORT_LEVELS:
            s.effort = "medium"
        s.require_approval = True
        return s

    def save(self) -> None:
        write_json_atomic(self.path(), asdict(self))


class SecretStore:
    """Reads/writes the Anthropic API key in the OS credential vault."""

    def __init__(self, backend=None, service: str = KEYRING_SERVICE, use_env: bool = True):
        self.service = service
        self.use_env = use_env
        if backend is None:
            try:
                import keyring
                backend = keyring
            except Exception:  # pragma: no cover - keyring missing
                backend = None
        self._kr = backend

    def get_api_key(self) -> str | None:
        if self._kr is not None:
            try:
                key = self._kr.get_password(self.service, KEYRING_ANTHROPIC)
                if key:
                    return key
            except Exception as exc:
                log.warning("Credential vault unavailable: %s", exc)
        return (os.environ.get("ANTHROPIC_API_KEY") or None) if self.use_env else None

    def key_source(self) -> str:
        if self._kr is not None:
            try:
                if self._kr.get_password(self.service, KEYRING_ANTHROPIC):
                    return "Windows Credential Manager" if sys.platform == "win32" else "system keyring"
            except Exception:
                pass
        if self.use_env and os.environ.get("ANTHROPIC_API_KEY"):
            return "ANTHROPIC_API_KEY environment variable"
        return "not set"

    def set_api_key(self, key: str) -> None:
        key = key.strip()
        if not key:
            raise ValueError("API key is empty")
        if self._kr is None:
            raise RuntimeError("No secure credential store is available on this system.")
        self._kr.set_password(self.service, KEYRING_ANTHROPIC, key)

    def clear_api_key(self) -> None:
        if self._kr is None:
            return
        try:
            self._kr.delete_password(self.service, KEYRING_ANTHROPIC)
        except Exception:
            pass


def mask_key(key: str | None) -> str:
    if not key:
        return ""
    return key[:7] + "..." + key[-4:] if len(key) > 14 else "*" * len(key)
