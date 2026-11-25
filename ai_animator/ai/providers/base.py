"""Image-generation provider interface.

Claude cannot output image files. Pictures come from a separate provider
(e.g. a local ComfyUI / Stable Diffusion server, or a cloud image API).
Every provider implements the same interface so they can be swapped
without touching the rest of the app. Real providers arrive in Phase 3.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ImageRequest:
    prompt: str
    negative_prompt: str = ""
    width: int = 1024
    height: int = 1024
    transparent: bool = False
    style_reference_paths: list[Path] = field(default_factory=list)
    structure_reference: Path | None = None   # pose / lineart / depth guide
    init_image: Path | None = None            # for redraw / img2img
    mask: Path | None = None                  # for "redraw only this area"
    seed: int | None = None
    count: int = 1


@dataclass
class ImageResult:
    paths: list[Path]
    seed: int | None = None
    provider: str = ""
    metadata: dict = field(default_factory=dict)


class ProviderUnavailable(RuntimeError):
    pass


class ImageProvider(ABC):
    id: str = "base"
    name: str = "Base"
    supports_inpainting = False
    supports_transparency = False
    supports_references = False
    requires_api_key = False
    is_local = False

    @abstractmethod
    def is_available(self) -> tuple[bool, str]:
        """(ready?, human-readable status)"""

    @abstractmethod
    def generate(self, request: ImageRequest, out_dir: Path) -> ImageResult:
        ...


class NoProvider(ImageProvider):
    id = "none"
    name = "No image provider (set up in Phase 3)"

    def is_available(self):
        return False, "No image-generation provider is configured yet (Phase 3)."

    def generate(self, request, out_dir):
        raise ProviderUnavailable("No image-generation provider is configured yet.")


_REGISTRY: dict[str, type[ImageProvider]] = {NoProvider.id: NoProvider}


def register(cls: type[ImageProvider]) -> type[ImageProvider]:
    _REGISTRY[cls.id] = cls
    return cls


def available_providers() -> dict[str, type[ImageProvider]]:
    return dict(_REGISTRY)


def get_provider(provider_id: str) -> ImageProvider:
    return _REGISTRY.get(provider_id, NoProvider)()
