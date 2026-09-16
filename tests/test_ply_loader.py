from pps.core.ply_loader import load_ply, get_ply_fields, filter_by_distance


def test_get_ply_fields(sample_ply_path):
    fields = get_ply_fields(sample_ply_path)
    assert "distances" in fields
    assert {"x", "y", "z"}.issubset(fields)


def test_load_ply_shapes(sample_ply_path):
    cloud = load_ply(sample_ply_path, "distances")
    assert cloud.points.shape == (cloud.num_points, 3)
    assert cloud.distances.shape == (cloud.num_points,)


def test_filter_by_distance(sample_ply_path):
    cloud = load_ply(sample_ply_path, "distances")
    filtered = filter_by_distance(cloud, min_dist=75, max_dist=125)
    assert filtered.num_points <= cloud.num_points
    assert (filtered.distances >= 75).all()
    assert (filtered.distances <= 125).all()
