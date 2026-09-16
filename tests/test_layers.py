import numpy as np

from pps.core.layers import LayerManager


def test_nearest_layer_id_picks_closest_layer():
    lm = LayerManager()
    lm.set_original("original", np.array([[0.0, 0.0, 0.0]]), np.array([10.0]))
    lm.add_segment(np.array([[100.0, 0.0, 0.0]]), np.array([20.0]), name="far_segment")

    assert lm.nearest_layer_id((1.0, 0.0, 0.0)) == lm.original.id
    assert lm.nearest_layer_id((99.0, 0.0, 0.0)) == lm.get("far_segment").id


def test_nearest_layer_id_ignores_hidden_layers():
    lm = LayerManager()
    lm.set_original("original", np.array([[0.0, 0.0, 0.0]]), np.array([10.0]))
    seg = lm.add_segment(np.array([[1.0, 0.0, 0.0]]), np.array([20.0]), name="closer_but_hidden")
    seg.visible = False

    # closer_but_hidden is nearer to (1,0,0) but hidden, so original wins
    assert lm.nearest_layer_id((1.0, 0.0, 0.0)) == lm.original.id


def test_nearest_layer_id_empty_manager_returns_none():
    lm = LayerManager()
    assert lm.nearest_layer_id((0.0, 0.0, 0.0)) is None
