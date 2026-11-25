"""Main window: sidebar | workspace | right panel, with the bottom panel underneath."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (QButtonGroup, QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton,
                               QSplitter, QStackedWidget, QVBoxLayout, QWidget)

from ai_animator import APP_NAME, __version__
from ai_animator.core.resources import resource_path
from ai_animator.ui.pages.assets_page import AssetsPage
from ai_animator.ui.pages.chat_page import ChatPage
from ai_animator.ui.pages.projects_page import ProjectsPage
from ai_animator.ui.pages.settings_page import SettingsPage
from ai_animator.ui.pages.studio_pages import StudioPage
from ai_animator.ui.panels.bottom_panel import BottomPanel
from ai_animator.ui.panels.right_panel import RightPanel

NAV = [("chat", "💬  Chat"), ("drawing", "✏️  Drawing Studio"), ("animation", "🎞️  Animation Studio"),
       ("fnf", "🎤  FNF Studio"), ("projects", "📁  Projects"), ("assets", "🖼️  Asset Library"),
       ("settings", "⚙️  Settings")]


class MainWindow(QMainWindow):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self.setWindowTitle(f"{APP_NAME} {__version__}")
        icon = resource_path("icon.png")
        if icon.exists():
            self.setWindowIcon(QIcon(str(icon)))
        self.resize(1440, 900)
        self.setMinimumSize(1100, 700)

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # sidebar
        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(210)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 0, 0, 10)
        logo = QLabel("AI ANIMATOR")
        logo.setObjectName("Logo")
        sub = QLabel("Digital art & animation studio")
        sub.setObjectName("LogoSub")
        sl.addWidget(logo)
        sl.addWidget(sub)
        self.nav_group = QButtonGroup(self)
        self.nav_buttons: dict[str, QPushButton] = {}
        for key, label in NAV:
            b = QPushButton(label)
            b.setObjectName("NavButton")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, k=key: self.show_page(k))
            self.nav_group.addButton(b)
            self.nav_buttons[key] = b
            sl.addWidget(b)
        sl.addStretch()
        ver = QLabel(f"v{__version__} • Phase 1")
        ver.setObjectName("LogoSub")
        sl.addWidget(ver)
        outer.addWidget(side)

        # workspace + right panel, above the bottom panel
        vsplit = QSplitter(Qt.Vertical)
        hsplit = QSplitter(Qt.Horizontal)
        self.stack = QStackedWidget()
        self.pages = {
            "chat": ChatPage(state), "drawing": StudioPage("drawing"),
            "animation": StudioPage("animation"), "fnf": StudioPage("fnf"),
            "projects": ProjectsPage(state), "assets": AssetsPage(state),
            "settings": SettingsPage(state),
        }
        for page in self.pages.values():
            self.stack.addWidget(page)
        hsplit.addWidget(self.stack)
        self.right = RightPanel(state)
        self.right.setMinimumWidth(280)
        hsplit.addWidget(self.right)
        hsplit.setStretchFactor(0, 1)
        hsplit.setSizes([1000, 320])
        vsplit.addWidget(hsplit)
        self.bottom = BottomPanel(state)
        vsplit.addWidget(self.bottom)
        vsplit.setStretchFactor(0, 1)
        vsplit.setSizes([700, 170])
        outer.addWidget(vsplit, 1)

        QShortcut(QKeySequence("Shift+Escape"), self, activated=state.emergency_stop)
        state.navigate.connect(self._navigate)
        self.show_page("chat" if state.secrets.get_api_key() else "settings")

    def _navigate(self, key: str) -> None:
        if key == "approvals":
            self.right.raise_()
            return
        self.show_page(key)

    def show_page(self, key: str) -> None:
        self.stack.setCurrentWidget(self.pages[key])
        self.nav_buttons[key].setChecked(True)

    def closeEvent(self, event) -> None:
        chat = self.pages["chat"]
        if chat.worker:
            chat.worker.cancel()
            chat.worker.wait(3000)
        self.bottom.detach()
        super().closeEvent(event)
