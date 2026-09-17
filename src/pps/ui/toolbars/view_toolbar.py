"""Camera view preset toolbar."""

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QToolBar

from pps.render import camera
from pps.ui.icons import load_icon

# (label, view function, shortcut, icon name)
_VIEWS = [
    ("Reset", camera.reset_view, "Home", "view_reset"),
    ("Top", camera.view_top, "T", "view_top"),
    ("Bottom", camera.view_bottom, "G", "view_bottom"),
    ("Front", camera.view_front, "F", "view_front"),
    ("Back", camera.view_back, "B", "view_back"),
    ("Right", camera.view_right, "R", "view_right"),
    ("Left", camera.view_left, "L", "view_left"),
    ("Iso", camera.view_iso, "I", "view_iso"),
]


class ViewToolbar(QToolBar):
    def __init__(self, viewport, parent=None):
        super().__init__("View", parent)
        self.setObjectName("toolbar_view")
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.setIconSize(QSize(20, 20))

        self._actions = []
        self._icon_names = []
        self._icon_color = "#dfe3ea"

        for label, view_fn, shortcut, icon_name in _VIEWS:
            action = QAction(label, self)
            action.setIcon(load_icon(icon_name, self._icon_color))
            action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(self._make_handler(viewport, view_fn))
            self.addAction(action)
            self._actions.append(action)
            self._icon_names.append(icon_name)

    @staticmethod
    def _make_handler(viewport, view_fn):
        def handler(_checked=False):
            view_fn(viewport.plotter)
            viewport.render()

        return handler

    def set_icon_color(self, color: str) -> None:
        self._icon_color = color
        for action, icon_name in zip(self._actions, self._icon_names):
            action.setIcon(load_icon(icon_name, color))
