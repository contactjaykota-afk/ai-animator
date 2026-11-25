"""Projects: create / open / back up / delete, characters and project memory."""
from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout, QFrame,
                               QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton,
                               QVBoxLayout, QWidget)

from ai_animator.projects.manager import PROJECT_TYPES
from ai_animator.safety.approval import ActionRequest, Risk

log = logging.getLogger(__name__)


class NewProjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New project")
        form = QFormLayout(self)
        self.name = QLineEdit()
        self.type = QComboBox()
        for key, label in PROJECT_TYPES.items():
            self.type.addItem(label, key)
        self.desc = QPlainTextEdit()
        self.desc.setFixedHeight(80)
        form.addRow("Name", self.name)
        form.addRow("Type", self.type)
        form.addRow("Description", self.desc)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)


class CharacterDialog(QDialog):
    def __init__(self, parent=None, name="", desc="", notes=""):
        super().__init__(parent)
        self.setWindowTitle("Character")
        form = QFormLayout(self)
        self.name = QLineEdit(name)
        self.desc = QPlainTextEdit(desc)
        self.desc.setFixedHeight(70)
        self.notes = QPlainTextEdit(notes)
        self.notes.setFixedHeight(90)
        self.notes.setPlaceholderText("Details that must never change, e.g. 'three scars on left "
                                      "cheek; torn red scarf; eyes always glow yellow'")
        form.addRow("Name", self.name)
        form.addRow("Description", self.desc)
        form.addRow("Locked design details", self.notes)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)


class ProjectsPage(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        root = QHBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 12)

        left = QVBoxLayout()
        t = QLabel("Projects")
        t.setObjectName("H1")
        left.addWidget(t)
        self.folder = QLabel()
        self.folder.setObjectName("Muted")
        self.folder.setWordWrap(True)
        left.addWidget(self.folder)
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda _: self.open_selected())
        left.addWidget(self.list, 1)
        row = QHBoxLayout()
        for label, fn, obj in [("New", self.new_project, "Primary"), ("Open", self.open_selected, ""),
                               ("Back up", self.backup, ""), ("Delete…", self.delete_selected, "Reject")]:
            b = QPushButton(label)
            if obj:
                b.setObjectName(obj)
            b.clicked.connect(fn)
            row.addWidget(b)
        left.addLayout(row)
        root.addLayout(left, 2)

        card = QFrame()
        card.setObjectName("Card")
        right = QVBoxLayout(card)
        self.p_title = QLabel("No project open")
        self.p_title.setObjectName("H2")
        right.addWidget(self.p_title)
        self.p_info = QLabel()
        self.p_info.setObjectName("Muted")
        self.p_info.setWordWrap(True)
        right.addWidget(self.p_info)

        right.addWidget(self._h2("Characters"))
        self.chars = QListWidget()
        self.chars.itemDoubleClicked.connect(lambda _: self.edit_character())
        right.addWidget(self.chars, 1)
        crow = QHBoxLayout()
        b1 = QPushButton("Add character")
        b1.clicked.connect(self.add_character)
        b2 = QPushButton("Edit")
        b2.clicked.connect(self.edit_character)
        crow.addWidget(b1)
        crow.addWidget(b2)
        crow.addStretch()
        right.addLayout(crow)

        right.addWidget(self._h2("Project memory"))
        self.memory = QListWidget()
        right.addWidget(self.memory, 1)
        mb = QPushButton("Remember something…")
        mb.clicked.connect(self.add_memory)
        right.addWidget(mb, 0, Qt.AlignLeft)
        root.addWidget(card, 3)

        state.project_changed.connect(lambda _: self.refresh())
        self.refresh()

    @staticmethod
    def _h2(text):
        lbl = QLabel(text)
        lbl.setObjectName("H2")
        return lbl

    def refresh(self) -> None:
        pm = self.state.projects
        self.folder.setText(f"Folder: {pm.projects_dir}")
        self.list.clear()
        for p in pm.list_projects():
            item = QListWidgetItem(f"{p.name}\n{PROJECT_TYPES.get(p.project_type, '')}")
            item.setData(Qt.UserRole, str(p.root))
            self.list.addItem(item)
            if self.state.project and p.root == self.state.project.root:
                item.setSelected(True)
        proj = self.state.project
        self.chars.clear()
        self.memory.clear()
        if not proj:
            self.p_title.setText("No project open")
            self.p_info.setText("Create or open a project. Each project remembers its characters, "
                                "references, decisions and chat.")
            return
        self.p_title.setText(proj.name)
        self.p_info.setText(f"{PROJECT_TYPES.get(proj.project_type, '')}  •  {proj.root}\n"
                            f"{proj.data.get('description', '')}")
        for c in proj.characters():
            item = QListWidgetItem(f"{c.name} — {c.description[:80]}")
            item.setData(Qt.UserRole, c.id)
            self.chars.addItem(item)
        for n in proj.data.get("memory", []):
            self.memory.addItem(n["text"])

    def _selected_project(self):
        item = self.list.currentItem()
        if not item:
            return None
        return self.state.projects.open_project(item.data(Qt.UserRole))

    def new_project(self) -> None:
        dlg = NewProjectDialog(self)
        if dlg.exec() and dlg.name.text().strip():
            p = self.state.projects.create_project(dlg.name.text(), dlg.desc.toPlainText(),
                                                   dlg.type.currentData())
            self.state.set_project(p)

    def open_selected(self) -> None:
        p = self._selected_project()
        if p:
            self.state.set_project(p)

    def backup(self) -> None:
        p = self.state.project
        if not p:
            return
        path = p.backup("manual")
        log.info("Backup created: %s", path)
        QMessageBox.information(self, "Backup created", f"Saved to:\n{path}")

    def delete_selected(self) -> None:
        p = self._selected_project()
        if not p:
            return
        pm = self.state.projects

        def execute():
            if self.state.project and self.state.project.root == p.root:
                self.state.set_project(None)
            return pm.delete_project(p)

        self.state.request_action(ActionRequest(
            title=f"Delete project '{p.name}'",
            application="AI Animator (file system)",
            reason="You asked to delete this project.",
            expected_result=f"The folder {p.root} is removed. A full zip backup is kept in "
                            f"{pm.projects_dir / '_deleted_backups'}.",
            execute=execute,
            verify=lambda archive: (not p.root.exists()) and archive.exists(),
            risk=Risk.DESTRUCTIVE,
        ))
        self.state.navigate.emit("approvals")

    def add_character(self) -> None:
        if not self.state.project:
            return
        dlg = CharacterDialog(self)
        if dlg.exec() and dlg.name.text().strip():
            self.state.project.add_character(dlg.name.text(), dlg.desc.toPlainText(),
                                             dlg.notes.toPlainText())
            self.refresh()

    def edit_character(self) -> None:
        proj, item = self.state.project, self.chars.currentItem()
        if not proj or not item:
            return
        c = next(c for c in proj.characters() if c.id == item.data(Qt.UserRole))
        dlg = CharacterDialog(self, c.name, c.description, c.design_notes)
        if dlg.exec():
            proj.backup(f"before editing {c.name}")
            proj.update_character(c.id, name=dlg.name.text().strip() or c.name,
                                  description=dlg.desc.toPlainText(),
                                  design_notes=dlg.notes.toPlainText())
            self.refresh()

    def add_memory(self) -> None:
        if not self.state.project:
            return
        text, ok = QInputDialog.getMultiLineText(self, "Remember", "What should the AI remember "
                                                 "about this project?")
        if ok and text.strip():
            self.state.project.add_memory_note(text)
            self.refresh()
