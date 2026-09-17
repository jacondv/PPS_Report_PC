"""
Inline note editor: a small text box embedded directly on top of the 3D
viewport at the point the user clicked, instead of a separate modal dialog
window. The user types the note text right where they placed it; Enter (or
clicking away) commits, Escape cancels.

Kept synchronous (like QDialog.exec()) via a local QEventLoop so it can
still be used as a drop-in NoteTool.note_editor callback, which expects an
immediate return value.
"""

from typing import Optional, Tuple

from PySide6.QtCore import QEventLoop, QPoint, Qt
from PySide6.QtGui import QColor, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QFrame,
    QHBoxLayout,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

_EDITOR_WIDTH = 220
_EDITOR_TEXT_HEIGHT = 70


class _InlineNoteEditor(QFrame):
    def __init__(self, parent, text: str, color: str, font_size: int):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "QFrame { background: #262b36; border: 1px solid #4a5468; border-radius: 4px; }"
            "QTextEdit { background: #1b1f27; color: #e8ebf0; border: 1px solid #333a47; }"
        )
        self._color = color
        self._committed: Optional[dict] = None
        self._choosing_color = False
        self._loop = QEventLoop()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        self.text_edit = QTextEdit(self)
        self.text_edit.setPlainText(text)
        self.text_edit.setFixedSize(_EDITOR_WIDTH, _EDITOR_TEXT_HEIGHT)
        self.text_edit.installEventFilter(self)
        layout.addWidget(self.text_edit)

        row = QHBoxLayout()
        row.setSpacing(4)
        self.color_button = QPushButton(self)
        self.color_button.setFixedSize(22, 20)
        self._update_color_button()
        self.color_button.clicked.connect(self._choose_color)
        row.addWidget(self.color_button)

        self.font_spin = QSpinBox(self)
        self.font_spin.setRange(8, 48)
        self.font_spin.setValue(font_size)
        self.font_spin.setFixedWidth(50)
        row.addWidget(self.font_spin)
        row.addStretch()

        ok_button = QPushButton("OK", self)
        ok_button.setFixedWidth(44)
        ok_button.clicked.connect(self._commit)
        row.addWidget(ok_button)
        layout.addLayout(row)

        self.adjustSize()

    def _update_color_button(self) -> None:
        self.color_button.setStyleSheet(f"background-color: {self._color}; border: 1px solid #555;")

    def _choose_color(self) -> None:
        self._choosing_color = True
        chosen = QColorDialog.getColor(QColor(self._color), self, "Note color")
        self._choosing_color = False
        if chosen.isValid():
            self._color = chosen.name()
            self._update_color_button()

    def eventFilter(self, obj, event) -> bool:
        if obj is self.text_edit and event.type() == event.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (
                event.modifiers() & Qt.KeyboardModifier.ShiftModifier
            ):
                self._commit()
                return True
            if key == Qt.Key.Key_Escape:
                self._cancel()
                return True
        return super().eventFilter(obj, event)

    def _commit(self) -> None:
        text = self.text_edit.toPlainText().strip()
        self._committed = (
            {"text": text, "color": self._color, "font_size": self.font_spin.value()}
            if text
            else None
        )
        self._loop.quit()

    def _cancel(self) -> None:
        self._committed = None
        self._loop.quit()

    def _on_focus_changed(self, _old, new) -> None:
        if self._choosing_color:
            return
        if new is None or not self.isAncestorOf(new):
            self._commit()

    def run(self, pos: QPoint) -> Optional[dict]:
        self.move(pos)
        self.show()
        self.raise_()
        self.text_edit.setFocus()
        self.text_edit.moveCursor(QTextCursor.MoveOperation.End)

        app = QApplication.instance()
        app.focusChanged.connect(self._on_focus_changed)
        try:
            self._loop.exec()
        finally:
            app.focusChanged.disconnect(self._on_focus_changed)
            self.hide()
            self.deleteLater()
        return self._committed


def _clamp_to_parent(parent_widget, pos: QPoint, size) -> QPoint:
    x = min(max(pos.x(), 0), max(parent_widget.width() - size.width(), 0))
    y = min(max(pos.y(), 0), max(parent_widget.height() - size.height(), 0))
    return QPoint(x, y)


def open_inline_note_editor(
    viewport_widget, screen_pos: Tuple[float, float], existing=None
) -> Optional[dict]:
    """Show the inline editor over `viewport_widget` at `screen_pos` (VTK
    convention: physical pixels, origin bottom-left — the same convention
    Tool pointer events use), pre-filled from `existing` when editing.

    Returns {text, color, font_size}, or None if cancelled / left empty.
    """
    text = existing.text if existing is not None else ""
    color = existing.color if existing is not None else "#ffd166"
    font_size = existing.font_size if existing is not None else 14

    dpr = viewport_widget.devicePixelRatioF()
    height = viewport_widget.height()
    qt_x = screen_pos[0] / dpr
    qt_y = height - (screen_pos[1] / dpr)

    editor = _InlineNoteEditor(viewport_widget, text=text, color=color, font_size=font_size)
    pos = _clamp_to_parent(viewport_widget, QPoint(int(qt_x), int(qt_y)), editor.sizeHint())
    return editor.run(pos)
