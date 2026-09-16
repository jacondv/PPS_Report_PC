import numpy as np
import pytest

from pps.core.layers import LayerManager
from pps.scene.document import Document
from pps.scene.measurements import AreaMeasurement
from pps.tools import measure_area as measure_area_module
from pps.tools.base import MouseButton, PointerEvent, PointerEventType, ToolContext
from pps.tools.measure_area import MeasureAreaTool
from pps.tools.region_select import RegionMode


class FakeOverlayRenderer:
    def AddActor(self, actor):
        pass

    def RemoveActor(self, actor):
        pass


class FakeViewport:
    plotter = None


def make_ctx(document, status_calls=None):
    from pps.render.overlay import Overlay

    return ToolContext(
        document=document,
        viewport=FakeViewport(),
        overlay=Overlay(FakeOverlayRenderer()),
        undo_stack=document.undo_stack,
        set_status=(status_calls.append if status_calls is not None else (lambda s: None)),
        request_render=lambda: None,
    )


@pytest.fixture
def document_with_square_layer(qtbot):
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
    monkeypatch.setattr(
        measure_area_module, "project_to_screen", lambda points, plotter: points[:, :2]
    )


def press(x, y, **kw):
    return PointerEvent(kind=PointerEventType.PRESS, x=x, y=y, button=MouseButton.LEFT, **kw)


def double_click(x, y, **kw):
    return PointerEvent(kind=PointerEventType.DOUBLE_CLICK, x=x, y=y, button=MouseButton.LEFT, **kw)


def test_polygon_area_measurement_created_with_injected_result(document_with_square_layer):
    doc = document_with_square_layer
    original_id = doc.layer_manager.original.id
    recorded = {}

    def fake_requester(points, on_done):
        recorded["points"] = points
        on_done(42.5)

    tool = MeasureAreaTool(area_requester=fake_requester)
    tool.activate(make_ctx(doc))

    tool.handle_pointer(press(-1, -1))
    tool.handle_pointer(press(11, -1))
    tool.handle_pointer(press(11, 11))
    tool.handle_pointer(press(-1, 11))
    tool.handle_pointer(double_click(-1, 11))

    assert len(doc.measurements) == 1
    measurement = doc.measurements[0]
    assert isinstance(measurement, AreaMeasurement)
    assert measurement.area_m2 == 42.5
    assert len(measurement.sources) == 1
    assert measurement.sources[0].layer_id == original_id
    assert len(measurement.sources[0].indices) == 4
    assert recorded["points"].shape == (4, 3)
    assert tool.is_idle()


def test_area_measurement_none_until_callback_fires(document_with_square_layer):
    doc = document_with_square_layer
    pending_callbacks = []

    def deferred_requester(points, on_done):
        pending_callbacks.append(on_done)  # don't call it yet

    tool = MeasureAreaTool(area_requester=deferred_requester)
    tool.activate(make_ctx(doc))

    tool.handle_pointer(press(-1, -1))
    tool.handle_pointer(press(11, -1))
    tool.handle_pointer(press(11, 11))
    tool.handle_pointer(press(-1, 11))
    tool.handle_pointer(double_click(-1, 11))

    measurement = doc.measurements[0]
    assert measurement.area_m2 is None

    pending_callbacks[0](7.0)
    assert doc.measurements[0].area_m2 == 7.0


def test_empty_area_creates_no_measurement(document_with_square_layer):
    doc = document_with_square_layer
    status_calls = []
    called = {"count": 0}

    def fake_requester(points, on_done):
        called["count"] += 1

    tool = MeasureAreaTool(area_requester=fake_requester)
    tool.activate(make_ctx(doc, status_calls))

    # polygon far away from every point
    tool.handle_pointer(press(1000, 1000))
    tool.handle_pointer(press(1010, 1000))
    tool.handle_pointer(press(1010, 1010))
    tool.handle_pointer(press(1000, 1010))
    tool.handle_pointer(double_click(1000, 1010))

    assert len(doc.measurements) == 0
    assert called["count"] == 0
    assert "No points" in status_calls[-1]


def test_rectangle_mode_inherited_from_region_select(document_with_square_layer):
    doc = document_with_square_layer
    recorded = {}

    def fake_requester(points, on_done):
        recorded["n"] = len(points)
        on_done(1.0)

    tool = MeasureAreaTool(area_requester=fake_requester)
    tool.activate(make_ctx(doc))
    tool.mode = RegionMode.RECTANGLE

    from pps.tools.base import PointerEventType as PET

    tool.handle_pointer(press(-1, -1))
    tool.handle_pointer(PointerEvent(kind=PET.MOVE, x=11, y=11))
    tool.handle_pointer(PointerEvent(kind=PET.RELEASE, x=11, y=11, button=MouseButton.LEFT))

    assert recorded["n"] == 4
    assert len(doc.measurements) == 1
