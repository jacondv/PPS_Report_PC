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

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFrame, QPushButton, QToolButton, QStyle, QToolTip, QInputDialog, QSizePolicy, QDialog, QDialogButtonBox, QLabel, QTextEdit, QColorDialog, QSpinBox, QLineEdit
from PyQt5.QtGui import QColor, QCursor, QIcon
from PyQt5.QtCore import pyqtSignal, QObject, QTimer, QSize, Qt
from .annotation.annotation_manager import AnnotationManager
from gui.annotation.text_annotation import TextAnnotation
from gui.annotation.line_annotation import LineAnnotation
from gui.annotation.delete_annotation import DeleteAnnotation
from gui.annotation.move_annotation import MoveAnnotation

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.layer_manager import Layer


# ============================================================ signals
class ViewerSignals(QObject):
    selection_changed  = pyqtSignal(object, object)  # (pts ndarray, dists ndarray)
    selection_cleared  = pyqtSignal()
    polygon_mode_ended = pyqtSignal()
    annotation_added   = pyqtSignal(str, object)


class TextAnnotationDialog(QDialog):
    def __init__(self, parent=None, initial_text="", initial_color=QColor(0, 0, 0), initial_size=14):
        super().__init__(parent)
        self.setWindowTitle("Text Annotation")
        self.setModal(True)
        self.resize(420, 320)

        self._color = initial_color

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        label = QLabel("Enter annotation text:")
        layout.addWidget(label)

        self.text_edit = QTextEdit(self)
        self.text_edit.setPlainText(initial_text)
        self.text_edit.setFixedHeight(160)
        layout.addWidget(self.text_edit)

        layout.addWidget(QLabel("Preview:"))
        self.preview = QLabel(self)
        self.preview.setWordWrap(True)
        self.preview.setMinimumHeight(70)
        self.preview.setStyleSheet("border: 1px solid #bbb; padding: 8px; background: #fff;")
        layout.addWidget(self.preview)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.text_edit.textChanged.connect(self._update_preview)
        self._update_preview()

    def _update_preview(self):
        text = self.text_edit.toPlainText().strip() or "Sample text"
        self.preview.setText(text)

    def properties(self):
        return {
            "text": self.text_edit.toPlainText().strip(),
        }


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

    def __init__(self, plotter, on_closed, on_cancelled, overlay_renderer=None):
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
        if overlay_renderer is not None:
            self._ren2d = overlay_renderer
        else:
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

        self.min_target = 20  # default
        self.max_target = 40  # default

        self.annotation_manager = AnnotationManager()
        self.annotation_manager.register("text", TextAnnotation(self))
        self.annotation_manager.register("line", LineAnnotation(self))
        self.annotation_manager.register("delete", DeleteAnnotation(self))
        self.annotation_manager.register("move", MoveAnnotation(self))


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
        QWidget {
            border: 1px solid #d0d7de;
        }

        /* BUTTON STYLE */
        QToolButton {
            border: none;
            background: transparent;
            padding: 6px;
            border-radius: 4px;
        }

        QToolButton:hover {
            border: none;
            
            background: #d0d7de;
            border: none;
        }
        QLabel {
            border: none;
            background: transparent;
            color: #374151;
        }

        QToolButton:checked {
            background: #d0d7de;
            border: none;
        }
        """)
        self._toolbar.setFixedHeight(75)
        toolbar_layout = QHBoxLayout(self._toolbar)
        toolbar_layout.setContentsMargins(4, 4, 4, 4)
        toolbar_layout.setSpacing(8)

        style = self.style()

        self.btn_add_text = QToolButton()
        self.btn_add_text.setText("Text")
        self.btn_add_text.setIcon(QIcon("gui\icons\icons8-text-48.png"))
        self.btn_add_text.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.btn_add_text.setIconSize(QSize(32, 32))
        self.btn_add_text.setCheckable(True)
        self.btn_add_text.setToolTip("Add a text annotation")
        # self.btn_add_text.clicked.connect(self._on_text_tool_clicked)
        self.btn_add_text.clicked.connect(lambda: self.annotation_manager.activate("text"))
        toolbar_layout.addWidget(self.btn_add_text)

        self.btn_add_line = QToolButton()
        self.btn_add_line.setText("Line")
        self.btn_add_line.setIcon(QIcon("gui\icons\icons8-note-60.png"))
        self.btn_add_line.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.btn_add_line.setIconSize(QSize(35, 34))
        self.btn_add_line.setCheckable(True)
        self.btn_add_line.setToolTip("Add an leader line annotation")
        self.btn_add_line.clicked.connect(lambda: self.annotation_manager.activate("line"))
        toolbar_layout.addWidget(self.btn_add_line)

        self.btn_move_annot = QToolButton()
        self.btn_move_annot.setText("Move")
        self.btn_move_annot.setIcon(QIcon("gui\icons\icons8-move-48.png"))
        self.btn_move_annot.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.btn_move_annot.setCheckable(True)
        self.btn_move_annot.setIconSize(QSize(32, 32))
        self.btn_move_annot.setToolTip("Move an existing annotation")
        self.btn_move_annot.clicked.connect(lambda: self.annotation_manager.activate("move"))
        toolbar_layout.addWidget(self.btn_move_annot)

        self.btn_delete_annot = QToolButton()
        self.btn_delete_annot.setText("Delete")
        self.btn_delete_annot.setIcon(QIcon("gui\icons\icons8-delete-48.png"))
        self.btn_delete_annot.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.btn_delete_annot.setCheckable(True)
        self.btn_delete_annot.setIconSize(QSize(32, 32))
        self.btn_delete_annot.setToolTip("Delete an existing annotation")
        self.btn_delete_annot.clicked.connect(lambda: self.annotation_manager.activate("delete"))
        toolbar_layout.addWidget(self.btn_delete_annot)

        toolbar_layout.addStretch(1)
        toolbar_layout.addWidget(QLabel("Color:"))
        self.btn_annotation_color = QPushButton()
        self.btn_annotation_color.setFixedSize(24, 24)
        self.btn_annotation_color.setStyleSheet("""
            QPushButton {
                border-radius: 0px;
            }
        """)
        self.btn_annotation_color.clicked.connect(self._choose_annotation_color)
        toolbar_layout.addWidget(self.btn_annotation_color)

        for btn in [
            self.btn_add_text,
            self.btn_move_annot,
            self.btn_delete_annot,
        ]:
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

        # overlay renderer for annotations and polygon drawing
        self._overlay_renderer = vtk.vtkRenderer()
        self._overlay_renderer.SetLayer(1)
        self._overlay_renderer.InteractiveOff()
        self.plotter.ren_win.SetNumberOfLayers(2)
        self.plotter.ren_win.AddRenderer(self._overlay_renderer)

        self._iren = self.plotter.ren_win.GetInteractor()
        self._annotation_mode = False
        self._annotation_action = None
        self._annotation_layer_name = None
        self._annotation_text = None
        self._annotation_arrow_start = None
        self._annotation_move_target = None
        self._annotation_obs = None
        self._annotation_move_obs = None
        self._annotation_cancel_obs = None
        self._annotation_key_obs = None
        self._annotation_release_obs = None
        self._annotation_preview_actor = None
        self._annotation_preview_actors = []
        self._selected_outline_actor = None
        self._pending_arrow_annotation = None
        self._annotation_move_target = None
        self._annotation_dragging = False
        self._annotation_drag_last = None
        self._annotations = []

        # VTK-native polygon picker (created after plotter is ready)
        self._picker = VTKPolygonPicker(
            plotter      = self.plotter,
            on_closed    = self._on_polygon_closed,
            on_cancelled = self._on_polygon_cancelled,
            overlay_renderer=self._overlay_renderer,
        )
        self._setup_interactor_events()

        # This ensures the plotter's interactor is fully initialized before we add VTK observers
        self.annotation_manager.activate("text")
        self.annotation_manager.activate(None)


    def _setup_interactor_events(self):
        self._iren.AddObserver('LeftButtonPressEvent', self._on_left_click)
        self._iren.AddObserver('MouseMoveEvent', self._on_mouse_move)
        self._iren.AddObserver('LeftButtonReleaseEvent', self._on_left_release)
        # self._iren.AddObserver('RightButtonPressEvent', self._on_right_click)
        self._iren.AddObserver('KeyPressEvent', self._on_key_press)


    def enable_annotation_mode(self, action: str, text: str = None):
        if self._picker.is_active:
            return
        self.annotation_manager.activate(action)
        
    # ------------------------------------------------------------------ layer sync
    def sync_layers(self, layers: List[Layer]):
        """Update the reference list used for polygon projection."""
        self._layers = layers

    # ------------------------------------------------------------------ add / remove
    def assign_colors(self, layer: Layer) -> np.ndarray:
        """
        Assign colors to points based on thickness thresholds.
        Override this method to customize color logic.
        """
        min_target = self.min_target
        max_target = self.max_target
        distances = layer.distances
        colors = np.zeros((len(distances), 3), dtype=np.float32)

        red = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        green = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        blue = np.array([0.0, 0.0, 1.0], dtype=np.float32)
        light_blue = np.array([0.68, 0.85, 0.9], dtype=np.float32)

        colors[distances < min_target] = red
        colors[(distances >= min_target) & (distances <= max_target)] = green
        colors[(distances > max_target) & (distances < 150)] = blue
        colors[distances >= 150] = light_blue

        return colors

    def add_layer(self, layer: Layer):
        """Add or refresh one layer. All layers use thickness colormap."""
        self._drop_actor(layer.name)
        cloud = pv.PolyData(layer.points)
        cloud['thickness'] = layer.distances

        # Assign colors using the customizable method
        colors = self.assign_colors(layer)
        cloud['colors'] = colors

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
        """Remove all layer actors for file reload. Does NOT close the plotter."""
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
                ann_actor = ann['annotation']['actor']
                ann_layer = ann['layer_name']
                if ann_layer == name:
                    if isinstance(ann_actor,dict):
                        for a in ann_actor.values():
                            a.SetVisibility(visible)
                    else:
                        ann_actor.SetVisibility(visible)

    # ------------------------------------------------------------------ settings
    def set_thickness_targets(self, min_t: float, max_t: float):
        self.min_target = min_t
        self.max_target = max_t
        # Refresh all layers
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



    def _reset_toolbar_buttons(self):
        for btn in (self.btn_add_text, self.btn_add_line, self.btn_move_annot, self.btn_delete_annot):
            btn.blockSignals(True)
            btn.setChecked(False)
            btn.blockSignals(False)

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
        print(tool)
        if not tool:
            return

        key = self._iren.GetKeySym()
        tool.on_key_press(key)

    def _on_annotation_move(self, obj, event):
        if not self._annotation_mode:
            return
        x, y = self._iren.GetEventPosition()
        if self._annotation_action == 'arrow' and self._annotation_arrow_start is not None:
            self._update_arrow_preview(self._annotation_arrow_start, (int(x), int(y)))
        elif self._annotation_action == 'move' and self._annotation_dragging and self._annotation_move_target is not None:
            self._drag_annotation(self._annotation_move_target, x, y)
        elif self._annotation_action == 'line' and self._annotation_arrow_start is not None:
            self._update_line_preview(self._annotation_arrow_start, (int(x), int(y)))

    def _current_annotation_style(self):
        return {
            "color": self._annotation_color,
            "line_width": self.spin_line_width.value(),
            "font_size": self.spin_font_size.value(),
        }

    def _choose_annotation_color(self):
        color = QColorDialog.getColor(QColor(self._annotation_color), self, "Select annotation color")
        if color.isValid():
            self._annotation_color = color.name()
            self.btn_annotation_color.setStyleSheet(f"background-color: {self._annotation_color}; border-radius: 0px;")



    def _clear_annotation_preview(self):
        if self._annotation_preview_actor is not None:
            try:
                self._overlay_renderer.RemoveActor(self._annotation_preview_actor)
            except Exception:
                pass
            self._annotation_preview_actor = None
            self.plotter.ren_win.Render()

        for actor in self._annotation_preview_actors:
            try:
                self._overlay_renderer.RemoveActor(actor)
            except Exception:
                pass

    def _clear_annotation_highlight(self):
        if self._selected_outline_actor is not None:
            try:
                self._overlay_renderer.RemoveActor(self._selected_outline_actor)
            except Exception:
                pass
            self._selected_outline_actor = None
            self.plotter.ren_win.Render()

    def _highlight_annotation(self, entry):
        self._clear_annotation_highlight()
        ann = entry["annotation"]
        if ann["type"] == "text":
            px, py = ann["position"]
            size = ann.get("font_size", 14)
            width = max(80, len(ann.get("text", "")) * size * 0.5)
            height = max(24, size * 1.4 + 10)
            bbox = [
                (px - 10, py - 10),
                (px + width, py - 10),
                (px + width, py + height),
                (px - 10, py + height),
            ]
        else:
            sx, sy = ann["position"]
            ex, ey = ann["end_position"]
            minx, miny = min(sx, ex), min(sy, ey)
            maxx, maxy = max(sx, ex), max(sy, ey)
            if ann.get("label_position") is not None:
                lx, ly = ann["label_position"]
                minx, miny = min(minx, lx), min(miny, ly)
                maxx, maxy = max(maxx, lx), max(maxy, ly)
            margin = 14
            bbox = [
                (minx - margin, miny - margin),
                (maxx + margin, miny - margin),
                (maxx + margin, maxy + margin),
                (minx - margin, maxy + margin),
            ]
        points = vtk.vtkPoints()
        for px, py in bbox:
            points.InsertNextPoint(px, py, 0)
        poly_line = vtk.vtkPolyLine()
        poly_line.GetPointIds().SetNumberOfIds(5)
        for i in range(4):
            poly_line.GetPointIds().SetId(i, i)
        poly_line.GetPointIds().SetId(4, 0)
        lines = vtk.vtkCellArray()
        lines.InsertNextCell(poly_line)
        outline = vtk.vtkPolyData()
        outline.SetPoints(points)
        outline.SetLines(lines)
        mapper = vtk.vtkPolyDataMapper2D()
        mapper.SetInputData(outline)
        actor = vtk.vtkActor2D()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(0.0, 0.0, 0.0)
        actor.GetProperty().SetLineWidth(2)
        actor.GetProperty().SetOpacity(0.9)
        self._overlay_renderer.AddActor(actor)
        self._selected_outline_actor = actor
        self.plotter.ren_win.Render()

    def _cancel_pending_arrow(self):
        if self._pending_arrow_annotation is not None:
            actor = self._pending_arrow_annotation.get("actor")
            if actor is not None:
                try:
                    self._overlay_renderer.RemoveActor(actor)
                except Exception:
                    pass
            self._pending_arrow_annotation = None
        self._annotation_action = 'arrow'
        self._annotation_arrow_start = None
        self._clear_annotation_preview()
        QToolTip.showText(self.mapToGlobal(self.cursor().pos()), "Arrow label placement canceled. Click first endpoint to start again.")

    def _place_arrow_label(self, x: int, y: int):
        if self._pending_arrow_annotation is None:
            return
        annotation = self._pending_arrow_annotation
        text, ok = QInputDialog.getText(self, "Arrow Label", "Enter arrow text:")
        if not ok:
            try:
                self._overlay_renderer.RemoveActor(annotation.get("actor"))
            except Exception:
                pass
            self._pending_arrow_annotation = None
            self._end_annotation_mode()
            return

        annotation["text"] = text.strip()
        if annotation["text"]:
            annotation["label_position"] = (int(x), int(y))
            annotation["text_actor"] = self._create_arrow_text_actor(annotation)

        self._pending_arrow_annotation = None
        self._annotations.append({
            "layer_name": self._annotation_layer_name,
            "annotation": annotation,
        })
        self.signals.annotation_added.emit(self._annotation_layer_name, {
            "action": "add",
            "annotation": annotation,
        })
        self._end_annotation_mode()

    def _update_tool_cursor(self):
        cursor = Qt.ArrowCursor
        if self._annotation_action == 'text':
            cursor = Qt.IBeamCursor
        elif self._annotation_action == 'arrow':
            cursor = Qt.CrossCursor
        elif self._annotation_action == 'arrow_label':
            cursor = Qt.CrossCursor
        elif self._annotation_action == 'move':
            cursor = Qt.SizeAllCursor
        elif self._annotation_action == 'delete':
            cursor = Qt.ForbiddenCursor
        elif self._annotation_action == 'line':
            cursor = Qt.CrossCursor
        try:
            self.setCursor(QCursor(cursor))
            self.plotter.interactor.setCursor(QCursor(cursor))
        except Exception:
            pass

    

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
            
    def _on_text_tool_clicked(self):
        if not self._annotation_layer_name:
            QToolTip.showText(self.mapToGlobal(self.cursor().pos()), "Select a layer before annotating.")
            self._reset_toolbar_buttons()
            return
        self.enable_annotation_mode('text')
        QToolTip.showText(self.mapToGlobal(self.cursor().pos()), "Click the view to place the text annotation.")

    def _on_arrow_tool_clicked(self):
        if not self._annotation_layer_name:
            QToolTip.showText(self.mapToGlobal(self.cursor().pos()), "Select a layer before annotating.")
            self._reset_toolbar_buttons()
            return
        self.enable_annotation_mode('arrow')
        QToolTip.showText(self.mapToGlobal(self.cursor().pos()), "Click the first endpoint, then click the second endpoint for the arrow. After that, click to place label text.")

    def _on_line_tool_clicked(self):
        if not self._annotation_layer_name:
            QToolTip.showText(self.mapToGlobal(self.cursor().pos()), "Select a layer before annotating.")
            self._reset_toolbar_buttons()
            return
        self.enable_annotation_mode('line')
        QToolTip.showText(self.mapToGlobal(self.cursor().pos()), "Click the start point, then click the end point for the leader line annotation.")

    def _on_move_tool_clicked(self):
        if not self._annotation_layer_name:
            QToolTip.showText(self.mapToGlobal(self.cursor().pos()), "Select a layer before moving annotations.")
            self._reset_toolbar_buttons()
            return
        self.enable_annotation_mode('move')

    def _on_delete_tool_clicked(self):
        if not self._annotation_layer_name:
            QToolTip.showText(self.mapToGlobal(self.cursor().pos()), "Select a layer before deleting annotations.")
            self._reset_toolbar_buttons()
            return
        self.enable_annotation_mode('delete')

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


    def _handle_line_click(self, x: int, y: int):
        if self._annotation_arrow_start is None:
            self._annotation_arrow_start = (int(x), int(y))
            QToolTip.showText(self.mapToGlobal(self.cursor().pos()), "Click the end point of the leader line.")
            return
        style = self._current_annotation_style()
        annotation = {
            "type": "line",
            "text": "",
            "color": style["color"],
            "line_width": style["line_width"],
            "font_size": style["font_size"],
            "position": self._annotation_arrow_start,
            "end_position": (int(x), int(y)),
        }
        self._clear_annotation_preview()
        actor = self._create_line_actor(annotation)
        annotation["actor"] = actor
        self._annotations.append({
            "layer_name": self._annotation_layer_name,
            "annotation": annotation,
        })
        self.signals.annotation_added.emit(self._annotation_layer_name, {
            "action": "add",
            "annotation": annotation,
        })
        self._annotation_arrow_start = None
        self._end_annotation_mode()


    def _handle_move_click(self, x: int, y: int):
        if self._annotation_move_target is None:
            target = self._find_annotation_at_position(x, y)
            if target is None:
                QToolTip.showText(self.mapToGlobal(self.cursor().pos()), "Click an annotation to move it.")
                return
            self._annotation_move_target = target
            self._annotation_dragging = True
            self._annotation_drag_last = (int(x), int(y))
            self._highlight_annotation(target)
            QToolTip.showText(self.mapToGlobal(self.cursor().pos()), "Drag the annotation and release the mouse to finish.")
            return
        QToolTip.showText(self.mapToGlobal(self.cursor().pos()), "Drag the annotation and release the mouse to finish.")

    def _handle_delete_click(self, x: int, y: int):
        target = self._find_annotation_at_position(x, y)
        if target is None:
            QToolTip.showText(self.mapToGlobal(self.cursor().pos()), "Click an annotation to delete it.")
            return
        annotation = target["annotation"]
        self._remove_annotation(target)
        self.signals.annotation_added.emit(self._annotation_layer_name, {
            "action": "delete",
            "annotation": annotation,
        })
        self._end_annotation_mode()

    def _find_annotation_at_position(self, x: int, y: int):
        def _distance_to_segment(px, py, x1, y1, x2, y2):
            dx = x2 - x1
            dy = y2 - y1
            if dx == 0 and dy == 0:
                return np.hypot(px - x1, py - y1)
            t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
            t = max(0.0, min(1.0, t))
            proj_x = x1 + t * dx
            proj_y = y1 + t * dy
            return np.hypot(px - proj_x, py - proj_y)

        for entry in reversed(self._annotations):
            ann = entry["annotation"]
            if ann["type"] == "text":
                px, py = ann["position"]
                if (x - px) ** 2 + (y - py) ** 2 < 900:
                    return entry
            elif ann["type"] == "arrow":
                sx, sy = ann["position"]
                ex, ey = ann["end_position"]
                if _distance_to_segment(x, y, sx, sy, ex, ey) < 18:
                    return entry
                if (x - sx) ** 2 + (y - sy) ** 2 < 900:
                    return entry
                if (x - ex) ** 2 + (y - ey) ** 2 < 900:
                    return entry
                if ann.get("label_position") is not None:
                    lx, ly = ann["label_position"]
                    if (x - lx) ** 2 + (y - ly) ** 2 < 900:
                        return entry
        return None

    def _move_annotation(self, entry, x: int, y: int):
        annotation = entry["annotation"]
        if annotation["type"] == "text":
            annotation["position"] = (int(x), int(y))
            self._safe_remove_actor(annotation, "actor")
            annotation["actor"] = self._create_text_actor(annotation)
        else:
            start = annotation["position"]
            end = annotation["end_position"]
            dx = int(x) - start[0]
            dy = int(y) - start[1]
            annotation["position"] = (start[0] + dx, start[1] + dy)
            annotation["end_position"] = (end[0] + dx, end[1] + dy)
            if annotation.get("label_position") is not None:
                lx, ly = annotation["label_position"]
                annotation["label_position"] = (lx + dx, ly + dy)
            self._safe_remove_actor(annotation, "actor")
            self._safe_remove_actor(annotation, "text_actor")
            annotation["actor"] = self._create_arrow_actor(annotation)
        self.plotter.ren_win.Render()

    def _drag_annotation(self, entry, x: int, y: int):
        if self._annotation_drag_last is None:
            self._annotation_drag_last = (int(x), int(y))
            return
        dx = int(x) - self._annotation_drag_last[0]
        dy = int(y) - self._annotation_drag_last[1]
        if dx == 0 and dy == 0:
            return
        annotation = entry["annotation"]
        if annotation["type"] == "text":
            annotation["position"] = (annotation["position"][0] + dx, annotation["position"][1] + dy)
            actor = annotation.get("actor")
            if actor is not None:
                actor.SetDisplayPosition(*annotation["position"])
        else:
            start = annotation["position"]
            end = annotation["end_position"]
            annotation["position"] = (start[0] + dx, start[1] + dy)
            annotation["end_position"] = (end[0] + dx, end[1] + dy)
            actor = annotation.get("actor")
            if actor is not None:
                current_pos = actor.GetPosition()
                if current_pos is None:
                    actor.SetPosition(dx, dy)
                else:
                    actor.SetPosition(current_pos[0] + dx, current_pos[1] + dy)
            if annotation.get("label_position") is not None:
                lx, ly = annotation["label_position"]
                annotation["label_position"] = (lx + dx, ly + dy)
                text_actor = annotation.get("text_actor")
                if text_actor is not None:
                    text_actor.SetDisplayPosition(*annotation["label_position"])
        self._annotation_drag_last = (int(x), int(y))
        if self._annotation_move_target is entry:
            self._highlight_annotation(entry)
        self.plotter.ren_win.Render()

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
        for key in ("actor", "text_actor"):
            self._safe_remove_actor(annotation, key)
        if self._annotation_move_target is entry:
            self._annotation_move_target = None
        self._clear_annotation_highlight()
        if entry in self._annotations:
            self._annotations.remove(entry)
        self.plotter.ren_win.Render()

    def _build_line_polydata(self, points):
        """
        points: list of (x, y) or (x, y, z)
        """

        if len(points) < 2:
            return None

        vtk_points = vtk.vtkPoints()

        for p in points:
            if len(p) == 2:
                x, y = p
                z = 0.0
            else:
                x, y, z = p

            vtk_points.InsertNextPoint(x, y, z)

        lines = vtk.vtkCellArray()

        line = vtk.vtkPolyLine()
        line.GetPointIds().SetNumberOfIds(len(points))

        for i in range(len(points)):
            line.GetPointIds().SetId(i, i)

        lines.InsertNextCell(line)

        poly = vtk.vtkPolyData()
        poly.SetPoints(vtk_points)
        poly.SetLines(lines)

        return poly

    def _build_arrow_polydata(self, start, end):
        points = vtk.vtkPoints()
        points.InsertNextPoint(start[0], start[1], 0)
        points.InsertNextPoint(end[0], end[1], 0)

        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length = max(np.hypot(dx, dy), 1.0)
        ux = dx / length
        uy = dy / length

        head_len = min(30.0, length * 0.25)
        head_width = max(5.0, head_len * 0.35)
        base_x = end[0] - ux * head_len
        base_y = end[1] - uy * head_len

        perp_x = -uy
        perp_y = ux

        points.InsertNextPoint(base_x + perp_x * head_width, base_y + perp_y * head_width, 0)
        points.InsertNextPoint(base_x - perp_x * head_width, base_y - perp_y * head_width, 0)

        lines = vtk.vtkCellArray()
        line = vtk.vtkLine()
        line.GetPointIds().SetId(0, 0)
        line.GetPointIds().SetId(1, 1)
        lines.InsertNextCell(line)

        triangle = vtk.vtkTriangle()
        triangle.GetPointIds().SetId(0, 1)
        triangle.GetPointIds().SetId(1, 2)
        triangle.GetPointIds().SetId(2, 3)

        tris = vtk.vtkCellArray()
        tris.InsertNextCell(triangle)

        poly = vtk.vtkPolyData()
        poly.SetPoints(points)
        poly.SetLines(lines)
        poly.SetPolys(tris)

        triangle = vtk.vtkTriangle()
        triangle.GetPointIds().SetId(0, 1)
        triangle.GetPointIds().SetId(1, 2)
        triangle.GetPointIds().SetId(2, 3)

        tris = vtk.vtkCellArray()
        tris.InsertNextCell(triangle)

        poly = vtk.vtkPolyData()
        poly.SetPoints(points)
        poly.SetLines(lines)
        poly.SetPolys(tris)
        
        return poly

    def _build_text_actor(self, annotation, preview=False):

        text_actor = vtk.vtkTextActor()
        text_actor.SetInput(annotation.get("text", ""))

        text_pos = annotation.get("text_position", (0,0))
        if text_pos:
            text_actor.SetDisplayPosition(*text_pos)

        prop = text_actor.GetTextProperty()
        prop.SetFontSize(annotation.get("font_size", 12))

        color = annotation.get("color", "#000000")
        if isinstance(color, str):
            qcolor = QColor(color)
        else:
            qcolor = color
        rgb = qcolor.getRgbF()[:3]
        prop.SetColor(*rgb)

        prop.SetBold(True)


        prop.SetBackgroundColor(1.0, 1.0, 1.0)


        if preview:
            prop.SetBackgroundOpacity(0.4)
        else:
            prop.SetBackgroundOpacity(0.75)
        
        return text_actor

    def _build_line_actor(self, annotation, preview=False):

        poly = self._build_line_polydata(
            annotation.get("points", [])
        )

        if poly is None:
            return None

        mapper = vtk.vtkPolyDataMapper2D()
        mapper.SetInputData(poly)

        line_actor = vtk.vtkActor2D()
        line_actor.SetMapper(mapper)

        color = annotation.get("color", "#000000")
        if isinstance(color, str):
            qcolor = QColor(color)
        else:
            qcolor = color
        rgb = qcolor.getRgbF()[:3]
        line_width = annotation.get("line_width", 2)
        line_actor.GetProperty().SetColor(*rgb)
        line_actor.GetProperty().SetLineWidth(line_width)

        if preview:
            line_actor.GetProperty().SetOpacity(0.6)
            line_actor.GetProperty().SetLineStipplePattern(0xF0F0)
        else:
            line_actor.GetProperty().SetOpacity(1.0)
            line_actor.GetProperty().SetLineStipplePattern(0xFFFF)

        return line_actor

    def _build_line_text_actors(self, annotation: dict, preview=False):

        line_actor = self._build_line_actor(annotation)

        text_actor = self._build_text_actor(annotation)

        return {
            "line_actor": line_actor,
            "text_actor": text_actor
        }

    def _create_text_actor(self, annotation: dict):
        actor = self._build_text_actor(annotation)
        self._overlay_renderer.AddActor(actor)
        self.plotter.ren_win.Render()
        return actor

    def _create_line_text_actor(self, annotation):
        actors = self._build_line_text_actors(annotation, preview=False)
        self._overlay_renderer.AddActor(actors["line_actor"])
        self._overlay_renderer.AddActor(actors["text_actor"])
        self.plotter.ren_win.Render()
        return actors

    def _remove_annotation_actors_for_layer(self, name: str):
        if name == "all":
            self._clear_annotation_actors()
            return
        remaining = []
        for entry in self._annotations:
            if entry["layer_name"] == name:
                for key in ("actor", "text_actor"):
                    self._safe_remove_actor(entry["annotation"], key)
            else:
                remaining.append(entry)
        self._annotations = remaining
        self._clear_annotation_highlight()
        self.plotter.ren_win.Render()

    def _clear_annotation_actors(self):
        for entry in self._annotations:
            for key in ("actor", "text_actor"):
                self._safe_remove_actor(entry["annotation"], key)
        self._annotations = []
        self._clear_annotation_highlight()
        self.plotter.ren_win.Render()

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
        print(f"Saved screenshot to: {path}")
        return path

    def close(self):
        self.plotter.close()
