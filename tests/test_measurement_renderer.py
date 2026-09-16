import numpy as np
import vtk

from pps.core.layers import SourceRef
from pps.render.measurement_renderer import MeasurementRenderer
from pps.render.overlay import Overlay
from pps.scene.measurements import AreaMeasurement, DistanceMeasurement


class FakePlotter:
    """Minimal stand-in for pyvistaqt's QtInteractor: a real (off-screen)
    VTK renderer + render window, no Qt widget needed."""

    def __init__(self):
        self.renderer = vtk.vtkRenderer()
        self.ren_win = vtk.vtkRenderWindow()
        self.ren_win.SetOffScreenRendering(1)
        self.ren_win.AddRenderer(self.renderer)
        self.ren_win.SetSize(400, 300)


def make_renderer():
    plotter = FakePlotter()
    overlay = Overlay(vtk.vtkRenderer())
    return MeasurementRenderer(plotter, overlay)


def test_sync_distance_creates_line_and_label():
    renderer = make_renderer()
    measurement = DistanceMeasurement(p1=(0.0, 0.0, 0.0), p2=(3.0, 4.0, 0.0))

    renderer.sync_one(measurement)

    assert measurement.id in renderer._labels
    assert measurement.id in renderer._line_actors
    assert measurement.id not in renderer._boundary_actors


def test_sync_area_creates_boundary_and_label():
    renderer = make_renderer()
    measurement = AreaMeasurement(
        boundary_px_at_creation=[(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)],
        sources=[SourceRef(layer_id="layer-1", indices=np.array([0, 1], dtype=np.uint32))],
        centroid=(1.0, 1.0, 0.0),
        area_m2=None,
    )

    renderer.sync_one(measurement)

    assert measurement.id in renderer._labels
    assert measurement.id in renderer._boundary_actors
    assert measurement.id not in renderer._line_actors


def test_sync_all_removes_stale_entries():
    renderer = make_renderer()
    m1 = DistanceMeasurement(p1=(0.0, 0.0, 0.0), p2=(1.0, 0.0, 0.0))
    m2 = DistanceMeasurement(p1=(0.0, 0.0, 0.0), p2=(2.0, 0.0, 0.0))

    renderer.sync_all([m1, m2])
    assert set(renderer._labels) == {m1.id, m2.id}

    renderer.sync_all([m2])
    assert set(renderer._labels) == {m2.id}


def test_remove_and_clear():
    renderer = make_renderer()
    m1 = DistanceMeasurement(p1=(0.0, 0.0, 0.0), p2=(1.0, 0.0, 0.0))
    renderer.sync_one(m1)

    renderer.remove(m1.id)
    assert m1.id not in renderer._labels
    assert m1.id not in renderer._line_actors

    renderer.sync_one(m1)
    renderer.clear()
    assert renderer._labels == {}
    assert renderer._line_actors == {}
    assert renderer._boundary_actors == {}


def test_sync_one_rebuilds_on_update():
    renderer = make_renderer()
    measurement = AreaMeasurement(
        boundary_px_at_creation=[(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)],
        sources=[],
        centroid=(1.0, 1.0, 0.0),
        area_m2=None,
    )
    renderer.sync_one(measurement)
    first_label = renderer._labels[measurement.id]

    measurement.area_m2 = 12.3
    renderer.sync_one(measurement)

    assert renderer._labels[measurement.id] is not first_label
    assert renderer._labels[measurement.id].text == "12.30 m²"
