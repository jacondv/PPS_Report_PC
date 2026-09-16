"""
Tests RegionSelectTool logic directly via synthetic PointerEvent/KeyEvent
objects (not real Qt events — that's ToolManager's job, covered separately
in test_tool_manager.py). project_to_screen() is monkeypatched to a trivial
projection so these tests don't need a real VTK camera.
"""

import numpy as np
import pytest

from pps.core.layers import LayerManager
from pps.scene.document import Document
from pps.tools import region_select as region_select_module
from pps.tools.base import KeyEvent, MouseButton, PointerEvent, PointerEventType, ToolContext
from pps.tools.region_select import RegionMode, RegionSelectTool


class FakeOverlayRenderer:
    def AddActor(self, actor):
        pass

    def RemoveActor(self, actor):
        pass


class FakeViewport:
    plotter = None  # unused: project_to_screen is monkeypatched


def make_ctx(document):
    from pps.render.overlay import Overlay

    overlay = Overlay(FakeOverlayRenderer())
    return ToolContext(
        document=document,
        viewport=FakeViewport(),
        overlay=overlay,
        undo_stack=document.undo_stack,
        set_status=lambda s: None,
        request_render=lambda: None,
    )


@pytest.fixture
def document_with_square_layer(qtbot):
    """5 points: 4 forming a 10x10 square (indices 0-3), 1 far outside (4)."""
    points = np.array(
        [[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [10.0, 10.0, 0.0], [0.0, 10.0, 0.0], [50.0, 50.0, 0.0]]
    )
    distances = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    doc = Document()
    doc.load_point_cloud(
        source_path="C:/data/sample.ply",
        project_info=None,
        points=points,
        distances=distances,
        distance_field="distances",
        target_min=0.0,
        target_max=100.0,
    )
    return doc


@pytest.fixture(autouse=True)
def fake_projection(monkeypatch):
    # identity projection: screen (x, y) == world (x, y) for this synthetic layer
    monkeypatch.setattr(
        region_select_module, "project_to_screen", lambda points, plotter: points[:, :2]
    )


def press(x, y, button=MouseButton.LEFT, **kw):
    return PointerEvent(kind=PointerEventType.PRESS, x=x, y=y, button=button, **kw)


def move(x, y, **kw):
    return PointerEvent(kind=PointerEventType.MOVE, x=x, y=y, **kw)


def double_click(x, y, **kw):
    return PointerEvent(kind=PointerEventType.DOUBLE_CLICK, x=x, y=y, button=MouseButton.LEFT, **kw)


def release(x, y, **kw):
    return PointerEvent(kind=PointerEventType.RELEASE, x=x, y=y, button=MouseButton.LEFT, **kw)


def test_polygon_select_replace(document_with_square_layer):
    doc = document_with_square_layer
    tool = RegionSelectTool()
    tool.activate(make_ctx(doc))

    # 4 vertices with margin so the 4 corner points are strictly inside
    # (a polygon exactly on the point coordinates makes contains_points()
    # ambiguous at shared vertices/edges).
    tool.handle_pointer(press(-1, -1))
    tool.handle_pointer(press(11, -1))
    tool.handle_pointer(press(11, 11))
    tool.handle_pointer(press(-1, 11))
    tool.handle_pointer(double_click(-1, 11))

    assert doc.selection.count() == 4
    assert tool.is_idle()


def test_polygon_backspace_removes_last_vertex():
    tool = RegionSelectTool()
    tool._points = [(0, 0), (1, 1), (2, 2)]
    tool._redraw_polygon = lambda **kw: None  # avoid needing a real ctx/render

    consumed = tool.handle_key(KeyEvent(key="BackSpace"))

    assert consumed is True
    assert tool._points == [(0, 0), (1, 1)]


def test_polygon_right_click_cancels_if_too_few_points(document_with_square_layer):
    doc = document_with_square_layer
    tool = RegionSelectTool()
    tool.activate(make_ctx(doc))

    tool.handle_pointer(press(0, 0))
    tool.handle_pointer(press(10, 0))
    tool.handle_pointer(press(10, 10, button=MouseButton.RIGHT))

    assert doc.selection.is_empty()
    assert tool.is_idle()


def test_polygon_add_and_subtract_modifiers(document_with_square_layer):
    doc = document_with_square_layer
    tool = RegionSelectTool()
    tool.activate(make_ctx(doc))

    # first: select just point 0 with a tiny 4-vertex square around it
    tool.handle_pointer(press(-1, -1))
    tool.handle_pointer(press(1, -1))
    tool.handle_pointer(press(1, 1))
    tool.handle_pointer(press(-1, 1))
    tool.handle_pointer(double_click(-1, 1))
    assert doc.selection.count() == 1

    # add the full square (shift) -> union -> 4 points total
    tool.handle_pointer(press(-1, -1, shift=True))
    tool.handle_pointer(press(11, -1, shift=True))
    tool.handle_pointer(press(11, 11, shift=True))
    tool.handle_pointer(press(-1, 11, shift=True))
    tool.handle_pointer(double_click(-1, 11, shift=True))
    assert doc.selection.count() == 4

    # subtract the tiny square around point 0 -> back to 3
    tool.handle_pointer(press(-1, -1, ctrl=True))
    tool.handle_pointer(press(1, -1, ctrl=True))
    tool.handle_pointer(press(1, 1, ctrl=True))
    tool.handle_pointer(press(-1, 1, ctrl=True))
    tool.handle_pointer(double_click(-1, 1, ctrl=True))
    assert doc.selection.count() == 3


def test_deactivate_clears_scratch_and_hud(document_with_square_layer):
    doc = document_with_square_layer
    tool = RegionSelectTool()
    ctx = make_ctx(doc)
    tool.activate(ctx)

    tool.handle_pointer(press(0, 0))
    tool.handle_pointer(press(10, 0))
    assert len(tool.scratch) > 0

    tool.deactivate()
    # scratch was cleared (can't inspect after ctx is dropped, so re-check
    # via the tool's own state instead)
    assert tool._points == []


def test_rectangle_mode_selects(document_with_square_layer):
    doc = document_with_square_layer
    tool = RegionSelectTool()
    tool.activate(make_ctx(doc))
    tool.mode = RegionMode.RECTANGLE  # bypass set_mode() to avoid its cancel() call

    tool.handle_pointer(press(-1, -1))
    tool.handle_pointer(move(11, 11))
    tool.handle_pointer(release(11, 11))

    assert doc.selection.count() == 4


def test_lasso_mode_selects(document_with_square_layer):
    doc = document_with_square_layer
    tool = RegionSelectTool()
    tool.activate(make_ctx(doc))
    tool.mode = RegionMode.LASSO

    tool.handle_pointer(press(-1, -1))
    tool.handle_pointer(move(11, -1))
    tool.handle_pointer(move(11, 11))
    tool.handle_pointer(move(-1, 11))
    tool.handle_pointer(release(-1, 11))

    assert doc.selection.count() == 4
