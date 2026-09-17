"""
Real Qt dialogs used as the default implementations of tool "editor"
callbacks (e.g. NoteTool.note_editor). Kept under app/ rather than ui/ for
now since the ui/ package (docks, main window, theme) doesn't exist yet —
these dialogs don't depend on it.
"""

from typing import Optional

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)


class NoteEditorDialog(QDialog):
    def __init__(self, parent=None, text="", color="#ffd166", font_size=14):
        super().__init__(parent)
        self.setWindowTitle("Note")
        self.setModal(True)
        self.resize(380, 280)
        self._color = color

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Text:"))
        self.text_edit = QTextEdit(self)
        self.text_edit.setPlainText(text)
        self.text_edit.setMinimumHeight(120)
        layout.addWidget(self.text_edit)

        form = QFormLayout()
        self.color_button = QPushButton()
        self.color_button.setFixedSize(28, 22)
        self._update_color_button()
        self.color_button.clicked.connect(self._choose_color)
        form.addRow("Color:", self.color_button)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 48)
        self.font_size_spin.setValue(font_size)
        form.addRow("Font size:", self.font_size_spin)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _update_color_button(self) -> None:
        self.color_button.setStyleSheet(f"background-color: {self._color}; border: 1px solid #555;")

    def _choose_color(self) -> None:
        chosen = QColorDialog.getColor(QColor(self._color), self, "Note color")
        if chosen.isValid():
            self._color = chosen.name()
            self._update_color_button()

    def values(self) -> dict:
        return {
            "text": self.text_edit.toPlainText().strip(),
            "color": self._color,
            "font_size": self.font_size_spin.value(),
        }


def open_note_editor(existing=None, screen_pos=None, parent=None) -> Optional[dict]:
    """Show NoteEditorDialog modally; `existing` (a NoteAnnotation or None)
    pre-fills the fields for editing. Returns the chosen {text, color,
    font_size}, or None if cancelled or the text was left empty."""
    if existing is not None:
        dialog = NoteEditorDialog(
            parent, text=existing.text, color=existing.color, font_size=existing.font_size
        )
    else:
        dialog = NoteEditorDialog(parent)

    if dialog.exec() != QDialog.Accepted:
        return None

    values = dialog.values()
    if not values["text"]:
        return None
    return values
