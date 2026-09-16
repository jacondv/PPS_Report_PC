from pps.core.filename_parser import parse_filename


def test_parse_filename_success(sample_ply_path):
    info = parse_filename(sample_ply_path)
    assert info.parse_success is True
    assert info.job_number == "sample"
    assert info.scan_time == "20260203_093652"
    assert info.segment_name == "cloud_compared_07"
    assert info.formatted_date == "03-Feb-2026"
    assert info.formatted_time == "09:36:52"


def test_parse_filename_fallback():
    info = parse_filename("/some/dir/not_matching_pattern.ply")
    assert info.parse_success is False
    assert info.original_filename == "not_matching_pattern.ply"
