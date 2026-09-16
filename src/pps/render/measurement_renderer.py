"""
Syncs Document measurements (distance/area) to on-screen visuals. Listens
to nothing itself — MainWindow (Phase 6) calls sync_one()/remove()/clear()
from Document's measurement_added/changed/removed/reset signal handlers,
keeping this a pure "data -> actors" mapper like LayerRenderer.
"""

from typing import Dict, Iterable, Tuple, Union

import numpy as np
import vtk

from pps.render.actors2d import polyline_actor
from pps.render.labels import AnchoredLabel, hex_to_rgb
from pps.scene.measurements import AreaMeasurement, DistanceMeasurement

Measurement = Union[DistanceMeasurement, AreaMeasurement]


class MeasurementRenderer:
    def __init__(self, plotter, overlay):
        self._plotter = plotter
        self._overlay = overlay
        self._labels: Dict[str, AnchoredLabel] = {}
        self._line_actors: Dict[str, vtk.vtkActor] = {}
        self._boundary_actors: Dict[str, vtk.vtkActor2D] = {}

    def sync_all(self, measurements: Iterable[Measurement]) -> None:
        measurements = list(measurements)
        wanted_ids = {m.id for m in measurements}
        for stale_id in set(self._labels) - wanted_ids:
            self.remove(stale_id)
        for measurement in measurements:
            self.sync_one(measurement)

    def sync_one(self, measurement: Measurement) -> None:
        self.remove(measurement.id)  # rebuild from scratch: simplest correct approach

        if isinstance(measurement, DistanceMeasurement):
            self._sync_distance(measurement)
        else:
            self._sync_area(measurement)

    def remove(self, measurement_id: str) -> None:
        label = self._labels.pop(measurement_id, None)
        if label is not None:
            label.remove()

        line_actor = self._line_actors.pop(measurement_id, None)
        if line_actor is not None:
            try:
                self._plotter.renderer.RemoveActor(line_actor)
            except Exception:
                pass

        boundary_actor = self._boundary_actors.pop(measurement_id, None)
        if boundary_actor is not None:
            try:
                self._overlay.renderer.RemoveActor(boundary_actor)
            except Exception:
                pass

    def clear(self) -> None:
        for measurement_id in list(self._labels) + list(self._line_actors) + list(self._boundary_actors):
            self.remove(measurement_id)

    # ------------------------------------------------------------------ distance
    def _sync_distance(self, measurement: DistanceMeasurement) -> None:
        line_source = vtk.vtkLineSource()
        line_source.SetPoint1(*measurement.p1)
        line_source.SetPoint2(*measurement.p2)
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(line_source.GetOutputPort())
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(*hex_to_rgb(measurement.color))
        actor.GetProperty().SetLineWidth(2.0)
        actor.SetVisibility(measurement.visible)
        self._plotter.renderer.AddActor(actor)
        self._line_actors[measurement.id] = actor

        midpoint = _midpoint(measurement.p1, measurement.p2)
        label = AnchoredLabel(
            self._plotter,
            self._overlay,
            anchor=midpoint,
            text=f"{measurement.distance_m:.3f} m",
            offset_px=measurement.label_offset_px,
            color=measurement.color,
            marker_radius=0.0,  # the line itself marks the segment; no extra sphere
        )
        label.set_visible(measurement.visible)
        self._labels[measurement.id] = label

    # ------------------------------------------------------------------ area
    def _sync_area(self, measurement: AreaMeasurement) -> None:
        # boundary_px_at_creation is a snapshot of screen pixels at the
        # moment the region was drawn — it does NOT track the camera
        # afterward (that would need re-projecting the original 3D
        # boundary, which we don't keep). Shown as a best-effort outline.
        if len(measurement.boundary_px_at_creation) >= 3:
            actor = polyline_actor(
                measurement.boundary_px_at_creation,
                closed=True,
                rgb=hex_to_rgb(measurement.color),
                line_width=2.0,
                opacity=0.7,
            )
            actor.SetVisibility(measurement.visible)
            self._overlay.renderer.AddActor(actor)
            self._boundary_actors[measurement.id] = actor

        text = "…" if measurement.area_m2 is None else f"{measurement.area_m2:.2f} m²"
        label = AnchoredLabel(
            self._plotter,
            self._overlay,
            anchor=measurement.centroid,
            text=text,
            offset_px=measurement.label_offset_px,
            color=measurement.color,
        )
        label.set_visible(measurement.visible)
        self._labels[measurement.id] = label


def _midpoint(p1: Tuple[float, float, float], p2: Tuple[float, float, float]) -> Tuple[float, float, float]:
    mid = (np.asarray(p1) + np.asarray(p2)) / 2.0
    return (float(mid[0]), float(mid[1]), float(mid[2]))
