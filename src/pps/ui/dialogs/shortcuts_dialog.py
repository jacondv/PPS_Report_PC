"""Keyboard shortcuts reference — built from the app's own QAction list, so
it can never drift out of sync with what the menus/toolbars actually do."""

from typing import Iterable

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class ShortcutsDialog(QDialog):
    def __init__(self, actions: Iterable[QAction], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.resize(420, 500)

        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        form = QFormLayout(content)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        seen = set()
        for action in actions:
            shortcut = action.shortcut().toString()
            label = action.text().replace("&", "")
            if not shortcut or (label, shortcut) in seen:
                continue
            seen.add((label, shortcut))
            form.addRow(label, QLabel(shortcut))

        scroll.setWidget(content)
        layout.addWidget(scroll)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Close).clicked.connect(self.accept)
        layout.addWidget(buttons)
