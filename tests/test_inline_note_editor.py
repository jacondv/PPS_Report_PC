"""
Inline note editor: typing directly into a small text box embedded on top
of the 3D viewport at the click location, instead of a separate modal
dialog window (that's the whole point of "Note" per the user's request:
type the text right where you clicked in the 3D view).
"""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget

from pps.ui.widgets.inline_note_editor import _InlineNoteEditor, open_inline_note_editor


def test_enter_commits_typed_text(qtbot):
    host = QWidget()
    qtbot.addWidget(host)
    host.resize(400, 300)
    host.show()

    def type_and_commit():
        editor = host.findChild(_InlineNoteEditor)
        assert editor is not None
        editor.text_edit.setPlainText("hello inline note")
        editor._commit()

    QTimer.singleShot(50, type_and_commit)
    result = open_inline_note_editor(host, (50, 50), existing=None)

    assert result == {"text": "hello inline note", "color": "#ffd166", "font_size": 14}


def test_escape_cancels_without_committing(qtbot):
    host = QWidget()
    qtbot.addWidget(host)
    host.resize(400, 300)
    host.show()

    def type_and_cancel():
        editor = host.findChild(_InlineNoteEditor)
        editor.text_edit.setPlainText("this should be discarded")
        editor._cancel()

    QTimer.singleShot(50, type_and_cancel)
    result = open_inline_note_editor(host, (50, 50), existing=None)

    assert result is None


def test_empty_text_commits_as_none(qtbot):
    host = QWidget()
    qtbot.addWidget(host)
    host.resize(400, 300)
    host.show()

    def commit_empty():
        editor = host.findChild(_InlineNoteEditor)
        editor._commit()

    QTimer.singleShot(50, commit_empty)
    result = open_inline_note_editor(host, (50, 50), existing=None)

    assert result is None


def test_editing_existing_note_prefills_text_color_and_font_size(qtbot):
    host = QWidget()
    qtbot.addWidget(host)
    host.resize(400, 300)
    host.show()

    class _Existing:
        text = "old text"
        color = "#00ff00"
        font_size = 22

    seen = {}

    def read_and_commit():
        editor = host.findChild(_InlineNoteEditor)
        seen["text"] = editor.text_edit.toPlainText()
        seen["color"] = editor._color
        seen["font_size"] = editor.font_spin.value()
        editor._commit()

    QTimer.singleShot(50, read_and_commit)
    open_inline_note_editor(host, (50, 50), existing=_Existing())

    assert seen == {"text": "old text", "color": "#00ff00", "font_size": 22}
