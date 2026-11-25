"""Background threads so the window never freezes while Claude works."""
from __future__ import annotations

import threading

from PySide6.QtCore import QThread, Signal

from ai_animator.ai.claude_service import ChatResult, ClaudeService, friendly_error


class ChatWorker(QThread):
    chunk = Signal(str)
    done = Signal(object)  # ChatResult

    def __init__(self, service: ClaudeService, messages, system, parent=None):
        super().__init__(parent)
        self.service, self.messages, self.system = service, messages, system
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        result = self.service.stream_reply(self.messages, self.system,
                                           on_text=self.chunk.emit,
                                           should_cancel=self._cancel.is_set)
        self.done.emit(result)


class CallWorker(QThread):
    """Run any blocking function off the UI thread."""
    ok = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self.fn = fn

    def run(self) -> None:
        try:
            self.ok.emit(self.fn())
        except Exception as exc:
            self.failed.emit(friendly_error(exc))


__all__ = ["ChatWorker", "CallWorker", "ChatResult"]
