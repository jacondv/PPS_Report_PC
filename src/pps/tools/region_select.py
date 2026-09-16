"""
RegionSelectTool: polygon / rectangle / lasso selection on the visible
layers, replacing the old VTKPolygonPicker + core/segmentation.py.

Selection mode at the moment a shape is closed: Shift = Add, Ctrl =
Subtract, neither = Replace — mirrors CloudCompare-style modifier use.
"""

from enum import Enum
from typing import List, Tuple

from pps.render.actors2d import points_actor, polyline_actor
from pps.render.picking import points_in_polygon, project_to_screen, rectangle_to_polygon
from pps.tools.base import MouseButton, PointerEvent, PointerEventType, Tool

Point2D = Tuple[float, float]


class RegionMode(Enum):
    POLYGON = "polygon"
    RECTANGLE = "rectangle"
    LASSO = "lasso"


class RegionSelectTool(Tool):
    id = "region_select"
    label = "Select Region"
    shortcut = "S"
    cursor = "cross"

    def __init__(self):
        super().__init__()
        self.mode = RegionMode.POLYGON
        self._points: List[Point2D] = []
        self._dragging = False

    def set_mode(self, mode: RegionMode) -> None:
        self.cancel()
        self.mode = mode

    def on_activate(self) -> None:
        self._reset()

    def on_deactivate(self) -> None:
        self._reset()

    def cancel(self) -> None:
        self._reset()

    def is_idle(self) -> bool:
        return not self._points and not self._dragging

    def status_hint(self) -> str:
        names = {
            RegionMode.POLYGON: "Polygon",
            RegionMode.RECTANGLE: "Rectangle",
            RegionMode.LASSO: "Lasso",
        }
        return (
            f"{names[self.mode]} select — Shift: add, Ctrl: subtract  |  "
            "Esc: cancel"
        )

    # ------------------------------------------------------------------ event routing
    def handle_pointer(self, event: PointerEvent) -> bool:
        if self.mode == RegionMode.POLYGON:
            return self._handle_polygon(event)
        if self.mode == RegionMode.RECTANGLE:
            return self._handle_drag(event, closed_shape=False)
        return self._handle_drag(event, closed_shape=True)

    def handle_key(self, event) -> bool:
        if self.mode != RegionMode.POLYGON:
            return False
        if event.key == "Return" and len(self._points) >= 3:
            self._apply(self._points, event.shift, event.ctrl)
            return True
        if event.key == "BackSpace" and self._points:
            self._points.pop()
            self._redraw_polygon()
            return True
        return False

    # ------------------------------------------------------------------ polygon mode
    def _handle_polygon(self, event: PointerEvent) -> bool:
        if event.kind == PointerEventType.PRESS and event.button == MouseButton.LEFT:
            self._points.append((event.x, event.y))
            self._redraw_polygon()
            return True

        if event.kind == PointerEventType.DOUBLE_CLICK and event.button == MouseButton.LEFT:
            if len(self._points) >= 3:
                self._apply(self._points, event.shift, event.ctrl)
            return True

        if event.kind == PointerEventType.PRESS and event.button == MouseButton.RIGHT:
            if len(self._points) >= 3:
                self._apply(self._points, event.shift, event.ctrl)
            else:
                self._reset()
            return True

        if event.kind == PointerEventType.MOVE and self._points:
            self._redraw_polygon(preview_point=(event.x, event.y))
            return True

        return False

    def _redraw_polygon(self, preview_point: Point2D = None) -> None:
        self.scratch.clear()
        n = len(self._points)

        if n >= 2:
            self.scratch.add(
                polyline_actor(self._points, closed=False, rgb=(1.0, 0.55, 0.05), line_width=2.5)
            )
        if n >= 1:
            self.scratch.add(
                points_actor(self._points, rgb=(1.0, 0.25, 0.0), point_size=9)
            )
        if preview_point is not None and n >= 1:
            preview_coords = [self._points[-1], preview_point]
            if n >= 2:
                preview_coords.append(self._points[0])
            self.scratch.add(
                polyline_actor(
                    preview_coords, closed=False, rgb=(1.0, 0.85, 0.2),
                    line_width=1.5, opacity=0.6, stipple=0xF0F0,
                )
            )

        hint = (
            f"Left-click: add point [{n}]  |  Esc: cancel"
            if n < 3
            else f"Double-click/Enter/Right-click: apply [{n} pts]  |  Backspace: undo  |  Esc: cancel"
        )
        self.ctx.overlay.set_hud_text(hint)
        self.ctx.request_render()

    # ------------------------------------------------------------------ rectangle / lasso (drag) modes
    def _handle_drag(self, event: PointerEvent, closed_shape: bool) -> bool:
        if event.kind == PointerEventType.PRESS and event.button == MouseButton.LEFT:
            self._points = [(event.x, event.y)]
            self._dragging = True
            return True

        if event.kind == PointerEventType.MOVE and self._dragging:
            if closed_shape:
                self._points.append((event.x, event.y))
            else:
                self._points = [self._points[0], (event.x, event.y)]
            self._redraw_drag(closed_shape)
            return True

        if event.kind == PointerEventType.RELEASE and event.button == MouseButton.LEFT and self._dragging:
            self._dragging = False
            polygon = (
                self._points if closed_shape else rectangle_to_polygon(self._points[0], self._points[-1])
            )
            if len(self._points) >= 2 and _bbox_size(polygon) > 3:
                self._apply(polygon, event.shift, event.ctrl)
            else:
                self._reset()
            return True

        return False

    def _redraw_drag(self, closed_shape: bool) -> None:
        self.scratch.clear()
        coords = self._points if closed_shape else rectangle_to_polygon(self._points[0], self._points[-1])
        if len(coords) >= 2:
            self.scratch.add(
                polyline_actor(coords, closed=True, rgb=(1.0, 0.55, 0.05), line_width=2.0, opacity=0.85)
            )
        self.ctx.overlay.set_hud_text("Release to apply  |  Esc: cancel")
        self.ctx.request_render()

    # ------------------------------------------------------------------ apply / reset
    def _apply(self, screen_polygon: List[Point2D], shift: bool, ctrl: bool) -> None:
        document = self.ctx.document
        mode = "add" if shift else ("subtract" if ctrl else "replace")

        masks = {}
        for layer in document.layer_manager.visible_layers():
            points_2d = project_to_screen(layer.points, self.ctx.viewport.plotter)
            if points_2d is None:
                continue
            masks[layer.id] = points_in_polygon(points_2d, screen_polygon)

        document.selection.apply(masks, mode)
        document.selection_changed.emit()
        self._reset()

    def _reset(self) -> None:
        self._points = []
        self._dragging = False
        if self.scratch is not None:
            self.scratch.clear()
        if self.ctx is not None:
            self.ctx.overlay.set_hud_text("")
            self.ctx.request_render()


def _bbox_size(polygon: List[Point2D]) -> float:
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return max(max(xs) - min(xs), max(ys) - min(ys))
