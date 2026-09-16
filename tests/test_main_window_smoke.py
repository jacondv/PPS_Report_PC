"""
Smoke tests for MainWindow: it must construct without error, load the
sample PLY, run the full mở → chọn → segment → tính → export flow (Phase 6
exit criterion), and produce PDF numbers matching the golden baseline.
"""

import json
import os

import pytest

from pps.ui.main_window import MainWindow


@pytest.fixture
def main_window(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    yield window
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
