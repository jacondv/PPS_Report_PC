"""
AnnotationTool (3D-anchored: one end on the cloud, the other draggable
text) is creation only now: every click on the cloud places a new
annotation. Selecting/dragging/editing/deleting an existing one all live
in NavigateTool instead — see test_navigate_tool.py.
"""

import numpy as np
import pytest

from pps.scene.document import Document
from pps.tools import annotation as annotation_module
from pps.tools.annotation import AnnotationTool
from pps.tools.base import MouseButton, PointerEvent, PointerEventType, ToolContext


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


def press(x, y, **kw):
    return PointerEvent(kind=PointerEventType.PRESS, x=x, y=y, button=MouseButton.LEFT, **kw)


def test_click_on_cloud_creates_an_anchored_annotation(document, monkeypatch):
    monkeypatch.setattr(annotation_module, "pick_nearest_point_3d", lambda x, y, plotter: (0.0, 0.0, 0.0))
    editor_calls = []

    def fake_editor(existing, screen_pos):
        editor_calls.append((existing, screen_pos))
        return {"text": "hello", "color": "#ff0000", "font_size": 20}

    tool = AnnotationTool(note_editor=fake_editor)
    tool.activate(make_ctx(document))

    tool.handle_pointer(press(100, 100))

    assert editor_calls == [(None, (100, 100))]
    assert len(document.annotations) == 1
    note = document.annotations[0]
    assert note.is_screen_note is False
    assert note.anchor == (0.0, 0.0, 0.0)
    assert note.text == "hello"
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
