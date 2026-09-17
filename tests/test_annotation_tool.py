"""
Tests AnnotationTool (3D-anchored note: one end on the cloud, the other
draggable text) directly via synthetic PointerEvent/KeyEvent objects.
pick_nearest_point_3d / project_to_screen / compute_label_bbox are
monkeypatched to trivial functions so these tests don't need a real VTK
camera — note.anchor is treated as if it were already screen-space (x, y)
for simplicity, matching the pattern used for RegionSelectTool's tests.
"""

import numpy as np
import pytest

from pps.scene.document import Document
from pps.tools import annotation as annotation_module
from pps.tools.base import KeyEvent, MouseButton, PointerEvent, PointerEventType, ToolContext
from pps.tools.annotation import AnnotationTool


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


@pytest.fixture
def document(qtbot):
    doc = Document()
    doc.load_point_cloud(
        source_path="C:/data/sample.ply",
        project_info=None,
        points=np.array([[0.0, 0.0, 0.0]]),
        distances=np.array([10.0]),
        distance_field="distances",
        target_min=0.0,
        target_max=100.0,
    )
    return doc


@pytest.fixture(autouse=True)
def fake_geometry(monkeypatch):
    # note.anchor is (x, y, 0) treated directly as screen pixels.
    monkeypatch.setattr(
        annotation_module, "project_to_screen", lambda pts, plotter: np.array([[p[0], p[1]] for p in pts])
    )

    def fake_bbox(anchor, offset_px, text, font_size, plotter):
        lx, ly = anchor[0] + offset_px[0], anchor[1] + offset_px[1]
        return (lx - 5, ly - 5, lx + 50, ly + 20)

    monkeypatch.setattr(annotation_module, "compute_label_bbox", fake_bbox)


def press(x, y, **kw):
    return PointerEvent(kind=PointerEventType.PRESS, x=x, y=y, button=MouseButton.LEFT, **kw)


def move(x, y, **kw):
    return PointerEvent(kind=PointerEventType.MOVE, x=x, y=y, **kw)


def release(x, y, **kw):
    return PointerEvent(kind=PointerEventType.RELEASE, x=x, y=y, button=MouseButton.LEFT, **kw)


def double_click(x, y, **kw):
    return PointerEvent(kind=PointerEventType.DOUBLE_CLICK, x=x, y=y, button=MouseButton.LEFT, **kw)


def test_click_creates_note(document, monkeypatch):
    monkeypatch.setattr(annotation_module, "pick_nearest_point_3d", lambda x, y, plotter: (0.0, 0.0, 0.0))
    editor_calls = []

    def fake_editor(existing, screen_pos):
        editor_calls.append(existing)
        return {"text": "hello", "color": "#ff0000", "font_size": 20}

    tool = AnnotationTool(note_editor=fake_editor)
    tool.activate(make_ctx(document))

    tool.handle_pointer(press(100, 100))

    assert editor_calls == [None]
    assert len(document.annotations) == 1
    note = document.annotations[0]
    assert note.text == "hello"
    assert note.color == "#ff0000"
    assert note.font_size == 20
    assert note.layer_id == document.layer_manager.original.id
    # legacy Layer.annotations kept in sync for the report
    assert document.layer_manager.original.annotations == [{"text": "hello"}]


def test_click_with_editor_cancelled_creates_nothing(document, monkeypatch):
    monkeypatch.setattr(annotation_module, "pick_nearest_point_3d", lambda x, y, plotter: (0.0, 0.0, 0.0))
    tool = AnnotationTool(note_editor=lambda existing, screen_pos: None)
    tool.activate(make_ctx(document))

    tool.handle_pointer(press(100, 100))

    assert len(document.annotations) == 0


def test_click_on_empty_space_creates_nothing(document, monkeypatch):
    monkeypatch.setattr(annotation_module, "pick_nearest_point_3d", lambda x, y, plotter: None)
    called = []
    tool = AnnotationTool(note_editor=lambda existing, screen_pos: called.append(existing) or {"text": "x"})
    tool.activate(make_ctx(document))

    consumed = tool.handle_pointer(press(500, 500))

    assert consumed is True
    assert called == []
    assert len(document.annotations) == 0


def _add_note(document, anchor=(100.0, 100.0, 0.0), text="hi"):
    from pps.scene.annotations import NoteAnnotation
    from pps.scene.commands import AddNoteCommand

    note = NoteAnnotation(anchor=anchor, text=text, layer_id=document.layer_manager.original.id)
    document.undo_stack.push(AddNoteCommand(document, note))
    return note


def test_press_on_label_selects_without_opening_editor(document):
    note = _add_note(document)
    editor_calls = []
    tool = AnnotationTool(note_editor=lambda existing, screen_pos: editor_calls.append(existing))
    tool.activate(make_ctx(document))

    # label bbox (per fake_bbox) is around (135..190, 135..160) for anchor
    # (100,100) + default offset (40,40)
    consumed = tool.handle_pointer(press(150, 150))

    assert consumed is True
    assert editor_calls == []
    assert tool._selected_note_id == note.id
    assert tool.is_idle() is False


def test_drag_label_moves_offset_on_release(document):
    note = _add_note(document)
    tool = AnnotationTool(note_editor=lambda existing, screen_pos: None)
    tool.activate(make_ctx(document))

    tool.handle_pointer(press(150, 150))
    tool.handle_pointer(move(170, 160))  # +20, +10
    tool.handle_pointer(release(170, 160))

    assert tool.is_idle() is True
    updated = document._find_note(note.id)
    assert updated.label_offset_px == (60, 50)  # (40+20, 40+10)

    document.undo_stack.undo()
    assert document._find_note(note.id).label_offset_px == (40, 40)


def test_tiny_drag_below_threshold_is_not_committed(document):
    note = _add_note(document)
    tool = AnnotationTool(note_editor=lambda existing, screen_pos: None)
    tool.activate(make_ctx(document))

    tool.handle_pointer(press(150, 150))
    tool.handle_pointer(move(151, 151))  # 1px, below DRAG_THRESHOLD_PX
    tool.handle_pointer(release(151, 151))

    assert document._find_note(note.id).label_offset_px == (40, 40)
    assert document.undo_stack.count() == 1  # only the AddNoteCommand from _add_note


def test_double_click_edits_existing_note(document):
    note = _add_note(document, text="old text")
    editor_calls = []

    def fake_editor(existing, screen_pos):
        editor_calls.append(existing)
        return {"text": "new text", "color": "#00ff00", "font_size": 18}

    tool = AnnotationTool(note_editor=fake_editor)
    tool.activate(make_ctx(document))

    tool.handle_pointer(double_click(150, 150))

    assert editor_calls[0] is note
    updated = document._find_note(note.id)
    assert updated.text == "new text"
    assert updated.color == "#00ff00"
    assert updated.font_size == 18
    assert document.layer_manager.original.annotations == [{"text": "new text"}]


def test_delete_key_removes_selected_note(document):
    note = _add_note(document)
    tool = AnnotationTool(note_editor=lambda existing, screen_pos: None)
    tool.activate(make_ctx(document))

    tool.handle_pointer(press(150, 150))
    consumed = tool.handle_key(KeyEvent(key="Delete"))

    assert consumed is True
    assert len(document.annotations) == 0
    assert document.layer_manager.original.annotations == []


def test_delete_key_without_selection_is_not_consumed(document):
    tool = AnnotationTool(note_editor=lambda existing, screen_pos: None)
    tool.activate(make_ctx(document))

    consumed = tool.handle_key(KeyEvent(key="Delete"))

    assert consumed is False


def test_cancel_during_drag_does_not_move_note(document):
    note = _add_note(document)
    tool = AnnotationTool(note_editor=lambda existing, screen_pos: None)
    tool.activate(make_ctx(document))

    tool.handle_pointer(press(150, 150))
    tool.handle_pointer(move(300, 300))
    tool.cancel()

    assert tool.is_idle() is True
    assert document._find_note(note.id).label_offset_px == (40, 40)
