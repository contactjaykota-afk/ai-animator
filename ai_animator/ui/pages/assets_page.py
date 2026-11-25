"""Asset Library: reference images with roles (style / character / anatomy / ...)."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFrame, QGridLayout,
                               QHBoxLayout, QLabel, QListView, QListWidget, QListWidgetItem,
                               QPlainTextEdit, QPushButton, QVBoxLayout, QWidget)

from ai_animator.projects.manager import IMAGE_EXTS, REFERENCE_ROLES


class AssetsPage(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        root = QHBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 12)

        left = QVBoxLayout()
        head = QHBoxLayout()
        t = QLabel("Asset Library — References")
        t.setObjectName("H1")
        head.addWidget(t)
        head.addStretch()
        imp = QPushButton("Import references…")
        imp.setObjectName("Primary")
        imp.clicked.connect(self.import_refs)
        head.addWidget(imp)
        left.addLayout(head)
        hint = QLabel("Tell the AI what each reference is FOR. A style reference won't change your "
                      "character's design, and a character reference won't change the art style.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        left.addWidget(hint)
        self.grid = QListWidget()
        self.grid.setViewMode(QListView.IconMode)
        self.grid.setIconSize(QSize(150, 150))
        self.grid.setResizeMode(QListView.Adjust)
        self.grid.setSpacing(10)
        self.grid.setMovement(QListView.Static)
        self.grid.currentItemChanged.connect(lambda *_: self.show_selected())
        left.addWidget(self.grid, 1)
        root.addLayout(left, 3)

        card = QFrame()
        card.setObjectName("Card")
        card.setFixedWidth(300)
        side = QVBoxLayout(card)
        self.preview = QLabel("Select a reference")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumHeight(200)
        side.addWidget(self.preview)
        lbl = QLabel("This reference controls:")
        lbl.setObjectName("H2")
        side.addWidget(lbl)
        roles = QGridLayout()
        self.role_boxes: dict[str, QCheckBox] = {}
        for i, (key, desc) in enumerate(REFERENCE_ROLES.items()):
            cb = QCheckBox(key.capitalize())
            cb.setToolTip(desc)
            self.role_boxes[key] = cb
            roles.addWidget(cb, i // 2, i % 2)
        side.addLayout(roles)
        side.addWidget(QLabel("Character"))
        self.char_combo = QComboBox()
        side.addWidget(self.char_combo)
        side.addWidget(QLabel("Notes (what to use / ignore)"))
        self.notes = QPlainTextEdit()
        self.notes.setPlaceholderText("e.g. 'use only the shading on the hair; ignore the outfit'")
        self.notes.setFixedHeight(80)
        side.addWidget(self.notes)
        save = QPushButton("Save reference settings")
        save.clicked.connect(self.save_selected)
        side.addWidget(save)
        side.addStretch()
        root.addWidget(card)

        state.project_changed.connect(lambda _: self.refresh())
        self.refresh()

    def refresh(self) -> None:
        self.grid.clear()
        self.char_combo.clear()
        self.char_combo.addItem("(none)", "")
        proj = self.state.project
        if not proj:
            return
        for c in proj.characters():
            self.char_combo.addItem(c.name, c.id)
        for ref in proj.references():
            pix = QPixmap(str(proj.reference_path(ref)))
            item = QListWidgetItem(QIcon(pix.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)),
                                   f"{ref.file.split('/')[-1]}\n[{', '.join(ref.roles)}]")
            item.setData(Qt.UserRole, ref.id)
            self.grid.addItem(item)

    def _selected_ref(self):
        item = self.grid.currentItem()
        if not item or not self.state.project:
            return None
        rid = item.data(Qt.UserRole)
        return next((r for r in self.state.project.references() if r.id == rid), None)

    def show_selected(self) -> None:
        ref = self._selected_ref()
        if not ref:
            return
        pix = QPixmap(str(self.state.project.reference_path(ref)))
        self.preview.setPixmap(pix.scaled(270, 240, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        for key, cb in self.role_boxes.items():
            cb.setChecked(key in ref.roles)
        idx = self.char_combo.findData(ref.character_id)
        self.char_combo.setCurrentIndex(max(idx, 0))
        self.notes.setPlainText(ref.notes)

    def save_selected(self) -> None:
        ref = self._selected_ref()
        if not ref:
            return
        roles = [k for k, cb in self.role_boxes.items() if cb.isChecked()]
        self.state.project.update_reference(ref.id, roles=roles, notes=self.notes.toPlainText(),
                                            character_id=self.char_combo.currentData() or "")
        row = self.grid.currentRow()
        self.refresh()
        self.grid.setCurrentRow(row)

    def import_refs(self) -> None:
        proj = self.state.project
        if not proj:
            proj = self.state.projects.create_project("Untitled Project")
            self.state.set_project(proj)
        exts = " ".join(f"*{e}" for e in sorted(IMAGE_EXTS))
        files, _ = QFileDialog.getOpenFileNames(self, "Import references", "", f"Images ({exts})")
        for f in files:
            proj.import_reference(f, ["general"])
        self.refresh()
