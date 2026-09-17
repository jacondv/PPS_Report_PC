"""Tool toolbar: one checkable, mutually-exclusive action per Tool, kept in
sync with ToolManager (which is the source of truth for the active tool)."""

from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import QToolBar

_TOOLS = [
    ("", "Navigate", "V"),
    ("region_select", "Select Region", "S"),
    ("measure_distance", "Measure Distance", "D"),
    ("measure_area", "Measure Area", "A"),
    ("note", "Note", "N"),
]


class ToolToolbar(QToolBar):
    def __init__(self, tool_manager, parent=None):
        super().__init__("Tools", parent)
        self.setObjectName("toolbar_tools")
        self.tool_manager = tool_manager

        self._group = QActionGroup(self)
        self._group.setExclusive(True)
        self._actions = {}

        for tool_id, label, shortcut in _TOOLS:
            action = QAction(label, self)
            action.setCheckable(True)
            action.setShortcut(QKeySequence(shortcut))
            action.setChecked(tool_id == "")
            action.triggered.connect(lambda _checked=False, tid=tool_id: tool_manager.activate(tid or None))
            self._group.addAction(action)
            self.addAction(action)
            self._actions[tool_id] = action

        tool_manager.tool_changed.connect(self._on_tool_changed)

        self.set_cloud_loaded(False)

    def _on_tool_changed(self, tool_id: str) -> None:
        action = self._actions.get(tool_id or "")
        if action is not None:
            action.blockSignals(True)
            action.setChecked(True)
            action.blockSignals(False)

    def set_cloud_loaded(self, loaded: bool) -> None:
        """Tools can only be active while a point cloud is loaded; without
        one, force back to (disabled) Navigate."""
        for action in self._actions.values():
            action.setEnabled(loaded)
        if not loaded:
            self.tool_manager.activate(None)
