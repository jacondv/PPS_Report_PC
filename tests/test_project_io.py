import os

import numpy as np

from pps.core.layers import SourceRef
from pps.core.ply_loader import load_ply
from pps.scene.annotations import NoteAnnotation
from pps.scene.commands import AddSegmentCommand
from pps.scene.document import Document
from pps.scene.measurements import AreaMeasurement, DistanceMeasurement
from pps.scene.project_io import _resolve_ply_path, load_project, save_project


def _build_document_with_content(sample_ply_path):
    doc = Document()
    cloud = load_ply(sample_ply_path, "distances")
    doc.load_point_cloud(
        source_path=sample_ply_path,
        project_info=None,
        points=cloud.points,
        distances=cloud.distances,
        distance_field="distances",
        target_min=40.0,
        target_max=60.0,
    )

    original = doc.layer_manager.original
    indices = np.array([0, 1, 2, 3, 4], dtype=np.uint32)
    ref = SourceRef(layer_id=original.id, indices=indices)
    doc.undo_stack.push(
        AddSegmentCommand(
            doc,
            original.points[indices],
            original.distances[indices],
            [ref],
            name="MySegment",
        )
    )

    doc.annotations.append(NoteAnnotation(anchor=(1.0, 2.0, 3.0), text="note text"))
    doc.measurements.append(
        DistanceMeasurement(p1=(0.0, 0.0, 0.0), p2=(3.0, 4.0, 0.0))
    )
    doc.measurements.append(
        AreaMeasurement(
            boundary_px_at_creation=[(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)],
            sources=[SourceRef(layer_id=original.id, indices=indices)],
            centroid=(1.0, 1.0, 0.0),
            area_m2=12.5,
        )
    )
    return doc


def test_save_and_load_project_round_trip(sample_ply_path, tmp_path, qtbot):
    doc = _build_document_with_content(sample_ply_path)
    original = doc.layer_manager.original
    segment = doc.layer_manager.get("MySegment")

    project_path = str(tmp_path / "test.ppsproj")
    save_project(doc, project_path)
    assert os.path.exists(project_path)
    assert doc.dirty is False

    loaded = Document()
    restored_original = load_project(loaded, project_path, load_ply)

    assert restored_original.id == original.id
    np.testing.assert_array_equal(restored_original.points, original.points)
    np.testing.assert_array_equal(restored_original.distances, original.distances)

    restored_segment = loaded.layer_manager.get("MySegment")
    assert restored_segment is not None
    assert restored_segment.id == segment.id
    np.testing.assert_array_equal(restored_segment.points, segment.points)
    np.testing.assert_array_equal(restored_segment.distances, segment.distances)
    assert len(restored_segment.sources) == 1
    assert restored_segment.sources[0].layer_id == original.id

    assert loaded.target_min == 40.0
    assert loaded.target_max == 60.0
    assert loaded.distance_field == "distances"
    assert loaded.source_path == sample_ply_path
    assert loaded.dirty is False

    assert len(loaded.annotations) == 1
    assert loaded.annotations[0].text == "note text"
    assert loaded.annotations[0].anchor == (1.0, 2.0, 3.0)

    assert len(loaded.measurements) == 2
    distance_m = next(m for m in loaded.measurements if isinstance(m, DistanceMeasurement))
    area_m = next(m for m in loaded.measurements if isinstance(m, AreaMeasurement))
    assert distance_m.distance_m == 5.0
    assert area_m.area_m2 == 12.5
    assert area_m.sources[0].layer_id == original.id
    np.testing.assert_array_equal(area_m.sources[0].indices, np.array([0, 1, 2, 3, 4]))


def test_save_and_load_project_round_trip_with_camera(sample_ply_path, tmp_path, qtbot):
    doc = _build_document_with_content(sample_ply_path)
    camera_state = {
        "position": (1.0, 2.0, 3.0),
        "focal_point": (0.0, 0.0, 0.0),
        "up": (0.0, 1.0, 0.0),
        "parallel_scale": 5.5,
        "view_angle": 30.0,
    }

    project_path = str(tmp_path / "test_camera.ppsproj")
    save_project(doc, project_path, camera_state=camera_state)

    loaded = Document()
    load_project(loaded, project_path, load_ply)

    assert loaded.camera_state["parallel_scale"] == camera_state["parallel_scale"]
    assert loaded.camera_state["view_angle"] == camera_state["view_angle"]
    assert tuple(loaded.camera_state["position"]) == camera_state["position"]
    assert tuple(loaded.camera_state["focal_point"]) == camera_state["focal_point"]
    assert tuple(loaded.camera_state["up"]) == camera_state["up"]


def test_save_project_without_camera_state_leaves_it_none(sample_ply_path, tmp_path, qtbot):
    doc = _build_document_with_content(sample_ply_path)
    project_path = str(tmp_path / "test_no_camera.ppsproj")
    save_project(doc, project_path)

    loaded = Document()
    load_project(loaded, project_path, load_ply)

    assert loaded.camera_state is None


def test_resolve_ply_path_falls_back_to_relative(tmp_path):
    ply_dir = tmp_path / "moved"
    ply_dir.mkdir()
    ply_path = ply_dir / "cloud.ply"
    ply_path.write_bytes(b"fake")

    project_path = tmp_path / "project.ppsproj"
    project = {
        "ply_path_absolute": "C:/this/path/does/not/exist.ply",
        "ply_path_relative": "moved/cloud.ply",
    }

    resolved = _resolve_ply_path(project, str(project_path))
    assert os.path.normpath(resolved) == os.path.normpath(str(ply_path))
