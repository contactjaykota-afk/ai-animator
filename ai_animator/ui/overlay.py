"""On-screen indicators while the AI controls the desktop.

  * ControlBorder - red frame around the screen + "AI IN CONTROL" tag (click-through)
  * AICursor      - the AI's own visible cursor, animated to each target (click-through)
  * ControlBar    - small floating bar: status, Pause/Resume, STOP, and Approve/Reject
                    for the step waiting on you (so approvals work while the main
                    window is minimized)

None of them take keyboard focus, and on Windows all are excluded from screen
capture, so Claude never sees them in its screenshots.
"""
from __future__ import annotations

import sys
import threading

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ai_animator.ui.theme import ACCENT

WDA_EXCLUDEFROMCAPTURE = 0x11


def exclude_from_capture(widget: QWidget) -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        return bool(ctypes.windll.user32.SetWindowDisplayAffinity(int(widget.winId()), WDA_EXCLUDEFROMCAPTURE))
    except Exception:
        return False


def physical_to_logical(x: int, y: int) -> QPoint:
    """Screen pixels (what SendInput uses) -> Qt logical coordinates."""
    for screen in QGuiApplication.screens():
        g, r = screen.geometry(), screen.devicePixelRatio()
        px0, py0 = int(g.x() * r), int(g.y() * r)  # works for the usual layouts
        if px0 <= x < px0 + g.width() * r and py0 <= y < py0 + g.height() * r:
            return QPoint(int(g.x() + (x - px0) / r), int(g.y() + (y - py0) / r))
    r = QGuiApplication.primaryScreen().devicePixelRatio()
    return QPoint(int(x / r), int(y / r))


OVERLAY_FLAGS = (Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                 | Qt.WindowDoesNotAcceptFocus | Qt.WindowTransparentForInput)


class ControlBorder(QWidget):
    def __init__(self):
        super().__init__(None, OVERLAY_FLAGS)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setGeometry(QGuiApplication.primaryScreen().geometry())
        self.paused = False

    def paintEvent(self, _):
        p = QPainter(self)
        color = QColor("#e0a43a") if self.paused else QColor(ACCENT)
        p.setPen(QPen(color, 6))
        p.drawRect(self.rect().adjusted(3, 3, -3, -3))
        tag = "AI PAUSED" if self.paused else "AI IN CONTROL  •  Shift+Esc to stop"
        f = QFont()
        f.setBold(True)
        f.setPointSize(9)
        p.setFont(f)
        w = p.fontMetrics().horizontalAdvance(tag) + 24
        r = QRect((self.width() - w) // 2, 0, w, 24)
        p.fillRect(r, color)
        p.setPen(Qt.white)
        p.drawText(r, Qt.AlignCenter, tag)

    def showEvent(self, e):
        super().showEvent(e)
        exclude_from_capture(self)


class AICursor(QWidget):
    arrived = Signal()

    def __init__(self):
        super().__init__(None, OVERLAY_FLAGS)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.resize(64, 40)
        self.anim = QPropertyAnimation(self, b"pos", self)
        self.anim.setEasingCurve(QEasingCurve.InOutCubic)
        self.anim.finished.connect(self.arrived.emit)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.moveTo(2, 2)
        path.lineTo(2, 24)
        path.lineTo(8, 18)
        path.lineTo(13, 28)
        path.lineTo(17, 26)
        path.lineTo(12, 16)
        path.lineTo(20, 16)
        path.closeSubpath()
        p.setPen(QPen(Qt.white, 2))
        p.setBrush(QColor(ACCENT))
        p.drawPath(path)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(ACCENT))
        p.drawRoundedRect(22, 18, 26, 16, 5, 5)
        p.setPen(Qt.white)
        f = QFont()
        f.setBold(True)
        f.setPointSize(7)
        p.setFont(f)
        p.drawText(QRect(22, 18, 26, 16), Qt.AlignCenter, "AI")

    def showEvent(self, e):
        super().showEvent(e)
        exclude_from_capture(self)

    def glide_to(self, x: int, y: int, ms: int = 280) -> None:
        target = physical_to_logical(x, y) - QPoint(2, 2)
        if not self.isVisible():
            self.move(target)
            self.show()
            self.arrived.emit()
            return
        self.anim.stop()
        dist = (target - self.pos()).manhattanLength()
        self.anim.setDuration(max(80, min(ms, dist)))
        self.anim.setStartValue(self.pos())
        self.anim.setEndValue(target)
        self.anim.start()


class ControlBar(QWidget):
    """Floating controls. Takes clicks, but never steals keyboard focus."""
    pause_clicked = Signal()
    resume_clicked = Signal()
    stop_clicked = Signal()
    approve_clicked = Signal(str)
    reject_clicked = Signal(str)

    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setObjectName("ControlBar")
        self.setStyleSheet(f"""
            QWidget#ControlBar {{ background: #121216; border: 2px solid {ACCENT}; border-radius: 10px; }}
            QLabel {{ color: #e6e6ea; }}
            QPushButton {{ background: #262630; color: #e6e6ea; border: 1px solid #34343f;
                           border-radius: 6px; padding: 5px 10px; }}
            QPushButton#Stop {{ background: #b3121f; border: 2px solid #ff4d5a; color: white; font-weight: 800; }}
            QPushButton#Approve {{ background: #1f7a4a; color: white; font-weight: 600; }}
            QPushButton#Reject {{ background: #3a2026; color: #ffc9cf; }}""")
        self._pending_id = ""
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        top = QHBoxLayout()
        self.status = QLabel("Starting…")
        self.status.setWordWrap(True)
        self.status.setMinimumWidth(260)
        top.addWidget(self.status, 1)
        self.pause_btn = QPushButton("⏸ Pause")
        self.pause_btn.clicked.connect(self._toggle_pause)
        self.stop_btn = QPushButton("■ STOP")
        self.stop_btn.setObjectName("Stop")
        self.stop_btn.clicked.connect(self.stop_clicked.emit)
        top.addWidget(self.pause_btn)
        top.addWidget(self.stop_btn)
        lay.addLayout(top)
        self.ask = QLabel()
        self.ask.setWordWrap(True)
        self.ask.hide()
        lay.addWidget(self.ask)
        row = QHBoxLayout()
        self.approve_btn = QPushButton("APPROVE")
        self.approve_btn.setObjectName("Approve")
        self.approve_btn.clicked.connect(lambda: self.approve_clicked.emit(self._pending_id))
        self.reject_btn = QPushButton("REJECT")
        self.reject_btn.setObjectName("Reject")
        self.reject_btn.clicked.connect(lambda: self.reject_clicked.emit(self._pending_id))
        row.addWidget(self.approve_btn)
        row.addWidget(self.reject_btn)
        self.approve_row = QWidget()
        self.approve_row.setLayout(row)
        self.approve_row.hide()
        lay.addWidget(self.approve_row)
        self.paused = False
        self.setFixedWidth(460)
        self._place()

    def _place(self) -> None:
        g = QGuiApplication.primaryScreen().availableGeometry()
        self.adjustSize()
        self.move(g.right() - self.width() - 16, g.bottom() - self.height() - 16)

    def _toggle_pause(self) -> None:
        (self.resume_clicked if self.paused else self.pause_clicked).emit()

    def set_paused(self, paused: bool) -> None:
        self.paused = paused
        self.pause_btn.setText("▶ Resume" if paused else "⏸ Pause")

    def set_status(self, text: str) -> None:
        self.status.setText(text)

    def show_request(self, req_id: str, text: str, destructive: bool) -> None:
        self._pending_id = req_id
        color = "#ff4d5a" if destructive else "#e0a43a"
        self.ask.setText(f"<span style='color:{color};font-weight:700'>"
                         f"{'DESTRUCTIVE - ' if destructive else ''}Approve this step?</span><br>{text}")
        self.ask.show()
        self.approve_row.show()
        self._place()

    def clear_request(self, req_id: str | None = None) -> None:
        if req_id is None or req_id == self._pending_id:
            self._pending_id = ""
            self.ask.hide()
            self.approve_row.hide()
            self._place()

    def showEvent(self, e):
        super().showEvent(e)
        exclude_from_capture(self)
        self._place()


class CursorBridge:
    """Lets the agent thread move the AI cursor and wait (briefly) for the glide."""

    def __init__(self, cursor: AICursor, request_signal):
        self.cursor = cursor
        self.request = request_signal  # Signal(int, int) connected to cursor.glide_to on UI thread
        self._arrived = threading.Event()
        cursor.arrived.connect(self._arrived.set)

    def before_pointer(self, x: int, y: int) -> None:
        self._arrived.clear()
        self.request.emit(x, y)
        self._arrived.wait(0.6)
