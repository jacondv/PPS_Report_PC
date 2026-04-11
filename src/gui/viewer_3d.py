"""
3D Point Cloud Viewer — layer-based architecture.

Polygon selection uses VTK's native 2D rendering (layer 1 overlay),
avoiding all Qt-over-OpenGL transparency issues.
All layers (original + segments) render with the same thickness colormap.
"""

import os
import sys
import time
import numpy as np
from typing import Optional, List, Dict

import vtk
import pyvista as pv
from pyvistaqt import QtInteractor

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QFrame
from PyQt5.QtCore import pyqtSignal, QObject, QTimer

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.layer_manager import Layer


# ============================================================ signals
class ViewerSignals(QObject):
    selection_changed  = pyqtSignal(object, object)  # (pts ndarray, dists ndarray)
    selection_cleared  = pyqtSignal()
    polygon_mode_ended = pyqtSignal()


# ============================================================ VTK polygon picker
class VTKPolygonPicker:
    """
    CloudCompare-style polygon selection drawn in VTK's 2D coordinate space.

    Uses a dedicated vtkRenderer on layer=1 so the polygon is always drawn
    on top of the scene without any Qt-overlay transparency problems.

    Coordinate system: VTK display coordinates, origin at BOTTOM-LEFT.
    This matches iren.GetEventPosition() directly.

    Controls
    --------
    Left click        – add vertex
    Double-click      – close & apply (≥ 3 pts)
    Right click       – close & apply (≥ 3 pts) / cancel
    Enter             – close & apply (≥ 3 pts)
    Backspace         – remove last vertex
    ESC               – cancel
    """

    def __init__(self, plotter, on_closed, on_cancelled):
        self._plotter      = plotter
        self._ren_win      = plotter.ren_win
        self._on_closed    = on_closed
        self._on_cancelled = on_cancelled

        self._pts: List     = []
        self._active        = False
        self._obs_tags      = []
        self._t_last_click  = 0.0

        # Raw VTK interactor (same underlying object pyvistaqt uses)
        self._iren = self._ren_win.GetInteractor()

        # ---- persistent 2D overlay renderer (layer 1) ----
        self._ren2d = vtk.vtkRenderer()
        self._ren2d.SetLayer(1)
        self._ren2d.InteractiveOff()
        self._ren_win.SetNumberOfLayers(2)
        self._ren_win.AddRenderer(self._ren2d)

        # actor slots
        self._a_edges = None   # committed polygon edges
        self._a_verts = None   # vertex dots
        self._a_prev  = None   # preview dashed lines to cursor
        self._a_text  = None   # instruction banner

    # ------------------------------------------------------------------ public
    @property
    def is_active(self) -> bool:
        return self._active

    def start(self):
        self._pts           = []
        self._active        = True
        self._t_last_click  = 0.0
        self._clear_actors()

        # Suspend camera interaction
        self._iren.SetInteractorStyle(vtk.vtkInteractorStyleUser())

        self._obs_tags = [
            self._iren.AddObserver('LeftButtonPressEvent',  self._on_left),
            self._iren.AddObserver('RightButtonPressEvent', self._on_right),
            self._iren.AddObserver('MouseMoveEvent',        self._on_move),
            self._iren.AddObserver('KeyPressEvent',         self._on_key),
        ]
        self._redraw()
        self._ren_win.Render()

    def stop(self):
        self._active = False
        for tag in self._obs_tags:
            try: self._iren.RemoveObserver(tag)
            except: pass
        self._obs_tags = []
        self._clear_actors()
        # Restore camera style via Qt timer (safe outside VTK callback)
        QTimer.singleShot(0, self._restore_camera)

    def _restore_camera(self):
        try:
            self._plotter.enable_rubber_band_style()
        except Exception:
            try:
                self._iren.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())
            except Exception:
                pass
        try:
            self._ren_win.Render()
        except Exception:
            pass

    # ------------------------------------------------------------------ observers
    def _on_left(self, obj, event):
        if not self._active:
            return
        x, y = self._iren.GetEventPosition()
        now   = time.time()

        # Double-click detection (same spot, <350 ms)
        is_dbl = (
            self._pts
            and now - self._t_last_click < 0.35
            and abs(x - self._pts[-1][0]) < 8
            and abs(y - self._pts[-1][1]) < 8
        )
        self._t_last_click = now

        if is_dbl:
            if len(self._pts) >= 3:
                pts = list(self._pts)
                self.stop()
                self._on_closed(pts)
            return

        self._pts.append((x, y))
        self._redraw()
        self._ren_win.Render()

    def _on_right(self, obj, event):
        if not self._active:
            return
        if len(self._pts) >= 3:
            pts = list(self._pts)
            self.stop()
            self._on_closed(pts)
        else:
            self.stop()
            self._on_cancelled()

    def _on_move(self, obj, event):
        if not self._active or not self._pts:
            return
        x, y = self._iren.GetEventPosition()
        self._draw_preview(x, y)
        self._ren_win.Render()

    def _on_key(self, obj, event):
        if not self._active:
            return
        key = self._iren.GetKeySym()
        if key == 'Escape':
            self.stop()
            self._on_cancelled()
        elif key in ('Return', 'KP_Enter') and len(self._pts) >= 3:
            pts = list(self._pts)
            self.stop()
            self._on_closed(pts)
        elif key == 'BackSpace' and self._pts:
            self._pts.pop()
            self._redraw()
            self._ren_win.Render()

    # ------------------------------------------------------------------ drawing helpers
    @staticmethod
    def _vtkpts(coords):
        p = vtk.vtkPoints()
        for x, y in coords:
            p.InsertNextPoint(float(x), float(y), 0.0)
        return p

    @staticmethod
    def _actor2d(poly, rgb, lw=None, ps=None, alpha=1.0):
        m = vtk.vtkPolyDataMapper2D()
        m.SetInputData(poly)
        a = vtk.vtkActor2D()
        a.SetMapper(m)
        pr = a.GetProperty()
        pr.SetColor(*rgb)
        pr.SetOpacity(alpha)
        if lw is not None: pr.SetLineWidth(lw)
        if ps is not None: pr.SetPointSize(ps)
        return a

    def _redraw(self):
        """Rebuild committed edges, vertex dots, and instruction text."""
        for a in (self._a_edges, self._a_verts, self._a_text):
            if a: self._ren2d.RemoveActor(a)
        self._a_edges = self._a_verts = self._a_text = None

        n = len(self._pts)

        # edges
        if n >= 2:
            pts_v = self._vtkpts(self._pts)
            lines = vtk.vtkCellArray()
            for i in range(n - 1):
                ln = vtk.vtkLine()
                ln.GetPointIds().SetId(0, i)
                ln.GetPointIds().SetId(1, i + 1)
                lines.InsertNextCell(ln)
            poly = vtk.vtkPolyData()
            poly.SetPoints(pts_v); poly.SetLines(lines)
            self._a_edges = self._actor2d(poly, (1.0, 0.55, 0.05), lw=2.5)
            self._ren2d.AddActor(self._a_edges)

        # vertex dots
        if n >= 1:
            pts_v = self._vtkpts(self._pts)
            verts = vtk.vtkCellArray()
            for i in range(n):
                verts.InsertNextCell(1); verts.InsertCellPoint(i)
            poly = vtk.vtkPolyData()
            poly.SetPoints(pts_v); poly.SetVerts(verts)
            self._a_verts = self._actor2d(poly, (1.0, 0.25, 0.0), ps=9)
            self._ren2d.AddActor(self._a_verts)

        # text banner
        try:
            _, h = self._ren_win.GetSize()
        except Exception:
            h = 600
        if n < 3:
            msg = f"Left-click: add point [{n}]  |  ESC: cancel"
        else:
            msg = f"Right-click/Enter: apply [{n} pts]  |  Backspace: undo  |  ESC: cancel"
        txt = vtk.vtkTextActor()
        txt.SetInput(msg)
        txt.SetPosition(10, max(h - 32, 4))
        p = txt.GetTextProperty()
        p.SetFontSize(13); p.SetColor(1.0, 1.0, 0.3)
        p.SetBold(True);   p.SetShadow(True)
        self._a_text = txt
        self._ren2d.AddActor(self._a_text)

    def _draw_preview(self, mx, my):
        """Dashed preview lines from last point → cursor → first point."""
        if self._a_prev:
            self._ren2d.RemoveActor(self._a_prev)
            self._a_prev = None
        if not self._pts:
            return

        coords = [self._pts[-1], (mx, my)]
        if len(self._pts) >= 2:
            coords.append(self._pts[0])

        pts_v = self._vtkpts(coords)
        lines = vtk.vtkCellArray()
        l1 = vtk.vtkLine()
        l1.GetPointIds().SetId(0, 0); l1.GetPointIds().SetId(1, 1)
        lines.InsertNextCell(l1)
        if len(self._pts) >= 2:
            l2 = vtk.vtkLine()
            l2.GetPointIds().SetId(0, 1); l2.GetPointIds().SetId(1, 2)
            lines.InsertNextCell(l2)
        poly = vtk.vtkPolyData()
        poly.SetPoints(pts_v); poly.SetLines(lines)
        self._a_prev = self._actor2d(poly, (1.0, 0.85, 0.2), lw=1.5, alpha=0.60)
        self._ren2d.AddActor(self._a_prev)

    def _clear_actors(self):
        for a in (self._a_edges, self._a_verts, self._a_prev, self._a_text):
            if a:
                try: self._ren2d.RemoveActor(a)
                except: pass
        self._a_edges = self._a_verts = self._a_prev = self._a_text = None
        try:
            self._ren_win.Render()
        except Exception:
            pass


# ============================================================ viewer
class PointCloudViewer(QWidget):
    """
    Interactive 3D viewer.
    Manages multiple independent layers (original cloud + segments).
    All layers render with the same thickness colormap.
    Polygon selection via VTK-native 2D overlay.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.signals = ViewerSignals()

        self._layers: List[Layer]       = []
        self._actors: Dict[str, object] = {}
        self._sel_actor                 = None

        self.sel_points:    Optional[np.ndarray] = None
        self.sel_distances: Optional[np.ndarray] = None

        self.point_size = 3
        self.colormap   = 'jet'

        self._setup_ui()

    # ------------------------------------------------------------------ setup
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        frame = QFrame()
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(0, 0, 0, 0)

        self.plotter = QtInteractor(frame)
        fl.addWidget(self.plotter.interactor)
        layout.addWidget(frame)

        self.plotter.set_background('white')
        self.plotter.add_axes()
        self.plotter.enable_rubber_band_style()

        # VTK-native polygon picker (created after plotter is ready)
        self._picker = VTKPolygonPicker(
            plotter      = self.plotter,
            on_closed    = self._on_polygon_closed,
            on_cancelled = self._on_polygon_cancelled,
        )

    # ------------------------------------------------------------------ layer sync
    def sync_layers(self, layers: List[Layer]):
        """Update the reference list used for polygon projection."""
        self._layers = layers

    # ------------------------------------------------------------------ add / remove
    def add_layer(self, layer: Layer):
        """Add or refresh one layer. All layers use thickness colormap."""
        self._drop_actor(layer.name)
        cloud = pv.PolyData(layer.points)
        cloud['thickness'] = layer.distances

        actor = self.plotter.add_mesh(
            cloud,
            scalars='thickness',
            cmap=self.colormap,
            point_size=self.point_size,
            render_points_as_spheres=True,
            show_scalar_bar=False,   # scalar bar only for original layer.is_original
            scalar_bar_args={
                'title': 'Thickness (mm)',
                'title_font_size': 12,
                'label_font_size': 10,
                'n_labels': 5,
                'position_x': 0.85,
                'position_y': 0.10,
                'width': 0.10,
                'height': 0.80,
            },
            name=f"layer_{layer.name}",
        )
        self._actors[layer.name] = actor
        if not layer.visible:
            actor.SetVisibility(False)
            self.plotter.render()

    def remove_layer(self, name: str):
        self._drop_actor(name)

    def _drop_actor(self, name: str):
        actor = self._actors.pop(name, None)
        if actor is not None:
            try:
                self.plotter.remove_actor(actor)
            except Exception:
                pass

    def clear_all_layers(self):
        """Remove all layer actors for file reload. Does NOT close the plotter."""
        for name in list(self._actors.keys()):
            self._drop_actor(name)
        self._layers = []
        self.clear_selection()
        try:
            self.plotter.clear()
            self.plotter.add_axes()
            self.plotter.enable_rubber_band_style()
        except Exception:
            pass

    # ------------------------------------------------------------------ visibility
    def set_layer_visible(self, name: str, visible: bool):
        actor = self._actors.get(name)
        if actor is not None:
            actor.SetVisibility(visible)
            self.plotter.render()

    # ------------------------------------------------------------------ settings
    def set_colormap(self, cmap: str):
        self.colormap = cmap
        for layer in self._layers:
            self.add_layer(layer)

    def set_point_size(self, size: int):
        self.point_size = size
        for layer in self._layers:
            self.add_layer(layer)

    # ------------------------------------------------------------------ polygon mode
    def enable_polygon_mode(self):
        if not self._layers:
            return
        self._picker.start()

    def disable_polygon_mode(self):
        if self._picker.is_active:
            self._picker.stop()

    def _on_polygon_cancelled(self):
        self.signals.polygon_mode_ended.emit()

    def _on_polygon_closed(self, screen_pts: list):
        """
        screen_pts are in VTK display coords (bottom-left origin).
        Project all visible cloud points to the same coordinate space.
        """
        vis = [l for l in self._layers if l.visible]
        if not vis:
            self.signals.polygon_mode_ended.emit()
            return

        all_pts   = np.concatenate([l.points    for l in vis])
        all_dists = np.concatenate([l.distances for l in vis])

        pts_2d = self._project_to_screen(all_pts)
        if pts_2d is not None:
            from matplotlib.path import Path
            inside = Path(screen_pts).contains_points(pts_2d)
            self.sel_points    = all_pts[inside]
            self.sel_distances = all_dists[inside]
            self._show_selection_highlight(self.sel_points)
            self.signals.selection_changed.emit(self.sel_points, self.sel_distances)

        self.signals.polygon_mode_ended.emit()

    # ------------------------------------------------------------------ distance-range selection
    def select_by_distance_range(self, min_d: float, max_d: float):
        vis = [l for l in self._layers if l.visible]
        if not vis:
            return
        all_pts   = np.concatenate([l.points    for l in vis])
        all_dists = np.concatenate([l.distances for l in vis])
        mask = (all_dists >= min_d) & (all_dists <= max_d)
        self.sel_points    = all_pts[mask]
        self.sel_distances = all_dists[mask]
        self._show_selection_highlight(self.sel_points)
        self.signals.selection_changed.emit(self.sel_points, self.sel_distances)

    def clear_selection(self):
        self.sel_points    = None
        self.sel_distances = None
        if self._sel_actor is not None:
            try:
                self.plotter.remove_actor(self._sel_actor)
            except Exception:
                pass
            self._sel_actor = None
        self.signals.selection_cleared.emit()

    def _show_selection_highlight(self, pts: np.ndarray):
        if self._sel_actor is not None:
            try:
                self.plotter.remove_actor(self._sel_actor)
            except Exception:
                pass
            self._sel_actor = None
        if pts is None or len(pts) == 0:
            return
        sel = pv.PolyData(pts)
        self._sel_actor = self.plotter.add_mesh(
            sel,
            color='yellow',
            point_size=self.point_size + 3,
            render_points_as_spheres=True,
            opacity=0.9,
        )

    # ------------------------------------------------------------------ projection
    def _project_to_screen(self, points: np.ndarray) -> Optional[np.ndarray]:
        """
        Vectorised projection: 3D world → VTK display coordinates (bottom-left).
        Consistent with iren.GetEventPosition() used by VTKPolygonPicker.
        Returns (N, 2) or None on error.
        """
        try:
            renderer = self.plotter.renderer
            camera   = renderer.GetActiveCamera()
            aspect   = renderer.GetTiledAspectRatio()

            def to_np(m):
                return np.array([[m.GetElement(i, j) for j in range(4)]
                                 for i in range(4)], dtype=np.float64)

            V = to_np(camera.GetViewTransformMatrix())
            P = to_np(camera.GetProjectionTransformMatrix(aspect, -1, 1))

            n = len(points)
            h = np.ones((n, 4), dtype=np.float64)
            h[:, :3] = points

            # Row-vector convention: x_out = x_in @ M.T
            clip = h @ V.T @ P.T
            w    = clip[:, 3:4]
            w    = np.where(np.abs(w) < 1e-10, 1e-10, w)
            ndc  = clip[:, :2] / w   # NDC in [-1, 1]

            # VTK display coords: origin bottom-left
            ww, wh = self.plotter.ren_win.GetSize()
            sx = (ndc[:, 0] + 1.0) * 0.5 * ww
            sy = (ndc[:, 1] + 1.0) * 0.5 * wh   # NO Y-flip

            return np.column_stack([sx, sy])
        except Exception as e:
            print(f"[_project_to_screen] {e}")
            return None

    # ------------------------------------------------------------------ camera
    def reset_view(self):
        self.plotter.reset_camera()
        self.plotter.view_isometric()

    def view_top(self):   self.plotter.view_xy()
    def view_front(self): self.plotter.view_xz()
    def view_side(self):  self.plotter.view_yz()

    def get_screenshot(self, path: str = None) -> Optional[str]:
        if path is None:
            import tempfile
            path = os.path.join(tempfile.gettempdir(), 'tunnel_screenshot.png')
        self.plotter.screenshot(path)
        return path

    def close(self):
        self.plotter.close()
