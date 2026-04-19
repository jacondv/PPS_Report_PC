"""
Main application window — Tunnel Concrete Thickness Analyzer.
Layer-based architecture: original cloud + independent segments.
Report always uses only the visible layers.
"""

import os
import sys
import json
from matplotlib import container
import numpy as np
from typing import Optional

from PyQt5.QtWidgets import (
    QFrame, QLineEdit, QMainWindow, QSizePolicy, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QToolBar, QAction, QFileDialog, QMessageBox, QGroupBox,
    QLabel, QPushButton, QSpinBox, QDoubleSpinBox, QComboBox,
    QListWidget, QListWidgetItem, QProgressBar, QStatusBar,
    QFormLayout, QScrollArea, QCheckBox, QMenu, QInputDialog,
    QAbstractItemView,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize, QPoint, QSettings
from PyQt5.QtGui import QFont, QColor, QPixmap, QIcon

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gui.viewer_3d_new import PointCloudViewer
from core.ply_loader import load_ply, get_ply_fields
from core.filename_parser import parse_filename, ProjectInfo
from core.layer_manager import Layer, LayerManager
from core.calculator import (
    calculate_area_and_volume, calculate_thickness_distribution,
    CalculationResult, ThicknessDistribution,
)
# from report.pdf_generator import generate_report


# ============================================================ background worker
class CalculationWorker(QThread):
    finished = pyqtSignal(object, object)
    error    = pyqtSignal(str)
    progress = pyqtSignal(int)

    def __init__(self, points, distances, target_min, target_max):
        super().__init__()
        self.points      = points
        self.distances   = distances
        self.target_min  = target_min
        self.target_max  = target_max

    def run(self):
        try:
            self.progress.emit(10)
            calc = calculate_area_and_volume(self.points, self.distances, target_min=self.target_min)
            self.progress.emit(70)
            dist = calculate_thickness_distribution(
                self.distances, self.target_min, self.target_max)
            self.progress.emit(100)
            self.finished.emit(calc, dist)
            print("Calculation completed successfully.")
        except Exception as e:
            self.error.emit(str(e))
            


# ============================================================ main window
class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tunnel Concrete Thickness Analyzer")
        self.setGeometry(100, 100, 1440, 900)

        # Data
        self.layer_manager   = LayerManager()
        self.project_info: Optional[ProjectInfo] = None
        self.calc_result:   Optional[CalculationResult]     = None
        self.thickness_dist: Optional[ThicknessDistribution] = None

        # Pending selection (from polygon / distance range)
        self._sel_pts:   Optional[np.ndarray] = None
        self._sel_dists: Optional[np.ndarray] = None

        # Settings
        self.target_min = 50.0
        self.target_max = 150.0

        self._setup_ui()
        self._setup_menubar()
        self._setup_toolbar()
        self._setup_statusbar()

        self.settings = QSettings('TunnelAnalyzer', 'TunnelConcreteThicknessAnalyzer')
        self._load_settings()

    # ================================================================== UI
    def _setup_ui(self):
        c = QWidget()
        self.setCentralWidget(c)
        lay = QHBoxLayout(c)
        lay.setContentsMargins(1, 1, 1, 1)

        sp = QSplitter(Qt.Horizontal)
        sp.addWidget(self._create_left_panel())
        sp.addWidget(self._create_segment_panel())

        self.viewer = PointCloudViewer()
        self.viewer.signals.selection_changed.connect(self._on_selection_changed)
        self.viewer.signals.selection_cleared.connect(self._on_selection_cleared)
        self.viewer.signals.polygon_mode_ended.connect(self._on_polygon_mode_ended)
        self.viewer.signals.annotation_added.connect(self._on_annotation_added)
        # Connect visualization controls that need viewer (created after left panel)
        self.spin_point_size.valueChanged.connect(self.viewer.set_point_size)
        self.cmb_colormap.currentTextChanged.connect(self.viewer.set_colormap)
        sp.addWidget(self.viewer)

        sp.addWidget(self._create_right_panel())
        sp.setSizes([280, 260, 620, 280])

        lay.addWidget(sp)

    # ------------------------------------------------------------------ left panel
    def _create_left_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("left_panel")
        panel.setStyleSheet("""
            QWidget#left_panel {
                border: 1px solid #d0d7de;
                border-radius: 0px;
            }
        """)
        panel.setMinimumWidth(260)
        panel.setMaximumWidth(360)
        lay = QVBoxLayout(panel)
        lay.setSpacing(8)

        # ---- File info ----
        fg = QGroupBox("File Information")
        fl = QFormLayout(fg)

        self.lbl_filename = QLineEdit("File is not loaded yet")
        self.lbl_filename.setReadOnly(True)
        self.lbl_filename.setStyleSheet("""
            QLineEdit {
                border: none;
                background: transparent;
                padding: 0px;
            }
        """)
        self.lbl_project  = QLabel("-")
        self.lbl_job      = QLabel("-")
        self.lbl_time     = QLabel("-")
        fl.addRow("File:",      self.lbl_filename)
        fl.addRow("Project:",   self.lbl_project)
        fl.addRow("Job:",       self.lbl_job)
        fl.addRow("Time:",      self.lbl_time)
        lay.addWidget(fg)

        # ---- Settings ----
        sg = QGroupBox("Analysis Settings")
        sl = QFormLayout(sg)

        self.cmb_dist_field = QComboBox()
        self.cmb_dist_field.addItem("distances")
        sl.addRow("Thickness Field:", self.cmb_dist_field)

        self.spin_target_min = QDoubleSpinBox()
        self.spin_target_min.setRange(0, 9999); self.spin_target_min.setValue(self.target_min)
        self.spin_target_min.setSuffix(" mm")
        sl.addRow("Min target thickness:", self.spin_target_min)

        self.spin_target_max = QDoubleSpinBox()
        self.spin_target_max.setRange(0, 9999); self.spin_target_max.setValue(self.target_max)
        self.spin_target_max.setSuffix(" mm")
        sl.addRow("Max target thickness:", self.spin_target_max)

        # Connect target changes
        self.spin_target_min.valueChanged.connect(self._on_target_changed)
        self.spin_target_max.valueChanged.connect(self._on_target_changed)

        lay.addWidget(sg)

        # ---- Visualization ----
        vg = QGroupBox("Visualization")
        vl = QFormLayout(vg)

        self.spin_point_size = QSpinBox()
        self.spin_point_size.setRange(1, 10); self.spin_point_size.setValue(1)
        vl.addRow("Point Size:", self.spin_point_size)

        self.cmb_colormap = QComboBox()
        self.cmb_colormap.addItems(['jet', 'viridis', 'plasma', 'coolwarm', 'rainbow'])
        self.cmb_colormap.hide()
        # vl.addRow("Colormap:", self.cmb_colormap)
        lay.addWidget(vg)
        lay.addStretch()
        return panel

    # ------------------------------------------------------------------ segment panel
    def _create_segment_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("segment_panel")
        panel.setStyleSheet("""
            QWidget#segment_panel {
                border: 1px solid #d0d7de;
                border-radius: 0px;
            }
        """)
        panel.setMinimumWidth(260)
        panel.setMaximumWidth(360)
        lay = QVBoxLayout(panel)
        lay.setSpacing(10)

        sel_box = QGroupBox("Create Segment Tools")
        sel_lay = QVBoxLayout(sel_box)

        rr = QHBoxLayout()
        self.spin_sel_min = QDoubleSpinBox()
        self.spin_sel_min.setRange(-9999, 99999); self.spin_sel_min.setValue(75)
        self.spin_sel_max = QDoubleSpinBox()
        self.spin_sel_max.setRange(-9999, 99999); self.spin_sel_max.setValue(100)
        rr.addWidget(QLabel("From:")); rr.addWidget(self.spin_sel_min)
        rr.addWidget(QLabel("To:")); rr.addWidget(self.spin_sel_max)
        sel_lay.addLayout(rr)

        btn_range = QPushButton("📏 Select by Thickness")
        btn_range.clicked.connect(self._on_select_by_range)
        sel_lay.addWidget(btn_range)
        lay.addWidget(sel_box)

        self.btn_polygon = QPushButton("🖊 Select Polygon")
        self.btn_polygon.setCheckable(True)
        self.btn_polygon.setMinimumHeight(32)
        self.btn_polygon.setToolTip("Draw an area to select points")
        self.btn_polygon.toggled.connect(self._on_polygon_toggled)
        sel_lay.addWidget(self.btn_polygon)


        self.lbl_sel_count = QLabel("No selection")
        self.lbl_sel_count.setStyleSheet("color:#2c5282; font-weight:bold; font-size:10px;")
        lay.addWidget(self.lbl_sel_count)


        self.btn_add_seg = QPushButton("✅ Create Segment")
        self.btn_add_seg.clicked.connect(self._on_add_segment)
        self.btn_clear_sel = QPushButton("❌ Clear Selection")
        self.btn_clear_sel.clicked.connect(self._on_clear_selection)
        sel_lay.addWidget(self.btn_add_seg)
        sel_lay.addWidget(self.btn_clear_sel)

        layer_box = QGroupBox("Layer Manager")
        layer_box.setStyleSheet("QGroupBox { margin-top: 10px; }")
        layer_layout = QVBoxLayout(layer_box)

        hint = QLabel("☑ Hide/Show  |  Right-click → Options")
        hint.setStyleSheet("color:#718096; font-size:9px;")
        layer_layout.addWidget(hint)

        self.list_layers = QListWidget()
        self.list_layers.setMinimumHeight(180)
        self.list_layers.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list_layers.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_layers.customContextMenuRequested.connect(self._on_layer_context_menu)
        self.list_layers.itemChanged.connect(self._on_layer_item_changed)
        self.list_layers.currentItemChanged.connect(self._on_layer_selected)
        layer_layout.addWidget(self.list_layers)
        lay.addWidget(layer_box)


        action_box = QGroupBox("Actions")
        action_layout = QVBoxLayout(action_box)

        # row_add = QHBoxLayout()

        # row_add.addWidget(self.btn_add_seg)
        # row_add.addWidget(self.btn_clear_sel)
        # action_layout.addLayout(row_add)

        note = QLabel("Calculation and PDF export only use visible layers (☑).")
        note.setWordWrap(True)
        note.setStyleSheet("color:#718096; font-size:9px;")
        action_layout.addWidget(note)

        self.btn_calculate = QPushButton("📊 Calculate")
        self.btn_calculate.setMinimumHeight(40)
        self.btn_calculate.clicked.connect(self._on_calculate)
        action_layout.addWidget(self.btn_calculate)

        self.btn_export_pdf = QPushButton("📄 PDF Report")
        self.btn_export_pdf.setMinimumHeight(40)
        self.btn_export_pdf.clicked.connect(self._on_export_pdf)
        action_layout.addWidget(self.btn_export_pdf)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        action_layout.addWidget(self.progress_bar)

        lay.addWidget(action_box)
        lay.addStretch()
        return panel

    # ------------------------------------------------------------------ right panel
    def _create_right_panel(self) -> QWidget:
        panel = QWidget()

        panel.setMinimumWidth(260)
        panel.setMaximumWidth(360)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setSpacing(10)
       

        # Results
        rg = QGroupBox("Analysis Results")
        rl = QFormLayout(rg)
        bold = QFont("Arial", 12, QFont.Bold)

        self.lbl_area           = QLabel("-"); self.lbl_area.setFont(bold)
        self.lbl_target_coverage  = QLabel("-"); self.lbl_target_coverage.setFont(bold)
        self.lbl_volume         = QLabel("-"); self.lbl_volume.setFont(bold)
        self.lbl_mean_thickness = QLabel("-"); self.lbl_mean_thickness.setFont(bold)
        self.lbl_min_thickness  = QLabel("-")
        self.lbl_max_thickness  = QLabel("-")
        self.lbl_std_thickness  = QLabel("-")
        self.lbl_num_points     = QLabel("-")
        rl.addRow("Surface Area (m²):",   self.lbl_area)
        rl.addRow("Target Coverage (m²):", self.lbl_target_coverage)
        rl.addRow("Volume (m³):",    self.lbl_volume)
        rl.addRow("Mean Thickness (mm):",   self.lbl_mean_thickness)
        rl.addRow("Min Thickness (mm):",  self.lbl_min_thickness)
        rl.addRow("Max Thickness (mm):",  self.lbl_max_thickness)
        rl.addRow("Standard Deviation:",    self.lbl_std_thickness)
        rl.addRow("Number of Points:",          self.lbl_num_points)
        lay.addWidget(rg)

        # Distribution
        dg = QGroupBox("Thickness Distribution")
        dl = QVBoxLayout(dg)
        self.lbl_below  = QLabel("-"); self.lbl_below.setStyleSheet("color:#c53030;font-weight:bold;")
        self.lbl_within = QLabel("-"); self.lbl_within.setStyleSheet("color:#276749;font-weight:bold;")
        self.lbl_above  = QLabel("-"); self.lbl_above.setStyleSheet("color:#315aff;font-weight:bold;")
        dl.addWidget(QLabel("Below Target:")); dl.addWidget(self.lbl_below)
        dl.addWidget(QLabel("Within Target:"));  dl.addWidget(self.lbl_within)
        dl.addWidget(QLabel("Above Target:")); dl.addWidget(self.lbl_above)
        lay.addWidget(dg)

        lay.addStretch()
        scroll.setWidget(content)
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.addWidget(scroll)
        return panel

    # ------------------------------------------------------------------ menu / toolbar
    def _setup_menubar(self):
        mb = self.menuBar()
        fm = mb.addMenu("File")
        for label, shortcut, fn in [
            ("Open PLY File…",       "Ctrl+O", self._on_open_file),
            ("Export PDF Report…",  "Ctrl+E", self._on_export_pdf),
            ("Exit",              "Ctrl+Q", self.close),
        ]:
            a = QAction(label, self); a.setShortcut(shortcut); a.triggered.connect(fn)
            if label == "Exit":
                fm.addSeparator()
            fm.addAction(a)

        vm = mb.addMenu("View")
        for label, key, fn in [
            ("Reset View", "R", self.viewer.reset_view),
            ("Top View",   "T", self.viewer.view_top),
            ("Front View", "F", self.viewer.view_front),
            ("Side View",  "S", self.viewer.view_side),
            ("Back View", "B", lambda: self.viewer.plotter.view_xz(negative=True)),
            ("Left View",  "L", lambda: self.viewer.plotter.view_yz(negative=True)),
            ("Iso View",   "I", lambda: self.viewer.plotter.view_isometric()),
        ]:
            a = QAction(label, self); a.setShortcut(key); a.triggered.connect(fn)
            vm.addAction(a)

        hm = mb.addMenu("Help")
        ab = QAction("About", self); ab.triggered.connect(self._show_about)
        hm.addAction(ab)

    def _setup_toolbar(self):
        tb = QToolBar("Main"); tb.setIconSize(QSize(24, 24))
        self.addToolBar(tb)
        for label, fn in [
            ("Open File",    self._on_open_file),
            ("Reset View", self.viewer.reset_view),
            ("Calculate",  self._on_calculate),
            ("Export PDF",   self._on_export_pdf),
        ]:
            a = QAction(label, self); a.triggered.connect(fn)
            tb.addAction(a); tb.addSeparator()

    def _setup_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("Ready — Please open a PLY file")

    # ================================================================== file
    def _on_open_file(self):
        fp, _ = QFileDialog.getOpenFileName(
            self, "Open Point Cloud File", "", "PLY Files (*.ply);;All Files (*)")
        if fp:
            self._load_file(fp)

    def _load_file(self, filepath: str):
        try:
            self.statusbar.showMessage(f"Loading: {filepath}…")

            fields = get_ply_fields(filepath)
            self.cmb_dist_field.clear()
            self.cmb_dist_field.addItems(fields)
            for f in ('distances', 'distance', 'thickness', 'scalar_distances'):
                if f in fields:
                    self.cmb_dist_field.setCurrentText(f); break

            cloud_data = load_ply(filepath, self.cmb_dist_field.currentText())
            self.project_info = parse_filename(filepath)

            # Load job info
            dir_path = os.path.dirname(filepath)
            job_info_path = os.path.join(dir_path, 'job_info.json')
            if os.path.exists(job_info_path):
                with open(job_info_path, 'r') as f:
                    job_info = json.load(f)
                target_thickness = job_info.get('parameters', {}).get('target_thickness', 30)
                tolerance = job_info.get('parameters', {}).get('tolerance', 10)
                min_target = target_thickness - tolerance
                max_target = target_thickness + tolerance
            else:
                min_target = 40
                max_target = 60

            # Set thickness targets in viewer
            self.viewer.set_thickness_targets(min_target, max_target)
            self.spin_target_min.setValue(min_target)
            self.spin_target_max.setValue(max_target)

            # Reset everything
            self.layer_manager.clear()
            self.viewer.clear_all_layers()
            self.list_layers.blockSignals(True)
            self.list_layers.clear()
            self.list_layers.blockSignals(False)
            self._clear_results()
            self._reset_selection()

            # Add original layer
            layer = self.layer_manager.set_original(
                name=os.path.basename(filepath),
                points=cloud_data.points,
                distances=cloud_data.distances,
            )
            self.viewer.sync_layers(self.layer_manager.layers)
            self.viewer.add_layer(layer)
            self.viewer.reset_view()
            self._add_layer_item(layer)

            # Update file info labels
            self.lbl_filename.setText(self.project_info.original_filename)
            self.lbl_project.setText(self.project_info.project_name)
            self.lbl_job.setText(self.project_info.job_number)
            self.lbl_time.setText(self.project_info.formatted_time)

            self.statusbar.showMessage(
                f"Loaded: {os.path.basename(filepath)}  ({cloud_data.num_points:,} point)"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Cannot load file:\n{e}")
            self.statusbar.showMessage("Error loading file")

    # ================================================================== layer list helpers
    def _layer_icon(self, layer: Layer) -> QIcon:
        pix = QPixmap(14, 14)
        if layer.color is None:
            pix.fill(QColor(50, 130, 255))   # blue = original
        else:
            r, g, b = (int(c * 255) for c in layer.color)
            pix.fill(QColor(r, g, b))
        return QIcon(pix)

    def _layer_display_text(self, layer: Layer) -> str:
        count = len(getattr(layer, "annotations", []))
        note_flag = f" 📝({count})" if count else ""
        return f"{layer.name}{note_flag}  ({layer.num_points:,} điểm)"

    def _layer_tooltip(self, layer: Layer) -> str:
        annotations = getattr(layer, "annotations", [])
        if not annotations:
            return ""
        return "\n".join(f"- {ann['text']}" for ann in annotations)

    def _uncheck_all_layers(self):
        for i in range(self.list_layers.count()):
            item = self.list_layers.item(i)
            item.setCheckState(Qt.Unchecked)

    def _add_layer_item(self, layer: Layer):
        item = QListWidgetItem(self._layer_display_text(layer))
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked if layer.visible else Qt.Unchecked)
        item.setData(Qt.UserRole, layer.name)
        item.setIcon(self._layer_icon(layer))
        if getattr(layer, "annotations", []):
            item.setToolTip(self._layer_tooltip(layer))
        if layer.is_original:
            f = item.font(); f.setBold(True); item.setFont(f)
        self.list_layers.blockSignals(True)
        self.list_layers.addItem(item)
        self.list_layers.blockSignals(False)
        return item

    def _item_for(self, name: str) -> Optional[QListWidgetItem]:
        for i in range(self.list_layers.count()):
            it = self.list_layers.item(i)
            if it.data(Qt.UserRole) == name:
                return it
        return None

    def _on_layer_item_changed(self, item: QListWidgetItem):
        name    = item.data(Qt.UserRole)
        visible = item.checkState() == Qt.Checked
        layer   = self.layer_manager.get(name)
        if layer:
            layer.visible = visible
        self.viewer.set_layer_visible(name, visible)

    def _on_layer_selected(self, current: QListWidgetItem, previous: QListWidgetItem):
        if current is None:
            return
        name = current.data(Qt.UserRole)
        self.viewer.set_annotation_layer(name)

    # ------------------------------------------------------------------ layer context menu
    def _on_layer_context_menu(self, pos: QPoint):
        item = self.list_layers.itemAt(pos)
        if item is None:
            return
        name  = item.data(Qt.UserRole)
        layer = self.layer_manager.get(name)
        if layer is None:
            return

        menu = QMenu(self)
        act_show     = menu.addAction("👁  Show")
        act_hide     = menu.addAction("🙈  Hide")
        menu.addSeparator()
        act_calc     = menu.addAction("📊  Calculate for this layer")
        act_export   = menu.addAction("📄  Export PDF for this layer")
        menu.addSeparator()
        act_note     = menu.addAction("�  Annotate this layer")
        act_rename   = menu.addAction("✏  Rename")
        if not layer.is_original:
            menu.addSeparator()
            act_delete = menu.addAction("🗑  Delete layer")
        else:
            act_delete = None

        chosen = menu.exec_(self.list_layers.mapToGlobal(pos))

        if chosen == act_show:
            item.setCheckState(Qt.Checked)
        elif chosen == act_hide:
            item.setCheckState(Qt.Unchecked)
        elif chosen == act_calc:
            self.list_layers.setCurrentItem(item)
            self._on_calculate()
        elif chosen == act_export:
            self._calc_and_export_layer(layer)
        elif chosen == act_rename:
            self._rename_layer(name, item)
        elif chosen == act_note:
            self._annotate_layer(layer, item)
        elif act_delete and chosen == act_delete:
            self._delete_layer(name)

    def _rename_layer(self, old_name: str, item: QListWidgetItem):
        new_name, ok = QInputDialog.getText(
            self, "Rename Layer", "New name:", text=old_name)
        if not ok or not new_name.strip() or new_name == old_name:
            return
        new_name = new_name.strip()
        layer = self.layer_manager.get(old_name)
        if layer is None:
            return
        self.layer_manager.rename(old_name, new_name)
        # update actor key in viewer
        actor = self.viewer._actors.pop(old_name, None)
        if actor:
            self.viewer._actors[new_name] = actor
        item.setText(self._layer_display_text(layer))
        item.setData(Qt.UserRole, new_name)

    def _delete_layer(self, name: str):
        self.layer_manager.remove(name)
        self.viewer.remove_layer(name)
        self.viewer.sync_layers(self.layer_manager.layers)
        item = self._item_for(name)
        if item:
            self.list_layers.takeItem(self.list_layers.row(item))

    # ================================================================== selection
    def _on_polygon_toggled(self, checked: bool):
        if checked:
            if not self.layer_manager.layers:
                self.btn_polygon.setChecked(False)
                QMessageBox.warning(self, "Warning", "Please load a PLY file first!")
                return
            self.btn_polygon.setText("⏹  Cancel polygon drawing")
            self.statusbar.showMessage(
                "Drawing polygon: Left-click to add points  |  Double-click/Enter: complete  |  ESC: cancel"
            )
            self.viewer.enable_polygon_mode()
        else:
            self.btn_polygon.setText("✏  Draw polygon")
            self.viewer.disable_polygon_mode()
            self.statusbar.showMessage("Ready")

    def _on_polygon_mode_ended(self):
        self.btn_polygon.blockSignals(True)
        self.btn_polygon.setChecked(False)
        self.btn_polygon.setText("✏  Draw polygon")
        self.btn_polygon.blockSignals(False)

    def _on_select_by_range(self):
        if not self.layer_manager.layers:
            return
        self.viewer.select_by_distance_range(
            self.spin_sel_min.value(), self.spin_sel_max.value())

    def _on_target_changed(self):
        min_t = self.spin_target_min.value()
        max_t = self.spin_target_max.value()
        self.viewer.set_thickness_targets(min_t, max_t)

    def _on_selection_changed(self, pts: np.ndarray, dists: np.ndarray):
        self._sel_pts   = pts
        self._sel_dists = dists
        n = len(pts) if pts is not None else 0
        print(f"[DEBUG] selection changed -> {n} points")
        self.lbl_sel_count.setText(f"Selected area: {n:,} points")
        self.statusbar.showMessage(f"Selected {n:,} points")

    def _on_selection_cleared(self):
        self._reset_selection()

    def _reset_selection(self):
        self._sel_pts   = None
        self._sel_dists = None
        self.lbl_sel_count.setText("No selection")

    def _on_clear_selection(self):
        self.viewer.clear_selection()

    def _on_add_segment(self):
        if self._sel_pts is None or len(self._sel_pts) == 0:
            QMessageBox.warning(self, "Warning", "No selection!")
            return

        layer = self.layer_manager.add_segment(
            points=self._sel_pts.copy(),
            distances=self._sel_dists.copy(),
        )
        self.viewer.sync_layers(self.layer_manager.layers)
        self._uncheck_all_layers()
        self.viewer.add_layer(layer)
        item = self._add_layer_item(layer)
        self.list_layers.setCurrentItem(item)
        self.viewer.clear_selection()
        self._reset_selection()
        self.statusbar.showMessage(f"Đã tạo {layer.name} ({layer.num_points:,} điểm)")

    # ================================================================== calculation
    def _on_calculate(self):
        selected_items = self.list_layers.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Warning",
                                "Please select one or more layers!")
            return
        
        # Collect points and distances from all selected layers
        all_points = []
        all_distances = []
        
        for item in selected_items:
            layer_name = item.data(Qt.UserRole)
            layer = self.layer_manager.get(layer_name)
            if layer is None:
                continue
            if len(layer.points) > 0:
                all_points.append(layer.points)
                all_distances.append(layer.distances)
        
        if not all_points:
            QMessageBox.warning(self, "Warning",
                                "Selected layers have no points!")
            return
        
        # Combine points and distances from all selected layers
        pts = np.vstack(all_points)
        dists = np.concatenate(all_distances)
        
        self._run_calculation(pts, dists)

    def _run_calculation(self, pts: np.ndarray, dists: np.ndarray):
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.btn_calculate.setEnabled(False)

        self.worker = CalculationWorker(
            pts, dists,
            self.spin_target_min.value(),
            self.spin_target_max.value(),
        )
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.finished.connect(self._on_calc_done)
        self.worker.error.connect(self._on_calc_error)
        self.worker.start()

    def _on_calc_done(self, calc: CalculationResult, dist: ThicknessDistribution):
        self.calc_result    = calc
        self.thickness_dist = dist

        self.lbl_area.setText(f"{calc.surface_area_m2:.1f}")
        self.lbl_target_coverage.setText(f"{calc.area_reached_target_m2:.1f}")
        self.lbl_volume.setText(f"{calc.volume_m3:.1f}")
        self.lbl_mean_thickness.setText(f"{calc.mean_thickness_mm:.0f}")
        self.lbl_min_thickness.setText(f"{calc.min_thickness_mm:.0f}")
        self.lbl_max_thickness.setText(f"{calc.max_thickness_mm:.0f}")
        self.lbl_std_thickness.setText(f"{calc.std_thickness_mm:.0f}")
        self.lbl_num_points.setText(f"{calc.num_points:,}")

        self.lbl_below.setText(
            f"{dist.below_target:,} points ({dist.below_target_percent:.1f}%)")
        self.lbl_within.setText(
            f"{dist.within_target:,} points ({dist.within_target_percent:.1f}%)")
        self.lbl_above.setText(
            f"{dist.above_target:,} points ({dist.above_target_percent:.1f}%)")

        self.progress_bar.setVisible(False)
        self.btn_calculate.setEnabled(True)
        self.statusbar.showMessage("Completed calculation")

    def _on_calc_error(self, msg: str):
        self.progress_bar.setVisible(False)
        self.btn_calculate.setEnabled(True)
        QMessageBox.critical(self, "Error", f"Error occurred while calculating:\n{msg}")

    def _annotate_layer(self, layer: Layer, item: QListWidgetItem = None):
        if not layer.visible:
            QMessageBox.warning(self, "Warning", "Layer must be visible to place an annotation on the view.")
            return
        text, ok = QInputDialog.getMultiLineText(
            self,
            "Add Annotation",
            f"Enter annotation text for {layer.name}:"
        )
        if not ok or not text.strip():
            return
        self.statusbar.showMessage(
            f"Click on the view to place the annotation for {layer.name}."
        )
        self.viewer.enable_annotation_mode(layer.name, text.strip())

    def _on_annotate_layer(self):
        item = self.list_layers.currentItem()
        if item is None:
            QMessageBox.warning(self, "Warning", "Please select a layer first!")
            return
        layer = self.layer_manager.get(item.data(Qt.UserRole))
        if layer is None:
            QMessageBox.warning(self, "Warning", "Selected layer not found.")
            return
        self._annotate_layer(layer, item)

    def _on_annotation_added(self, layer_name: str, event: object):
        layer = self.layer_manager.get(layer_name)
        item = self._item_for(layer_name)
        if layer is None or item is None:
            return

        action = event.get("action") if isinstance(event, dict) else None
        annotation = event.get("annotation") if isinstance(event, dict) else event

        if action == "add":
            layer.annotations.append(annotation)
        elif action == "move":
            found = None
            for existing in layer.annotations:
                if existing is annotation or existing.get("type") == annotation.get("type") and existing.get("position") == annotation.get("position"):
                    found = existing
                    break
            if found:
                found.update(annotation)
        elif action == "delete":
            layer.annotations = [ann for ann in layer.annotations if ann is not annotation and not (
                ann.get("type") == annotation.get("type")
                and ann.get("position") == annotation.get("position")
                and ann.get("end_position") == annotation.get("end_position")
            )]

        item.setText(self._layer_display_text(layer))
        item.setToolTip(self._layer_tooltip(layer))
        self.statusbar.showMessage(
            f"Annotation updated for {layer_name}."
        )

    def _clear_results(self):
        for w in (self.lbl_area, self.lbl_volume, self.lbl_target_coverage,
                  self.lbl_mean_thickness, self.lbl_min_thickness,
                  self.lbl_max_thickness, self.lbl_std_thickness,
                  self.lbl_num_points, self.lbl_below, self.lbl_within,
                  self.lbl_above):
            w.setText("-")
        self.calc_result    = None
        self.thickness_dist = None

    # ================================================================== export
    def _on_export_pdf(self):
        if self.calc_result is None:
            QMessageBox.warning(self, "Warning", "Please run calculation first!")
            return
        visible_layers = self.layer_manager.visible_layers()
        self._do_export(self.calc_result, self.thickness_dist,
                        visible_layers=visible_layers)

    def _calc_and_export_layer(self, layer: Layer):
        """Calculate for a single layer synchronously, then export."""
        try:
            # calc = calculate_area_and_volume(layer.points, layer.distances)
            # dist = calculate_thickness_distribution(
            #     layer.distances,
            #     self.spin_target_min.value(),
            #     self.spin_target_max.value(),
            # )
            calc = self.calc_result
            dist = self.thickness_dist
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Calculation failed:\n{e}")
            return
        self._do_export(calc, dist,
                        visible_layers=[layer],
                        suffix=f"_{layer.name}")


    def _do_export(self, calc: CalculationResult, dist: ThicknessDistribution,
                visible_layers, suffix: str = ""):

        import os
        import subprocess
        import platform
        from PyQt5.QtWidgets import QMessageBox, QFileDialog

        if self.project_info is None:
            QMessageBox.warning(self, "Warning", "Please load a PLY file first!")
            return

        # =========================
        # 1. Default filename
        # =========================
        default = (
            f"report_{self.project_info.project_name}_"
            f"{self.project_info.job_number}{suffix}.pdf"
        )

        fp, _ = QFileDialog.getSaveFileName(
            self,
            "Save PDF Report",
            default,
            "PDF Files (*.pdf)"
        )

        if not fp:
            return

        try:
            self.statusbar.showMessage("Generating PDF report…")

            # =========================
            # 2. Capture data (UI layer only)
            # =========================
            screenshot = self.viewer.get_screenshot()

            original_area_m2 = None
            original_layer = self.layer_manager.original
            if original_layer is not None:
                try:
                    # original_area_m2 = calculate_area_and_volume(
                    #     original_layer.points,
                    #     original_layer.distances
                    # ).surface_area_m2
                    pass
                except Exception:
                    original_area_m2 = None

            ctx = {
                "project_info": self.project_info,
                "calculation_result": calc,
                "thickness_distribution": dist,
                "target_min": self.spin_target_min.value(),
                "target_max": self.spin_target_max.value(),
                "original_area_m2": original_area_m2,
                "screenshot_path": screenshot,
                "visible_layers": visible_layers,
            }

            # =========================
            # 3. Generate report (NEW ARCH)
            # =========================

            from report import PDFGenerator

            generator = PDFGenerator(fp)
            out = generator.generate(ctx)

            # =========================
            # 4. UI feedback
            # =========================
            self.statusbar.showMessage(f"Completed: {out}")

            QMessageBox.information(
                self,
                "Success",
                f"Report exported:\n{out}"
            )

            # =========================
            # 5. Auto-open file
            # =========================
            if platform.system() == 'Windows':
                os.startfile(out)
            elif platform.system() == 'Darwin':
                subprocess.call(['open', out])
            else:
                subprocess.call(['xdg-open', out])

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to generate report:\n{str(e)}"
            )
    # ================================================================== misc
    def _show_about(self):
        
        QMessageBox.about(
            self, "About Tunnel Analyzer",
            "Tunnel Concrete Thickness Analyzer\n\n"
            "Analysis of sprayed concrete thickness in tunnel engineering from Point Cloud (.ply)\n\n"
            "Version 2.0 — Layer-based architecture")

    def closeEvent(self, event):
        self._save_settings()
        self.viewer.close()
        event.accept()

    # ------------------------------------------------------------------ persistence
    def _load_settings(self):
        self.settings.beginGroup('Visualization')
        self.spin_point_size.setValue(self.settings.value('point_size', 1, type=int))
        colormap = self.settings.value('colormap', 'jet')
        idx = self.cmb_colormap.findText(colormap)
        if idx >= 0:
            self.cmb_colormap.setCurrentIndex(idx)
        self.spin_target_min.setValue(self.settings.value('target_min', self.target_min, type=float))
        self.spin_target_max.setValue(self.settings.value('target_max', self.target_max, type=float))
        self.settings.endGroup()

        self.settings.beginGroup('Annotation')
        annotation_color = self.settings.value('annotation_color', '#000000')
        self.viewer._annotation_color = annotation_color
        self.viewer.btn_annotation_color.setStyleSheet(f'background-color: {annotation_color};border-radius: 0px;')
        self.viewer.spin_line_width.setValue(self.settings.value('line_width', 3, type=int))
        self.viewer.spin_font_size.setValue(self.settings.value('font_size', 14, type=int))
        self.settings.endGroup()

    def _save_settings(self):
        self.settings.beginGroup('Visualization')
        self.settings.setValue('point_size', self.spin_point_size.value())
        self.settings.setValue('colormap', self.cmb_colormap.currentText())
        self.settings.setValue('target_min', self.spin_target_min.value())
        self.settings.setValue('target_max', self.spin_target_max.value())
        self.settings.endGroup()

        self.settings.beginGroup('Annotation')
        self.settings.setValue('annotation_color', self.viewer._annotation_color)
        self.settings.setValue('line_width', self.viewer.spin_line_width.value())
        self.settings.setValue('font_size', self.viewer.spin_font_size.value())
        self.settings.endGroup()
