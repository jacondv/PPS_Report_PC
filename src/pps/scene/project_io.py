"""
.ppsproj project file: a zip containing project.json plus one .npy file per
non-original layer (its own points + distances), so segments load back
exactly as they were without depending on any other layer still existing.

Segments used to be rebuilt by re-slicing their source layer's points with
saved indices, but that breaks (NoneType) if the source layer was since
deleted (e.g. via multi-select bulk delete) -- segments now carry their own
baked geometry in the project file instead, same as the original layer's
PLY-backed points. The `sources` list is still recorded for information
only; it is not required to reconstruct a layer.

Calculation results are never saved -- they are always recomputed after
loading, so a stored report number can never drift from the current
calculator code.
"""

import io
import json
import os
import zipfile
from dataclasses import asdict
from typing import Callable

import numpy as np

from pps.core.filename_parser import parse_filename
from pps.core.layers import Layer, SourceRef
from pps.scene.annotations import NoteAnnotation
from pps.scene.document import Document
from pps.scene.measurements import AreaMeasurement, DistanceMeasurement

FORMAT_VERSION = 2

PlyLoader = Callable[[str, str], object]  # (filepath, distance_field) -> PointCloudData-like


def _layer_points_entry(layer_id: str) -> str:
    return f"layers/{layer_id}__points.npy"


def _layer_distances_entry(layer_id: str) -> str:
    return f"layers/{layer_id}__distances.npy"


def _tuple(values, length):
    return tuple(float(v) for v in values[:length])


def save_project(document: Document, path: str, camera_state: dict = None) -> None:
    if document.source_path is None:
        raise ValueError("Document has no loaded point cloud to save")

    project_dir = os.path.dirname(os.path.abspath(path))
    try:
        ply_relpath = os.path.relpath(document.source_path, project_dir)
    except ValueError:
        ply_relpath = None  # different drive on Windows

    layers_data = []
    npy_entries = {}

    for layer in document.layer_manager.layers:
        entry = {
            "id": layer.id,
            "name": layer.name,
            "is_original": layer.is_original,
            "visible": layer.visible,
            "color": list(layer.color) if layer.color is not None else None,
            "sources": [
                {"layer_id": ref.layer_id, "indices": ref.indices.tolist()}
                for ref in layer.sources
            ],
        }
        if not layer.is_original:
            points_entry = _layer_points_entry(layer.id)
            distances_entry = _layer_distances_entry(layer.id)
            npy_entries[points_entry] = layer.points
            npy_entries[distances_entry] = layer.distances
            entry["points_file"] = points_entry
            entry["distances_file"] = distances_entry
        layers_data.append(entry)

    project = {
        "format_version": FORMAT_VERSION,
        "ply_path_absolute": document.source_path,
        "ply_path_relative": ply_relpath,
        "distance_field": document.distance_field,
        "target_min": document.target_min,
        "target_max": document.target_max,
        "layers": layers_data,
        "annotations": [asdict(a) for a in document.annotations],
        "measurements": [_measurement_to_dict(m) for m in document.measurements],
        "camera": camera_state,
    }

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("project.json", json.dumps(project, indent=2))
        for name, array in npy_entries.items():
            buf = io.BytesIO()
            np.save(buf, array)
            zf.writestr(name, buf.getvalue())

    document.mark_clean()


def _measurement_to_dict(measurement) -> dict:
    data = asdict(measurement)
    if isinstance(measurement, AreaMeasurement):
        data["kind"] = "area"
        data["sources"] = [
            {"layer_id": ref.layer_id, "indices": ref.indices.tolist()}
            for ref in measurement.sources
        ]
    else:
        data["kind"] = "distance"
    return data


def _measurement_from_dict(data: dict):
    data = dict(data)
    kind = data.pop("kind")
    data["label_offset_px"] = _tuple(data["label_offset_px"], 2)

    if kind == "area":
        data["sources"] = [
            SourceRef(layer_id=s["layer_id"], indices=np.array(s["indices"], dtype=np.uint32))
            for s in data["sources"]
        ]
        data["centroid"] = _tuple(data["centroid"], 3)
        data["boundary_px_at_creation"] = [
            _tuple(p, 2) for p in data["boundary_px_at_creation"]
        ]
        return AreaMeasurement(**data)

    data["p1"] = _tuple(data["p1"], 3)
    data["p2"] = _tuple(data["p2"], 3)
    return DistanceMeasurement(**data)


def _note_from_dict(data: dict) -> NoteAnnotation:
    data = dict(data)
    data["anchor"] = _tuple(data["anchor"], 3) if data.get("anchor") is not None else None
    data["screen_pos_frac"] = (
        _tuple(data["screen_pos_frac"], 2) if data.get("screen_pos_frac") is not None else None
    )
    data["label_offset_px"] = _tuple(data["label_offset_px"], 2)
    return NoteAnnotation(**data)


def load_project(document: Document, path: str, ply_loader: PlyLoader) -> Layer:
    """Load a .ppsproj into `document`, returning the restored original layer.

    `ply_loader` is injected (rather than importing pps.core.ply_loader
    directly) so this module stays testable without VTK/Qt/a real PLY file.
    """
    with zipfile.ZipFile(path, "r") as zf:
        project = json.loads(zf.read("project.json").decode("utf-8"))

        ply_path = _resolve_ply_path(project, path)
        cloud = ply_loader(ply_path, project["distance_field"])

        document._clear_state()
        document.source_path = ply_path
        document.project_info = parse_filename(ply_path)
        document.distance_field = project["distance_field"]
        document.target_min = project["target_min"]
        document.target_max = project["target_max"]

        for layer_data in project["layers"]:
            sources = [
                SourceRef(layer_id=s["layer_id"], indices=np.array(s["indices"], dtype=np.uint32))
                for s in layer_data.get("sources", [])
            ]
            if layer_data["is_original"]:
                layer = Layer(
                    id=layer_data["id"],
                    name=layer_data["name"],
                    points=cloud.points,
                    distances=cloud.distances,
                    visible=layer_data["visible"],
                    is_original=True,
                    color=None,
                )
            else:
                points = np.load(io.BytesIO(zf.read(layer_data["points_file"])))
                distances = np.load(io.BytesIO(zf.read(layer_data["distances_file"])))
                layer = Layer(
                    id=layer_data["id"],
                    name=layer_data["name"],
                    points=points,
                    distances=distances,
                    visible=layer_data["visible"],
                    is_original=False,
                    color=tuple(layer_data["color"]) if layer_data["color"] else None,
                    sources=sources,
                )
            document.layer_manager.add_layer(layer)

        document.annotations.extend(_note_from_dict(d) for d in project["annotations"])
        document.measurements.extend(
            _measurement_from_dict(d) for d in project["measurements"]
        )
        for layer in document.layer_manager.layers:
            document._sync_layer_annotations(layer.id)

        document.camera_state = project.get("camera")

    document.mark_clean()
    document.reset.emit()
    return document.layer_manager.original


def _resolve_ply_path(project: dict, project_file_path: str) -> str:
    absolute = project.get("ply_path_absolute")
    if absolute and os.path.exists(absolute):
        return absolute

    relative = project.get("ply_path_relative")
    if relative:
        candidate = os.path.normpath(
            os.path.join(os.path.dirname(os.path.abspath(project_file_path)), relative)
        )
        if os.path.exists(candidate):
            return candidate

    raise FileNotFoundError(
        "Could not locate the source PLY for this project "
        f"(tried '{absolute}' and relative path '{relative}')."
    )
