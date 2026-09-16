"""Small VTK 2D actor builders shared by tools that draw screen-space
previews on the overlay renderer (polygon/rectangle/lasso selection,
measurement preview lines, ...)."""

from typing import List, Tuple

import vtk

Point2D = Tuple[float, float]


def vtk_points_2d(coords: List[Point2D]) -> vtk.vtkPoints:
    pts = vtk.vtkPoints()
    for x, y in coords:
        pts.InsertNextPoint(float(x), float(y), 0.0)
    return pts


def actor2d(poly, rgb, line_width=None, point_size=None, opacity=1.0, stipple=None) -> vtk.vtkActor2D:
    mapper = vtk.vtkPolyDataMapper2D()
    mapper.SetInputData(poly)
    actor = vtk.vtkActor2D()
    actor.SetMapper(mapper)
    prop = actor.GetProperty()
    prop.SetColor(*rgb)
    prop.SetOpacity(opacity)
    if line_width is not None:
        prop.SetLineWidth(line_width)
    if point_size is not None:
        prop.SetPointSize(point_size)
    if stipple is not None:
        prop.SetLineStipplePattern(stipple)
    return actor


def polyline_actor(coords: List[Point2D], closed: bool, **style) -> vtk.vtkActor2D:
    n = len(coords)
    pts = vtk_points_2d(coords)
    lines = vtk.vtkCellArray()
    limit = n if closed else n - 1
    for i in range(limit):
        line = vtk.vtkLine()
        line.GetPointIds().SetId(0, i)
        line.GetPointIds().SetId(1, (i + 1) % n)
        lines.InsertNextCell(line)
    poly = vtk.vtkPolyData()
    poly.SetPoints(pts)
    poly.SetLines(lines)
    return actor2d(poly, **style)


def points_actor(coords: List[Point2D], **style) -> vtk.vtkActor2D:
    pts = vtk_points_2d(coords)
    verts = vtk.vtkCellArray()
    for i in range(len(coords)):
        verts.InsertNextCell(1)
        verts.InsertCellPoint(i)
    poly = vtk.vtkPolyData()
    poly.SetPoints(pts)
    poly.SetVerts(verts)
    return actor2d(poly, **style)
