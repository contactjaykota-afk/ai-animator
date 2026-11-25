"""Runs one desktop-agent task and wires it to the overlay, control bar and STOP systems."""
from __future__ import annotations

import logging
import threading

from PySide6.QtCore import QObject, QThread, Signal

from ai_animator.desktop.actions import ActionExecutor
from ai_animator.desktop.agent import AgentResult, DesktopAgent, RunControl
from ai_animator.desktop.frames import capture_frame
from ai_animator.desktop.input_backend import InputBackend
from ai_animator.desktop.policy import PermissionProfile
from ai_animator.desktop.watchers import GlobalHotkey, MouseWatcher
from ai_animator.safety.approval import Risk, Status

log = logging.getLogger(__name__)


class TrackedInput(InputBackend):
    """Wraps the real backend and remembers where the AI put the cursor (for takeover detection)."""

    def __init__(self, inner: InputBackend):
        self.inner = inner
        self.expected: tuple[int, int] | None = None
        self._lock = threading.Lock()

    def move(self, x, y):
        with self._lock:
            self.expected = None
            self.inner.move(x, y)
            self.expected = (x, y)

    def button(self, b, down):
        self.inner.button(b, down)

    def scroll(self, dx, dy):
        self.inner.scroll(dx, dy)

    def key(self, n, down):
        self.inner.key(n, down)

    def type_text(self, t):
        self.inner.type_text(t)

    def cursor_position(self):
        return self.inner.cursor_position()

    def forget(self):
        self.expected = None


class _Runner(QThread):
    done = Signal(object)

    def __init__(self, agent: DesktopAgent, task: str, refs):
        super().__init__()
        self.agent, self.task, self.refs = agent, task, refs

    def run(self):
        self.done.emit(self.agent.run(self.task, self.refs))


class AgentSession(QObject):
    event = Signal(str, object)          # (kind, data) from the agent thread
    finished = Signal(object)            # AgentResult
    paused_changed = Signal(bool)
    _glide = Signal(int, int)
    _stop_now = Signal()
    _pause_now = Signal(str)

    def __init__(self, state, backend: InputBackend, profile: PermissionProfile,
                 window_title, capture=capture_frame, show_overlay: bool = True):
        super().__init__()
        self.state = state
        self.profile = profile
        self.input = TrackedInput(backend)
        self.control = RunControl(state.stop)
        self.control.on_pause_change = self.paused_changed.emit
        self.show_overlay = show_overlay
        self.border = self.cursor = self.bar = None
        before = lambda x, y: None
        if show_overlay:
            from ai_animator.ui.overlay import AICursor, ControlBar, ControlBorder, CursorBridge
            self.border, self.cursor, self.bar = ControlBorder(), AICursor(), ControlBar()
            self._glide.connect(self.cursor.glide_to)
            before = CursorBridge(self.cursor, self._glide).before_pointer
            self.bar.pause_clicked.connect(lambda: self.pause("paused by you"))
            self.bar.resume_clicked.connect(self.resume)
            self.bar.stop_clicked.connect(state.emergency_stop)
            self.bar.approve_clicked.connect(self._approve_from_bar)
            self.bar.reject_clicked.connect(lambda rid: rid and state.approvals.reject(rid))
            self.paused_changed.connect(self._on_paused_ui)
            state.action_updated.connect(self._on_action_ui)
            self.event.connect(self._on_event_ui)
        self.executor = ActionExecutor(self.input, capture, before_pointer=before,
                                       checkpoint=self.control.checkpoint)
        self.agent = DesktopAgent(lambda: state.claude.make_client(), state.settings.model,
                                  state.settings.effort, self.executor, state.approvals, self.control,
                                  profile, window_title=window_title,
                                  on_event=lambda k, d: self.event.emit(k, d))
        self._stop_now.connect(state.emergency_stop)
        self._pause_now.connect(self.pause)
        self.hotkey = GlobalHotkey(self._stop_now.emit)
        self.watcher = MouseWatcher(self.input.cursor_position, lambda: self.input.expected,
                                    on_corner=self._corner, on_takeover=self._takeover)
        self.runner: _Runner | None = None
        state.stop_triggered.connect(self._on_stop)

    # ---- lifecycle -------------------------------------------------------------
    def start(self, task: str, reference_images=None) -> None:
        self.state.resume_after_stop()
        log.warning("DESKTOP CONTROL ACTIVE (%s mode): %s", self.profile.mode, task[:120])
        if self.show_overlay:
            self.border.show()
            self.bar.set_status(f"{self.profile.mode.capitalize()} mode - starting…")
            self.bar.show()
        self.hotkey.start()
        self.watcher.start()
        self.runner = _Runner(self.agent, task, reference_images or [])
        self.runner.done.connect(self._finish)
        self.runner.start()

    def pause(self, reason: str = "") -> None:
        self.control.pause(reason)
        self.input.forget()

    def resume(self) -> None:
        self.input.forget()  # don't treat the click on "Resume" as a takeover
        self.control.resume()

    def _corner(self) -> None:
        log.warning("Mouse pushed into the screen corner - emergency stop")
        self._stop_now.emit()

    def _takeover(self) -> None:
        if not self.control.paused:
            self.input.forget()
            self._pause_now.emit("you moved the mouse, so the AI paused. Press Resume to continue.")

    def _on_stop(self) -> None:
        self.control.resume()  # unblock a paused thread so it can see the stop

    def _finish(self, result: AgentResult) -> None:
        self.watcher.stop()
        self.hotkey.stop()
        if self.show_overlay:
            for w in (self.border, self.cursor, self.bar):
                w.hide()
                w.deleteLater()
            self.state.action_updated.disconnect(self._on_action_ui)
        log.warning("Desktop control ended: %s (%d steps)", result.status, result.steps)
        if self.runner:
            self.runner.wait(2000)
        self.finished.emit(result)

    @property
    def running(self) -> bool:
        return bool(self.runner and self.runner.isRunning())

    # ---- control bar wiring ---------------------------------------------------
    def _approve_from_bar(self, rid: str) -> None:
        if not rid:
            return
        req = self.state.approvals.get(rid)
        if req.risk == Risk.DESTRUCTIVE:
            from PySide6.QtWidgets import QInputDialog
            text, ok = QInputDialog.getText(None, "Confirm destructive step",
                                            f"{req.title}\n\nType DELETE to confirm:")
            if not (ok and text.strip().upper() == "DELETE"):
                return
            self.state.approvals.approve(rid, confirmed_destructive=True)
        else:
            self.state.approvals.approve(rid)

    def _on_action_ui(self, req) -> None:
        if req.status == Status.PENDING:
            self.bar.show_request(req.id, f"{req.title}<br><span style='color:#8b8b99'>{req.reason}</span>",
                                  req.risk == Risk.DESTRUCTIVE)
        else:
            self.bar.clear_request(req.id)

    def _on_paused_ui(self, paused: bool) -> None:
        self.bar.set_paused(paused)
        self.border.paused = paused
        self.border.update()
        if paused:
            self.bar.set_status("Paused - " + ("press Resume to continue."))

    def _on_event_ui(self, kind: str, data) -> None:
        if kind in ("status", "action") and not self.control.paused:
            self.bar.set_status(str(data)[:160])
