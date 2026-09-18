"""
NavigateTool: the default tool now also owns selecting/highlighting,
dragging (moving), and right-click editing/deleting existing notes/
annotations/measurements — Note and Annotation are creation-only (see
test_note_tool.py / test_annotation_tool.py). A click that hits nothing
must return False so VTK's own camera style still handles it.

project_to_screen is monkeypatched to treat a 3D point's (x, y) as literal
screen pixels, matching the convention used by the old note/annotation
tool tests — anchor (x, y, 0) IS the screen position.
"""

import numpy as np
import pytest

from pps.render import labels as labels_module
from pps.scene.annotations import NoteAnnotation
from pps.scene.commands import AddNoteCommand
from pps.scene.document import Document
from pps.scene.measurements import AreaMeasurement, DistanceMeasurement
from pps.tools.base import KeyEvent, MouseButton, PointerEvent, PointerEventType, ToolContext
from pps.tools.navigate import NavigateTool

VIEWPORT_SIZE = (1000, 1000)


class FakeRenWin:
    def GetSize(self):
        return VIEWPORT_SIZE


class FakePlotter:
    ren_win = FakeRenWin()


class FakeViewport:
    plotter = FakePlotter()


class FakeOverlayRenderer:
    def AddActor(self, actor):
        pass

    def RemoveActor(self, actor):
        pass


@pytest.fixture(autouse=True)
def fake_projection(monkeypatch):
    monkeypatch.setattr(
        labels_module, "project_to_screen", lambda pts, plotter: np.array([[p[0], p[1]] for p in pts])
    )


class Recorder:
    def __init__(self):
        self.highlighted = []
        self.moved = []

    def set_highlighted(self, kind, object_id):
        self.highlighted.append((kind, object_id))

    def move_object_preview(self, kind, object_id, **kwargs):
        self.moved.append((kind, object_id, kwargs))


def make_ctx(document, recorder=None, undo_stack=None):
    from pps.render.overlay import Overlay

    recorder = recorder or Recorder()
    return ToolContext(
        document=document,
        viewport=FakeViewport(),
        overlay=Overlay(FakeOverlayRenderer()),
        undo_stack=undo_stack if undo_stack is not None else document.undo_stack,
        set_status=lambda s: None,
        request_render=lambda: None,
        move_object_preview=recorder.move_object_preview,
        set_highlighted=recorder.set_highlighted,
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


def press(x, y, button=MouseButton.LEFT, **kw):
    return PointerEvent(kind=PointerEventType.PRESS, x=x, y=y, button=button, **kw)


def move(x, y, **kw):
    return PointerEvent(kind=PointerEventType.MOVE, x=x, y=y, **kw)


def release(x, y, **kw):
    return PointerEvent(kind=PointerEventType.RELEASE, x=x, y=y, button=MouseButton.LEFT, **kw)


def _add_anchored_note(document, anchor=(100.0, 100.0, 0.0), text="hi"):
    note = NoteAnnotation(anchor=anchor, text=text, layer_id=document.layer_manager.original.id)
    document.undo_stack.push(AddNoteCommand(document, note))
    return note


def _add_screen_note(document, pos_frac=(0.5, 0.5), text="hi"):
    note = NoteAnnotation(text=text, screen_pos_frac=pos_frac)
    document.undo_stack.push(AddNoteCommand(document, note))
    return note


def test_click_on_empty_space_does_not_consume_and_deselects(document):
    recorder = Recorder()
    tool = NavigateTool()
    tool.activate(make_ctx(document, recorder))

    consumed = tool.handle_pointer(press(500, 500))

    assert consumed is False
    assert recorder.highlighted[-1] == (None, None)


def test_click_on_anchored_annotation_selects_and_highlights(document):
    note = _add_anchored_note(document)
    recorder = Recorder()
    tool = NavigateTool()
    tool.activate(make_ctx(document, recorder))

    # label sits around anchor (100,100) + default offset (40,40)
    consumed = tool.handle_pointer(press(150, 150))

    assert consumed is True
    assert recorder.highlighted[-1] == ("note", note.id)


def test_click_on_screen_note_selects_and_highlights(document):
    note = _add_screen_note(document, pos_frac=(0.5, 0.5))  # -> (500, 500)
    recorder = Recorder()
    tool = NavigateTool()
    tool.activate(make_ctx(document, recorder))

    consumed = tool.handle_pointer(press(510, 510))

    assert consumed is True
    assert recorder.highlighted[-1] == ("note", note.id)


def test_click_on_measurement_selects_but_is_not_draggable(document):
    m = DistanceMeasurement(p1=(100.0, 100.0, 0.0), p2=(100.0, 100.0, 0.0), layer_id=None)
    document.measurements.append(m)
    recorder = Recorder()
    tool = NavigateTool()
    tool.activate(make_ctx(document, recorder))

    consumed = tool.handle_pointer(press(140, 140))  # midpoint (100,100) + default offset (20,20)

    assert consumed is True
    assert recorder.highlighted[-1] == ("distance", m.id)
    assert tool.is_idle() is True  # not armed for dragging

    # a MOVE now should do nothing / not consume, since nothing is dragging
    consumed_move = tool.handle_pointer(move(200, 200))
    assert consumed_move is False


def test_drag_screen_note_previews_live_and_commits_on_release(document):
    note = _add_screen_note(document, pos_frac=(0.5, 0.5))
    recorder = Recorder()
    tool = NavigateTool()
    tool.activate(make_ctx(document, recorder))

    tool.handle_pointer(press(510, 510))
    tool.handle_pointer(move(610, 560))  # +100px x, +50px y -> +0.1, +0.05 frac

    # live preview happened without touching the Document yet
    assert recorder.moved[-1] == ("note", note.id, {"pos_frac": pytest.approx((0.6, 0.55))})
    assert document._find_note(note.id).screen_pos_frac == (0.5, 0.5)

    tool.handle_pointer(release(610, 560))

    updated = document._find_note(note.id)
    assert updated.screen_pos_frac == pytest.approx((0.6, 0.55))

    document.undo_stack.undo()
    assert document._find_note(note.id).screen_pos_frac == (0.5, 0.5)


def test_drag_anchored_annotation_commits_offset_on_release(document):
    note = _add_anchored_note(document)
    recorder = Recorder()
    tool = NavigateTool()
    tool.activate(make_ctx(document, recorder))

    tool.handle_pointer(press(150, 150))
    tool.handle_pointer(move(170, 160))  # +20, +10
    tool.handle_pointer(release(170, 160))

    updated = document._find_note(note.id)
    assert updated.label_offset_px == (60, 50)  # (40+20, 40+10)


def test_tiny_drag_below_threshold_is_not_committed_and_snaps_back(document):
    note = _add_screen_note(document, pos_frac=(0.5, 0.5))
    recorder = Recorder()
    tool = NavigateTool()
    tool.activate(make_ctx(document, recorder))

    tool.handle_pointer(press(510, 510))
    tool.handle_pointer(move(511, 511))  # 1px, below DRAG_THRESHOLD_PX
    tool.handle_pointer(release(511, 511))

    assert document._find_note(note.id).screen_pos_frac == (0.5, 0.5)
    assert document.undo_stack.count() == 1  # only the AddNoteCommand
    assert recorder.moved[-1] == ("note", note.id, {"pos_frac": (0.5, 0.5)})  # snapped back


def test_cancel_during_drag_reverts_preview_and_keeps_document_unchanged(document):
    note = _add_screen_note(document, pos_frac=(0.5, 0.5))
    recorder = Recorder()
    tool = NavigateTool()
    tool.activate(make_ctx(document, recorder))

    tool.handle_pointer(press(510, 510))
    tool.handle_pointer(move(900, 900))
    tool.cancel()

    assert tool.is_idle() is True
    assert document._find_note(note.id).screen_pos_frac == (0.5, 0.5)
    assert recorder.moved[-1] == ("note", note.id, {"pos_frac": (0.5, 0.5)})


def test_delete_key_removes_selected_note(document):
    _add_screen_note(document, pos_frac=(0.5, 0.5))
    recorder = Recorder()
    tool = NavigateTool()
    tool.activate(make_ctx(document, recorder))

    tool.handle_pointer(press(510, 510))
    consumed = tool.handle_key(KeyEvent(key="Delete"))

    assert consumed is True
    assert len(document.annotations) == 0


def test_delete_key_without_selection_is_not_consumed(document):
    tool = NavigateTool()
    tool.activate(make_ctx(document))

    assert tool.handle_key(KeyEvent(key="Delete")) is False


def test_right_click_edit_calls_note_editor_and_pushes_edit_command(document):
    note = _add_screen_note(document, pos_frac=(0.5, 0.5), text="old")
    recorder = Recorder()
    editor_calls = []

    def fake_editor(existing, screen_pos):
        editor_calls.append(existing)
        return {"text": "new", "color": "#00ff00", "font_size": 18}

    tool = NavigateTool(note_editor=fake_editor, object_menu=lambda kind, oid: "edit")
    tool.activate(make_ctx(document, recorder))

    consumed = tool.handle_pointer(press(510, 510, button=MouseButton.RIGHT))

    assert consumed is True
    assert editor_calls[0] is note
    assert document._find_note(note.id).text == "new"


def test_right_click_delete_removes_note_and_clears_selection(document):
    note = _add_screen_note(document, pos_frac=(0.5, 0.5))
    recorder = Recorder()
    tool = NavigateTool(object_menu=lambda kind, oid: "delete")
    tool.activate(make_ctx(document, recorder))

    consumed = tool.handle_pointer(press(510, 510, button=MouseButton.RIGHT))

    assert consumed is True
    assert document._find_note(note.id) is None
    assert tool._selected is None


def test_right_click_on_empty_space_does_not_consume(document):
    tool = NavigateTool(object_menu=lambda kind, oid: "delete")
    tool.activate(make_ctx(document))

    consumed = tool.handle_pointer(press(500, 500, button=MouseButton.RIGHT))

    assert consumed is False


def test_right_click_measurement_delete(document):
    m = AreaMeasurement(
        boundary_px_at_creation=[(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)],
        sources=[],
        centroid=(100.0, 100.0, 0.0),
        area_m2=5.0,
    )
    document.measurements.append(m)
    tool = NavigateTool(object_menu=lambda kind, oid: "delete")
    tool.activate(make_ctx(document))

    consumed = tool.handle_pointer(press(140, 140, button=MouseButton.RIGHT))

    assert consumed is True
    assert document._find_measurement(m.id) is None


def test_external_select_preselects_for_the_next_drag(document):
    """Used by the Project dock's "Move" context action."""
    note = _add_screen_note(document, pos_frac=(0.5, 0.5))
    recorder = Recorder()
    tool = NavigateTool()
    tool.activate(make_ctx(document, recorder))

    tool.select("note", note.id)
    assert recorder.highlighted[-1] == ("note", note.id)

    tool.handle_pointer(move(510, 510))  # not dragging yet: a plain move does nothing
    assert tool.is_idle() is True
