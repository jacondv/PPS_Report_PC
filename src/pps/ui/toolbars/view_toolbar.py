"""Camera view preset toolbar."""

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QToolBar

from pps.render import camera

_VIEWS = [
    ("Reset", camera.reset_view, "Home"),
    ("Top", camera.view_top, "T"),
    ("Bottom", camera.view_bottom, "G"),
    ("Front", camera.view_front, "F"),
    ("Back", camera.view_back, "B"),
    ("Right", camera.view_right, "R"),
    ("Left", camera.view_left, "L"),
    ("Iso", camera.view_iso, "I"),
]


class ViewToolbar(QToolBar):
    def __init__(self, viewport, parent=None):
        super().__init__("View", parent)
        self.setObjectName("toolbar_view")

        for label, view_fn, shortcut in _VIEWS:
            action = QAction(label, self)
            action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(self._make_handler(viewport, view_fn))
            self.addAction(action)

    @staticmethod
    def _make_handler(viewport, view_fn):
        def handler(_checked=False):
            view_fn(viewport.plotter)
            viewport.render()

        return handler
