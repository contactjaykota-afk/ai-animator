"""Desktop agent tests: scripted Claude + fake desktop. No real mouse/keyboard is touched."""
import threading
import time
from types import SimpleNamespace

import pytest
from PIL import Image

from ai_animator.desktop.actions import ActionExecutor
from ai_animator.desktop.agent import NOT_EXECUTED, DesktopAgent, RunControl
from ai_animator.desktop.frames import make_frame, scale_factor
from ai_animator.desktop.input_backend import FakeInput, parse_combo
from ai_animator.desktop.policy import PermissionProfile, classify
from ai_animator.safety.approval import ApprovalQueue, EmergencyStop, Status


class Block(SimpleNamespace):
    def to_dict(self):
        return dict(vars(self))


def use(i, name, **inp):
    return Block(type="tool_use", id=f"t{i}", name=name, toolset_name="computer", input=inp)


def text(t):
    return Block(type="text", text=t)


class ScriptedClaude:
    """Returns one scripted assistant turn per request; records every request."""

    def __init__(self, turns):
        self.turns = list(turns)
        self.requests = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **kw):
        self.requests.append({**kw, "messages": list(kw["messages"])})
        content = self.turns.pop(0)
        stop = "tool_use" if any(b.type == "tool_use" for b in content) else "end_turn"
        msg = SimpleNamespace(content=content, stop_reason=stop)

        class S:
            def __enter__(s):
                return s

            def __exit__(s, *a):
                return False

            def get_final_message(s):
                return msg
        return S()


def make_agent(turns, mode="autonomous", title="Untitled - Notepad", **profile):
    backend = FakeInput(2560, 1440)
    full = Image.new("RGB", (2560, 1440), (30, 30, 30))
    stop = EmergencyStop()
    control = RunControl(stop)
    ex = ActionExecutor(backend, lambda: make_frame(full), checkpoint=control.checkpoint)
    q = ApprovalQueue(stop)
    claude = ScriptedClaude(turns)
    agent = DesktopAgent(lambda: claude, "claude-opus-5-5", "medium", ex, q, control,
                         PermissionProfile.from_dict({"mode": mode, **profile}),
                         window_title=lambda: title)
    return agent, backend, q, claude, control


def test_screenshot_is_scaled_and_coordinates_map_back():
    f = make_frame(Image.new("RGB", (2560, 1440)))
    assert max(f.image.size) <= 1568 and f.image.width * f.image.height <= 1_150_000
    x, y = f.to_screen(f.image.width / 2, f.image.height / 2)
    assert abs(x - 1280) <= 2 and abs(y - 720) <= 2
    assert scale_factor(1024, 768) == 1.0


def test_autonomous_run_executes_actions_and_verifies():
    agent, backend, q, claude, _ = make_agent([
        [text("Opening the menu."), use(1, "left_click", coordinate=[100, 50]), use(2, "type", text="hello")],
        [text("Done: typed hello and confirmed it on screen.")],
    ])
    r = agent.run("type hello")
    assert r.status == "completed" and r.steps == 2
    assert ("type", "hello") in backend.calls
    assert ("button", "left", True) in backend.calls
    sent_x, sent_y = backend.calls[0][1], backend.calls[0][2]   # first call is the move
    assert sent_x > 100 and sent_y > 50                          # scaled up to real pixels
    req = claude.requests[1]
    results = req["messages"][-1]["content"]
    assert all(r["toolset_name"] == "computer" for r in results)
    # verification screenshot attached to the last result of the batch
    assert any(c.get("type") == "image" for c in results[-1]["content"])
    tools = claude.requests[0]["tools"]
    assert tools[0] == {"type": "computer_toolset_20260801"}


def test_batch_stops_at_first_failure():
    agent, backend, q, claude, _ = make_agent([
        [use(1, "left_click", coordinate=[99999, 5]), use(2, "type", text="never")],
        [text("I could not click there.")],
    ])
    r = agent.run("x")
    results = claude.requests[1]["messages"][-1]["content"]
    assert results[0]["is_error"] and "outside the screenshot" in results[0]["content"]
    assert results[1]["content"] == NOT_EXECUTED
    assert ("type", "never") not in backend.calls
    assert r.status == "completed"


def run_in_thread(agent, task="t"):
    out = {}
    th = threading.Thread(target=lambda: out.setdefault("r", agent.run(task)))
    th.start()
    return th, out


def wait_pending(q, n=1, timeout=3):
    end = time.time() + timeout
    while time.time() < end:
        if len(q.pending()) >= n:
            return q.pending()
        time.sleep(0.02)
    raise AssertionError("no pending approval")


def test_supervised_waits_for_approval_and_reject_blocks_action():
    agent, backend, q, claude, _ = make_agent([
        [use(1, "type", text="secret plan")],
        [text("Stopped because you rejected it.")],
    ], mode="supervised")
    th, out = run_in_thread(agent)
    req = wait_pending(q)[0]
    assert "Type" in req.title and ("type", "secret plan") not in backend.calls
    q.reject(req.id)
    th.join(5)
    assert ("type", "secret plan") not in backend.calls
    assert "rejected" in claude.requests[1]["messages"][-1]["content"][0]["content"]


def test_supervised_approve_runs_action():
    agent, backend, q, claude, _ = make_agent([
        [use(1, "key", text="ctrl+s")], [text("Saved.")]], mode="supervised")
    th, out = run_in_thread(agent)
    q.approve(wait_pending(q)[0].id)
    th.join(5)
    assert out["r"].status == "completed"
    assert ("key", "ctrl", True) in backend.calls and ("key", "s", True) in backend.calls


def test_autonomous_still_confirms_sensitive_window():
    agent, backend, q, claude, _ = make_agent([
        [use(1, "left_click", coordinate=[10, 10])], [text("ok")]],
        mode="autonomous", title="Checkout - Payment - Browser")
    th, out = run_in_thread(agent)
    req = wait_pending(q)[0]
    assert "purchase" in req.reason
    q.reject(req.id)
    th.join(5)
    assert ("button", "left", True) not in backend.calls


def test_destructive_key_needs_typed_confirmation_flag():
    d = classify("key", {"text": "shift+Delete"}, "Explorer", PermissionProfile.from_dict({"mode": "autonomous"}))
    assert d.needs_approval and d.destructive
    d2 = classify("type", {"text": "rm -rf /"}, "editor", PermissionProfile.from_dict({"mode": "autonomous"}))
    assert d2.needs_approval
    d3 = classify("left_click", {}, "Krita", PermissionProfile.from_dict({"mode": "autonomous",
                                                                         "allowed_apps": ["Animate"]}))
    assert d3.needs_approval and "allowed" in d3.reasons[0]
    assert classify("screenshot", {}, "Checkout", PermissionProfile()).needs_approval is False


def test_safety_categories_cannot_be_disabled():
    p = PermissionProfile.from_dict({"confirm_categories": [], "mode": "yolo", "max_steps": 10**9})
    assert {"delete", "install", "purchase", "credentials", "overwrite"} <= set(p.confirm_categories)
    assert p.mode == "supervised" and p.max_steps == 1000


def test_confirmation_tool_round_trip():
    confirm = Block(type="tool_use", id="c1", name="request_user_confirmation",
                    input={"action": "Delete old.png", "reason": "cleanup", "category": "delete"})
    agent, backend, q, claude, _ = make_agent([[confirm], [text("Skipped deleting.")]])
    th, out = run_in_thread(agent)
    req = wait_pending(q)[0]
    assert req.risk.value == "destructive"
    q.reject(req.id)
    th.join(5)
    res = claude.requests[1]["messages"][-1]["content"][0]
    assert "DECLINED" in res["content"] and "toolset_name" not in res


def test_stop_during_approval_ends_run():
    agent, backend, q, claude, control = make_agent([[use(1, "type", text="x")]], mode="supervised")
    th, out = run_in_thread(agent)
    wait_pending(q)
    control.stop.trigger()
    q.cancel_all()
    th.join(5)
    assert out["r"].status == "stopped" and ("type", "x") not in backend.calls


def test_pause_blocks_until_resume():
    agent, backend, q, claude, control = make_agent([
        [use(1, "type", text="abc")], [text("done")]])
    control.pause()
    th, out = run_in_thread(agent)
    time.sleep(0.3)
    assert not claude.requests  # paused before even asking Claude
    control.resume()
    th.join(5)
    assert out["r"].status == "completed" and ("type", "abc") in backend.calls


def test_step_limit():
    agent, backend, q, claude, _ = make_agent([
        [use(1, "key", text="a"), use(2, "key", text="b"), use(3, "key", text="c")]], max_steps=2)
    r = agent.run("t")
    assert r.status == "limit" and r.steps == 2
    assert ("key", "c", True) not in backend.calls


def test_executor_members():
    backend = FakeInput()
    full = Image.new("RGB", (1024, 768))
    ex = ActionExecutor(backend, lambda: make_frame(full))
    ex.run("screenshot", {})
    ex.run("scroll", {"coordinate": [10, 10], "scroll_direction": "down", "scroll_amount": 3})
    assert ("scroll", 0, -3) in backend.calls
    ex.run("left_click_drag", {"start_coordinate": [0, 0], "coordinate": [100, 100], "text": "shift"})
    assert backend.calls[-1] == ("key", "shift", False) and backend.pos == (100, 100)
    ex.run("key", {"text": "Tab", "repeat": 3})
    assert sum(1 for c in backend.calls if c == ("key", "Tab", True)) == 3
    assert ex.run("cursor_position", {}) == "X=100,Y=100"
    zoom = ex.run("zoom", {"region": [0, 0, 200, 100]})
    assert zoom[0]["type"] == "image"
    for bad in [("scroll", {"scroll_direction": "sideways"}), ("key", {"text": ""}),
                ("teleport", {}), ("type", {"text": 5})]:
        with pytest.raises(ValueError):
            ex.run(*bad)
    assert parse_combo("ctrl++") == ["ctrl", "+"] and parse_combo("ctrl+shift+s") == ["ctrl", "shift", "s"]
