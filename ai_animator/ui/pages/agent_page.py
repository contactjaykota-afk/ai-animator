"""Desktop Agent page: give a task, choose permissions, watch it work."""
from __future__ import annotations

import logging
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (QCheckBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QMessageBox, QPlainTextEdit, QPushButton, QRadioButton,
                               QSpinBox, QVBoxLayout, QWidget)

from ai_animator.core.screen import active_window_title
from ai_animator.desktop.policy import PermissionProfile

log = logging.getLogger(__name__)

CONSENT = ("<b>Before the AI controls your computer</b><br>"
           "• It moves the real mouse and types on your real keyboard. A red border and its own "
           "cursor show whenever it's in control.<br>"
           "• STOP anytime: the STOP button, <b>Shift+Esc</b>, or push your mouse into the "
           "<b>top-left corner</b>. Moving your mouse yourself pauses it.<br>"
           "• Deleting, overwriting, installing, purchases, logins and sending always need your "
           "approval, even in Autonomous mode. These checks are a safety net, not a guarantee.<br>"
           "• Text on web pages can try to trick AI agents. Close sensitive windows (banking, "
           "email, password managers) before starting.")


def pil_to_pixmap(img) -> QPixmap:
    img = img.convert("RGB")
    q = QImage(img.tobytes(), img.width, img.height, img.width * 3, QImage.Format_RGB888).copy()
    return QPixmap.fromImage(q)


class AgentPage(QWidget):
    def __init__(self, state, backend_factory=None, capture=None, show_overlay=True):
        super().__init__()
        self.state = state
        self.backend_factory = backend_factory
        self.capture = capture
        self.show_overlay = show_overlay
        self.session = None
        prof = PermissionProfile.from_dict(state.settings.agent_profile)

        root = QHBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 12)
        left = QVBoxLayout()
        t = QLabel("Desktop Agent")
        t.setObjectName("H1")
        left.addWidget(t)
        sub = QLabel("Give it a task. It looks at your screen, plans, uses the mouse and keyboard, "
                     "and checks its own work, while you watch.")
        sub.setObjectName("Muted")
        sub.setWordWrap(True)
        left.addWidget(sub)

        self.task = QPlainTextEdit()
        self.task.setPlaceholderText('e.g. "Open Krita, create a new 1920x1080 canvas and save it as '
                                     'test.kra in Documents"')
        self.task.setFixedHeight(90)
        left.addWidget(self.task)

        perm = QFrame()
        perm.setObjectName("Card")
        g = QGridLayout(perm)
        h = QLabel("Permissions")
        h.setObjectName("H2")
        g.addWidget(h, 0, 0, 1, 4)
        self.supervised = QRadioButton("Supervised: approve every step")
        self.autonomous = QRadioButton("Autonomous: works alone within limits")
        (self.autonomous if prof.mode == "autonomous" else self.supervised).setChecked(True)
        g.addWidget(self.supervised, 1, 0, 1, 2)
        g.addWidget(self.autonomous, 1, 2, 1, 2)
        g.addWidget(QLabel("Allowed apps"), 2, 0)
        self.apps = QLineEdit(", ".join(prof.allowed_apps))
        self.apps.setPlaceholderText("window-title keywords, e.g. Animate, Krita (empty = any app)")
        g.addWidget(self.apps, 2, 1, 1, 3)
        g.addWidget(QLabel("Max steps"), 3, 0)
        self.max_steps = QSpinBox()
        self.max_steps.setRange(1, 1000)
        self.max_steps.setValue(prof.max_steps)
        g.addWidget(self.max_steps, 3, 1)
        g.addWidget(QLabel("Max minutes"), 3, 2)
        self.max_minutes = QSpinBox()
        self.max_minutes.setRange(1, 240)
        self.max_minutes.setValue(prof.max_minutes)
        g.addWidget(self.max_minutes, 3, 3)
        self.minimize = QCheckBox("Minimize AI Animator while the agent works")
        self.minimize.setChecked(True)
        g.addWidget(self.minimize, 4, 0, 1, 4)
        always = QLabel("Always asks first: delete • overwrite • install • purchases • logins/passwords "
                        "• sending messages • system settings")
        always.setObjectName("Muted")
        always.setWordWrap(True)
        g.addWidget(always, 5, 0, 1, 4)
        left.addWidget(perm)

        row = QHBoxLayout()
        self.start_btn = QPushButton("▶ Start")
        self.start_btn.setObjectName("Primary")
        self.start_btn.clicked.connect(self.start)
        self.pause_btn = QPushButton("⏸ Pause")
        self.pause_btn.clicked.connect(self.toggle_pause)
        self.stop_btn = QPushButton("■ Stop")
        self.stop_btn.setObjectName("Reject")
        self.stop_btn.clicked.connect(state.emergency_stop)
        for b in (self.start_btn, self.pause_btn, self.stop_btn):
            row.addWidget(b)
        left.addLayout(row)
        self.status = QLabel("Idle")
        self.status.setObjectName("H2")
        self.status.setWordWrap(True)
        left.addWidget(self.status)
        self.steps = QListWidget()
        left.addWidget(self.steps, 1)
        root.addLayout(left, 3)

        right = QVBoxLayout()
        h = QLabel("What the AI sees")
        h.setObjectName("H2")
        right.addWidget(h)
        self.preview = QLabel("Live view appears here while the agent works.")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(360, 220)
        self.preview.setStyleSheet("background:#0c0c0f; border:1px solid #23232b; border-radius:6px;")
        right.addWidget(self.preview)
        h = QLabel("Its reasoning")
        h.setObjectName("H2")
        right.addWidget(h)
        self.thoughts = QPlainTextEdit()
        self.thoughts.setReadOnly(True)
        right.addWidget(self.thoughts, 1)
        root.addLayout(right, 2)
        self._set_running(False)

    # ---- helpers ---------------------------------------------------------------
    def profile(self) -> PermissionProfile:
        return PermissionProfile.from_dict({
            "mode": "autonomous" if self.autonomous.isChecked() else "supervised",
            "allowed_apps": [a.strip() for a in self.apps.text().split(",") if a.strip()],
            "max_steps": self.max_steps.value(), "max_minutes": self.max_minutes.value(),
        })

    def _set_running(self, running: bool) -> None:
        self.start_btn.setEnabled(not running)
        self.pause_btn.setEnabled(running)
        self.stop_btn.setEnabled(running)
        for w in (self.supervised, self.autonomous, self.apps, self.max_steps, self.max_minutes, self.task):
            w.setEnabled(not running)

    # ---- actions ---------------------------------------------------------------
    def start(self, _=False, skip_consent: bool = False) -> bool:
        task = self.task.toPlainText().strip()
        if not task or (self.session and self.session.running):
            return False
        if not self.state.claude.has_key():
            QMessageBox.warning(self, "API key needed",
                                "The desktop agent needs your Anthropic API key.\n\n"
                                "Open Settings, paste your key, press Save key, then Test connection.")
            self.state.navigate.emit("settings")
            return False
        if not skip_consent and not self.state.settings.agent_consent:
            box = QMessageBox(QMessageBox.Warning, "Desktop control", CONSENT,
                              QMessageBox.Ok | QMessageBox.Cancel, self)
            box.button(QMessageBox.Ok).setText("I understand, start")
            if box.exec() != QMessageBox.Ok:
                return False
            self.state.settings.agent_consent = True
        try:
            backend = (self.backend_factory or _default_backend)()
        except Exception as exc:
            QMessageBox.warning(self, "Desktop control unavailable", str(exc))
            return False
        prof = self.profile()
        self.state.settings.agent_profile = prof.to_dict()
        self.state.settings.save()

        from ai_animator.desktop.frames import capture_frame
        from ai_animator.ui.agent_session import AgentSession
        self.session = AgentSession(self.state, backend, prof, active_window_title,
                                    capture=self.capture or capture_frame, show_overlay=self.show_overlay)
        self.session.event.connect(self._on_event)
        self.session.finished.connect(self._on_finished)
        self.session.paused_changed.connect(lambda p: self.pause_btn.setText("▶ Resume" if p else "⏸ Pause"))
        self.steps.clear()
        self.thoughts.clear()
        self._set_running(True)
        self.status.setText(f"Running ({prof.mode})…")
        self.state.task_changed.emit(f"Desktop agent: {task[:60]}", -1)
        if self.minimize.isChecked() and self.window():
            self.window().showMinimized()
        self.session.start(task)
        return True

    def toggle_pause(self) -> None:
        if not self.session:
            return
        if self.session.control.paused:
            self.session.resume()
        else:
            self.session.pause("paused by you")

    def _on_event(self, kind: str, data) -> None:
        if kind == "frame":
            pix = pil_to_pixmap(data)
            self.preview.setPixmap(pix.scaled(self.preview.width() - 4, self.preview.height() - 4,
                                              Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.state.screen_frame.emit(pix)
        elif kind == "action":
            self.steps.addItem(str(data))
            self.steps.scrollToBottom()
            log.info("AI action: %s", data)
        elif kind == "thinking":
            self.thoughts.appendPlainText("💭 " + str(data).strip() + "\n")
        elif kind == "say":
            self.thoughts.appendPlainText("🗨 " + str(data).strip() + "\n")
        elif kind == "status":
            self.status.setText(str(data))

    def _on_finished(self, result) -> None:
        self._set_running(False)
        labels = {"completed": "✔ Finished", "stopped": "■ Stopped", "limit": "⚠ Limit reached",
                  "refused": "✖ Declined", "error": "✖ Error"}
        self.status.setText(f"{labels.get(result.status, result.status)} - {result.steps} actions"
                            + (f": {result.summary}" if result.status == "error" else ""))
        if result.summary:
            self.thoughts.appendPlainText("── Result ──\n" + result.summary)
        self.state.task_changed.emit(f"Desktop agent {result.status}", 100 if result.status == "completed" else 0)
        w = self.window()
        if w and w.isMinimized():
            w.showNormal()
            w.raise_()
            w.activateWindow()
        if result.status == "error":
            detail = result.errors[-1][:800] if result.errors else ""
            QMessageBox.warning(self, "Desktop agent stopped",
                                f"{result.summary}\n\nTechnical details (safe to share, contains no key):\n{detail}")
        if self.state.project:
            self.state.project.add_memory_note(
                f"Desktop task ({result.status}, {result.steps} actions): "
                f"{self.task.toPlainText().strip()[:200]}")


def _default_backend():
    if sys.platform != "win32":
        raise RuntimeError("Desktop control works on Windows only.")
    from ai_animator.desktop.input_backend import WindowsInput
    return WindowsInput()
