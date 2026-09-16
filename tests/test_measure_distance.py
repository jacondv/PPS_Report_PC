import numpy as np
import pytest

from pps.scene.document import Document
from pps.scene.measurements import DistanceMeasurement
from pps.tools import measure_distance as measure_distance_module
from pps.tools.base import MouseButton, PointerEvent, PointerEventType, ToolContext
from pps.tools.measure_distance import MeasureDistanceTool


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
        points=np.zeros((1, 3)),
        distances=np.zeros(1),
        distance_field="distances",
        target_min=0.0,
        target_max=100.0,
    )
    return doc


def press(x, y, **kw):
    return PointerEvent(kind=PointerEventType.PRESS, x=x, y=y, button=MouseButton.LEFT, **kw)


def move(x, y, **kw):
    return PointerEvent(kind=PointerEventType.MOVE, x=x, y=y, **kw)


def test_two_clicks_create_distance_measurement(document, monkeypatch):
    points = {(0, 0): (0.0, 0.0, 0.0), (30, 40): (3.0, 4.0, 0.0)}
    monkeypatch.setattr(
        measure_distance_module, "pick_nearest_point_3d", lambda x, y, plotter: points[(x, y)]
    )
    monkeypatch.setattr(
        measure_distance_module, "project_to_screen", lambda pts, plotter: np.zeros((len(pts), 2))
    )

    tool = MeasureDistanceTool()
    tool.activate(make_ctx(document))

    assert tool.is_idle() is True
    tool.handle_pointer(press(0, 0))
    assert tool.is_idle() is False

    tool.handle_pointer(press(30, 40))

    assert tool.is_idle() is True
    assert len(document.measurements) == 1
    m = document.measurements[0]
    assert isinstance(m, DistanceMeasurement)
    assert m.p1 == (0.0, 0.0, 0.0)
    assert m.p2 == (3.0, 4.0, 0.0)
    assert m.distance_m == 5.0


def test_click_with_no_pick_is_consumed_but_no_state_change(document, monkeypatch):
    monkeypatch.setattr(measure_distance_module, "pick_nearest_point_3d", lambda x, y, plotter: None)

    tool = MeasureDistanceTool()
    tool.activate(make_ctx(document))

    consumed = tool.handle_pointer(press(5, 5))

    assert consumed is True
    assert tool.is_idle() is True
    assert len(document.measurements) == 0


def test_move_before_first_click_is_not_consumed(document):
    tool = MeasureDistanceTool()
    tool.activate(make_ctx(document))

    consumed = tool.handle_pointer(move(5, 5))

    assert consumed is False


def test_cancel_resets_in_progress_measurement(document, monkeypatch):
    monkeypatch.setattr(
        measure_distance_module, "pick_nearest_point_3d", lambda x, y, plotter: (1.0, 2.0, 3.0)
    )
    monkeypatch.setattr(
        measure_distance_module, "project_to_screen", lambda pts, plotter: np.zeros((len(pts), 2))
    )

    tool = MeasureDistanceTool()
    tool.activate(make_ctx(document))
    tool.handle_pointer(press(0, 0))
    assert tool.is_idle() is False

    tool.cancel()

    assert tool.is_idle() is True
    assert len(document.measurements) == 0
