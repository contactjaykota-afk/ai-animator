"""Claude integration.

Claude is the *reasoning* engine: it plans, critiques, analyzes references
and drives tools. It does not produce image files itself - that is the job
of the image-provider system (ai/providers).

Conversation records are stored in the project's chat/history.jsonl. The
assistant's full content blocks (including thinking blocks) are kept and sent
back unchanged on later turns, as the API requires.
"""
from __future__ import annotations

import base64
import io
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import anthropic
from PIL import Image

from ai_animator.ai.prompts import CURRENT_CAPABILITIES, STUDIO_SYSTEM_PROMPT
from ai_animator.config.settings import SecretStore, Settings

log = logging.getLogger(__name__)

FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_IMAGE_EDGE = 1568  # larger images are downscaled before sending


@dataclass
class ChatResult:
    text: str = ""
    content: list[dict] = field(default_factory=list)  # raw blocks to store
    stop_reason: str = ""
    model: str = ""
    cancelled: bool = False
    error: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


def encode_image(path: Path) -> dict:
    """Load an image file as an API image block (downscaled, PNG/JPEG)."""
    with Image.open(path) as im:
        im.load()
        if max(im.size) > MAX_IMAGE_EDGE:
            im.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE), Image.LANCZOS)
        has_alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
        buf = io.BytesIO()
        if has_alpha:
            im.convert("RGBA").save(buf, "PNG")
            media = "image/png"
        else:
            im.convert("RGB").save(buf, "JPEG", quality=90)
            media = "image/jpeg"
    return {"type": "image", "source": {"type": "base64", "media_type": media,
                                        "data": base64.standard_b64encode(buf.getvalue()).decode()}}


def to_api_content(content: list[dict], project_root: Path | None) -> list[dict]:
    """Convert stored blocks to API blocks ('local_image' -> base64 image)."""
    out = []
    for block in content:
        if block.get("type") == "local_image":
            path = Path(block["path"])
            if project_root is not None and not path.is_absolute():
                path = project_root / path
            if path.exists():
                out.append(encode_image(path))
            else:
                out.append({"type": "text", "text": f"[image missing: {block['path']}]"})
        else:
            out.append(block)
    return out


def friendly_error(exc: Exception) -> str:
    if isinstance(exc, anthropic.AuthenticationError):
        return "Your Anthropic API key is missing or invalid. Open Settings to add it."
    if isinstance(exc, anthropic.PermissionDeniedError):
        return "This API key doesn't have permission for that model. Try another model in Settings."
    if isinstance(exc, anthropic.NotFoundError):
        return "Model not found. Pick a different model in Settings."
    if isinstance(exc, anthropic.RateLimitError):
        return "Rate limit reached. Wait a moment and try again."
    if isinstance(exc, anthropic.BadRequestError):
        return f"The request was rejected: {getattr(exc, 'message', exc)}"
    if isinstance(exc, anthropic.APIStatusError):
        return f"Anthropic API error ({exc.status_code}). Please try again."
    if isinstance(exc, anthropic.APIConnectionError):
        return "Can't reach the Anthropic API. Check your internet connection."
    if isinstance(exc, TypeError) and "api_key" in str(exc).lower():
        return "No Anthropic API key configured. Open Settings to add it."
    return f"{type(exc).__name__}: {exc}"


class ClaudeService:
    def __init__(self, settings: Settings, secrets: SecretStore,
                 client_factory: Callable[[str | None], object] | None = None):
        self.settings = settings
        self.secrets = secrets
        self._factory = client_factory or (lambda key: anthropic.Anthropic(api_key=key) if key
                                           else anthropic.Anthropic())

    def make_client(self):
        return self._factory(self.secrets.get_api_key())

    def has_key(self) -> bool:
        return bool(self.secrets.get_api_key())

    def build_system(self, project_memory: str = "") -> list[dict]:
        blocks = [{"type": "text", "text": STUDIO_SYSTEM_PROMPT},
                  {"type": "text", "text": CURRENT_CAPABILITIES}]
        if project_memory:
            blocks.append({"type": "text", "text": "PROJECT MEMORY\n" + project_memory})
        return blocks

    def build_messages(self, records: list[dict], project_root: Path | None) -> list[dict]:
        msgs: list[dict] = []
        for rec in records:
            if rec.get("role") not in ("user", "assistant") or not rec.get("content"):
                continue
            msgs.append({"role": rec["role"], "content": to_api_content(rec["content"], project_root)})
        return msgs

    def stream_reply(self, messages: list[dict], system: list[dict],
                     on_text: Callable[[str], None] = lambda t: None,
                     should_cancel: Callable[[], bool] = lambda: False) -> ChatResult:
        result = ChatResult()
        try:
            client = self._factory(self.secrets.get_api_key())
            with client.beta.messages.stream(
                model=self.settings.model,
                max_tokens=self.settings.max_tokens,
                system=system,
                messages=messages,
                thinking={"type": "adaptive"},
                output_config={"effort": self.settings.effort},
                cache_control={"type": "ephemeral"},
                betas=[FALLBACK_BETA],
                fallbacks="default",
            ) as stream:
                for text in stream.text_stream:
                    if should_cancel():
                        result.cancelled = True
                        break
                    result.text += text
                    on_text(text)
                if not result.cancelled:
                    final = stream.get_final_message()
                    result.stop_reason = final.stop_reason or ""
                    result.model = final.model
                    result.content = [b.to_dict() for b in final.content]
                    result.text = "".join(b.text for b in final.content if b.type == "text")
                    usage = final.usage
                    result.input_tokens = (usage.input_tokens or 0) + (usage.cache_read_input_tokens or 0)
                    result.output_tokens = usage.output_tokens or 0
        except Exception as exc:  # surfaced to the UI as a readable message
            log.exception("Claude request failed")
            result.error = friendly_error(exc)
            return result

        if result.cancelled:
            partial = result.text.strip()
            result.content = [{"type": "text", "text": (partial + "\n\n[stopped by user]") if partial
                               else "[stopped by user]"}]
        elif result.stop_reason == "refusal":
            result.error = "Claude declined this request. Try rephrasing it."
        elif result.stop_reason == "max_tokens":
            result.text += "\n\n[reply hit the length limit]"
        return result

    def test_connection(self) -> str:
        """Tiny request used by the Settings screen. Returns the serving model."""
        client = self._factory(self.secrets.get_api_key())
        msg = client.messages.create(
            model=self.settings.model, max_tokens=64,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": "Reply with the single word: ready"}],
        )
        return msg.model
