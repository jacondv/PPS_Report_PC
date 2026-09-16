"""
MeasureAreaTool: draws a region exactly like RegionSelectTool (polygon /
rectangle / lasso) but, on close, creates an AreaMeasurement instead of
changing the selection — area is computed with the same BPA method/radii
as the PDF report, via an injectable `area_requester` so the actual
QThread work (AreaMeasureWorker) can be owned by MainWindow (Phase 6)
while this tool stays fully testable without Qt threads.
"""

from typing import Callable, List

import numpy as np

from pps.core.analysis import compute_area_m2
from pps.core.layers import SourceRef
from pps.render.picking import points_in_polygon, project_to_screen
from pps.scene.commands import AddMeasurementCommand
from pps.scene.measurements import AreaMeasurement
from pps.tools.region_select import Point2D, RegionMode, RegionSelectTool

AreaRequester = Callable[[np.ndarray, Callable[[float], None]], None]


def _synchronous_area_requester(points: np.ndarray, on_done: Callable[[float], None]) -> None:
    on_done(compute_area_m2(points))


class MeasureAreaTool(RegionSelectTool):
    id = "measure_area"
    label = "Measure Area"
    shortcut = "A"
    cursor = "cross"

    def __init__(self, area_requester: AreaRequester = None):
        super().__init__()
        self.area_requester = area_requester or _synchronous_area_requester

    def status_hint(self) -> str:
        names = {
            RegionMode.POLYGON: "Polygon",
            RegionMode.RECTANGLE: "Rectangle",
            RegionMode.LASSO: "Lasso",
        }
        return f"{names[self.mode]} area measurement  |  Esc: cancel"

    def _apply(self, screen_polygon: List[Point2D], shift: bool, ctrl: bool) -> None:
        document = self.ctx.document

        sources = []
        points_parts = []
        for layer in document.layer_manager.visible_layers():
            points_2d = project_to_screen(layer.points, self.ctx.viewport.plotter)
            if points_2d is None:
                continue
            mask = points_in_polygon(points_2d, screen_polygon)
            if not mask.any():
                continue
            indices = np.where(mask)[0].astype(np.uint32)
            sources.append(SourceRef(layer_id=layer.id, indices=indices))
            points_parts.append(layer.points[indices])

        self._reset()

        if not points_parts:
            self.ctx.set_status("No points inside the drawn area.")
            return

        all_points = np.concatenate(points_parts)
        centroid = tuple(float(v) for v in all_points.mean(axis=0))

        measurement = AreaMeasurement(
            boundary_px_at_creation=list(screen_polygon),
            sources=sources,
            centroid=centroid,
            area_m2=None,
        )
        self.ctx.undo_stack.push(AddMeasurementCommand(document, measurement))
        self.ctx.set_status("Calculating area…")

        measurement_id = measurement.id

        def on_done(area_m2: float) -> None:
            # Not wrapped in a command: this fulfills a pending calculation
            # for a measurement that already exists, it isn't a new
            # user-undoable action, and undo shouldn't revert area back to
            # "unknown".
            document._update_measurement(measurement_id, area_m2=area_m2)

        self.area_requester(all_points, on_done)
