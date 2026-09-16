import hashlib
import json
import os

import numpy as np

from pps.core.layers import LayerManager
from pps.core.ply_loader import load_ply
from pps.scene.selection import Selection

GOLDEN_PATH = os.path.join(os.path.dirname(__file__), "golden", "sample_baseline.json")


def array_hash(arr: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest()


def make_layer_manager(layers):
    """layers: list of (name, distances_array, is_original)."""
    lm = LayerManager()
    for i, (name, distances, is_original) in enumerate(layers):
        points = np.column_stack([distances, distances, distances]).astype(np.float64)
        if is_original:
            lm.set_original(name, points, distances)
        else:
            lm.add_segment(points, distances, name=name)
    return lm


def test_select_by_distance_range_matches_golden_segment(sample_ply_path):
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        baseline = json.load(f)
    seg = baseline["distance_range_segment"]
    lo, hi = seg["range"]

    cloud = load_ply(sample_ply_path, "distances")
    lm = LayerManager()
    lm.set_original("sample.ply", cloud.points, cloud.distances)
    selection = Selection(lm)

    selection.select_by_distance_range(lo, hi)
    points, distances = selection.get_points_and_distances()

    assert len(points) == seg["num_points"]
    assert array_hash(points) == seg["points_hash"]
    assert array_hash(distances) == seg["distances_hash"]


def test_to_sources_preserves_layer_manager_order():
    lm = make_layer_manager([
        ("original", np.array([10.0, 60.0, 200.0]), True),
        ("seg_a", np.array([15.0, 65.0]), False),
        ("seg_b", np.array([300.0]), False),
    ])
    selection = Selection(lm)
    selection.select_by_distance_range(0, 1000)  # everything

    sources = selection.to_sources()
    layer_ids_in_order = [l.id for l in lm.layers]

    assert [ref.layer_id for ref in sources] == layer_ids_in_order
    for ref in sources:
        assert list(ref.indices) == sorted(ref.indices.tolist())


def test_replace_add_subtract_invert():
    lm = make_layer_manager([("original", np.array([10.0, 20.0, 30.0, 40.0]), True)])
    layer_id = lm.original.id
    selection = Selection(lm)

    selection.replace({layer_id: np.array([True, False, False, False])})
    assert selection.count() == 1

    selection.add({layer_id: np.array([False, True, False, False])})
    assert selection.count() == 2

    selection.subtract({layer_id: np.array([True, False, False, False])})
    assert selection.count() == 1
    assert selection.mask_for(layer_id).tolist() == [False, True, False, False]

    selection.invert()
    assert selection.mask_for(layer_id).tolist() == [True, False, True, True]
    assert selection.count() == 3

    selection.clear()
    assert selection.is_empty()


def test_select_all():
    lm = make_layer_manager([
        ("original", np.array([10.0, 20.0]), True),
        ("seg_a", np.array([30.0, 40.0, 50.0]), False),
    ])
    selection = Selection(lm)
    selection.select_all()
    assert selection.count() == 5
    assert not selection.is_empty()
