"""
Compact 3-band thickness classification color legend (< target_min /
within / > target_max), drawn on the overlay render layer so it's always
visible on top of the point cloud regardless of camera — and, since the
PDF report screenshot captures both render layers composited together,
the legend is automatically included in the exported report too.

Deliberately minimal: no title, no "mm" unit text — just the three colors
(matching LayerRenderer's classification colors) and the two boundary
numbers, anchored to the viewport's right edge in normalized viewport
coordinates so it stays put across window resizes without recomputing.
"""

import vtk

from pps.render.actors2d import vtk_points_2d

_BAR_WIDTH = 0.028
_BAR_HEIGHT = 0.32
_BAR_RIGHT_MARGIN = 0.025
_BAR_BOTTOM = 0.34
_LABEL_FONT_SIZE = 13
_LABEL_GAP = 0.008


def _quad_actor() -> tuple:
    points = vtk_points_2d([(0, 0), (0, 0), (0, 0), (0, 0)])
    quad = vtk.vtkCellArray()
    quad.InsertNextCell(4)
    for i in range(4):
        quad.InsertCellPoint(i)
    poly = vtk.vtkPolyData()
    poly.SetPoints(points)
    poly.SetPolys(quad)

    coord = vtk.vtkCoordinate()
    coord.SetCoordinateSystemToNormalizedViewport()

    mapper = vtk.vtkPolyDataMapper2D()
    mapper.SetInputData(poly)
    mapper.SetTransformCoordinate(coord)

    actor = vtk.vtkActor2D()
    actor.SetMapper(mapper)
    return actor, points


def _label_actor() -> vtk.vtkTextActor:
    actor = vtk.vtkTextActor()
    prop = actor.GetTextProperty()
    prop.SetFontSize(_LABEL_FONT_SIZE)
    prop.SetColor(1.0, 1.0, 1.0)
    prop.SetJustificationToRight()
    prop.SetVerticalJustificationToCentered()
    prop.BoldOff()
    prop.ShadowOn()
    actor.GetPositionCoordinate().SetCoordinateSystemToNormalizedViewport()
    return actor


def _format_mm(value: float) -> str:
    return f"{int(value)}" if float(value).is_integer() else f"{value:g}"


class ColorLegend:
    """Owns its own actors on the overlay renderer; call update() whenever
    targets or classification colors change, set_visible() to show/hide
    (e.g. no cloud loaded)."""

    def __init__(self, overlay_renderer):
        self._renderer = overlay_renderer
        self._bands = [_quad_actor() for _ in range(3)]  # bottom -> top
        for actor, _points in self._bands:
            self._renderer.AddActor(actor)

        self._label_min = _label_actor()
        self._label_max = _label_actor()
        self._renderer.AddActor(self._label_min)
        self._renderer.AddActor(self._label_max)

    def update(self, color_below, color_within, color_above, target_min: float, target_max: float) -> None:
        x1 = 1.0 - _BAR_RIGHT_MARGIN - _BAR_WIDTH
        x2 = 1.0 - _BAR_RIGHT_MARGIN
        band_h = _BAR_HEIGHT / 3.0
        y0 = _BAR_BOTTOM

        colors = (color_below, color_within, color_above)
        for i, ((actor, points), color) in enumerate(zip(self._bands, colors)):
            y1, y2 = y0 + i * band_h, y0 + (i + 1) * band_h
            for j, (x, y) in enumerate([(x1, y1), (x2, y1), (x2, y2), (x1, y2)]):
                points.SetPoint(j, x, y, 0.0)
            points.Modified()
            actor.GetProperty().SetColor(*color)

        label_x = x1 - _LABEL_GAP
        self._label_min.SetInput(_format_mm(target_min))
        self._label_min.GetPositionCoordinate().SetValue(label_x, y0 + band_h)
        self._label_max.SetInput(_format_mm(target_max))
        self._label_max.GetPositionCoordinate().SetValue(label_x, y0 + 2 * band_h)

    def set_visible(self, visible: bool) -> None:
        for actor, _points in self._bands:
            actor.SetVisibility(visible)
        self._label_min.SetVisibility(visible)
        self._label_max.SetVisibility(visible)
