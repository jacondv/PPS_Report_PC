"""
NoteTool (plain 2D screen-space text, no cloud anchor at all) is creation
only now: every click places a new note. Selecting/dragging/editing/
deleting an existing one all live in NavigateTool instead — see
test_navigate_tool.py.
"""

import pytest

from pps.scene.document import Document
from pps.tools.base import MouseButton, PointerEvent, PointerEventType, ToolContext
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


def test_clicking_an_existing_note_creates_another_one_instead_of_selecting_it(document):
    """Note is creation-only — it doesn't try to detect/select an existing
    note under the click the way NavigateTool does."""
    tool = make_tool(lambda existing, screen_pos: {"text": "n2"})
    tool.activate(make_ctx(document))

    tool.handle_pointer(press(100, 100))
    tool.handle_pointer(press(100, 100))

    assert len(document.annotations) == 2
