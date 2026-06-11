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

from numpy.ma import count
import vtk
import pyvista as pv
from pyvistaqt import QtInteractor

from PyQt5.QtWidgets import (
    QShortcut, QWidget, QVBoxLayout, QHBoxLayout, QFrame,
    QPushButton, QToolButton, QStyle, QToolTip, QInputDialog,
    QSizePolicy, QColorDialog, QSpinBox, QLabel
)
from PyQt5.QtGui import QColor, QCursor, QIcon, QKeySequence
from PyQt5.QtCore import pyqtSignal, QObject, QTimer, QSize, Qt

from gui.annotation.annotation_manager import AnnotationManager
from gui.annotation.text_annotation import TextAnnotation
from gui.annotation.line_annotation import LineAnnotation
from gui.annotation.delete_annotation import DeleteAnnotation
from gui.annotation.move_annotation import MoveAnnotation
from utils.path_helper import resource_path

if not getattr(sys, 'frozen', False):
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.layer_manager import Layer


# ============================================================ signals
class ViewerSignals(QObject):
    selection_changed  = pyqtSignal(object, object)
    selection_cleared  = pyqtSignal()
    polygon_mode_ended = pyqtSignal()
    annotation_added   = pyqtSignal(str, object)


# ============================================================ VTK polygon picker
class VTKPolygonPicker:
    """
    CloudCompare-style polygon selection drawn in VTK's 2D coordinate space.

    Controls
    --------
    Left click        – add vertex
    Double-click      – close & apply (≥ 3 pts)
    Right click       – close & apply (≥ 3 pts) / cancel
    Enter             – close & apply (≥ 3 pts)
    Backspace         – remove last vertex
    ESC               – cancel
    """

    def __init__(self, plotter, on_closed, on_cancelled, overlay_renderer=None):
        self._plotter      = plotter
        self._ren_win      = plotter.ren_win
        self._on_closed    = on_closed
        self._on_cancelled = on_cancelled

        self._pts: List     = []
        self._active        = False
        self._obs_tags      = []
        self._t_last_click  = 0.0

        self._iren = self._ren_win.GetInteractor()

        if overlay_renderer is not None:
            self._ren2d = overlay_renderer
        else:
            self._ren2d = vtk.vtkRenderer()
            self._ren2d.SetLayer(1)
            self._ren2d.InteractiveOff()
            self._ren_win.SetNumberOfLayers(2)
            self._ren_win.AddRenderer(self._ren2d)

        self._a_edges = None
        self._a_verts = None
        self._a_prev  = None
        self._a_text  = None

    @property
    def is_active(self) -> bool:
        return self._active

    def start(self):
        self._pts           = []
        self._active        = True
        self._t_last_click  = 0.0
        self._clear_actors()

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

    def _on_left(self, obj, event):
        if not self._active:
            return
        x, y = self._iren.GetEventPosition()
        now  = time.time()

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
        for a in (self._a_edges, self._a_verts, self._a_text):
            if a: self._ren2d.RemoveActor(a)
        self._a_edges = self._a_verts = self._a_text = None

        n = len(self._pts)

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

        if n >= 1:
            pts_v = self._vtkpts(self._pts)
            verts = vtk.vtkCellArray()
            for i in range(n):
                verts.InsertNextCell(1); verts.InsertCellPoint(i)
            poly = vtk.vtkPolyData()
            poly.SetPoints(pts_v); poly.SetVerts(verts)
            self._a_verts = self._actor2d(poly, (1.0, 0.25, 0.0), ps=9)
            self._ren2d.AddActor(self._a_verts)

        try:
            _, h = self._ren_win.GetSize()
        except Exception:
            h = 600
        msg = (
            f"Left-click: add point [{n}]  |  ESC: cancel"
            if n < 3 else
            f"Right-click/Enter: apply [{n} pts]  |  Backspace: undo  |  ESC: cancel"
        )
        txt = vtk.vtkTextActor()
        txt.SetInput(msg)
        txt.SetPosition(10, max(h - 32, 4))
        p = txt.GetTextProperty()
        p.SetFontSize(13); p.SetColor(1.0, 1.0, 0.3)
        p.SetBold(True);   p.SetShadow(True)
        self._a_text = txt
        self._ren2d.AddActor(self._a_text)

    def _draw_preview(self, mx, my):
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
        self.min_target = 20
        self.max_target = 40

        self.annotation_manager = AnnotationManager()
        self.annotation_manager.register("text",   TextAnnotation(self))
        self.annotation_manager.register("line",   LineAnnotation(self))
        self.annotation_manager.register("delete", DeleteAnnotation(self))
        self.annotation_manager.register("move",   MoveAnnotation(self))

        self._setup_ui()

    # ------------------------------------------------------------------ setup
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        frame = QFrame()
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(0, 0, 0, 0)

        self._toolbar = QWidget()
        self._toolbar.setObjectName("toolbar")
        self._toolbar.setStyleSheet("""
        QWidget { border: 1px solid #d0d7de; }
        QToolButton {
            border: none; background: transparent;
            padding: 6px; border-radius: 4px;
        }
        QToolButton:hover { background: #d0d7de; border: none; }
        QLabel { border: none; background: transparent; color: #374151; }
        QToolButton:checked { background: #d0d7de; border: none; }
        """)
        self._toolbar.setFixedHeight(75)
        toolbar_layout = QHBoxLayout(self._toolbar)
        toolbar_layout.setContentsMargins(4, 4, 4, 4)
        toolbar_layout.setSpacing(8)

        self.btn_add_text = QToolButton()
        self.btn_add_text.setText("Text")
        self.btn_add_text.setIcon(QIcon(resource_path("gui\\icons\\icons8-text-48.png")))
        self.btn_add_text.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.btn_add_text.setIconSize(QSize(32, 32))
        self.btn_add_text.setCheckable(True)
        self.btn_add_text.setToolTip("Add a text annotation")
        self.btn_add_text.clicked.connect(lambda: self.annotation_manager.activate("text"))
        QShortcut(QKeySequence("1"), self).activated.connect(self.btn_add_text.click)
        toolbar_layout.addWidget(self.btn_add_text)

        self.btn_add_line = QToolButton()
        self.btn_add_line.setText("Line")
        self.btn_add_line.setIcon(QIcon(resource_path("gui\\icons\\icons8-note-60.png")))
        self.btn_add_line.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.btn_add_line.setIconSize(QSize(35, 34))
        self.btn_add_line.setCheckable(True)
        self.btn_add_line.setToolTip("Add an leader line annotation")
        self.btn_add_line.clicked.connect(lambda: self.annotation_manager.activate("line"))
        QShortcut(QKeySequence("2"), self).activated.connect(self.btn_add_line.click)
        toolbar_layout.addWidget(self.btn_add_line)

        self.btn_move_annot = QToolButton()
        self.btn_move_annot.setText("Move")
        self.btn_move_annot.setIcon(QIcon(resource_path("gui\\icons\\icons8-move-48.png")))
        self.btn_move_annot.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.btn_move_annot.setCheckable(True)
        self.btn_move_annot.setIconSize(QSize(32, 32))
        self.btn_move_annot.setToolTip("Move an existing annotation")
        self.btn_move_annot.clicked.connect(lambda: self.annotation_manager.activate("move"))
        QShortcut(QKeySequence("3"), self).activated.connect(self.btn_move_annot.click)
        toolbar_layout.addWidget(self.btn_move_annot)

        self.btn_delete_annot = QToolButton()
        self.btn_delete_annot.setText("Delete")
        self.btn_delete_annot.setIcon(QIcon(resource_path("gui\\icons\\icons8-delete-48.png")))
        self.btn_delete_annot.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.btn_delete_annot.setCheckable(True)
        self.btn_delete_annot.setIconSize(QSize(32, 32))
        self.btn_delete_annot.setToolTip("Delete an existing annotation")
        self.btn_delete_annot.clicked.connect(lambda: self.annotation_manager.activate("delete"))
        QShortcut(QKeySequence("4"), self).activated.connect(self.btn_delete_annot.click)
        toolbar_layout.addWidget(self.btn_delete_annot)

        toolbar_layout.addStretch(1)
        toolbar_layout.addWidget(QLabel("Color:"))

        self.btn_annotation_color = QPushButton()
        self.btn_annotation_color.setFixedSize(24, 24)
        self.btn_annotation_color.setStyleSheet("QPushButton { border-radius: 0px; }")
        self.btn_annotation_color.clicked.connect(self._choose_annotation_color)
        toolbar_layout.addWidget(self.btn_annotation_color)

        self._tool_buttons = [
            self.btn_add_text, self.btn_add_line,
            self.btn_move_annot, self.btn_delete_annot,
        ]
        self._set_tool_buttons_enabled(False)
        for btn in self._tool_buttons:
            btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        toolbar_layout.addWidget(QLabel("Line Width:"))
        self.spin_line_width = QSpinBox()
        self.spin_line_width.setRange(1, 10)
        self.spin_line_width.setValue(3)
        toolbar_layout.addWidget(self.spin_line_width)

        toolbar_layout.addWidget(QLabel("Font Size:"))
        self.spin_font_size = QSpinBox()
        self.spin_font_size.setRange(8, 48)
        self.spin_font_size.setValue(14)
        toolbar_layout.addWidget(self.spin_font_size)

        self._annotation_color = "#000000"

        fl.addWidget(self._toolbar)

        self.plotter = QtInteractor(frame)
        fl.addWidget(self.plotter.interactor)
        layout.addWidget(frame)

        self.plotter.set_background('white')
        self.plotter.add_axes()
        self.plotter.enable_rubber_band_style()

        self._overlay_renderer = vtk.vtkRenderer()
        self._overlay_renderer.SetLayer(1)
        self._overlay_renderer.InteractiveOff()
        self.plotter.ren_win.SetNumberOfLayers(2)
        self.plotter.ren_win.AddRenderer(self._overlay_renderer)

        self._iren = self.plotter.ren_win.GetInteractor()

        self._annotation_layer_name  = None
        self._annotation_preview_actor  = None
        self._annotation_preview_actors = []
        self._annotations = []

        self._picker = VTKPolygonPicker(
            plotter          = self.plotter,
            on_closed        = self._on_polygon_closed,
            on_cancelled     = self._on_polygon_cancelled,
            overlay_renderer = self._overlay_renderer,
        )
        self._setup_interactor_events()

        self.annotation_manager.activate("text")
        self.annotation_manager.activate(None)

    def _setup_interactor_events(self):
        self._iren.AddObserver('LeftButtonPressEvent',   self._on_left_click)
        self._iren.AddObserver('MouseMoveEvent',         self._on_mouse_move)
        self._iren.AddObserver('LeftButtonReleaseEvent', self._on_left_release)
        self._iren.AddObserver('KeyPressEvent',          self._on_key_press)

    def _set_tool_buttons_enabled(self, enabled: bool):
        for btn in self._tool_buttons:
            btn.setEnabled(enabled)

    # ------------------------------------------------------------------ layer sync
    def sync_layers(self, layers: List[Layer]):
        self._layers = layers

    # ------------------------------------------------------------------ add / remove
    def assign_colors(self, layer: Layer,
                      color1=np.array([1.0, 0.0, 0.0], dtype=np.float32),
                      color2=np.array([0.0, 1.0, 0.0], dtype=np.float32),
                      color3=np.array([0.0, 0.0, 1.0], dtype=np.float32),
                      color4=np.array([0.0, 0.0, 1.0], dtype=np.float32)) -> np.ndarray:
        min_target = self.min_target
        max_target = self.max_target
        distances  = layer.distances
        colors     = np.zeros((len(distances), 3), dtype=np.float32)

        colors[distances < min_target] = color1
        colors[(distances >= min_target) & (distances <= max_target)] = color2
        colors[(distances > max_target) & (distances < 150)] = color3
        colors[distances >= 150] = color4
        return colors

    def add_layer(self, layer: Layer):
        self._drop_actor(layer.name)
        cloud = pv.PolyData(layer.points)
        cloud['thickness'] = layer.distances
        cloud['colors']    = self.assign_colors(layer)

        actor = self.plotter.add_mesh(
            cloud,
            scalars='colors',
            rgb=True,
            point_size=self.point_size,
            render_points_as_spheres=True,
            show_scalar_bar=False,
            name=f"layer_{layer.name}",
        )
        self._actors[layer.name] = actor
        if not layer.visible:
            actor.SetVisibility(False)
            self.plotter.render()

    def remove_layer(self, name: str):
        self._drop_actor(name)
        self._remove_annotation_actors_for_layer(name)

    def _drop_actor(self, name: str):
        actor = self._actors.pop(name, None)
        if actor is not None:
            try:
                self.plotter.remove_actor(actor)
            except Exception:
                pass

    def clear_all_layers(self):
        for name in list(self._actors.keys()):
            self._drop_actor(name)
        self._remove_annotation_actors_for_layer(name="all")
        self._layers = []
        self.clear_selection()
        try:
            self.plotter.clear()
            self.plotter.add_axes()
            self.plotter.enable_rubber_band_style()
            self.plotter.ren_win.SetNumberOfLayers(2)
            self.plotter.ren_win.AddRenderer(self._overlay_renderer)
        except Exception:
            pass

    # ------------------------------------------------------------------ visibility
    def set_layer_visible(self, name: str, visible: bool):
        actor = self._actors.get(name)
        if actor is not None:
            actor.SetVisibility(visible)
            self.plotter.render()

        for ann in self._annotations:
            if ann['layer_name'] != name:
                continue
            ann_actor = ann['annotation']['actor']
            if isinstance(ann_actor, dict):
                for a in ann_actor.values():
                    a.SetVisibility(visible)
            else:
                ann_actor.SetVisibility(visible)

    # ------------------------------------------------------------------ settings
    def set_thickness_targets(self, min_t: float, max_t: float):
        self.min_target = min_t
        self.max_target = max_t
        for layer in self._layers:
            self.add_layer(layer)

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

    def set_annotation_layer(self, layer_name: str):
        self._annotation_layer_name = layer_name

    def enable_annotation_mode(self, action: str, text: str = None):
        if self._picker.is_active:
            return
        self.annotation_manager.activate(action)

    # ------------------------------------------------------------------ toolbar helpers
    def _reset_toolbar_buttons(self):
        for btn in self._tool_buttons:
            btn.blockSignals(True)
            btn.setChecked(False)
            btn.blockSignals(False)

    def _current_annotation_style(self):
        return {
            "color":      self._annotation_color,
            "line_width": self.spin_line_width.value(),
            "font_size":  self.spin_font_size.value(),
        }

    def _choose_annotation_color(self):
        color = QColorDialog.getColor(QColor(self._annotation_color), self, "Select annotation color")
        if color.isValid():
            self._annotation_color = color.name()
            self.btn_annotation_color.setStyleSheet(
                f"background-color: {self._annotation_color}; border-radius: 0px;"
            )

    # ------------------------------------------------------------------ interactor callbacks
    def _on_left_click(self, obj, event):
        tool = self.annotation_manager.active_annotation
        if not tool:
            return
        x, y = self._iren.GetEventPosition()
        tool.on_left_click(x, y)

    def _on_mouse_move(self, obj, event):
        tool = self.annotation_manager.active_annotation
        if not tool:
            return
        x, y = self._iren.GetEventPosition()
        tool.on_mouse_move(x, y)

    def _on_left_release(self, obj, event):
        tool = self.annotation_manager.active_annotation
        if not tool:
            return
        x, y = self._iren.GetEventPosition()
        tool.on_left_release(x, y)

    def _on_key_press(self, obj, event):
        tool = self.annotation_manager.active_annotation
        if not tool:
            return
        key = self._iren.GetKeySym()
        tool.on_key_press(key)

    # ------------------------------------------------------------------ annotation preview
    def _clear_annotation_preview(self):
        if self._annotation_preview_actor is not None:
            try:
                self._overlay_renderer.RemoveActor(self._annotation_preview_actor)
            except Exception:
                pass
            self._annotation_preview_actor = None

        for actor in self._annotation_preview_actors:
            try:
                self._overlay_renderer.RemoveActor(actor)
            except Exception:
                pass
        self._annotation_preview_actors = []
        self.plotter.ren_win.Render()



    def _update_text_preview(self, annotation):
        self._clear_annotation_preview()

        if annotation.get("text_position") is None or not annotation.get("text"):
            return

        actor = self._create_text_actor(annotation)
        actor.GetProperty().SetOpacity(0.85)
        self._annotation_preview_actors.append(actor)
        
    def _update_line_text_preview(self, annotation):
        self._clear_annotation_preview()
        if annotation is None:
            return

        actors = self._build_line_text_actors(annotation, preview=True)
        self._overlay_renderer.AddActor(actors["line_actor"])
        self._overlay_renderer.AddActor(actors["text_actor"])
        self._annotation_preview_actors = list(actors.values())
        self.plotter.ren_win.Render()

    # ------------------------------------------------------------------ annotation builders
    def _build_line_polydata(self, points):
        if len(points) < 2:
            return None

        vtk_points = vtk.vtkPoints()
        for p in points:
            x, y = p[0], p[1]
            z    = p[2] if len(p) > 2 else 0.0
            vtk_points.InsertNextPoint(x, y, z)

        line = vtk.vtkPolyLine()
        line.GetPointIds().SetNumberOfIds(len(points))
        for i in range(len(points)):
            line.GetPointIds().SetId(i, i)

        lines = vtk.vtkCellArray()
        lines.InsertNextCell(line)

        poly = vtk.vtkPolyData()
        poly.SetPoints(vtk_points)
        poly.SetLines(lines)
        return poly

    def _build_text_actor(self, annotation, preview=False):
        text_actor = vtk.vtkTextActor()
        text_actor.SetInput(annotation.get("text", ""))

        text_pos = annotation.get("text_position", (0, 0))
        if text_pos:
            text_actor.SetDisplayPosition(*text_pos)

        prop = text_actor.GetTextProperty()
        prop.SetFontSize(annotation.get("font_size", 12))

        color = annotation.get("color", "#000000")
        qcolor = QColor(color) if isinstance(color, str) else color
        prop.SetColor(*qcolor.getRgbF()[:3])
        prop.SetBold(True)
        prop.SetBackgroundColor(1.0, 1.0, 1.0)
        prop.SetBackgroundOpacity(0.4 if preview else 0.75)
        return text_actor

    def _build_line_actor(self, annotation, preview=False):
        poly = self._build_line_polydata(annotation.get("points", []))
        if poly is None:
            return None

        mapper = vtk.vtkPolyDataMapper2D()
        mapper.SetInputData(poly)

        line_actor = vtk.vtkActor2D()
        line_actor.SetMapper(mapper)

        color = annotation.get("color", "#000000")
        qcolor = QColor(color) if isinstance(color, str) else color
        line_actor.GetProperty().SetColor(*qcolor.getRgbF()[:3])
        line_actor.GetProperty().SetLineWidth(annotation.get("line_width", 2))

        if preview:
            line_actor.GetProperty().SetOpacity(0.6)
            line_actor.GetProperty().SetLineStipplePattern(0xF0F0)
        else:
            line_actor.GetProperty().SetOpacity(1.0)
            line_actor.GetProperty().SetLineStipplePattern(0xFFFF)
        return line_actor

    def _build_line_text_actors(self, annotation: dict, preview=False):
        return {
            "line_actor": self._build_line_actor(annotation, preview),
            "text_actor": self._build_text_actor(annotation, preview),
        }

    def _create_text_actor(self, annotation: dict):
        actor = self._build_text_actor(annotation)
        self._overlay_renderer.AddActor(actor)
        self.plotter.ren_win.Render()
        return actor

    def _create_line_text_actor(self, annotation: dict):
        actors = self._build_line_text_actors(annotation, preview=False)
        self._overlay_renderer.AddActor(actors["line_actor"])
        self._overlay_renderer.AddActor(actors["text_actor"])
        self.plotter.ren_win.Render()
        return actors

    # ------------------------------------------------------------------ annotation removal
    def _delete_annotation_by_layer(self, layer_name: str):
        if layer_name in ("all", None, ""):
            to_remove = self._annotations[:]
        else:
            to_remove = [a for a in self._annotations if a['layer_name'] == layer_name]

        for ann in to_remove:
            actor = ann['annotation']['actor']
            if isinstance(actor, dict):
                for a in actor.values():
                    try: self._overlay_renderer.RemoveActor(a)
                    except: pass
            else:
                try: self._overlay_renderer.RemoveActor(actor)
                except: pass
            self._annotations.remove(ann)

    def _safe_remove_actor(self, annotation: dict, key: str):
        actor = annotation.get(key)
        if actor is None:
            return
        try:
            self._overlay_renderer.RemoveActor(actor)
        except Exception:
            pass
        annotation[key] = None

    def _remove_annotation(self, entry):
        annotation = entry["annotation"]
        actor = annotation.get("actor")
        if isinstance(actor, dict):
            for a in actor.values():
                try: self._overlay_renderer.RemoveActor(a)
                except: pass
        else:
            self._safe_remove_actor(annotation, "actor")
        if entry in self._annotations:
            self._annotations.remove(entry)
        self.plotter.ren_win.Render()

    def _remove_annotation_actors_for_layer(self, name: str):
        if name == "all":
            self._clear_annotation_actors()
            return
        remaining = []
        for entry in self._annotations:
            if entry["layer_name"] == name:
                actor = entry["annotation"].get("actor")
                if isinstance(actor, dict):
                    for a in actor.values():
                        try: self._overlay_renderer.RemoveActor(a)
                        except: pass
                else:
                    self._safe_remove_actor(entry["annotation"], "actor")
            else:
                remaining.append(entry)
        self._annotations = remaining
        self.plotter.ren_win.Render()

    def _clear_annotation_actors(self):
        for entry in self._annotations:
            actor = entry["annotation"].get("actor")
            if isinstance(actor, dict):
                for a in actor.values():
                    try: self._overlay_renderer.RemoveActor(a)
                    except: pass
            else:
                self._safe_remove_actor(entry["annotation"], "actor")
        self._annotations = []
        self.plotter.ren_win.Render()

    # ------------------------------------------------------------------ camera
    def _restore_camera(self):
        try:
            self.plotter.enable_rubber_band_style()
        except Exception:
            try:
                self._iren.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())
            except Exception:
                pass
        try:
            self.plotter.ren_win.Render()
        except Exception:
            pass

    def reset_view(self):
        self.plotter.reset_camera()
        self.plotter.view_isometric()

    def view_top(self):    self.plotter.view_yx(-1)
    def view_bottom(self):
        self.plotter.view_yx(render=False)
        self.plotter.camera.Roll(180)
    def view_front(self):  self.plotter.view_yz(-1)
    def view_back(self):   self.plotter.view_yz()
    def view_right(self):  self.plotter.view_xz()
    def view_left(self):   self.plotter.view_xz(-1)
    def view_iso(self):
        self.plotter.view_isometric(render=False)
        self.plotter.camera.Azimuth(180)

    # ------------------------------------------------------------------ polygon callbacks
    def _on_polygon_cancelled(self):
        self.signals.polygon_mode_ended.emit()

    def _on_polygon_closed(self, screen_pts: list):
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

            clip = h @ V.T @ P.T
            w    = clip[:, 3:4]
            w    = np.where(np.abs(w) < 1e-10, 1e-10, w)
            ndc  = clip[:, :2] / w

            ww, wh = self.plotter.ren_win.GetSize()
            sx = (ndc[:, 0] + 1.0) * 0.5 * ww
            sy = (ndc[:, 1] + 1.0) * 0.5 * wh

            return np.column_stack([sx, sy])
        except Exception as e:
            print(f"[_project_to_screen] {e}")
            return None

    # ------------------------------------------------------------------ screenshot
    def get_screenshot(self, path: str = None) -> Optional[str]:
        if path is None:
            import tempfile
            path = os.path.join(tempfile.gettempdir(), 'tunnel_screenshot.png')
        self.plotter.screenshot(path)
        return path

    def close(self):
        self.plotter.close()