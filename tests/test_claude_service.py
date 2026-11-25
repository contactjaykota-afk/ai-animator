"""Claude service tested against a fake client (no network, no API cost)."""
from types import SimpleNamespace

import anthropic
import httpx2 as httpx
from PIL import Image

from ai_animator.ai.claude_service import ClaudeService, encode_image, to_api_content
from ai_animator.config.settings import SecretStore, Settings


class FakeBlock(SimpleNamespace):
    def to_dict(self):
        return dict(vars(self))


class FakeStream:
    def __init__(self, chunks, stop_reason="end_turn"):
        self.chunks, self.stop_reason = chunks, stop_reason

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    @property
    def text_stream(self):
        yield from self.chunks

    def get_final_message(self):
        blocks = [FakeBlock(type="thinking", thinking="", signature="sig"),
                  FakeBlock(type="text", text="".join(self.chunks))]
        return SimpleNamespace(content=blocks, stop_reason=self.stop_reason, model="claude-opus-5-5",
                               usage=SimpleNamespace(input_tokens=10, cache_read_input_tokens=5,
                                                     output_tokens=7))


class FakeClient:
    def __init__(self, stream=None, exc=None):
        self.calls = []
        self._stream, self._exc = stream, exc
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._make))

    def _make(self, **kw):
        self.calls.append(kw)
        if self._exc:
            raise self._exc
        return self._stream


def service(client):
    return ClaudeService(Settings.load(), SecretStore(backend=None), client_factory=lambda key: client)


def test_stream_reply_collects_text_and_blocks():
    client = FakeClient(FakeStream(["Hel", "lo"]))
    got = []
    r = service(client).stream_reply([{"role": "user", "content": "hi"}], [], on_text=got.append)
    assert r.text == "Hello" and got == ["Hel", "lo"] and not r.error
    assert r.content[0]["type"] == "thinking"  # thinking blocks preserved for next turn
    kw = client.calls[0]
    assert kw["model"] == "claude-opus-5-5"
    assert kw["thinking"] == {"type": "adaptive"}
    assert kw["fallbacks"] == "default" and "server-side-fallback-2026-07-01" in kw["betas"]
    assert "temperature" not in kw
    assert r.input_tokens == 15


def test_cancel_mid_stream():
    client = FakeClient(FakeStream(["a", "b", "c"]))
    n = {"i": 0}

    def cancel():
        n["i"] += 1
        return n["i"] > 1

    r = service(client).stream_reply([], [], should_cancel=cancel)
    assert r.cancelled and r.text == "a"
    assert "[stopped by user]" in r.content[0]["text"]


def test_refusal_and_errors_are_reported():
    r = service(FakeClient(FakeStream(["x"], stop_reason="refusal"))).stream_reply([], [])
    assert "declined" in r.error
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    exc = anthropic.AuthenticationError("bad key", response=httpx.Response(401, request=req), body=None)
    r2 = service(FakeClient(exc=exc)).stream_reply([], [])
    assert "API key" in r2.error


def test_image_encoding_and_local_images(tmp_path):
    big = tmp_path / "big.png"
    Image.new("RGBA", (3000, 1000), (1, 2, 3, 128)).save(big)
    block = encode_image(big)
    assert block["source"]["media_type"] == "image/png"
    content = to_api_content([{"type": "local_image", "path": "big.png"},
                              {"type": "local_image", "path": "missing.png"},
                              {"type": "text", "text": "hi"}], tmp_path)
    assert content[0]["type"] == "image" and "missing" in content[1]["text"] and content[2]["text"] == "hi"


def test_system_includes_project_memory():
    sys_blocks = service(FakeClient()).build_system("Project: X\nCharacters: Mr. Grin")
    assert any("Mr. Grin" in b["text"] for b in sys_blocks)
    assert "never blend" in sys_blocks[0]["text"].lower()
