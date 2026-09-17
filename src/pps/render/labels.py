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

# Extra pixels added on every side of an estimated text bbox for hit-testing
# (selecting/dragging/double-clicking to edit). The estimate itself is only
# approximate (no real glyph metrics without a live render), and text is a
# thin target to begin with, so a generous margin makes it practical to
# actually grab a note/annotation instead of missing it by a few pixels.
_HIT_MARGIN_PX = 10

# Text background used to flag the currently-selected note/annotation/
# measurement (e.g. selected in the Project dock's tree) versus the default
# dark translucent backing plate every label otherwise uses.
_HIGHLIGHT_BG = (1.0, 0.65, 0.0)
_HIGHLIGHT_OPACITY = 0.9
_DEFAULT_BG = (0.1, 0.1, 0.1)
_DEFAULT_OPACITY = 0.65


def hex_to_rgb(color: str) -> RGB:
    color = color.lstrip("#")
    return tuple(int(color[i : i + 2], 16) / 255.0 for i in (0, 2, 4))


def default_marker_radius(plotter, fraction: float = 0.004) -> float:
    """A marker sphere radius scaled to the visible scene, instead of a
    fixed absolute size — a fixed radius looks fine on a 10 m tunnel scan
    and comically huge (or invisible) on data at a different scale."""
    try:
        bounds = plotter.renderer.ComputeVisiblePropBounds()
        diagonal = (
            (bounds[1] - bounds[0]) ** 2
            + (bounds[3] - bounds[2]) ** 2
            + (bounds[5] - bounds[4]) ** 2
        ) ** 0.5
    except Exception:
        diagonal = 0.0
    return diagonal * fraction if diagonal > 0 else 0.05


def compute_label_bbox(
    anchor: Tuple[float, float, float],
    offset_px: Tuple[int, int],
    text: str,
    font_size: int,
    plotter,
) -> Optional[Tuple[float, float, float, float]]:
    """Rough (x0, y0, x1, y1) screen bounding box of a label's text, for
    hit-testing clicks/drags without needing a live AnchoredLabel/actor —
    just the raw anchor/offset/text data (e.g. straight from a
    NoteAnnotation). Width is estimated from character count since VTK
    doesn't expose real glyph metrics without a live render."""
    projected = project_to_screen(np.array([anchor]), plotter)
    if projected is None:
        return None
    ax, ay = float(projected[0, 0]), float(projected[0, 1])
    lx, ly = ax + offset_px[0], ay + offset_px[1]
    width = max(len(text), 1) * font_size * 0.62
    height = font_size * 1.5
    m = _HIT_MARGIN_PX
    return (lx - 4 - m, ly - 4 - m, lx + width + m, ly + height + m)


def compute_screen_note_bbox(
    pos_frac: Tuple[float, float], text: str, font_size: int, viewport_size: Tuple[int, int]
) -> Tuple[float, float, float, float]:
    """Rough (x0, y0, x1, y1) screen bounding box of a screen-space note's
    text, for hit-testing without needing a live ScreenLabel/actor — same
    idea as compute_label_bbox but for notes with no 3D anchor."""
    width, height = viewport_size
    x, y = pos_frac[0] * width, pos_frac[1] * height
    text_width = max(len(text), 1) * font_size * 0.62
    text_height = font_size * 1.5
    m = _HIT_MARGIN_PX
    return (x - 4 - m, y - 4 - m, x + text_width + m, y + text_height + m)


class ScreenLabel:
    """Plain 2D text drawn directly on the overlay layer at a normalized
    viewport position — no 3D anchor, no leader line, nothing tying it to
    the cloud. Used by the Note tool (free-floating text anywhere in the
    view), as opposed to AnchoredLabel (used by the Annotation tool, tied
    to a 3D point). `pos_frac` is (0..1, 0..1) in VTK's normalized-viewport
    convention (origin bottom-left), matching Tool pointer-event coordinates
    directly so no conversion is needed when placing/dragging one.
    """

    def __init__(
        self,
        overlay,
        pos_frac: Tuple[float, float],
        text: str,
        color: str = "#ffd166",
        font_size: int = 14,
    ):
        self._overlay = overlay
        self.pos_frac = (float(pos_frac[0]), float(pos_frac[1]))
        self.text = text
        self.font_size = font_size

        self._text_actor = vtk.vtkTextActor()
        self._text_actor.SetInput(text)
        prop = self._text_actor.GetTextProperty()
        prop.SetFontSize(font_size)
        prop.SetBold(True)
        prop.SetBackgroundColor(*_DEFAULT_BG)
        prop.SetBackgroundOpacity(_DEFAULT_OPACITY)
        self._apply_text_color(color)
        self._text_actor.GetPositionCoordinate().SetCoordinateSystemToNormalizedViewport()
        self._text_actor.GetPositionCoordinate().SetValue(*self.pos_frac)
        overlay.renderer.AddActor(self._text_actor)

    # ------------------------------------------------------------------ mutation
    def set_text(self, text: str) -> None:
        self.text = text
        self._text_actor.SetInput(text)

    def set_pos_frac(self, pos_frac: Tuple[float, float]) -> None:
        self.pos_frac = (float(pos_frac[0]), float(pos_frac[1]))
        self._text_actor.GetPositionCoordinate().SetValue(*self.pos_frac)

    def set_color(self, color: str) -> None:
        self._apply_text_color(color)

    def set_highlighted(self, highlighted: bool) -> None:
        prop = self._text_actor.GetTextProperty()
        if highlighted:
            prop.SetBackgroundColor(*_HIGHLIGHT_BG)
            prop.SetBackgroundOpacity(_HIGHLIGHT_OPACITY)
        else:
            prop.SetBackgroundColor(*_DEFAULT_BG)
            prop.SetBackgroundOpacity(_DEFAULT_OPACITY)

    def set_font_size(self, font_size: int) -> None:
        self.font_size = font_size
        self._text_actor.GetTextProperty().SetFontSize(font_size)

    def set_visible(self, visible: bool) -> None:
        self._text_actor.SetVisibility(visible)

    # ------------------------------------------------------------------ query / hit-testing
    def screen_pos(self, viewport_size: Tuple[int, int]) -> Tuple[float, float]:
        width, height = viewport_size
        return self.pos_frac[0] * width, self.pos_frac[1] * height

    def screen_bbox(self, viewport_size: Tuple[int, int]) -> Tuple[float, float, float, float]:
        return compute_screen_note_bbox(self.pos_frac, self.text, self.font_size, viewport_size)

    def contains_screen_point(self, x: float, y: float, viewport_size: Tuple[int, int]) -> bool:
        x0, y0, x1, y1 = self.screen_bbox(viewport_size)
        return x0 <= x <= x1 and y0 <= y <= y1

    # ------------------------------------------------------------------ lifecycle
    def remove(self) -> None:
        try:
            self._overlay.renderer.RemoveActor(self._text_actor)
        except Exception:
            pass

    def _apply_text_color(self, color: str) -> None:
        self._text_actor.GetTextProperty().SetColor(*hex_to_rgb(color))


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
        marker_radius: Optional[float] = None,
    ):
        self._plotter = plotter
        self._overlay = overlay
        self.anchor = tuple(anchor)
        self.offset_px = (int(offset_px[0]), int(offset_px[1]))
        self.text = text
        self.font_size = font_size

        if marker_radius is None:
            marker_radius = default_marker_radius(plotter)
        self._marker_actor = self._build_marker(marker_radius, color)
        plotter.renderer.AddActor(self._marker_actor)

        self._text_actor = vtk.vtkBillboardTextActor3D()
        self._text_actor.SetPosition(*self.anchor)
        self._text_actor.SetInput(text)
        self._text_actor.SetDisplayOffset(*self.offset_px)
        prop = self._text_actor.GetTextProperty()
        prop.SetFontSize(font_size)
        prop.SetBold(True)
        prop.SetBackgroundColor(*_DEFAULT_BG)
        prop.SetBackgroundOpacity(_DEFAULT_OPACITY)
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

    def set_highlighted(self, highlighted: bool) -> None:
        prop = self._text_actor.GetTextProperty()
        if highlighted:
            prop.SetBackgroundColor(*_HIGHLIGHT_BG)
            prop.SetBackgroundOpacity(_HIGHLIGHT_OPACITY)
        else:
            prop.SetBackgroundColor(*_DEFAULT_BG)
            prop.SetBackgroundOpacity(_DEFAULT_OPACITY)

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
        return compute_label_bbox(self.anchor, self.offset_px, self.text, self.font_size, self._plotter)

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
