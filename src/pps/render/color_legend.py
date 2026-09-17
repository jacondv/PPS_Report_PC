"""
Compact 3-band thickness classification color legend (< target_min /
within / > target_max), drawn on the overlay render layer so it's always
visible on top of the point cloud regardless of camera — and, since the
PDF report screenshot captures both render layers composited together,
the legend is automatically included in the exported report too.

Deliberately minimal: no title text — just the three colors (matching
LayerRenderer's classification colors), a thin border, tick marks at the
two boundaries, and the boundary values in mm. Anchored to the viewport's
right edge in normalized viewport coordinates so it stays put across
window resizes without recomputing.
"""

import vtk

from pps.render.actors2d import vtk_points_2d

_BAR_WIDTH = 0.028
_BAR_HEIGHT = 0.32
_BAR_RIGHT_MARGIN = 0.025
_BAR_BOTTOM = 0.34
_TICK_LENGTH = 0.012
_LABEL_FONT_SIZE = 14
_LABEL_GAP = 0.006
_BORDER_COLOR = (0.85, 0.85, 0.85)  # light: reads well against the default dark 3D background
_BORDER_WIDTH = 1.5


def _normalized_viewport_coord() -> vtk.vtkCoordinate:
    coord = vtk.vtkCoordinate()
    coord.SetCoordinateSystemToNormalizedViewport()
    return coord


def _quad_actor() -> tuple:
    points = vtk_points_2d([(0, 0)] * 4)
    quad = vtk.vtkCellArray()
    quad.InsertNextCell(4)
    for i in range(4):
        quad.InsertCellPoint(i)
    poly = vtk.vtkPolyData()
    poly.SetPoints(points)
    poly.SetPolys(quad)

    mapper = vtk.vtkPolyDataMapper2D()
    mapper.SetInputData(poly)
    mapper.SetTransformCoordinate(_normalized_viewport_coord())

    actor = vtk.vtkActor2D()
    actor.SetMapper(mapper)
    return actor, points


def _line_actor(n_points: int, closed: bool = False) -> tuple:
    """An open or closed polyline in normalized-viewport space, used for
    the border outline and tick marks — solid, thin, dark, professional."""
    points = vtk_points_2d([(0, 0)] * n_points)
    lines = vtk.vtkCellArray()
    limit = n_points if closed else n_points - 1
    for i in range(limit):
        line = vtk.vtkLine()
        line.GetPointIds().SetId(0, i)
        line.GetPointIds().SetId(1, (i + 1) % n_points)
        lines.InsertNextCell(line)
    poly = vtk.vtkPolyData()
    poly.SetPoints(points)
    poly.SetLines(lines)

    mapper = vtk.vtkPolyDataMapper2D()
    mapper.SetInputData(poly)
    mapper.SetTransformCoordinate(_normalized_viewport_coord())

    actor = vtk.vtkActor2D()
    actor.SetMapper(mapper)
    prop = actor.GetProperty()
    prop.SetColor(*_BORDER_COLOR)
    prop.SetLineWidth(_BORDER_WIDTH)
    return actor, points


def _label_actor() -> vtk.vtkTextActor:
    """Black, bold text on a translucent white backing plate so it stays
    legible over any 3D-view background color the user picks."""
    actor = vtk.vtkTextActor()
    prop = actor.GetTextProperty()
    prop.SetFontSize(_LABEL_FONT_SIZE)
    prop.SetColor(0.0, 0.0, 0.0)
    prop.BoldOn()
    prop.ShadowOff()
    prop.SetJustificationToRight()
    prop.SetVerticalJustificationToCentered()
    prop.SetBackgroundColor(1.0, 1.0, 1.0)
    prop.SetBackgroundOpacity(0.75)
    actor.GetPositionCoordinate().SetCoordinateSystemToNormalizedViewport()
    return actor


def _format_mm(value: float) -> str:
    number = f"{int(value)}" if float(value).is_integer() else f"{value:g}"
    return f"{number} mm"


class ColorLegend:
    """Owns its own actors on the overlay renderer; call update() whenever
    targets or classification colors change, set_visible() to show/hide
    (e.g. no cloud loaded)."""

    def __init__(self, overlay_renderer):
        self._renderer = overlay_renderer
        self._bands = [_quad_actor() for _ in range(3)]  # bottom -> top
        for actor, _points in self._bands:
            self._renderer.AddActor(actor)

        self._border = _line_actor(4, closed=True)
        self._renderer.AddActor(self._border[0])

        self._tick_min = _line_actor(2)
        self._tick_max = _line_actor(2)
        self._renderer.AddActor(self._tick_min[0])
        self._renderer.AddActor(self._tick_max[0])

        self._label_min = _label_actor()
        self._label_max = _label_actor()
        self._renderer.AddActor(self._label_min)
        self._renderer.AddActor(self._label_max)

    def update(self, color_below, color_within, color_above, target_min: float, target_max: float) -> None:
        x1 = 1.0 - _BAR_RIGHT_MARGIN - _BAR_WIDTH
        x2 = 1.0 - _BAR_RIGHT_MARGIN
        band_h = _BAR_HEIGHT / 3.0
        y0 = _BAR_BOTTOM
        y_min, y_max = y0 + band_h, y0 + 2 * band_h

        colors = (color_below, color_within, color_above)
        for i, ((actor, points), color) in enumerate(zip(self._bands, colors)):
            y1, y2 = y0 + i * band_h, y0 + (i + 1) * band_h
            for j, (x, y) in enumerate([(x1, y1), (x2, y1), (x2, y2), (x1, y2)]):
                points.SetPoint(j, x, y, 0.0)
            points.Modified()
            actor.GetProperty().SetColor(*color)

        border_points = self._border[1]
        for j, (x, y) in enumerate([(x1, y0), (x2, y0), (x2, y0 + _BAR_HEIGHT), (x1, y0 + _BAR_HEIGHT)]):
            border_points.SetPoint(j, x, y, 0.0)
        border_points.Modified()

        tick_x1 = x1 - _TICK_LENGTH
        min_points = self._tick_min[1]
        min_points.SetPoint(0, tick_x1, y_min, 0.0)
        min_points.SetPoint(1, x1, y_min, 0.0)
        min_points.Modified()
        max_points = self._tick_max[1]
        max_points.SetPoint(0, tick_x1, y_max, 0.0)
        max_points.SetPoint(1, x1, y_max, 0.0)
        max_points.Modified()

        label_x = tick_x1 - _LABEL_GAP
        self._label_min.SetInput(_format_mm(target_min))
        self._label_min.GetPositionCoordinate().SetValue(label_x, y_min)
        self._label_max.SetInput(_format_mm(target_max))
        self._label_max.GetPositionCoordinate().SetValue(label_x, y_max)

    def set_visible(self, visible: bool) -> None:
        for actor, _points in self._bands:
            actor.SetVisibility(visible)
        self._border[0].SetVisibility(visible)
        self._tick_min[0].SetVisibility(visible)
        self._tick_max[0].SetVisibility(visible)
        self._label_min.SetVisibility(visible)
        self._label_max.SetVisibility(visible)
