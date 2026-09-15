"""
main_window.py
---------------
File LOGIC của ứng dụng. Toàn bộ giao diện (widget, layout, menu, toolbar,
statusbar) nằm trong main_window.ui và được mở/sửa bằng Qt Designer.

File này CHỈ làm 2 việc:
  1. Nạp main_window.ui bằng uic.loadUi(...)
  2. Connect signal/slot + xử lý nghiệp vụ (giữ nguyên logic gốc)

LƯU Ý quan trọng khi chỉnh sửa main_window.ui bằng Qt Designer:
  - KHÔNG đổi objectName của các widget đang được dùng trong file .py này
    (vd: lbl_filename, spin_target_min, list_layers, viewer, btn_calculate...).
    Nếu đổi tên trong Designer thì phải sửa lại tên tương ứng trong file .py.
  - Widget "viewer" trong .ui đã được khai báo là custom widget (promoted)
    với class PointCloudViewer, header "pointcloud_viewer". Hãy đảm bảo:
      + Bạn có file pointcloud_viewer.py chứa class PointCloudViewer
      + Hoặc trong Qt Designer: chuột phải vào widget "viewer" -> Promote to...
        rồi điền đúng tên class/đường dẫn module của bạn.
  - Có thể thêm/sửa widget mới trong Designer thoải mái, miễn giữ đúng
    objectName của các widget đã có ở trên.
"""

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

from PyQt5 import uic
from PyQt5.QtWidgets import (
    QFrame, QLineEdit, QMainWindow, QSizePolicy, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QToolBar, QAction, QFileDialog, QMessageBox, QGroupBox,
    QLabel, QPushButton, QSpinBox, QDoubleSpinBox, QComboBox,
    QListWidget, QListWidgetItem, QProgressBar, QStatusBar,
    QFormLayout, QScrollArea, QCheckBox, QMenu, QInputDialog,
    QAbstractItemView,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize, QPoint, QSettings
from PyQt5.QtGui import QFont, QColor, QPixmap, QIcon, QPixmapCache


if not getattr(sys, 'frozen', False):
    # Chỉ chạy khi là source, không phải exe
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from gui.help import HotkeysDialog
from gui.viewer_3d import PointCloudViewer
from core.ply_loader import load_ply, get_ply_fields
from core.filename_parser import parse_filename, ProjectInfo
from core.layer_manager import Layer, LayerManager
from core.calculator import (
    calculate_area_and_volume, calculate_thickness_distribution,
    CalculationResult, ThicknessDistribution,
)
# from report.pdf_generator import generate_report

UI_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main_window.ui")


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        # ---- Nạp giao diện từ file .ui ----
        uic.loadUi(UI_FILE, self)

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

        self._connect_signals()

        self.statusbar.showMessage("Ready — Please open a PLY file")

        self.settings = QSettings('TunnelAnalyzer', 'TunnelConcreteThicknessAnalyzer')
        self._load_settings()

    # ================================================================== connect signals
    def _connect_signals(self):
        # ---- viewer (custom widget "viewer" promoted thành PointCloudViewer) ----
        self.viewer.signals.selection_changed.connect(self._on_selection_changed)
        self.viewer.signals.selection_cleared.connect(self._on_selection_cleared)
        self.viewer.signals.polygon_mode_ended.connect(self._on_polygon_mode_ended)
        self.viewer.signals.annotation_added.connect(self._on_annotation_added)

        self.spin_point_size.valueChanged.connect(self.viewer.set_point_size)
        self.cmb_colormap.currentTextChanged.connect(self.viewer.set_colormap)

        # ---- left panel ----
        self.spin_target_min.valueChanged.connect(self._on_target_changed)
        self.spin_target_max.valueChanged.connect(self._on_target_changed)

        # ---- segment panel ----
        self.btn_select_range.clicked.connect(self._on_select_by_range)
        self.btn_polygon.toggled.connect(self._on_polygon_toggled)
        self.btn_add_seg.clicked.connect(self._on_add_segment)
        self.btn_clear_sel.clicked.connect(self._on_clear_selection)

        self.list_layers.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_layers.customContextMenuRequested.connect(self._on_layer_context_menu)
        self.list_layers.itemChanged.connect(self._on_layer_item_changed)
        self.list_layers.currentItemChanged.connect(self._on_layer_selected)

        self.btn_calculate.clicked.connect(self._on_calculate)
        self.btn_export_pdf.clicked.connect(self._on_export_pdf)

        # ---- menu actions ----
        self.actionOpen.triggered.connect(self._on_open_file)
        self.actionExportPdf.triggered.connect(self._on_export_pdf)
        self.actionExit.triggered.connect(self.close)

        self.actionTopView.triggered.connect(self.viewer.view_top)
        self.actionBottomView.triggered.connect(self.viewer.view_bottom)
        self.actionFrontView.triggered.connect(self.viewer.view_front)
        self.actionBackView.triggered.connect(self.viewer.view_back)
        self.actionRightView.triggered.connect(self.viewer.view_right)
        self.actionLeftView.triggered.connect(self.viewer.view_left)
        self.actionIsoView.triggered.connect(self.viewer.view_iso)

        self.actionAbout.triggered.connect(self._show_about)
        self.actionHotkeys.triggered.connect(self._show_hotkeys)

        # ---- toolbar actions ----
        self.actionToolbarOpen.triggered.connect(self._on_open_file)
        self.actionResetView.triggered.connect(self.viewer.reset_view)
        self.actionToolbarCalculate.triggered.connect(self._on_calculate)
        self.actionToolbarExport.triggered.connect(self._on_export_pdf)

    def _show_hotkeys(self):
        dlg = HotkeysDialog(self)
        dlg.exec_()

    # ================================================================== file
    def _on_open_file(self):
        fp, _ = QFileDialog.getOpenFileName(
            self, "Open Point Cloud File", "",
            "Compare Files (*compare*.ply);;"
            "PLY Files (*.ply);;"
            "All Files (*)"
        )
        if fp:
            self._load_file(fp)

    def _load_file(self, filepath: str):
        try:
            self.statusbar.showMessage(f"Loading: {filepath}…")

            fields = get_ply_fields(filepath)
            self.ui.cmb_dist_field.clear()
            self.ui.cmb_dist_field.addItems(fields)
            for f in ('distances', 'distance', 'thickness', 'scalar_distances'):
                if f in fields:
                    self.ui.cmb_dist_field.setCurrentText(f); break

            cloud_data = load_ply(filepath, self.ui.cmb_dist_field.currentText())
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
            self.ui.spin_target_min.setValue(min_target)
            self.ui.spin_target_max.setValue(max_target)

            # Reset everything
            self.layer_manager.clear()
            self.viewer.clear_all_layers()
            self.ui.list_layers.blockSignals(True)
            self.ui.list_layers.clear()
            self.ui.list_layers.blockSignals(False)
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
        return f"{layer.name}{note_flag}  ({layer.num_points:,} points)"

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
        self.viewer._set_tool_buttons_enabled(True)
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
        act_note     = menu.addAction("📝  Annotate this layer")
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
        self.viewer._delete_annotation_by_layer(name)
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
            self.btn_polygon.setText("✏  Select Polygon")
            self.viewer.disable_polygon_mode()
            self.statusbar.showMessage("Ready")

    def _on_polygon_mode_ended(self):
        self.btn_polygon.blockSignals(True)
        self.btn_polygon.setChecked(False)
        self.btn_polygon.setText("🖊 Select Polygon")
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
        self.statusbar.showMessage(f"Created {layer.name} ({layer.num_points:,} points)")

    # ================================================================== calculation
    def _on_calculate(self):
        selected_items = [
            self.list_layers.item(i)
            for i in range(self.list_layers.count())
            if self.list_layers.item(i).checkState() == Qt.Checked
        ]
        if not selected_items or len(selected_items) == 0:
            QMessageBox.warning(self, "Warning",
                                "Please check one or more layers!")
            return

        # Collect points and distances from all selected layers
        all_points = []
        all_distances = []

        for item in selected_items:
            layer_name = item.data(Qt.UserRole)
            layer = self.layer_manager.get(layer_name)
            # only include visible layers with points to caculate
            if layer is None or layer.visible == False:
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

        if self.project_info is None:
            QMessageBox.warning(self, "Warning", "Please load a PLY file first!")
            return

        # =========================
        # 1. Default filename
        # =========================
        _segment_str = ""
        for _layer in visible_layers:
            _segment_str += f"_{_layer.name}" if _layer.name and (self.project_info.job_number not in _layer.name) else ""

        default = (
            f"{self.project_info.project_name}_"
            f"{self.project_info.job_number}_{self.project_info.scan_time}_{self.project_info.segment_name}{_segment_str}{suffix}.pdf"
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
            # 3. Generate report
            # =========================
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


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
