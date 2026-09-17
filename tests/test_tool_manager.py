"""
ToolManager contract tests: exclusivity, mandatory cleanup on switch, and
the two-tier ESC behavior. Uses a real Qt widget + real QMouseEvent/
QKeyEvent objects fed straight into ToolManager.eventFilter() (bypassing
the Qt event queue for determinism), with two trivial recording tools
instead of the real ones.
"""

import vtk
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QWidget

from pps.tools.base import PointerEvent, Tool
from pps.tools.manager import ToolManager


class RecordingTool(Tool):
    def __init__(self, tool_id, cursor=None):
        super().__init__()
        self.id = tool_id
        self.cursor = cursor
        self.events = []
        self.activate_count = 0
        self.deactivate_count = 0
        self.cancel_count = 0
        self._idle = True

    def on_activate(self):
        self.activate_count += 1
        self.scratch.add(vtk.vtkActor2D())  # pretend we drew something

    def on_deactivate(self):
        self.deactivate_count += 1

    def cancel(self):
        self.cancel_count += 1
        self._idle = True

    def is_idle(self):
        return self._idle

    def handle_pointer(self, event: PointerEvent) -> bool:
        self.events.append(event)
        self._idle = False
        return True  # consume everything


def make_manager(widget, tools):
    ctx_holders = {}

    def ctx_factory():
        from pps.render.overlay import Overlay

        if "overlay" not in ctx_holders:
            ctx_holders["overlay"] = Overlay(vtk.vtkRenderer())
        from pps.tools.base import ToolContext

        return ToolContext(
            document=None,
            viewport=None,
            overlay=ctx_holders["overlay"],
            undo_stack=None,
            set_status=lambda s: None,
            request_render=lambda: None,
        )

    manager = ToolManager(ctx_factory, widget)
    for tool in tools:
        manager.register(tool)
    return manager


def mouse_press(widget, x, y):
    return QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(x, y),
        QPointF(x, y),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


def key_press(key):
    return QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)


def test_activate_and_toggle_back_to_navigate(qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)
    tool_a = RecordingTool("a")
    manager = make_manager(widget, [tool_a])

    manager.activate("a")
    assert manager.active_id == "a"
    assert tool_a.activate_count == 1

    manager.activate("a")  # toggle
    assert manager.active_id is None
    assert tool_a.deactivate_count == 1


def test_switching_tools_clears_previous_scratch_and_cursor(qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)
    tool_a = RecordingTool("a", cursor="cross")
    tool_b = RecordingTool("b", cursor="ibeam")
    manager = make_manager(widget, [tool_a, tool_b])

    manager.activate("a")
    tool_a_scratch = tool_a.scratch  # capture before deactivate() drops the ref
    assert len(tool_a_scratch) == 1
    assert widget.cursor().shape() == Qt.CursorShape.CrossCursor

    manager.activate("b")
    assert tool_a.deactivate_count == 1
    assert len(tool_a_scratch) == 0  # wiped as part of deactivate()
    assert tool_a.scratch is None
    assert widget.cursor().shape() == Qt.CursorShape.IBeamCursor
    assert tool_b.activate_count == 1


def test_events_only_reach_active_tool(qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)
    tool_a = RecordingTool("a")
    tool_b = RecordingTool("b")
    manager = make_manager(widget, [tool_a, tool_b])

    manager.activate("a")
    consumed = manager.eventFilter(widget, mouse_press(widget, 5, 5))
    assert consumed is True
    assert len(tool_a.events) == 1

    manager.activate("b")
    manager.eventFilter(widget, mouse_press(widget, 6, 6))
    assert len(tool_a.events) == 1  # unchanged — tool_a received nothing more
    assert len(tool_b.events) == 1


def test_no_active_tool_never_consumes_events(qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)
    manager = make_manager(widget, [])

    consumed = manager.eventFilter(widget, mouse_press(widget, 0, 0))
    assert consumed is False


def test_escape_two_tier(qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)
    tool_a = RecordingTool("a")
    manager = make_manager(widget, [tool_a])

    manager.activate("a")
    manager.eventFilter(widget, mouse_press(widget, 1, 1))  # make it non-idle
    assert tool_a.is_idle() is False

    manager.eventFilter(widget, key_press(Qt.Key.Key_Escape))
    assert tool_a.cancel_count == 1
    assert manager.active_id == "a"  # first Escape: still active, just reset

    manager.eventFilter(widget, key_press(Qt.Key.Key_Escape))
    assert manager.active_id is None  # second Escape (now idle): back to Navigate


def test_activate_grabs_keyboard_focus_so_escape_works_without_a_prior_click(qtbot):
    """Regression: Escape used to do nothing until the user first clicked
    inside the 3D view, because key events only reach ToolManager's
    eventFilter while the interactor widget itself has focus. Asserting the
    real OS-level hasFocus() is unreliable in a batch test run (depends on
    window-manager activation state left over from earlier tests), so this
    spies on setFocus() being called instead."""
    widget = QWidget()
    qtbot.addWidget(widget)
    focus_calls = []
    widget.setFocus = lambda *a, **k: focus_calls.append(1)

    tool_a = RecordingTool("a")
    manager = make_manager(widget, [tool_a])

    manager.activate("a")
    assert len(focus_calls) == 1

    manager.activate(None)  # back to Navigate
    assert len(focus_calls) == 2


def test_document_reset_returns_to_navigate(qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)
    tool_a = RecordingTool("a")
    manager = make_manager(widget, [tool_a])

    manager.activate("a")
    manager.on_document_reset()

    assert manager.active_id is None
    assert tool_a.deactivate_count == 1
