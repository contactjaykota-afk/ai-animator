"""Right panel: screen preview, current app, pending actions with APPROVE / REJECT."""
from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMessageBox,
                               QPushButton, QScrollArea, QVBoxLayout, QWidget)

from ai_animator.core.screen import active_window_title, capture_screen
from ai_animator.safety.approval import ActionRequest, ConfirmationRequired, Risk, Status

log = logging.getLogger(__name__)

RISK_COLORS = {Risk.READ_ONLY: "#4aa3ff", Risk.CHANGE: "#e0a43a", Risk.DESTRUCTIVE: "#ff4d5a"}


class ActionCard(QFrame):
    def __init__(self, req: ActionRequest, on_approve, on_reject):
        super().__init__()
        self.setObjectName("Card")
        self.req = req
        lay = QVBoxLayout(self)
        color = RISK_COLORS[req.risk]
        head = QLabel(f"<span style='color:{color}; font-weight:700'>{req.risk.value.upper()}</span>"
                      f"  <b>{req.title}</b>")
        head.setWordWrap(True)
        lay.addWidget(head)
        for label, value in [("App", req.application), ("Why", req.reason),
                             ("Expected", req.expected_result)]:
            lbl = QLabel(f"<span style='color:#8b8b99'>{label}:</span> {value}")
            lbl.setWordWrap(True)
            lay.addWidget(lbl)
        self.status = QLabel()
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        row = QHBoxLayout()
        self.approve = QPushButton("APPROVE")
        self.approve.setObjectName("Approve")
        self.approve.clicked.connect(lambda: on_approve(req))
        self.reject = QPushButton("REJECT")
        self.reject.setObjectName("Reject")
        self.reject.clicked.connect(lambda: on_reject(req))
        row.addWidget(self.approve)
        row.addWidget(self.reject)
        lay.addLayout(row)
        self.update_status()

    def update_status(self) -> None:
        st = self.req.status
        pending = st == Status.PENDING
        self.approve.setVisible(pending)
        self.reject.setVisible(pending)
        msg = {Status.SUCCEEDED: "✔ Done and verified", Status.UNVERIFIED: "⚠ Ran, but could not verify",
               Status.FAILED: "✖ Failed", Status.REJECTED: "Rejected", Status.CANCELLED: "Cancelled",
               Status.RUNNING: "Running…"}.get(st, "")
        if self.req.error and st != Status.SUCCEEDED:
            msg += f" — {self.req.error}"
        self.status.setText(msg)
        self.status.setVisible(bool(msg))


class RightPanel(QFrame):
    def __init__(self, state):
        super().__init__()
        self.setObjectName("RightPanel")
        self.state = state
        self.cards: dict[str, ActionCard] = {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)

        h = QLabel("Screen")
        h.setObjectName("H2")
        lay.addWidget(h)
        self.preview = QLabel("No capture yet")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumHeight(150)
        self.preview.setStyleSheet("background:#0c0c0f; border:1px solid #23232b; border-radius:6px;")
        lay.addWidget(self.preview)
        self.app_label = QLabel("Current app: —")
        self.app_label.setObjectName("Muted")
        self.app_label.setWordWrap(True)
        lay.addWidget(self.app_label)
        cap = QPushButton("Capture screenshot")
        cap.setToolTip("Read-only. Takes a picture of your screen; nothing is clicked or changed.")
        cap.clicked.connect(self.capture)
        lay.addWidget(cap)

        h = QLabel("Pending actions")
        h.setObjectName("H2")
        lay.addWidget(h)
        self.empty = QLabel("Nothing waiting for approval.\nThe AI can't change anything without you.")
        self.empty.setObjectName("Muted")
        self.empty.setWordWrap(True)
        lay.addWidget(self.empty)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        holder = QWidget()
        self.cards_lay = QVBoxLayout(holder)
        self.cards_lay.addStretch()
        scroll.setWidget(holder)
        lay.addWidget(scroll, 1)

        state.action_updated.connect(self.on_action)
        state.screen_frame.connect(self.show_frame)

    def show_frame(self, pix) -> None:
        self.preview.setPixmap(pix.scaled(self.preview.width() - 4, 200, Qt.KeepAspectRatio,
                                          Qt.SmoothTransformation))
        title = active_window_title()
        if title:
            self.app_label.setText(f"Current app: {title}")

    def capture(self) -> None:
        try:
            img = capture_screen()
        except Exception as exc:
            log.error("Screenshot failed: %s", exc)
            self.preview.setText(f"Screenshot failed:\n{exc}")
            return
        qimg = QImage(img.tobytes(), img.width, img.height, img.width * 3, QImage.Format_RGB888).copy()
        self.preview.setPixmap(QPixmap.fromImage(qimg).scaled(
            self.preview.width() - 4, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        title = active_window_title()
        self.app_label.setText(f"Current app: {title or 'unknown (window detection: Phase 2)'}")
        log.info("Screenshot captured (%dx%d)", img.width, img.height)

    def on_action(self, req: ActionRequest) -> None:
        card = self.cards.get(req.id)
        if card is None:
            card = ActionCard(req, self.approve, self.reject)
            self.cards[req.id] = card
            self.cards_lay.insertWidget(0, card)
        card.update_status()
        self.empty.setVisible(not any(c.req.status == Status.PENDING for c in self.cards.values()))

    def approve(self, req: ActionRequest) -> None:
        try:
            self.state.approvals.approve(req.id)
        except ConfirmationRequired:
            word = "DELETE"
            text, ok = QInputDialog.getText(
                self, "Confirm destructive action",
                f"{req.title}\n\n{req.expected_result}\n\nThis is destructive. Type {word} to confirm:",
                QLineEdit.Normal)
            if ok and text.strip().upper() == word:
                self.state.approvals.approve(req.id, confirmed_destructive=True)
            else:
                QMessageBox.information(self, "Not confirmed", "Nothing was changed. The action is "
                                        "still pending.")
        except Exception as exc:
            QMessageBox.warning(self, "Could not run", str(exc))

    def reject(self, req: ActionRequest) -> None:
        self.state.approvals.reject(req.id)
