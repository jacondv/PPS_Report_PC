"""
Manual demo: shows the new (Phase 1/2) viewport rendering the sample PLY.

There is no full MainWindow yet (that's Phase 6) — this just proves the
render stack works interactively. Run from the repo root:

    .venv\\Scripts\\python.exe scripts\\demo_viewport.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from pps.app.application import create_app
from pps.core.layers import LayerManager
from pps.core.ply_loader import load_ply
from pps.render.camera import reset_view
from pps.render.layer_renderer import LayerRenderer
from pps.render.viewport import Viewport

SAMPLE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "sample", "2_thickness_01#20260203_093652#cloud_compared_07.ply",
)


def main():
    app = create_app(sys.argv)

    cloud = load_ply(SAMPLE, "distances")
    layer_manager = LayerManager()
    layer = layer_manager.set_original("sample.ply", cloud.points, cloud.distances)

    viewport = Viewport()
    viewport.setWindowTitle("PPS viewport demo (Phase 1/2)")
    viewport.resize(1000, 700)

    renderer = LayerRenderer(viewport.plotter)
    renderer.sync(layer, target_min=40, target_max=60, point_size=2)
    reset_view(viewport.plotter)

    viewport.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
