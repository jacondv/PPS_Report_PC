"""
ToolToolbar: exactly one action stays checked at a time, including when the
switch back to Navigate is driven by code (Escape, document reset, cloud
unloaded) rather than a direct button click — a regression that used to
leave the previously active tool's button visually stuck "on" because
_on_tool_changed() blocked signals, bypassing QActionGroup's own
mutual-exclusion enforcement (which listens on the `toggled` signal).
"""

from pps.tools.manager import ToolManager
from pps.ui.toolbars.tool_toolbar import ToolToolbar


class _StubTool:
    def __init__(self, tool_id):
        self.id = tool_id
        self.cursor = None

    def activate(self, ctx):
        pass

    def deactivate(self):
        pass

    def cancel(self):
        pass

    def is_idle(self):
        return True

    def handle_pointer(self, event):
        return False

    def handle_key(self, event):
        return False

    def status_hint(self):
        return ""


def _checked_ids(toolbar):
    return [tid for tid, action in toolbar._actions.items() if action.isChecked()]


def test_only_one_action_checked_after_programmatic_switch_back_to_navigate(qtbot):
    from PySide6.QtWidgets import QWidget

    widget = QWidget()
    qtbot.addWidget(widget)
    manager = ToolManager(lambda: _FakeCtx(), widget)
    manager.register(_StubTool("region_select"))
    toolbar = ToolToolbar(manager)
    toolbar.set_cloud_loaded(True)

    manager.activate("region_select")
    assert _checked_ids(toolbar) == ["region_select"]

    # Programmatic switch back to Navigate (what Escape / document reset /
    # cloud-unloaded all do) must also clear the previously checked button.
    manager.activate(None)
    assert _checked_ids(toolbar) == [""]


class _FakeCtx:
    def set_status(self, _msg):
        pass
