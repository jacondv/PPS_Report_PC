import os

# Force pytest-qt and qtpy/pyvistaqt to use PySide6 before any Qt import,
# in case another Qt binding is also present in the environment.
os.environ.setdefault("QT_API", "pyside6")
os.environ.setdefault("PYTEST_QT_API", "pyside6")

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE_PLY = os.path.join(
    REPO_ROOT, "sample", "2_thickness_01#20260203_093652#cloud_compared_07.ply"
)


@pytest.fixture(scope="session")
def sample_ply_path():
    return SAMPLE_PLY
