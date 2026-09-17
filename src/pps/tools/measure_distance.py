"""
MeasureDistanceTool: click two points on the cloud (snapped to the nearest
visible vertex) to create a DistanceMeasurement anchored in 3D.
"""

from typing import List, Optional, Tuple

import numpy as np

from pps.render.actors2d import polyline_actor
from pps.render.picking import pick_nearest_point_3d, project_to_screen
from pps.scene.commands import AddMeasurementCommand
from pps.scene.measurements import DistanceMeasurement
from pps.tools.base import MouseButton, PointerEvent, PointerEventType, Tool

Point3D = Tuple[float, float, float]


class MeasureDistanceTool(Tool):
    id = "measure_distance"
    label = "Measure Distance"
    shortcut = "D"
    cursor = "cross"

    def __init__(self):
        super().__init__()
        self._first_point: Optional[Point3D] = None

    def on_activate(self) -> None:
        self._first_point = None

    def on_deactivate(self) -> None:
        self._first_point = None

    def cancel(self) -> None:
        self._first_point = None
        if self.scratch is not None:
            self.scratch.clear()
        if self.ctx is not None:
            self.ctx.overlay.set_hud_text("")
            self.ctx.request_render()

    def is_idle(self) -> bool:
        return self._first_point is None

    def status_hint(self) -> str:
        if self._first_point is None:
            return "Click a point on the cloud to start measuring  |  Esc: cancel"
        return "Click a second point to finish  |  Esc: cancel"

    def handle_pointer(self, event: PointerEvent) -> bool:
        if event.kind == PointerEventType.PRESS and event.button == MouseButton.LEFT:
            picked = pick_nearest_point_3d(event.x, event.y, self.ctx.viewport.plotter)
            if picked is None:
                return True

            if self._first_point is None:
                self._first_point = picked
            else:
                self._finish(self._first_point, picked)
                return True

            self.ctx.set_status(self.status_hint())
            self._draw_preview(self._first_point)
            return True

        if event.kind == PointerEventType.MOVE and self._first_point is not None:
            picked = pick_nearest_point_3d(event.x, event.y, self.ctx.viewport.plotter)
            self._draw_preview(self._first_point, picked)
            return True

        return False

    def _draw_preview(self, p1: Point3D, p2: Optional[Point3D] = None) -> None:
        self.scratch.clear()
        end = p2 if p2 is not None else p1
        screen = project_to_screen(np.array([p1, end]), self.ctx.viewport.plotter)
        if screen is not None:
            self.scratch.add(
                polyline_actor(
                    [tuple(screen[0]), tuple(screen[1])],
                    closed=False,
                    rgb=(0.3, 0.85, 1.0),
                    line_width=2.0,
                    opacity=0.8,
                    stipple=0xF0F0,
                )
            )
        if p2 is not None:
            distance = float(np.linalg.norm(np.asarray(p2) - np.asarray(p1)))
            self.ctx.overlay.set_hud_text(f"Distance: {distance:.3f} m")
        self.ctx.request_render()

    def _finish(self, p1: Point3D, p2: Point3D) -> None:
        layer_id = self.ctx.document.layer_manager.nearest_layer_id(p1)
        measurement = DistanceMeasurement(p1=tuple(p1), p2=tuple(p2), layer_id=layer_id)
        self.ctx.undo_stack.push(AddMeasurementCommand(self.ctx.document, measurement))

        self._first_point = None
        self.scratch.clear()
        self.ctx.overlay.set_hud_text("")
        self.ctx.set_status(self.status_hint())
        self.ctx.request_render()
