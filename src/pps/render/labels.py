"""
AnchoredLabel: a text label anchored to a 3D point on the cloud, with a
screen-space offset the user can drag, and a leader line connecting the
anchor to the label. Shared by the Note and Measure tools (Phase 4/5) —
this is what makes annotations/measurements follow the cloud when the
camera rotates/zooms/pans, unlike the old pixel-anchored system.
"""

from typing import Optional, Tuple

import numpy as np
import vtk

from pps.render.picking import project_to_screen

RGB = Tuple[float, float, float]


def hex_to_rgb(color: str) -> RGB:
    color = color.lstrip("#")
    return tuple(int(color[i : i + 2], 16) / 255.0 for i in (0, 2, 4))


class AnchoredLabel:
    """Owns 3 actors: a small 3D marker at the anchor, a 3D billboard text
    (screen-facing, offset in pixels from the anchor), and a 2D leader line
    on the overlay renderer connecting the two. The leader is recomputed
    before every render via a StartEvent observer, so it tracks the camera
    during interactive rotate/zoom/pan without any extra wiring."""

    def __init__(
        self,
        plotter,
        overlay,
        anchor: Tuple[float, float, float],
        text: str,
        offset_px: Tuple[int, int] = (40, 40),
        color: str = "#ffd166",
        font_size: int = 14,
        line_width: int = 2,
        marker_radius: float = 1.0,
    ):
        self._plotter = plotter
        self._overlay = overlay
        self.anchor = tuple(anchor)
        self.offset_px = (int(offset_px[0]), int(offset_px[1]))
        self.text = text
        self.font_size = font_size

        self._marker_actor = self._build_marker(marker_radius, color)
        plotter.renderer.AddActor(self._marker_actor)

        self._text_actor = vtk.vtkBillboardTextActor3D()
        self._text_actor.SetPosition(*self.anchor)
        self._text_actor.SetInput(text)
        self._text_actor.SetDisplayOffset(*self.offset_px)
        prop = self._text_actor.GetTextProperty()
        prop.SetFontSize(font_size)
        prop.SetBold(True)
        prop.SetBackgroundColor(0.1, 0.1, 0.1)
        prop.SetBackgroundOpacity(0.65)
        self._apply_text_color(color)
        plotter.renderer.AddActor(self._text_actor)

        self._leader_mapper = vtk.vtkPolyDataMapper2D()
        self._leader_actor = vtk.vtkActor2D()
        self._leader_actor.SetMapper(self._leader_mapper)
        self._leader_actor.GetProperty().SetLineWidth(line_width)
        self._apply_leader_color(color)
        overlay.renderer.AddActor(self._leader_actor)

        self._obs_tag = plotter.ren_win.AddObserver("StartEvent", lambda *_: self.update_leader())
        self.update_leader()

    # ------------------------------------------------------------------ mutation
    def set_text(self, text: str) -> None:
        self.text = text
        self._text_actor.SetInput(text)

    def set_offset(self, offset_px: Tuple[int, int]) -> None:
        self.offset_px = (int(offset_px[0]), int(offset_px[1]))
        self._text_actor.SetDisplayOffset(*self.offset_px)
        self.update_leader()

    def set_color(self, color: str) -> None:
        self._apply_text_color(color)
        self._apply_leader_color(color)
        self._marker_actor.GetProperty().SetColor(*hex_to_rgb(color))

    def set_font_size(self, font_size: int) -> None:
        self.font_size = font_size
        self._text_actor.GetTextProperty().SetFontSize(font_size)

    def set_visible(self, visible: bool) -> None:
        self._marker_actor.SetVisibility(visible)
        self._text_actor.SetVisibility(visible)
        self._leader_actor.SetVisibility(visible)

    # ------------------------------------------------------------------ query / hit-testing
    def anchor_screen_pos(self) -> Optional[Tuple[float, float]]:
        projected = project_to_screen(np.array([self.anchor]), self._plotter)
        if projected is None:
            return None
        return float(projected[0, 0]), float(projected[0, 1])

    def label_screen_bbox(self) -> Optional[Tuple[float, float, float, float]]:
        """Rough (x0, y0, x1, y1) screen bounding box of the label text, for
        hit-testing clicks/drags. Width is estimated from character count
        since VTK doesn't expose real glyph metrics without a live render."""
        anchor_pos = self.anchor_screen_pos()
        if anchor_pos is None:
            return None
        ax, ay = anchor_pos
        lx, ly = ax + self.offset_px[0], ay + self.offset_px[1]
        width = max(len(self.text), 1) * self.font_size * 0.62
        height = self.font_size * 1.5
        return (lx - 4, ly - 4, lx + width, ly + height)

    def contains_screen_point(self, x: float, y: float) -> bool:
        bbox = self.label_screen_bbox()
        if bbox is None:
            return False
        x0, y0, x1, y1 = bbox
        return x0 <= x <= x1 and y0 <= y <= y1

    # ------------------------------------------------------------------ leader line
    def update_leader(self) -> None:
        anchor_pos = self.anchor_screen_pos()
        if anchor_pos is None:
            return
        ax, ay = anchor_pos
        lx, ly = ax + self.offset_px[0], ay + self.offset_px[1]

        points = vtk.vtkPoints()
        points.InsertNextPoint(ax, ay, 0.0)
        points.InsertNextPoint(lx, ly, 0.0)
        line = vtk.vtkLine()
        line.GetPointIds().SetId(0, 0)
        line.GetPointIds().SetId(1, 1)
        cells = vtk.vtkCellArray()
        cells.InsertNextCell(line)
        poly = vtk.vtkPolyData()
        poly.SetPoints(points)
        poly.SetLines(cells)
        self._leader_mapper.SetInputData(poly)

    # ------------------------------------------------------------------ lifecycle
    def remove(self) -> None:
        try:
            self._plotter.ren_win.RemoveObserver(self._obs_tag)
        except Exception:
            pass
        for actor, renderer in (
            (self._marker_actor, self._plotter.renderer),
            (self._text_actor, self._plotter.renderer),
            (self._leader_actor, self._overlay.renderer),
        ):
            try:
                renderer.RemoveActor(actor)
            except Exception:
                pass

    # ------------------------------------------------------------------ construction helpers
    def _build_marker(self, radius: float, color: str) -> vtk.vtkActor:
        sphere = vtk.vtkSphereSource()
        sphere.SetRadius(radius)
        sphere.SetCenter(*self.anchor)
        sphere.SetThetaResolution(12)
        sphere.SetPhiResolution(12)
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(sphere.GetOutputPort())
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(*hex_to_rgb(color))
        return actor

    def _apply_text_color(self, color: str) -> None:
        self._text_actor.GetTextProperty().SetColor(*hex_to_rgb(color))

    def _apply_leader_color(self, color: str) -> None:
        self._leader_actor.GetProperty().SetColor(*hex_to_rgb(color))
