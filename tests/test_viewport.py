"""
Phase 1 spike checks: the PySide6 + pyvistaqt viewport renders a layer with
the correct threshold colors and, critically, that a screenshot captures
BOTH render layers (cloud + overlay) composited together — the PDF report
depends on tool previews/labels showing up in the exported screenshot.
"""

import os

import numpy as np
import pytest
import vtk

from pps.core.layers import LayerManager
from pps.core.ply_loader import load_ply
from pps.render.camera import reset_view
from pps.render.layer_renderer import LayerRenderer, threshold_colors
from pps.render.viewport import Viewport


def test_threshold_colors_matches_old_assign_colors():
    distances = np.array([10.0, 50.0, 100.0, 200.0])
    colors = threshold_colors(distances, target_min=40, target_max=60)

    assert colors[0].tolist() == [1.0, 0.0, 0.0]   # below -> red
    assert colors[1].tolist() == [0.0, 1.0, 0.0]   # within -> green
    assert colors[2].tolist() == [0.0, 0.0, 1.0]   # above (< 150) -> blue
    assert colors[3].tolist() == [0.0, 0.0, 1.0]   # far (>= 150) -> blue


def test_viewport_renders_layer_and_overlay(qtbot, sample_ply_path, tmp_path):
    cloud = load_ply(sample_ply_path, "distances")
    layer_manager = LayerManager()
    layer = layer_manager.set_original("sample.ply", cloud.points, cloud.distances)

    viewport = Viewport()
    qtbot.addWidget(viewport)
    viewport.resize(400, 300)

    renderer = LayerRenderer(viewport.plotter)
    actor = renderer.sync(layer, target_min=40, target_max=60, point_size=2)
    assert actor is not None
    reset_view(viewport.plotter)

    # Distinct yellow marker on the overlay (layer 1) render.
    marker = vtk.vtkTextActor()
    marker.SetInput("X")
    marker.SetPosition(5, 5)
    marker.GetTextProperty().SetFontSize(40)
    marker.GetTextProperty().SetColor(1.0, 1.0, 0.0)
    viewport.overlay_renderer.AddActor(marker)

    viewport.show()
    qtbot.waitExposed(viewport)
    viewport.render()

    out_path = os.path.join(str(tmp_path), "shot.png")
    viewport.screenshot(out_path)
    viewport.close()

    assert os.path.exists(out_path)
    assert os.path.getsize(out_path) > 0

    from PIL import Image
    img = np.array(Image.open(out_path).convert("RGB"))

    # Bottom-left corner (VTK y-axis is flipped vs image row order) should
    # contain the yellow overlay marker pixels, proving both render layers
    # were composited into the screenshot.
    corner = img[-40:, 0:40]
    is_yellowish = (
        (corner[:, :, 0] > 180) & (corner[:, :, 1] > 180) & (corner[:, :, 2] < 120)
    )
    assert is_yellowish.any(), "overlay layer content missing from screenshot"
