"""
MainWindow: wires Document, Viewport, renderers, ToolManager and docks
together. This is the only place that knows about all of them at once —
docks/tools/renderers each only see the slice they need (per plan §2.1).
"""

import logging
import os
import platform
import subprocess
import tempfile

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow, QMessageBox

import pyvista as pv

from pps.app.dialogs import open_note_editor
from pps.app.settings import AppSettings
from pps.app.workers import AreaMeasureWorker, CalculationWorker
from pps.core.filename_parser import parse_filename
from pps.core.job_info import resolve_targets
from pps.core.ply_loader import get_ply_fields, load_ply
from pps.render import camera
from pps.render.labels import hex_to_rgb
from pps.render.layer_renderer import LayerRenderer
from pps.render.measurement_renderer import MeasurementRenderer
from pps.render.note_renderer import NoteRenderer
from pps.render.viewport import Viewport
from pps.report import PDFGenerator
from pps.scene.document import Document
from pps.scene.project_io import load_project, save_project
from pps.tools.base import ToolContext
from pps.tools.manager import ToolManager
from pps.tools.measure_area import MeasureAreaTool
from pps.tools.measure_distance import MeasureDistanceTool
from pps.tools.navigate import NavigateTool
from pps.tools.note import NoteTool
from pps.tools.region_select import RegionSelectTool
from pps.ui.dialogs.about_dialog import show_about
from pps.ui.dialogs.settings_dialog import SettingsDialog
from pps.ui.dialogs.shortcuts_dialog import ShortcutsDialog
from pps.ui.docks.objects_dock import ObjectsDock
from pps.ui.docks.project_dock import ProjectDock
from pps.ui.docks.properties_dock import PropertiesDock
from pps.ui.docks.results_dock import ResultsDock
from pps.ui.docks.selection_dock import SelectionDock
from pps.ui.theme import apply_theme
from pps.ui.toolbars.tool_toolbar import ToolToolbar
from pps.ui.toolbars.view_toolbar import ViewToolbar

logger = logging.getLogger(__name__)

_DISTANCE_FIELD_PRIORITY = ("distances", "distance", "thickness", "scalar_distances")

RECENT_PROJECTS_KEY = "recent/projects"
RECENT_PROJECTS_MAX = 10


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tunnel Concrete Thickness Analyzer")
        self.resize(1400, 900)

        self.settings = QSettings("TunnelAnalyzer", "TunnelConcreteThicknessAnalyzer")
        self.settings_store = AppSettings(self)

        self.document = Document(self)
        self._point_size = self.settings_store.point_size
        self._calc_result = None
        self._thickness_dist = None
        self._selection_highlight_actor = None
        self._area_workers = []  # keep QThreads alive while running
        self.current_project_path = None

        self.viewport = Viewport(self)
        self.setCentralWidget(self.viewport)

        self.layer_renderer = LayerRenderer(self.viewport.plotter)
        self.note_renderer = NoteRenderer(self.viewport.plotter, self.viewport.overlay)
        self.measurement_renderer = MeasurementRenderer(self.viewport.plotter, self.viewport.overlay)
        self._sync_layer_renderer_colors()

        self.tool_manager = ToolManager(self._build_tool_context, self.viewport.interactor_widget, self)
        self._register_tools()

        self._build_docks()
        self.properties_dock.set_point_size_silently(self._point_size)
        self._build_toolbars()
        self._build_menus()

        self._connect_document_signals()
        self.settings_store.changed.connect(self._on_display_settings_changed)

        self._restore_window_state()

    # ------------------------------------------------------------------ tools
    def _build_tool_context(self) -> ToolContext:
        return ToolContext(
            document=self.document,
            viewport=self.viewport,
            overlay=self.viewport.overlay,
            undo_stack=self.document.undo_stack,
            set_status=self.statusBar().showMessage,
            request_render=self.viewport.render,
        )

    def _register_tools(self) -> None:
        self.region_select_tool = RegionSelectTool()
        self.measure_area_tool = MeasureAreaTool(area_requester=self._request_area_calculation)
        self.note_tool = NoteTool(note_editor=lambda existing: open_note_editor(existing, parent=self))

        self.tool_manager.register(NavigateTool())
        self.tool_manager.register(self.region_select_tool)
        self.tool_manager.register(MeasureDistanceTool())
        self.tool_manager.register(self.measure_area_tool)
        self.tool_manager.register(self.note_tool)

    def _request_area_calculation(self, points, on_done) -> None:
        worker = AreaMeasureWorker("", points, parent=self)
        self._area_workers.append(worker)

        def handle_ok(_measurement_id, area_m2):
            on_done(area_m2)
            self._area_workers.remove(worker)

        def handle_failed(_measurement_id, message):
            QMessageBox.warning(self, "Area calculation failed", message)
            self._area_workers.remove(worker)

        worker.finished_ok.connect(handle_ok)
        worker.failed.connect(handle_failed)
        worker.start()

    # ------------------------------------------------------------------ docks
    def _build_docks(self) -> None:
        self.project_dock = ProjectDock(self.document, self)
        self.selection_dock = SelectionDock(
            self.document, self.region_select_tool, self.measure_area_tool, self
        )
        self.properties_dock = PropertiesDock(self.document, self)
        self.results_dock = ResultsDock(self)
        self.objects_dock = ObjectsDock(self.document, self)

        self.properties_dock.point_size_changed.connect(self._on_point_size_changed)

        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.project_dock)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.selection_dock)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.properties_dock)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.results_dock)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.objects_dock)

    # ------------------------------------------------------------------ toolbars / menus
    def _build_toolbars(self) -> None:
        main_toolbar = self.addToolBar("Main")
        main_toolbar.setObjectName("toolbar_main")

        self.action_open = QAction("Open PLY…", self)
        self.action_open.setShortcut(QKeySequence.StandardKey.Open)
        self.action_open.triggered.connect(self._on_open_file)
        main_toolbar.addAction(self.action_open)

        main_toolbar.addSeparator()

        self.action_undo = self.document.undo_stack.createUndoAction(self, "Undo")
        self.action_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self.action_redo = self.document.undo_stack.createRedoAction(self, "Redo")
        self.action_redo.setShortcut(QKeySequence.StandardKey.Redo)
        main_toolbar.addAction(self.action_undo)
        main_toolbar.addAction(self.action_redo)

        main_toolbar.addSeparator()

        self.action_calculate = QAction("Calculate", self)
        self.action_calculate.triggered.connect(self._on_calculate)
        main_toolbar.addAction(self.action_calculate)

        self.action_export_pdf = QAction("Export PDF…", self)
        self.action_export_pdf.setShortcut(QKeySequence("Ctrl+E"))
        self.action_export_pdf.triggered.connect(self._on_export_pdf)
        main_toolbar.addAction(self.action_export_pdf)

        self.tool_toolbar = ToolToolbar(self.tool_manager, self)
        self.addToolBar(self.tool_toolbar)
        self.addToolBar(ViewToolbar(self.viewport, self))

        self.action_select_all = QAction("Select All", self)
        self.action_select_all.setShortcut(QKeySequence.StandardKey.SelectAll)
        self.action_select_all.triggered.connect(self._on_select_all)
        self.addAction(self.action_select_all)  # keyboard-only, no toolbar/menu slot needed

    def _build_menus(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction(self.action_open)
        file_menu.addSeparator()

        self.action_save_project = QAction("Save Project", self)
        self.action_save_project.setShortcut(QKeySequence.StandardKey.Save)
        self.action_save_project.triggered.connect(self._on_save_project)
        file_menu.addAction(self.action_save_project)

        self.action_save_project_as = QAction("Save Project As…", self)
        self.action_save_project_as.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.action_save_project_as.triggered.connect(self._on_save_project_as)
        file_menu.addAction(self.action_save_project_as)

        self.action_open_project = QAction("Open Project…", self)
        self.action_open_project.setShortcut(QKeySequence("Ctrl+Shift+O"))
        self.action_open_project.triggered.connect(self._on_open_project)
        file_menu.addAction(self.action_open_project)

        self.recent_projects_menu = file_menu.addMenu("Recent Projects")
        self._update_recent_projects_menu()

        file_menu.addSeparator()
        file_menu.addAction(self.action_export_pdf)
        file_menu.addSeparator()
        action_exit = QAction("Exit", self)
        action_exit.setShortcut(QKeySequence.StandardKey.Quit)
        action_exit.triggered.connect(self.close)
        file_menu.addAction(action_exit)

        edit_menu = menu_bar.addMenu("&Edit")
        edit_menu.addAction(self.action_undo)
        edit_menu.addAction(self.action_redo)
        edit_menu.addSeparator()
        edit_menu.addAction(self.action_select_all)

        view_menu = menu_bar.addMenu("&View")
        for dock in (
            self.project_dock, self.selection_dock, self.properties_dock,
            self.results_dock, self.objects_dock,
        ):
            view_menu.addAction(dock.toggleViewAction())
        view_menu.addSeparator()
        action_reset_layout = QAction("Reset Layout", self)
        action_reset_layout.triggered.connect(self._reset_layout)
        view_menu.addAction(action_reset_layout)

        settings_menu = menu_bar.addMenu("&Settings")
        action_preferences = QAction("Preferences…", self)
        action_preferences.triggered.connect(self._on_open_settings)
        settings_menu.addAction(action_preferences)

        help_menu = menu_bar.addMenu("&Help")
        action_shortcuts = QAction("Keyboard Shortcuts", self)
        action_shortcuts.triggered.connect(self._show_shortcuts)
        help_menu.addAction(action_shortcuts)
        action_about = QAction("About", self)
        action_about.triggered.connect(lambda: show_about(self))
        help_menu.addAction(action_about)

    # ------------------------------------------------------------------ document signal wiring
    def _connect_document_signals(self) -> None:
        d = self.document
        d.reset.connect(self._on_document_reset)
        d.layer_added.connect(self._on_layer_added)
        d.layer_removed.connect(self._on_layer_removed)
        d.layer_changed.connect(self._on_layer_changed)
        d.targets_changed.connect(self._on_targets_changed)
        d.selection_changed.connect(self._on_selection_changed)
        d.annotation_added.connect(self._on_note_upserted)
        d.annotation_changed.connect(self._on_note_upserted)
        d.annotation_removed.connect(self._on_note_removed)
        d.measurement_added.connect(self._on_measurement_upserted)
        d.measurement_changed.connect(self._on_measurement_upserted)
        d.measurement_removed.connect(self._on_measurement_removed)
        d.dirty_changed.connect(self._on_dirty_changed)

    def _on_document_reset(self) -> None:
        self.layer_renderer.clear()
        self.note_renderer.clear()
        self.measurement_renderer.clear()
        self._clear_selection_highlight()
        for layer in self.document.layer_manager.layers:
            self.layer_renderer.sync(layer, self.document.target_min, self.document.target_max, self._point_size)
        self.note_renderer.sync_all(self.document.annotations)
        self.measurement_renderer.sync_all(self.document.measurements)

        if self.document.camera_state is not None:
            camera.set_camera_state(self.viewport.plotter, self.document.camera_state)
            self.document.camera_state = None
        else:
            camera.reset_view(self.viewport.plotter)
        self.tool_manager.on_document_reset()
        self.tool_toolbar.set_cloud_loaded(self.document.layer_manager.original is not None)
        self._calc_result = None
        self._thickness_dist = None
        self.results_dock.clear_result()
        self.viewport.render()

    def _on_layer_added(self, layer_id: str) -> None:
        layer = self.document.layer_manager.get_by_id(layer_id)
        if layer is not None:
            self.layer_renderer.sync(layer, self.document.target_min, self.document.target_max, self._point_size)
            self.viewport.render()

    def _on_layer_removed(self, layer_id: str) -> None:
        self.layer_renderer.remove(layer_id)
        self.viewport.render()

    def _on_layer_changed(self, layer_id: str) -> None:
        layer = self.document.layer_manager.get_by_id(layer_id)
        if layer is not None:
            self.layer_renderer.set_visible(layer_id, layer.visible)
            self.viewport.render()

    def _on_targets_changed(self, target_min: float, target_max: float) -> None:
        for layer in self.document.layer_manager.layers:
            self.layer_renderer.sync(layer, target_min, target_max, self._point_size)
        self.viewport.render()

    def _on_point_size_changed(self, size: int) -> None:
        self._point_size = size
        for layer in self.document.layer_manager.layers:
            self.layer_renderer.sync(layer, self.document.target_min, self.document.target_max, size)
        self.viewport.render()

    def _on_selection_changed(self) -> None:
        self._clear_selection_highlight()
        points, _distances = self.document.selection.get_points_and_distances()
        if len(points):
            cloud = pv.PolyData(points)
            self._selection_highlight_actor = self.viewport.plotter.add_mesh(
                cloud, color="yellow", point_size=self._point_size + 3,
                render_points_as_spheres=True, opacity=0.9,
            )
        self.viewport.render()

    def _clear_selection_highlight(self) -> None:
        if self._selection_highlight_actor is not None:
            try:
                self.viewport.plotter.remove_actor(self._selection_highlight_actor)
            except Exception:
                pass
            self._selection_highlight_actor = None

    def _on_note_upserted(self, note_id: str) -> None:
        note = self.document._find_note(note_id)
        if note is not None:
            self.note_renderer.sync_one(note)
        self.viewport.render()

    def _on_note_removed(self, note_id: str) -> None:
        self.note_renderer.remove(note_id)
        self.viewport.render()

    def _on_measurement_upserted(self, measurement_id: str) -> None:
        measurement = self.document._find_measurement(measurement_id)
        if measurement is not None:
            self.measurement_renderer.sync_one(measurement)
        self.viewport.render()

    def _on_measurement_removed(self, measurement_id: str) -> None:
        self.measurement_renderer.remove(measurement_id)
        self.viewport.render()

    def _on_dirty_changed(self, dirty: bool) -> None:
        self._update_window_title()

    def _update_window_title(self) -> None:
        title = "Tunnel Concrete Thickness Analyzer"
        if self.current_project_path:
            title = f"{title} — {os.path.basename(self.current_project_path)}"
        if self.document.dirty:
            title += " *"
        self.setWindowTitle(title)

    def _on_select_all(self) -> None:
        self.document.selection.select_all()
        self.document.selection_changed.emit()

    # ------------------------------------------------------------------ File > Open
    def _on_open_file(self) -> None:
        if not self._confirm_discard_unsaved():
            return
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Open Point Cloud File", "",
            "Compare Files (*compare*.ply);;PLY Files (*.ply);;All Files (*)",
        )
        if filepath:
            self.current_project_path = None
            self._load_file(filepath)

    def _load_file(self, filepath: str) -> None:
        try:
            self.statusBar().showMessage(f"Loading: {filepath}…")

            fields = get_ply_fields(filepath)
            distance_field = fields[0] if fields else "distances"
            for candidate in _DISTANCE_FIELD_PRIORITY:
                if candidate in fields:
                    distance_field = candidate
                    break

            cloud = load_ply(filepath, distance_field)
            project_info = parse_filename(filepath)
            target_min, target_max = resolve_targets(filepath)

            self.document.load_point_cloud(
                source_path=filepath,
                project_info=project_info,
                points=cloud.points,
                distances=cloud.distances,
                distance_field=distance_field,
                target_min=target_min,
                target_max=target_max,
            )
            self.document.mark_clean()
            self._update_window_title()

            self.statusBar().showMessage(
                f"Loaded: {os.path.basename(filepath)}  ({cloud.num_points:,} points)"
            )
        except Exception as exc:
            logger.exception("Failed to load %s", filepath)
            QMessageBox.critical(self, "Error", f"Cannot load file:\n{exc}")
            self.statusBar().showMessage("Error loading file")

    # ------------------------------------------------------------------ File > Save/Open Project
    def _confirm_discard_unsaved(self) -> bool:
        """Return True if it's OK to discard the current document (not dirty,
        or the user chose to save/discard). False means the caller should
        abort (user chose Cancel, or a save attempt failed)."""
        if not self.document.dirty:
            return True
        choice = QMessageBox.question(
            self, "Unsaved Changes",
            "The current project has unsaved changes. Save before continuing?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if choice == QMessageBox.StandardButton.Cancel:
            return False
        if choice == QMessageBox.StandardButton.Save:
            return self._on_save_project()
        return True

    def _on_save_project(self) -> bool:
        if self.document.source_path is None:
            QMessageBox.warning(self, "Warning", "Please load a PLY file first!")
            return False
        if self.current_project_path is None:
            return self._on_save_project_as()
        self._save_project_to(self.current_project_path)
        return True

    def _on_save_project_as(self) -> bool:
        if self.document.source_path is None:
            QMessageBox.warning(self, "Warning", "Please load a PLY file first!")
            return False
        default_path = self.current_project_path or os.path.splitext(self.document.source_path)[0] + ".ppsproj"
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Project As", default_path, "PPS Project Files (*.ppsproj)"
        )
        if not filepath:
            return False
        self._save_project_to(filepath)
        return True

    def _save_project_to(self, filepath: str) -> None:
        try:
            camera_state = camera.get_camera_state(self.viewport.plotter)
            save_project(self.document, filepath, camera_state=camera_state)
            self.current_project_path = filepath
            self._add_recent_project(filepath)
            self._update_window_title()
            self.statusBar().showMessage(f"Project saved: {filepath}")
        except Exception as exc:
            logger.exception("Failed to save project %s", filepath)
            QMessageBox.critical(self, "Error", f"Cannot save project:\n{exc}")

    def _on_open_project(self) -> None:
        if not self._confirm_discard_unsaved():
            return
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "", "PPS Project Files (*.ppsproj)"
        )
        if filepath:
            self._open_project_path(filepath)

    def _open_project_path(self, filepath: str) -> None:
        try:
            self.statusBar().showMessage(f"Loading project: {filepath}…")
            load_project(self.document, filepath, load_ply)
            self.current_project_path = filepath
            self._add_recent_project(filepath)
            self._update_window_title()
            self.statusBar().showMessage(f"Project loaded: {filepath}")
        except Exception as exc:
            logger.exception("Failed to load project %s", filepath)
            QMessageBox.critical(self, "Error", f"Cannot load project:\n{exc}")
            self.statusBar().showMessage("Error loading project")
            self._remove_recent_project(filepath)

    def _recent_projects(self) -> list:
        return self.settings.value(RECENT_PROJECTS_KEY, [], type=list) or []

    def _add_recent_project(self, filepath: str) -> None:
        recent = [p for p in self._recent_projects() if p != filepath]
        recent.insert(0, filepath)
        self.settings.setValue(RECENT_PROJECTS_KEY, recent[:RECENT_PROJECTS_MAX])
        self._update_recent_projects_menu()

    def _remove_recent_project(self, filepath: str) -> None:
        recent = [p for p in self._recent_projects() if p != filepath]
        self.settings.setValue(RECENT_PROJECTS_KEY, recent)
        self._update_recent_projects_menu()

    def _update_recent_projects_menu(self) -> None:
        menu = self.recent_projects_menu
        menu.clear()
        recent = self._recent_projects()
        if not recent:
            empty_action = QAction("(No recent projects)", self)
            empty_action.setEnabled(False)
            menu.addAction(empty_action)
            return
        for filepath in recent:
            action = QAction(filepath, self)
            action.triggered.connect(lambda checked=False, p=filepath: self._on_recent_project_triggered(p))
            menu.addAction(action)

    def _on_recent_project_triggered(self, filepath: str) -> None:
        if not os.path.exists(filepath):
            QMessageBox.warning(self, "Warning", f"Project file not found:\n{filepath}")
            self._remove_recent_project(filepath)
            return
        if not self._confirm_discard_unsaved():
            return
        self._open_project_path(filepath)

    # ------------------------------------------------------------------ Settings
    def _on_open_settings(self) -> None:
        dialog = SettingsDialog(self.settings_store, self)
        dialog.exec()

    def _sync_layer_renderer_colors(self) -> None:
        self.layer_renderer.set_classification_colors(
            hex_to_rgb(self.settings_store.color_below),
            hex_to_rgb(self.settings_store.color_within),
            hex_to_rgb(self.settings_store.color_above),
        )

    def _on_display_settings_changed(self) -> None:
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, self.settings_store.theme)

        self._sync_layer_renderer_colors()
        self._point_size = self.settings_store.point_size
        for layer in self.document.layer_manager.layers:
            self.layer_renderer.sync(layer, self.document.target_min, self.document.target_max, self._point_size)
        self.properties_dock.set_point_size_silently(self._point_size)
        self.viewport.render()

    # ------------------------------------------------------------------ Calculate
    def _on_calculate(self) -> None:
        points, distances = self.document.layer_manager.combined_visible()
        if len(points) == 0:
            QMessageBox.warning(self, "Warning", "Please check one or more layers!")
            return

        self.results_dock.progress_bar.setVisible(True)
        self.results_dock.progress_bar.setValue(0)
        self.action_calculate.setEnabled(False)

        self._calc_worker = CalculationWorker(
            points, distances, self.document.target_min, self.document.target_max, parent=self
        )
        self._calc_worker.progress.connect(self.results_dock.progress_bar.setValue)
        self._calc_worker.finished_ok.connect(self._on_calc_done)
        self._calc_worker.failed.connect(self._on_calc_failed)
        self._calc_worker.start()

    def _on_calc_done(self, calc, dist) -> None:
        self._calc_result = calc
        self._thickness_dist = dist
        self.results_dock.show_result(calc, dist)
        self.results_dock.progress_bar.setVisible(False)
        self.action_calculate.setEnabled(True)
        self.statusBar().showMessage("Completed calculation")

    def _on_calc_failed(self, message: str) -> None:
        self.results_dock.progress_bar.setVisible(False)
        self.action_calculate.setEnabled(True)
        # Known sharp edge (plan §7.1.6): if no point reaches the target
        # thickness, the core calculation raises rather than silently
        # returning zero. We surface it clearly here instead of "fixing"
        # core behavior.
        QMessageBox.critical(
            self, "Calculation Error",
            f"Error occurred while calculating:\n{message}\n\n"
            "This usually means no point reached the target thickness — "
            "try lowering the minimum target or checking a different layer.",
        )

    # ------------------------------------------------------------------ Export PDF
    def _on_export_pdf(self) -> None:
        if self._calc_result is None:
            QMessageBox.warning(self, "Warning", "Please run calculation first!")
            return
        info = self.document.project_info
        if info is None:
            QMessageBox.warning(self, "Warning", "Please load a PLY file first!")
            return

        visible_layers = self.document.layer_manager.visible_layers()
        segment_str = "".join(
            f"_{layer.name}" for layer in visible_layers
            if layer.name and info.job_number not in layer.name
        )
        default_name = (
            f"{info.project_name}_{info.job_number}_{info.scan_time}_"
            f"{info.segment_name}{segment_str}.pdf"
        )

        filepath, _ = QFileDialog.getSaveFileName(self, "Save PDF Report", default_name, "PDF Files (*.pdf)")
        if not filepath:
            return

        try:
            self.statusBar().showMessage("Generating PDF report…")
            screenshot_path = os.path.join(tempfile.gettempdir(), "pps_report_screenshot.png")
            self.viewport.screenshot(screenshot_path)

            ctx = {
                "project_info": info,
                "calculation_result": self._calc_result,
                "thickness_distribution": self._thickness_dist,
                "target_min": self.document.target_min,
                "target_max": self.document.target_max,
                "original_area_m2": None,
                "screenshot_path": screenshot_path,
                "visible_layers": visible_layers,
            }

            generator = PDFGenerator(filepath)
            out = generator.generate(ctx)

            self.statusBar().showMessage(f"Completed: {out}")
            QMessageBox.information(self, "Success", f"Report exported:\n{out}")

            if platform.system() == "Windows":
                os.startfile(out)
            elif platform.system() == "Darwin":
                subprocess.call(["open", out])
            else:
                subprocess.call(["xdg-open", out])
        except Exception as exc:
            logger.exception("Failed to generate report")
            QMessageBox.critical(self, "Error", f"Failed to generate report:\n{exc}")

    # ------------------------------------------------------------------ misc
    def _show_shortcuts(self) -> None:
        actions = self.findChildren(QAction)
        ShortcutsDialog(actions, self).exec()

    # ------------------------------------------------------------------ window state
    def _restore_window_state(self) -> None:
        geometry = self.settings.value("window/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        state = self.settings.value("window/state")
        if state is not None:
            self.restoreState(state)

    def _reset_layout(self) -> None:
        self.settings.remove("window/geometry")
        self.settings.remove("window/state")
        QMessageBox.information(self, "Reset Layout", "Restart the application to apply the reset layout.")

    def closeEvent(self, event) -> None:
        if not self._confirm_discard_unsaved():
            event.ignore()
            return
        self.settings.setValue("window/geometry", self.saveGeometry())
        self.settings.setValue("window/state", self.saveState())
        self.viewport.close()
        event.accept()
