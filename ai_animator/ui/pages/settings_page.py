"""Settings: API key setup (secure), model, folders, providers, integrations."""
from __future__ import annotations

import logging

from PySide6.QtWidgets import (QComboBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QPushButton, QScrollArea, QVBoxLayout,
                               QWidget)

from ai_animator.ai.providers.base import available_providers
from ai_animator.config.settings import AVAILABLE_MODELS, EFFORT_LEVELS, mask_key
from ai_animator.integrations.registry import INTEGRATIONS, detect_installed
from ai_animator.projects.manager import ProjectManager
from ai_animator.ui.workers import CallWorker

log = logging.getLogger(__name__)


class SettingsPage(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self._worker = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        body = QWidget()
        scroll.setWidget(body)
        root = QVBoxLayout(body)
        root.setContentsMargins(18, 14, 18, 18)
        t = QLabel("Settings")
        t.setObjectName("H1")
        root.addWidget(t)

        # --- API key ---------------------------------------------------------
        card = self._card(root, "Anthropic API key",
                          "Get a key at console.anthropic.com. It is stored in Windows Credential "
                          "Manager - never in project files or in the app itself.")
        form = QFormLayout()
        self.key_status = QLabel()
        form.addRow("Status", self.key_status)
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.Password)
        self.key_edit.setPlaceholderText("sk-ant-…")
        form.addRow("New key", self.key_edit)
        card.addLayout(form)
        row = QHBoxLayout()
        for label, fn, obj in [("Save key", self.save_key, "Primary"), ("Test connection", self.test, ""),
                               ("Remove key", self.clear_key, "Reject")]:
            b = QPushButton(label)
            if obj:
                b.setObjectName(obj)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch()
        card.addLayout(row)
        self.test_result = QLabel()
        self.test_result.setWordWrap(True)
        card.addWidget(self.test_result)

        # --- AI model --------------------------------------------------------
        card = self._card(root, "AI model", "Opus gives the best creative reasoning. Higher effort = "
                          "more careful thinking but slower and more expensive.")
        form = QFormLayout()
        self.model = QComboBox()
        for mid, label in AVAILABLE_MODELS.items():
            self.model.addItem(label, mid)
        self.model.setCurrentIndex(self.model.findData(state.settings.model))
        self.model.currentIndexChanged.connect(self.save_prefs)
        self.effort = QComboBox()
        self.effort.addItems(EFFORT_LEVELS)
        self.effort.setCurrentText(state.settings.effort)
        self.effort.currentIndexChanged.connect(self.save_prefs)
        form.addRow("Model", self.model)
        form.addRow("Effort", self.effort)
        card.addLayout(form)

        # --- Image provider --------------------------------------------------
        card = self._card(root, "Image generation provider",
                          "Claude plans and critiques; a separate image model paints the pixels. "
                          "Providers are added in Phase 3.")
        self.provider = QComboBox()
        for pid, cls in available_providers().items():
            self.provider.addItem(cls.name, pid)
        card.addWidget(self.provider)

        # --- Folders ---------------------------------------------------------
        card = self._card(root, "Projects folder", "")
        row = QHBoxLayout()
        self.folder = QLineEdit(state.settings.projects_dir)
        self.folder.setReadOnly(True)
        b = QPushButton("Change…")
        b.clicked.connect(self.change_folder)
        row.addWidget(self.folder, 1)
        row.addWidget(b)
        card.addLayout(row)

        # --- Integrations ----------------------------------------------------
        card = self._card(root, "Creative applications",
                          "Detected on this computer. Control adapters are built in Phase 6.")
        self.apps_label = QLabel()
        self.apps_label.setWordWrap(True)
        card.addWidget(self.apps_label)
        b = QPushButton("Re-scan")
        b.clicked.connect(self.scan_apps)
        card.addWidget(b)

        # --- Safety ----------------------------------------------------------
        card = self._card(root, "Safety", "")
        lbl = QLabel("✔ Every action that changes your computer needs your approval (always on).\n"
                     "✔ Deleting, overwriting or installing needs a second confirmation.\n"
                     "✔ The red STOP button cancels everything immediately.")
        card.addWidget(lbl)
        root.addStretch()

        self.refresh_key_status()
        self.scan_apps()

    def _card(self, root, title, subtitle):
        frame = QFrame()
        frame.setObjectName("Card")
        lay = QVBoxLayout(frame)
        h = QLabel(title)
        h.setObjectName("H2")
        lay.addWidget(h)
        if subtitle:
            s = QLabel(subtitle)
            s.setObjectName("Muted")
            s.setWordWrap(True)
            lay.addWidget(s)
        root.addWidget(frame)
        return lay

    def refresh_key_status(self) -> None:
        key = self.state.secrets.get_api_key()
        src = self.state.secrets.key_source()
        self.key_status.setText(f"✔ {mask_key(key)}  (from {src})" if key else "✖ No key configured")

    def save_key(self) -> None:
        key = self.key_edit.text().strip()
        if not key:
            return
        try:
            self.state.secrets.set_api_key(key)
        except Exception as exc:
            QMessageBox.warning(self, "Could not save key", str(exc))
            return
        self.key_edit.clear()
        self.refresh_key_status()
        log.info("API key saved to secure storage")

    def clear_key(self) -> None:
        if QMessageBox.question(self, "Remove key", "Remove the stored API key?") == QMessageBox.Yes:
            self.state.secrets.clear_api_key()
            self.refresh_key_status()

    def test(self) -> None:
        if self._worker:
            return
        self.test_result.setText("Testing…")
        self._worker = CallWorker(self.state.claude.test_connection, self)
        self._worker.ok.connect(lambda model: self._test_done(f"✔ Connected. Served by {model}."))
        self._worker.failed.connect(lambda msg: self._test_done(f"✖ {msg}"))
        self._worker.failed.connect(lambda msg: log.error("Connection test failed: %s", msg))
        self._worker.start()

    def _test_done(self, msg: str) -> None:
        self.test_result.setText(msg)
        log.info("Connection test: %s", msg)
        self._worker.wait()
        self._worker = None

    def save_prefs(self) -> None:
        s = self.state.settings
        s.model = self.model.currentData()
        s.effort = self.effort.currentText()
        s.save()
        self.state.settings_changed.emit()

    def change_folder(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Projects folder", self.state.settings.projects_dir)
        if d:
            self.state.settings.projects_dir = d
            self.state.settings.save()
            self.state.projects = ProjectManager(d)
            self.folder.setText(d)
            self.state.set_project(None)

    def scan_apps(self) -> None:
        found = detect_installed()
        lines = []
        for app_id, path in found.items():
            app = INTEGRATIONS[app_id]
            mark = "✔" if path else "–"
            lines.append(f"{mark} <b>{app.name}</b> — {app.good_for}"
                         + (f"<br><span style='color:#7d7d8c'>{path}</span>" if path else ""))
        self.apps_label.setText("<br>".join(lines))
