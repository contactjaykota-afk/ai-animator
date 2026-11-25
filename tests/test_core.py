import zipfile
from pathlib import Path

import pytest
from PIL import Image

from ai_animator.config.settings import SecretStore, Settings, mask_key
from ai_animator.core.fileio import unique_path
from ai_animator.projects.manager import ProjectManager
from ai_animator.safety.approval import (ActionRequest, ApprovalQueue, ConfirmationRequired,
                                         EmergencyStop, Risk, Status)
from ai_animator.workflows.registry import suggest_workflow


def make_png(path: Path, size=(64, 48), color=(200, 30, 40)):
    Image.new("RGB", size, color).save(path)
    return path


# ---- settings & secrets ----------------------------------------------------
def test_settings_roundtrip_and_sanitize():
    s = Settings.load()
    assert s.model == "claude-opus-5-5"
    s.effort = "high"
    s.save()
    assert Settings.load().effort == "high"
    Settings.path().write_text('{"model": "bogus", "effort": "x", "require_approval": false}')
    s2 = Settings.load()
    assert s2.model == "claude-opus-5-5" and s2.effort == "medium" and s2.require_approval is True


def test_api_key_never_written_to_settings(keyring_mem):
    store = SecretStore(keyring_mem)
    store.set_api_key("sk-ant-secret-123456789")
    Settings.load().save()
    assert "sk-ant" not in Settings.path().read_text()
    assert store.get_api_key() == "sk-ant-secret-123456789"
    store.clear_api_key()
    assert store.get_api_key() is None


def test_env_key_fallback(keyring_mem, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-env-key-abcdef1234")
    store = SecretStore(keyring_mem)
    assert store.get_api_key() == "sk-env-key-abcdef1234"
    assert "environment" in store.key_source()
    assert mask_key("sk-ant-abcdefghijkl1234").endswith("1234")


def test_unique_path(tmp_path):
    a = tmp_path / "x.png"
    a.write_text("1")
    assert unique_path(a).name == "x_1.png"


# ---- projects ----------------------------------------------------------------
def test_project_lifecycle(tmp_path):
    pm = ProjectManager(tmp_path / "projects")
    p = pm.create_project("My Horror Short", "test", "animation_2d")
    assert (p.root / "references").is_dir() and (p.root / "project.json").exists()
    p2 = pm.create_project("My Horror Short")
    assert p2.root != p.root  # never overwrites an existing project
    ch = p.add_character("Mr. Grin", "tall clown", "three scars on left cheek")
    assert p.find_character("grin").id == ch.id
    assert p.find_character("nobody") is None
    reopened = pm.open_project(p.root)
    assert reopened.characters()[0].design_notes == "three scars on left cheek"


def test_reference_import_copies_and_never_overwrites(tmp_path):
    pm = ProjectManager(tmp_path / "projects")
    p = pm.create_project("Refs")
    ch = p.add_character("Hero")
    src = make_png(tmp_path / "ref.png")
    r1 = p.import_reference(src, ["style", "bogus"], notes="hair only")
    r2 = p.import_reference(src, ["character"], character_id=ch.id)
    assert src.exists()
    assert r1.file != r2.file
    assert r1.roles == ["style"]
    assert p.characters()[0].reference_ids == [r2.id]
    mem = p.memory_summary()
    assert "roles=style" in mem and "hair only" in mem
    with pytest.raises(ValueError):
        p.import_reference(tmp_path / "notes.txt")


def test_chat_history_tolerates_torn_line(tmp_path):
    p = ProjectManager(tmp_path / "pr").create_project("Chat")
    p.append_chat({"role": "user", "content": [{"type": "text", "text": "hi"}]})
    with open(p.chat_file, "a") as fh:
        fh.write('{"role": "assist')  # simulated crash mid-write
    assert len(p.load_chat()) == 1


def test_backup_and_delete(tmp_path):
    pm = ProjectManager(tmp_path / "pr")
    p = pm.create_project("Doomed")
    p.add_memory_note("eyes are always yellow")
    b = p.backup("before change")
    assert zipfile.ZipFile(b).namelist()
    archive = pm.delete_project(p)
    assert not p.root.exists() and archive.exists()
    assert "project.json" in zipfile.ZipFile(archive).namelist()


# ---- approval queue ----------------------------------------------------------
def test_approval_requires_approval_and_verifies():
    q = ApprovalQueue(EmergencyStop())
    ran = []
    req = q.submit(ActionRequest("Click Import", "Adobe Animate", "import art", "art on stage",
                                 execute=lambda: ran.append(1) or "ok", verify=lambda r: r == "ok"))
    assert req.status == Status.PENDING and not ran
    q.approve(req.id)
    assert ran == [1] and req.status == Status.SUCCEEDED


def test_unverified_is_not_success():
    q = ApprovalQueue(EmergencyStop())
    req = q.submit(ActionRequest("t", "a", "r", "e", execute=lambda: None))
    q.approve(req.id)
    assert req.status == Status.UNVERIFIED
    req2 = q.submit(ActionRequest("t", "a", "r", "e", execute=lambda: 1, verify=lambda r: False))
    q.approve(req2.id)
    assert req2.status == Status.UNVERIFIED


def test_reject_and_failure():
    q = ApprovalQueue(EmergencyStop())
    ran = []
    r = q.submit(ActionRequest("t", "a", "r", "e", execute=lambda: ran.append(1)))
    q.reject(r.id)
    assert r.status == Status.REJECTED and not ran
    with pytest.raises(RuntimeError):
        q.approve(r.id)
    f = q.submit(ActionRequest("t", "a", "r", "e", execute=lambda: 1 / 0))
    q.approve(f.id)
    assert f.status == Status.FAILED and "ZeroDivision" in f.error


def test_destructive_needs_second_confirmation():
    q = ApprovalQueue(EmergencyStop())
    ran = []
    r = q.submit(ActionRequest("Delete", "Explorer", "r", "e", risk=Risk.DESTRUCTIVE,
                               execute=lambda: ran.append(1) or True, verify=bool))
    with pytest.raises(ConfirmationRequired):
        q.approve(r.id)
    assert not ran and r.status == Status.PENDING
    q.approve(r.id, confirmed_destructive=True)
    assert ran and r.status == Status.SUCCEEDED


def test_emergency_stop_cancels_and_blocks():
    stop = EmergencyStop()
    q = ApprovalQueue(stop)
    ran = []
    r = q.submit(ActionRequest("t", "a", "r", "e", execute=lambda: ran.append(1)))
    stop.trigger()
    assert q.cancel_all() == 1 and r.status == Status.CANCELLED
    r2 = q.submit(ActionRequest("t", "a", "r", "e", execute=lambda: ran.append(1)))
    assert r2.status == Status.CANCELLED
    stop.reset()
    r3 = q.submit(ActionRequest("t", "a", "r", "e", execute=lambda: ran.append(1)))
    q.approve(r3.id)
    assert ran == [1]


def test_workflow_suggestions():
    assert suggest_workflow("make a logo for my band").id == "logo"
    assert suggest_workflow("animate a walk cycle").id == "frame_by_frame"
    assert suggest_workflow("FNF character for psych engine").id == "fnf_character"
    assert suggest_workflow("paint a foggy forest background").id == "environment"
