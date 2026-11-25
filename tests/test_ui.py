"""Smoke tests for the real window, run headless (offscreen)."""
import pytest
from PySide6.QtWidgets import QApplication

from ai_animator.config.settings import SecretStore, Settings
from ai_animator.safety.approval import Status
from ai_animator.ui.main_window import MainWindow
from ai_animator.ui.state import AppState
from ai_animator.ui.theme import STYLESHEET


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    a.setStyleSheet(STYLESHEET)
    return a


def test_window_builds_and_navigates(app, keyring_mem):
    state = AppState(Settings.load(), SecretStore(keyring_mem))
    win = MainWindow(state)
    win.show()
    assert win.stack.currentWidget() is win.pages["settings"]  # no key -> setup screen first
    for key in win.pages:
        win.show_page(key)
        app.processEvents()
    win.close()


def test_project_delete_goes_through_approval(app, keyring_mem):
    state = AppState(Settings.load(), SecretStore(keyring_mem))
    win = MainWindow(state)
    p = state.projects.create_project("Delete Me")
    state.set_project(p)
    page = win.pages["projects"]
    page.refresh()
    page.list.setCurrentRow(0)
    page.delete_selected()
    app.processEvents()
    pending = state.approvals.pending()
    assert len(pending) == 1 and p.root.exists()  # nothing happened yet
    assert not win.right.cards[pending[0].id].approve.isHidden()
    state.emergency_stop()
    assert pending[0].status == Status.CANCELLED and p.root.exists()
    win.close()


def test_project_switch_updates_chat(app, keyring_mem):
    state = AppState(Settings.load(), SecretStore(keyring_mem))
    win = MainWindow(state)
    p = state.projects.create_project("Chatty")
    p.append_chat({"role": "user", "content": [{"type": "text", "text": "hello"}], "display": "hello"})
    state.set_project(p)
    chat = win.pages["chat"]
    assert "Chatty" in chat.project_label.text()
    assert chat.feed_lay.count() == 3  # welcome + 1 message + stretch
    win.close()
