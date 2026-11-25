"""Desktop Agent page + overlay + control bar, end to end on a fake desktop (offscreen)."""
import time

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication

from ai_animator.config.settings import SecretStore, Settings
from ai_animator.desktop.frames import make_frame
from ai_animator.desktop.input_backend import FakeInput
from ai_animator.desktop.watchers import MouseWatcher
from ai_animator.ui.main_window import MainWindow
from ai_animator.ui.state import AppState
from tests.test_desktop_agent import ScriptedClaude, text, use


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def pump(app, cond, timeout=8):
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.01)
    return False


def setup(app, keyring_mem, turns, mode):
    state = AppState(Settings.load(), SecretStore(keyring_mem))
    claude = ScriptedClaude(turns)
    state.claude._factory = lambda key: claude
    backend = FakeInput(1920, 1080)
    win = MainWindow(state)
    page = win.pages["agent"]
    page.backend_factory = lambda: backend
    page.capture = lambda: make_frame(Image.new("RGB", (1920, 1080), (20, 20, 20)))
    page.minimize.setChecked(False)
    page.task.setPlainText("Type hi into the editor")
    (page.autonomous if mode == "autonomous" else page.supervised).setChecked(True)
    return state, claude, backend, win, page


def test_supervised_run_with_control_bar_approval(app, keyring_mem):
    state, claude, backend, win, page = setup(app, keyring_mem, [
        [text("Typing now."), use(1, "type", text="hi")], [text("Typed hi; verified on screen.")]],
        "supervised")
    assert page.start(skip_consent=True)
    sess = page.session
    assert sess.border.isVisible() and sess.bar.isVisible()          # control indicator shown
    assert pump(app, lambda: sess.bar.approve_row.isVisible())        # approval shown on the bar
    assert ("type", "hi") not in backend.calls
    sess.bar.approve_btn.click()
    assert pump(app, lambda: "Finished" in page.status.text(), timeout=10)
    assert ("type", "hi") in backend.calls
    assert "Finished" in page.status.text() and page.steps.count() == 1
    assert "Typed hi" in page.thoughts.toPlainText()
    win.close()


def test_stop_button_ends_autonomous_run(app, keyring_mem):
    state, claude, backend, win, page = setup(app, keyring_mem, [
        [use(1, "wait", duration=30)], [text("never")]], "autonomous")
    page.start(skip_consent=True)
    sess = page.session
    assert pump(app, lambda: page.steps.count() == 1)                 # waiting inside the action
    sess.bar.stop_btn.click()                                         # STOP on the control bar
    assert pump(app, lambda: "Stopped" in page.status.text(), timeout=8)
    assert len(claude.requests) == 1                                  # no further turns
    win.close()


def test_user_mouse_takeover_pauses_and_resume_continues(app, keyring_mem):
    state, claude, backend, win, page = setup(app, keyring_mem, [
        [use(1, "left_click", coordinate=[100, 100])],
        [use(2, "wait", duration=2)], [text("done")]], "autonomous")
    page.start(skip_consent=True)
    sess = page.session
    assert pump(app, lambda: backend.pos != (0, 0))                   # AI moved its cursor
    backend.pos = (900, 900)                                          # the user grabs the mouse
    assert pump(app, lambda: sess.control.paused, timeout=3)
    assert "Resume" in sess.bar.pause_btn.text()
    sess.bar.pause_btn.click()                                        # Resume
    assert pump(app, lambda: "Finished" in page.status.text(), timeout=10)
    win.close()


def test_corner_stop_logic():
    hits = []
    pos = {"p": (500, 500)}
    w = MouseWatcher(lambda: pos["p"], lambda: (500, 500), lambda: hits.append("stop"),
                     lambda: hits.append("pause"))
    assert w.check_once() == ""
    pos["p"] = (0, 0)
    assert w.check_once() == "corner" and hits == ["stop"]
    resting = MouseWatcher(lambda: (0, 0), lambda: None, lambda: hits.append("bad"), lambda: None)
    assert resting.check_once() == ""                                 # already there at start: no stop
    w2 = MouseWatcher(lambda: (0, 0), lambda: (0, 0), lambda: hits.append("x"), lambda: None)
    assert w2.check_once() == ""                                      # the AI itself is at the corner
