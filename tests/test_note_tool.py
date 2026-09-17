"""
Tests NoteTool (plain 2D screen-space text, no cloud anchor at all) directly
via synthetic PointerEvent/KeyEvent objects. `_viewport_size` is monkeypatched
to a fixed size so drag/hit-test math is predictable without a real VTK
render window.
"""

import pytest

from pps.scene.document import Document
from pps.tools.base import KeyEvent, MouseButton, PointerEvent, PointerEventType, ToolContext
from pps.tools.note import NoteTool

VIEWPORT_SIZE = (1000, 1000)


class FakeOverlayRenderer:
    def AddActor(self, actor):
        pass

    def RemoveActor(self, actor):
        pass


class FakeViewport:
    plotter = None


def make_ctx(document):
    from pps.render.overlay import Overlay

    return ToolContext(
        document=document,
        viewport=FakeViewport(),
        overlay=Overlay(FakeOverlayRenderer()),
        undo_stack=document.undo_stack,
        set_status=lambda s: None,
        request_render=lambda: None,
    )


def make_tool(note_editor):
    tool = NoteTool(note_editor=note_editor)
    tool._viewport_size = lambda: VIEWPORT_SIZE
    return tool


@pytest.fixture
def document(qtbot):
    return Document()


def press(x, y, **kw):
    return PointerEvent(kind=PointerEventType.PRESS, x=x, y=y, button=MouseButton.LEFT, **kw)


def move(x, y, **kw):
    return PointerEvent(kind=PointerEventType.MOVE, x=x, y=y, **kw)


def release(x, y, **kw):
    return PointerEvent(kind=PointerEventType.RELEASE, x=x, y=y, button=MouseButton.LEFT, **kw)


def double_click(x, y, **kw):
    return PointerEvent(kind=PointerEventType.DOUBLE_CLICK, x=x, y=y, button=MouseButton.LEFT, **kw)


def test_click_anywhere_creates_a_screen_note_with_no_cloud_point_needed(document):
    editor_calls = []

    def fake_editor(existing, screen_pos):
        editor_calls.append((existing, screen_pos))
        return {"text": "hello", "color": "#ff0000", "font_size": 20}

    tool = make_tool(fake_editor)
    tool.activate(make_ctx(document))

    tool.handle_pointer(press(100, 200))

    assert editor_calls == [(None, (100, 200))]
    assert len(document.annotations) == 1
    note = document.annotations[0]
    assert note.is_screen_note is True
    assert note.anchor is None
    assert note.text == "hello"
    assert note.color == "#ff0000"
    assert note.font_size == 20
    assert note.screen_pos_frac == (0.1, 0.2)


def test_click_with_editor_cancelled_creates_nothing(document):
    tool = make_tool(lambda existing, screen_pos: None)
    tool.activate(make_ctx(document))

    tool.handle_pointer(press(100, 100))

    assert len(document.annotations) == 0


def _add_note(document, pos_frac=(0.5, 0.5), text="hi"):
    from pps.scene.annotations import NoteAnnotation
    from pps.scene.commands import AddNoteCommand

    note = NoteAnnotation(text=text, screen_pos_frac=pos_frac)
    document.undo_stack.push(AddNoteCommand(document, note))
    return note


def test_press_on_existing_text_selects_without_opening_editor(document):
    note = _add_note(document, pos_frac=(0.5, 0.5))  # -> (500, 500)
    editor_calls = []
    tool = make_tool(lambda existing, screen_pos: editor_calls.append(existing))
    tool.activate(make_ctx(document))

    consumed = tool.handle_pointer(press(510, 510))

    assert consumed is True
    assert editor_calls == []
    assert tool._selected_note_id == note.id
    assert tool.is_idle() is False


def test_drag_moves_note_to_new_position_on_release(document):
    note = _add_note(document, pos_frac=(0.5, 0.5))
    tool = make_tool(lambda existing, screen_pos: None)
    tool.activate(make_ctx(document))

    tool.handle_pointer(press(510, 510))
    tool.handle_pointer(move(610, 560))  # +100px x, +50px y -> +0.1, +0.05 frac
    tool.handle_pointer(release(610, 560))

    assert tool.is_idle() is True
    updated = document._find_note(note.id)
    assert updated.screen_pos_frac == pytest.approx((0.6, 0.55))

    document.undo_stack.undo()
    assert document._find_note(note.id).screen_pos_frac == (0.5, 0.5)


def test_tiny_drag_below_threshold_is_not_committed(document):
    note = _add_note(document, pos_frac=(0.5, 0.5))
    tool = make_tool(lambda existing, screen_pos: None)
    tool.activate(make_ctx(document))

    tool.handle_pointer(press(510, 510))
    tool.handle_pointer(move(511, 511))  # 1px, below DRAG_THRESHOLD_PX
    tool.handle_pointer(release(511, 511))

    assert document._find_note(note.id).screen_pos_frac == (0.5, 0.5)
    assert document.undo_stack.count() == 1  # only the AddNoteCommand from _add_note


def test_double_click_edits_existing_note_text(document):
    note = _add_note(document, pos_frac=(0.5, 0.5), text="old text")
    editor_calls = []

    def fake_editor(existing, screen_pos):
        editor_calls.append(existing)
        return {"text": "new text", "color": "#00ff00", "font_size": 18}

    tool = make_tool(fake_editor)
    tool.activate(make_ctx(document))

    tool.handle_pointer(double_click(510, 510))

    assert editor_calls[0] is note
    updated = document._find_note(note.id)
    assert updated.text == "new text"
    assert updated.color == "#00ff00"
    assert updated.font_size == 18


def test_delete_key_removes_selected_note(document):
    _add_note(document, pos_frac=(0.5, 0.5))
    tool = make_tool(lambda existing, screen_pos: None)
    tool.activate(make_ctx(document))

    tool.handle_pointer(press(510, 510))
    consumed = tool.handle_key(KeyEvent(key="Delete"))

    assert consumed is True
    assert len(document.annotations) == 0


def test_delete_key_without_selection_is_not_consumed(document):
    tool = make_tool(lambda existing, screen_pos: None)
    tool.activate(make_ctx(document))

    consumed = tool.handle_key(KeyEvent(key="Delete"))

    assert consumed is False


def test_cancel_during_drag_does_not_move_note(document):
    note = _add_note(document, pos_frac=(0.5, 0.5))
    tool = make_tool(lambda existing, screen_pos: None)
    tool.activate(make_ctx(document))

    tool.handle_pointer(press(510, 510))
    tool.handle_pointer(move(900, 900))
    tool.cancel()

    assert tool.is_idle() is True
    assert document._find_note(note.id).screen_pos_frac == (0.5, 0.5)
