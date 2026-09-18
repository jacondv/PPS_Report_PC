"""Tool toolbar: one checkable, mutually-exclusive action per Tool, kept in
sync with ToolManager (which is the source of truth for the active tool)."""

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import QToolBar

from pps.ui.icons import load_icon

# (tool_id, label, shortcuts, icon name) — each tool also gets a "1".."6"
# number-key shortcut (in activation order) alongside its mnemonic letter.
_TOOLS = [
    ("", "Navigate", ["V", "1"], "navigate"),
    ("region_select", "Select", ["S", "2"], "select_region"),
    ("measure_distance", "Distance", ["D", "3"], "measure_distance"),
    ("measure_area", "Area", ["A", "4"], "measure_area"),
    ("note", "Note", ["N", "5"], "note"),
    ("annotation", "Annotation", ["G", "6"], "annotation"),
]


class ToolToolbar(QToolBar):
    def __init__(self, tool_manager, parent=None):
        super().__init__("Tools", parent)
        self.setObjectName("toolbar_tools")
        self.tool_manager = tool_manager
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.setIconSize(QSize(22, 22))

        self._group = QActionGroup(self)
        self._group.setExclusive(True)
        self._actions = {}
        self._icon_names = {}
        self._icon_color = "#dfe3ea"

        for tool_id, label, shortcuts, icon_name in _TOOLS:
            action = QAction(label, self)
            action.setIcon(load_icon(icon_name, self._icon_color))
            action.setCheckable(True)
            action.setShortcuts([QKeySequence(s) for s in shortcuts])
            action.setChecked(tool_id == "")
            action.triggered.connect(lambda _checked=False, tid=tool_id: tool_manager.activate(tid or None))
            self._group.addAction(action)
            self.addAction(action)
            self._actions[tool_id] = action
            self._icon_names[tool_id] = icon_name

        tool_manager.tool_changed.connect(self._on_tool_changed)

        self.set_cloud_loaded(False)

    def _on_tool_changed(self, tool_id: str) -> None:
        action = self._actions.get(tool_id or "")
        if action is not None:
            # Do NOT blockSignals here: setChecked() only emits toggled (never
            # triggered, so there's no risk of re-entering activate()), and
            # QActionGroup's mutual-exclusion enforcement listens on toggled —
            # blocking it left the previously active button visually stuck
            # checked whenever the switch to Navigate came from code (Escape,
            # document reset, cloud unloaded) instead of a direct button click.
            action.setChecked(True)

    def set_cloud_loaded(self, loaded: bool) -> None:
        """Tools can only be active while a point cloud is loaded; without
        one, force back to (disabled) Navigate."""
        for action in self._actions.values():
            action.setEnabled(loaded)
        if not loaded:
            self.tool_manager.activate(None)

    def set_icon_color(self, color: str) -> None:
        self._icon_color = color
        for tool_id, action in self._actions.items():
            action.setIcon(load_icon(self._icon_names[tool_id], color))
