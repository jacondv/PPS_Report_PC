"""
ColorLegend: a compact 3-band thickness classification key drawn on the
overlay render layer, so it's always visible on top of the cloud and gets
captured by viewport.screenshot() the same way tool previews do — which is
exactly why the PDF report picks it up automatically (Phase-6 contract:
the report screenshot is whatever the viewport currently shows).
"""

import os

import numpy as np

from pps.render.color_legend import ColorLegend
from pps.render.viewport import Viewport


def test_legend_bands_and_visibility_toggle(qtbot, tmp_path):
    viewport = Viewport()
    qtbot.addWidget(viewport)
    viewport.resize(400, 400)

    legend = ColorLegend(viewport.overlay_renderer)
    legend.update(
        color_below=(1.0, 0.0, 0.0),
        color_within=(0.0, 1.0, 0.0),
        color_above=(0.0, 0.0, 1.0),
        target_min=40, target_max=60,
    )

    viewport.show()
    qtbot.waitExposed(viewport)
    viewport.render()

    out_path = os.path.join(str(tmp_path), "legend.png")
    viewport.screenshot(out_path)
    viewport.close()

    from PIL import Image
    img = np.array(Image.open(out_path).convert("RGB"))
    h, w, _ = img.shape

    # Bar sits near the right edge; sample one pixel inside each band's
    # expected vertical position (bottom -> top: red, green, blue), image
    # rows run top-to-bottom while our normalized y runs bottom-to-top.
    x = int(w * (1.0 - 0.025 - 0.014))  # center of the bar horizontally
    y_below = int(h * (1.0 - (0.34 + 0.32 / 6)))    # bottom third -> red
    y_within = int(h * (1.0 - (0.34 + 0.32 / 2)))   # middle third -> green
    y_above = int(h * (1.0 - (0.34 + 5 * 0.32 / 6)))  # top third -> blue

    def is_close(pixel, rgb, tol=40):
        return all(abs(int(pixel[i]) - rgb[i]) < tol for i in range(3))

    assert is_close(img[y_below, x], (255, 0, 0))
    assert is_close(img[y_within, x], (0, 255, 0))
    assert is_close(img[y_above, x], (0, 0, 255))


def test_legend_set_visible_hides_all_actors(qtbot):
    viewport = Viewport()
    qtbot.addWidget(viewport)

    legend = ColorLegend(viewport.overlay_renderer)
    legend.update((1, 0, 0), (0, 1, 0), (0, 0, 1), 40, 60)

    legend.set_visible(False)
    for actor, _points in legend._bands:
        assert actor.GetVisibility() == 0
    assert legend._label_min.GetVisibility() == 0
    assert legend._label_max.GetVisibility() == 0

    legend.set_visible(True)
    for actor, _points in legend._bands:
        assert actor.GetVisibility() == 1

    viewport.close()
