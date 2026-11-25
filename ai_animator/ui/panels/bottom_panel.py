"""Bottom panel: current task, progress, activity log and the emergency STOP."""
from __future__ import annotations

import logging
from datetime import datetime

from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QProgressBar,
                               QPushButton, QVBoxLayout)


class QtLogHandler(logging.Handler):
    def __init__(self, state):
        super().__init__(logging.INFO)
        self.state = state

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.state.log_message.emit(record.levelname, record.getMessage())
        except Exception:
            pass


class BottomPanel(QFrame):
    def __init__(self, state):
        super().__init__()
        self.setObjectName("BottomPanel")
        self.state = state
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)

        col = QVBoxLayout()
        self.task = QLabel("Idle")
        self.task.setObjectName("H2")
        col.addWidget(self.task)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        col.addWidget(self.progress)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)
        col.addWidget(self.log, 1)
        lay.addLayout(col, 1)

        self.stop_btn = QPushButton("■ STOP")
        self.stop_btn.setObjectName("Stop")
        self.stop_btn.setToolTip("Emergency stop: halts the AI and cancels every pending action (Esc+Shift)")
        self.stop_btn.setMinimumSize(110, 70)
        self.stop_btn.clicked.connect(state.emergency_stop)
        lay.addWidget(self.stop_btn)

        state.task_changed.connect(self.set_task)
        state.log_message.connect(self.add_log)
        self.handler = QtLogHandler(state)
        logging.getLogger().addHandler(self.handler)

    def set_task(self, text: str, progress: int) -> None:
        self.task.setText(text)
        if progress < 0:
            self.progress.setRange(0, 0)  # busy animation
        else:
            self.progress.setRange(0, 100)
            self.progress.setValue(progress)

    def add_log(self, level: str, text: str) -> None:
        color = {"WARNING": "#e0a43a", "ERROR": "#ff6b76", "CRITICAL": "#ff6b76"}.get(level)
        line = f"{datetime.now():%H:%M:%S}  {text}"
        if color:
            self.log.appendHtml(f"<span style='color:{color}'>{line.replace('<', '&lt;')}</span>")
        else:
            self.log.appendPlainText(line)

    def detach(self) -> None:
        logging.getLogger().removeHandler(self.handler)
