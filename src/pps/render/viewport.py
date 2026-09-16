"""
3D viewport widget: wraps a pyvistaqt QtInteractor with a second VTK render
layer reserved for overlay content (selection HUD, tool previews, anchored
labels — added in later phases).
"""

from pps.app import qt_env  # noqa: F401  (sets QT_API before Qt/pyvista import)

import vtk
from PySide6.QtWidgets import QVBoxLayout, QWidget
from pyvistaqt import QtInteractor

from pps.render.overlay import Overlay

BACKGROUND_COLOR = "#1b1f27"


class Viewport(QWidget):
    """Owns the plotter and the two render layers (cloud + overlay)."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.plotter = QtInteractor(self)
        self.interactor_widget = self.plotter.interactor
        layout.addWidget(self.interactor_widget)

        self.plotter.set_background(BACKGROUND_COLOR)
        self.plotter.add_axes()
        self.plotter.enable_rubber_band_style()

        self.overlay_renderer = vtk.vtkRenderer()
        self.overlay_renderer.SetLayer(1)
        self.overlay_renderer.InteractiveOff()
        self.plotter.ren_win.SetNumberOfLayers(2)
        self.plotter.ren_win.AddRenderer(self.overlay_renderer)

        self.overlay = Overlay(self.overlay_renderer)

    def render(self) -> None:
        self.plotter.ren_win.Render()

    def screenshot(self, path: str, scale: int = 1) -> str:
        """Capture the full render window (both layers) to `path`."""
        self.plotter.screenshot(path, scale=scale)
        return path

    def close(self) -> None:
        self.plotter.close()
