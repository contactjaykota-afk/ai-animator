"""Chat with the studio AI."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QFileDialog, QFrame, QHBoxLayout, QLabel, QMessageBox,
                               QPlainTextEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget)

from ai_animator.projects.manager import IMAGE_EXTS
from ai_animator.ui.workers import ChatWorker
from ai_animator.workflows.registry import suggest_workflow

log = logging.getLogger(__name__)

WELCOME = ("**Welcome to AI Animator.** Describe what you want to create - a character, a "
           "creature, an environment, a logo, an animation - and attach reference images with "
           "📎. I'll plan it with you and remember the project.\n\n"
           "*Phase 1 build: planning, critique, reference analysis and project memory work now. "
           "Image generation and the animation engine arrive in later phases.*")


class Bubble(QFrame):
    def __init__(self, role: str, text: str = "", images: list[str] | None = None):
        super().__init__()
        self.setObjectName({"user": "UserBubble", "assistant": "AiBubble"}.get(role, "ErrorBubble"))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 10)
        who = QLabel({"user": "You", "assistant": "AI Animator"}.get(role, "Notice"))
        who.setObjectName("Muted")
        lay.addWidget(who)
        if images:
            chips = QLabel("📎 " + ", ".join(Path(p).name for p in images))
            chips.setObjectName("Badge")
            lay.addWidget(chips)
        self.body = QLabel()
        self.body.setWordWrap(True)
        self.body.setTextFormat(Qt.MarkdownText)
        self.body.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        self.body.setOpenExternalLinks(True)
        lay.addWidget(self.body)
        self._text = ""
        self.set_text(text)

    def set_text(self, text: str) -> None:
        self._text = text
        self.body.setText(text or "…")

    def append(self, text: str) -> None:
        self.set_text(self._text + text)


class ChatPage(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self.worker: ChatWorker | None = None
        self.pending_images: list[Path] = []
        self.live_bubble: Bubble | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 12)
        head = QHBoxLayout()
        title = QLabel("Studio Chat")
        title.setObjectName("H1")
        head.addWidget(title)
        head.addStretch()
        self.project_label = QLabel()
        self.project_label.setObjectName("Badge")
        head.addWidget(self.project_label)
        root.addLayout(head)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.feed = QWidget()
        self.feed_lay = QVBoxLayout(self.feed)
        self.feed_lay.setSpacing(10)
        self.feed_lay.addStretch()
        self.scroll.setWidget(self.feed)
        root.addWidget(self.scroll, 1)

        self.attach_label = QLabel()
        self.attach_label.setObjectName("Muted")
        self.attach_label.hide()
        root.addWidget(self.attach_label)

        box = QFrame()
        box.setObjectName("Card")
        bl = QHBoxLayout(box)
        self.input = QPlainTextEdit()
        self.input.setPlaceholderText("Describe what to draw or animate…  (Ctrl+Enter to send)")
        self.input.setFixedHeight(84)
        bl.addWidget(self.input, 1)
        col = QVBoxLayout()
        self.attach_btn = QPushButton("📎 Attach")
        self.attach_btn.setToolTip("Attach reference images (they're copied into the project)")
        self.attach_btn.clicked.connect(self.attach_images)
        self.send_btn = QPushButton("Send")
        self.send_btn.setObjectName("Primary")
        self.send_btn.clicked.connect(self.send)
        col.addWidget(self.attach_btn)
        col.addWidget(self.send_btn)
        bl.addLayout(col)
        root.addWidget(box)
        QShortcut(QKeySequence("Ctrl+Return"), self.input, activated=self.send)

        state.project_changed.connect(self.load_project)
        state.stop_triggered.connect(self.cancel)
        self.load_project(state.project)

    # ---- feed --------------------------------------------------------------
    def _clear_feed(self) -> None:
        while self.feed_lay.count() > 1:
            item = self.feed_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _add_bubble(self, bubble: Bubble) -> Bubble:
        self.feed_lay.insertWidget(self.feed_lay.count() - 1, bubble)
        QTimer.singleShot(30, self._scroll_bottom)
        return bubble

    def _scroll_bottom(self) -> None:
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def load_project(self, project) -> None:
        self._clear_feed()
        self.project_label.setText(f"Project: {project.name}" if project else "No project open")
        self._add_bubble(Bubble("assistant", WELCOME))
        if project:
            for rec in project.load_chat():
                imgs = [b["path"] for b in rec.get("content", []) if b.get("type") == "local_image"]
                self._add_bubble(Bubble(rec["role"], rec.get("display", ""), imgs))

    # ---- input -------------------------------------------------------------
    def attach_images(self) -> None:
        if not self.state.project:
            QMessageBox.information(self, "No project", "Open or create a project first - "
                                    "attached references are stored inside the project.")
            return
        exts = " ".join(f"*{e}" for e in sorted(IMAGE_EXTS))
        files, _ = QFileDialog.getOpenFileNames(self, "Attach reference images", "", f"Images ({exts})")
        self.pending_images += [Path(f) for f in files]
        self._update_attach_label()

    def _update_attach_label(self) -> None:
        if self.pending_images:
            self.attach_label.setText("Attached: " + ", ".join(p.name for p in self.pending_images)
                                      + "  (tag their roles later in Asset Library)")
            self.attach_label.show()
        else:
            self.attach_label.hide()

    def send(self) -> None:
        text = self.input.toPlainText().strip()
        if self.worker is not None or (not text and not self.pending_images):
            return
        project = self.state.project
        if project is None:
            project = self.state.projects.create_project("Untitled Project")
            self.state.set_project(project)
        if self.state.stop.triggered:
            self.state.resume_after_stop()

        content: list[dict] = []
        shown: list[str] = []
        for img in self.pending_images:
            try:
                ref = project.import_reference(img, ["general"], notes="attached in chat")
                content.append({"type": "local_image", "path": ref.file})
                shown.append(ref.file)
            except Exception as exc:
                log.error("Could not attach %s: %s", img, exc)
        self.pending_images = []
        self._update_attach_label()
        if text:
            content.append({"type": "text", "text": text})
        if not content:
            return

        record = {"role": "user", "content": content, "display": text,
                  "ts": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        history = project.load_chat()
        project.append_chat(record)
        self._add_bubble(Bubble("user", text, shown))
        self.input.clear()

        if not self.state.claude.has_key():
            log.info("No API key configured - SDK will try other credential sources")

        messages = self.state.claude.build_messages(history + [record], project.root)
        system = self.state.claude.build_system(project.memory_summary())
        self.live_bubble = self._add_bubble(Bubble("assistant", ""))
        self.send_btn.setEnabled(False)
        wf = suggest_workflow(text) if text else None
        self.state.task_changed.emit(
            f"Claude is thinking… (likely workflow: {wf.name})" if wf else "Claude is looking…", -1)
        self.worker = ChatWorker(self.state.claude, messages, system, self)
        self.worker.chunk.connect(self._on_chunk)
        self.worker.done.connect(self._on_done)
        self.worker.start()

    def _on_chunk(self, text: str) -> None:
        if self.live_bubble:
            self.live_bubble.append(text)
            self._scroll_bottom()

    def _on_done(self, result) -> None:
        project = self.state.project
        worker, self.worker = self.worker, None
        if worker:
            worker.wait(2000)
            worker.deleteLater()
        self.send_btn.setEnabled(True)
        if result.error:
            if self.live_bubble:
                self.live_bubble.deleteLater()
            self._add_bubble(Bubble("error", "⚠️ " + result.error))
            self.state.task_changed.emit("Idle", 0)
            log.error("Chat failed: %s", result.error)
            self.live_bubble = None
            return
        if self.live_bubble:
            self.live_bubble.set_text(result.content[0]["text"] if result.cancelled else result.text)
        if project and result.content:
            project.append_chat({"role": "assistant", "content": result.content,
                                 "display": self.live_bubble._text if self.live_bubble else result.text,
                                 "model": result.model,
                                 "ts": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        self.live_bubble = None
        if result.cancelled:
            self.state.task_changed.emit("Reply stopped", 0)
        else:
            log.info("Reply from %s (%d in / %d out tokens)", result.model,
                     result.input_tokens, result.output_tokens)
            self.state.task_changed.emit("Idle", 100)

    def cancel(self) -> None:
        if self.worker:
            self.worker.cancel()
