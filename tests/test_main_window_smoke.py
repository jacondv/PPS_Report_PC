"""
Smoke tests for MainWindow: it must construct without error, load the
sample PLY, run the full mở → chọn → segment → tính → export flow (Phase 6
exit criterion), and produce PDF numbers matching the golden baseline.
"""

import json
import os

import pytest
from PySide6.QtCore import Qt

from pps.ui.main_window import MainWindow


@pytest.fixture
def main_window(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    yield window
    # Bypass the unsaved-changes confirmation dialog on teardown — that flow
    # has its own dedicated tests below and must not block here on a real
    # (non-mocked) QMessageBox if a test left the document dirty.
    window.document._dirty = False
    window.close()


def test_main_window_constructs(main_window):
    assert main_window.document is not None
    assert main_window.viewport is not None
    assert main_window.tool_manager.active_id is None  # Navigate by default


def test_open_sample_file_populates_document(main_window, sample_ply_path):
    main_window._load_file(sample_ply_path)

    assert main_window.document.layer_manager.original is not None
    assert main_window.document.project_info is not None
    assert main_window.document.project_info.job_number == "sample"
    # LayerRenderer actually built an actor for the original layer
    assert main_window.layer_renderer.get(main_window.document.layer_manager.original.id) is not None


def test_tools_disabled_until_cloud_loaded(main_window, sample_ply_path):
    for action in main_window.tool_toolbar._actions.values():
        assert action.isEnabled() is False

    main_window._load_file(sample_ply_path)

    for action in main_window.tool_toolbar._actions.values():
        assert action.isEnabled() is True


def test_extract_segment_hides_other_layers_and_selects_new_one(main_window, sample_ply_path):
    main_window._load_file(sample_ply_path)
    original = main_window.document.layer_manager.original

    dock = main_window.selection_dock
    dock.spin_from.setValue(75)
    dock.spin_to.setValue(125)
    dock._on_filter_clicked()
    dock._on_extract_segment()

    layers = main_window.document.layer_manager.layers
    segment = next(l for l in layers if l.id != original.id)

    assert original.visible is False
    assert segment.visible is True

    current_item = main_window.project_dock.list_widget.currentItem()
    assert current_item.data(Qt.ItemDataRole.UserRole) == segment.id


def test_full_flow_matches_golden_baseline(main_window, sample_ply_path, tmp_path, qtbot):
    main_window._load_file(sample_ply_path)

    # force the same targets the baseline used (40/60 — no job_info.json
    # next to the sample file)
    assert main_window.document.target_min == 40.0
    assert main_window.document.target_max == 60.0

    main_window._on_calculate()
    worker = main_window._calc_worker
    with qtbot.waitSignal(worker.finished_ok, timeout=60000):
        pass

    assert main_window._calc_result is not None

    golden_path = os.path.join(os.path.dirname(__file__), "golden", "sample_baseline.json")
    with open(golden_path, encoding="utf-8") as f:
        baseline = json.load(f)
    expected = baseline["cases"][0]["calculation_result"]

    calc = main_window._calc_result
    assert calc.surface_area_m2 == pytest.approx(expected["surface_area_m2"], rel=1e-9)
    assert calc.volume_m3 == pytest.approx(expected["volume_m3"], rel=1e-9)
    assert calc.num_points == expected["num_points"]


def test_select_by_thickness_and_extract_segment(main_window, sample_ply_path):
    main_window._load_file(sample_ply_path)
    original_id = main_window.document.layer_manager.original.id

    dock = main_window.selection_dock
    dock.spin_from.setValue(75)
    dock.spin_to.setValue(125)
    dock._on_filter_clicked()

    assert main_window.document.selection.count() > 0
    # selection highlight actor was created by _on_selection_changed
    assert main_window._selection_highlight_actor is not None

    dock._on_extract_segment()

    layers = main_window.document.layer_manager.layers
    assert len(layers) == 2
    segment = next(l for l in layers if l.id != original_id)
    assert segment.sources[0].layer_id == original_id
    assert main_window.layer_renderer.get(segment.id) is not None
    assert main_window.document.selection.is_empty()

    main_window.document.undo_stack.undo()
    assert len(main_window.document.layer_manager.layers) == 1
    assert main_window.layer_renderer.get(segment.id) is None


def test_export_pdf_produces_real_file(main_window, sample_ply_path, tmp_path, qtbot, monkeypatch):
    main_window._load_file(sample_ply_path)
    main_window._on_calculate()
    with qtbot.waitSignal(main_window._calc_worker.finished_ok, timeout=60000):
        pass

    out_path = str(tmp_path / "report.pdf")
    monkeypatch.setattr(
        "pps.ui.main_window.QFileDialog.getSaveFileName", lambda *a, **k: (out_path, "")
    )
    monkeypatch.setattr("pps.ui.main_window.QMessageBox.information", lambda *a, **k: None)
    monkeypatch.setattr("os.startfile", lambda *a, **k: None, raising=False)

    main_window._on_export_pdf()

    assert os.path.exists(out_path)
    assert os.path.getsize(out_path) > 0


def test_save_project_as_then_reopen_restores_camera(main_window, sample_ply_path, tmp_path, qtbot, monkeypatch):
    main_window._load_file(sample_ply_path)

    project_path = str(tmp_path / "phase7.ppsproj")
    monkeypatch.setattr(
        "pps.ui.main_window.QFileDialog.getSaveFileName", lambda *a, **k: (project_path, "")
    )
    assert main_window._on_save_project_as() is True
    assert main_window.current_project_path == project_path
    assert os.path.exists(project_path)
    assert main_window.document.dirty is False

    # Recent Projects menu now lists it
    assert project_path in main_window._recent_projects()

    other_window = MainWindow()
    qtbot.addWidget(other_window)
    other_window._open_project_path(project_path)
    assert other_window.current_project_path == project_path
    assert other_window.document.layer_manager.original is not None
    other_window.close()


def test_save_project_uses_current_path_without_dialog(main_window, sample_ply_path, tmp_path, qtbot, monkeypatch):
    main_window._load_file(sample_ply_path)
    project_path = str(tmp_path / "direct_save.ppsproj")
    main_window.current_project_path = project_path

    def fail_dialog(*a, **k):
        raise AssertionError("Save dialog should not be shown when current_project_path is set")

    monkeypatch.setattr("pps.ui.main_window.QFileDialog.getSaveFileName", fail_dialog)
    assert main_window._on_save_project() is True
    assert os.path.exists(project_path)


def test_close_with_unsaved_changes_prompts_and_can_cancel(main_window, sample_ply_path, monkeypatch):
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QMessageBox

    main_window._load_file(sample_ply_path)
    main_window.document.mark_dirty()

    monkeypatch.setattr(
        "pps.ui.main_window.QMessageBox.question",
        lambda *a, **k: QMessageBox.StandardButton.Cancel,
    )

    event = QCloseEvent()
    main_window.closeEvent(event)
    assert not event.isAccepted()


def test_close_with_unsaved_changes_discard_proceeds(main_window, sample_ply_path, monkeypatch):
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QMessageBox

    main_window._load_file(sample_ply_path)
    main_window.document.mark_dirty()

    monkeypatch.setattr(
        "pps.ui.main_window.QMessageBox.question",
        lambda *a, **k: QMessageBox.StandardButton.Discard,
    )

    event = QCloseEvent()
    main_window.closeEvent(event)
    assert event.isAccepted()
