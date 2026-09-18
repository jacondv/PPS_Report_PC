"""
ToolManager: exactly one active tool at a time, routed via a single Qt
eventFilter installed on the viewport's interactor widget.

This replaces the old code's two competing dispatch paths (a permanent Qt
observer on the viewer plus a second one an active tool would add on top of
it) with one funnel: a tool's handle_pointer()/handle_key() returning True
means "I consumed this", the event never reaches VTK's own camera style;
returning False lets navigation (orbit/pan/zoom) work normally even while a
tool is active, for any button/gesture that tool doesn't care about.
"""

from typing import Callable, Dict, Optional

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QCursor

from pps.tools.base import KeyEvent, MouseButton, PointerEvent, PointerEventType, Tool, ToolContext

_BUTTON_MAP = {
    Qt.MouseButton.LeftButton: MouseButton.LEFT,
    Qt.MouseButton.RightButton: MouseButton.RIGHT,
    Qt.MouseButton.MiddleButton: MouseButton.MIDDLE,
}

_CURSOR_MAP = {
    "cross": Qt.CursorShape.CrossCursor,
    "ibeam": Qt.CursorShape.IBeamCursor,
    "size_all": Qt.CursorShape.SizeAllCursor,
    "forbidden": Qt.CursorShape.ForbiddenCursor,
    "pointing_hand": Qt.CursorShape.PointingHandCursor,
}

_KEY_NAMES = {
    Qt.Key.Key_Escape: "Escape",
    Qt.Key.Key_Return: "Return",
    Qt.Key.Key_Enter: "Return",
    Qt.Key.Key_Backspace: "BackSpace",
    Qt.Key.Key_Delete: "Delete",
}


class ToolManager(QObject):
    tool_changed = Signal(str)  # active tool id, "" when back to Navigate

    def __init__(
        self,
        ctx_factory: Callable[[], ToolContext],
        interactor_widget,
        parent=None,
    ):
        """`ctx_factory` builds a fresh ToolContext on each activate() call,
        so it always captures the current document/viewport/overlay."""
        super().__init__(parent)
        self._ctx_factory = ctx_factory
        self._interactor_widget = interactor_widget
        self._tools: Dict[str, Tool] = {}
        self._active: Optional[Tool] = None
        self._active_id: Optional[str] = None

        interactor_widget.installEventFilter(self)

    def register(self, tool: Tool) -> None:
        # A tool with a falsy id ("" — e.g. NavigateTool) registers under the
        # same None key activate()/None uses for "Navigate", so it's an
        # actual Tool instance that runs instead of no tool at all.
        self._tools[tool.id or None] = tool

    @property
    def active_id(self) -> Optional[str]:
        return self._active_id

    @property
    def active_tool(self) -> Optional[Tool]:
        return self._active

    def activate(self, tool_id: Optional[str]) -> None:
        """Activate `tool_id`, or None/"" for Navigate. Activating the tool
        that is already active toggles back to Navigate."""
        tool_id = tool_id or None
        if tool_id == self._active_id:
            tool_id = None

        new_tool = self._tools.get(tool_id)
        if tool_id is not None and new_tool is None:
            return  # unknown id, ignore

        if self._active is not None:
            self._active.deactivate()
            self._interactor_widget.unsetCursor()

        self._active = new_tool
        self._active_id = tool_id

        if self._active is not None:
            ctx = self._ctx_factory()
            self._active.activate(ctx)
            self._apply_cursor(self._active.cursor)
            ctx.set_status(self._active.status_hint())
        else:
            self._ctx_factory().set_status("")

        # Keyboard events (Escape in particular) only reach this manager's
        # eventFilter while the interactor widget itself has focus. Without
        # this, Escape does nothing until the user first clicks inside the
        # 3D view — grab focus proactively whenever a tool (or Navigate)
        # becomes active so Escape/keys work right away.
        self._interactor_widget.setFocus()

        self.tool_changed.emit(tool_id or "")

    def cancel_active(self) -> None:
        """ESC: cancel in-progress state; a second ESC (tool already idle)
        falls through to Navigate."""
        if self._active is None:
            return
        if self._active.is_idle():
            self.activate(None)
        else:
            self._active.cancel()

    def on_document_reset(self) -> None:
        """Call when Document.reset fires (new file/project loaded)."""
        self.activate(None)

    def _apply_cursor(self, cursor_name: Optional[str]) -> None:
        shape = _CURSOR_MAP.get(cursor_name) if cursor_name else None
        if shape is not None:
            self._interactor_widget.setCursor(QCursor(shape))
        else:
            self._interactor_widget.unsetCursor()

    # ------------------------------------------------------------------ Qt event routing
    def eventFilter(self, obj, event) -> bool:
        if self._active is None:
            return False

        et = event.type()
        if et == QEvent.Type.MouseButtonPress:
            return self._dispatch_pointer(event, PointerEventType.PRESS)
        if et == QEvent.Type.MouseMove:
            return self._dispatch_pointer(event, PointerEventType.MOVE)
        if et == QEvent.Type.MouseButtonRelease:
            return self._dispatch_pointer(event, PointerEventType.RELEASE)
        if et == QEvent.Type.MouseButtonDblClick:
            return self._dispatch_pointer(event, PointerEventType.DOUBLE_CLICK)
        if et == QEvent.Type.KeyPress:
            return self._dispatch_key(event)
        return False

    def _dispatch_pointer(self, qevent, kind: PointerEventType) -> bool:
        dpr = self._interactor_widget.devicePixelRatioF()
        pos = qevent.position()
        height = self._interactor_widget.height()

        # Qt: logical pixels, origin top-left. VTK: physical pixels, origin
        # bottom-left. Both conversions matter at fractional DPI scaling.
        x = pos.x() * dpr
        y = (height - pos.y()) * dpr

        mods = qevent.modifiers()
        pe = PointerEvent(
            kind=kind,
            x=x,
            y=y,
            button=_BUTTON_MAP.get(qevent.button(), MouseButton.NONE),
            shift=bool(mods & Qt.KeyboardModifier.ShiftModifier),
            ctrl=bool(mods & Qt.KeyboardModifier.ControlModifier),
            alt=bool(mods & Qt.KeyboardModifier.AltModifier),
        )
        consumed = self._active.handle_pointer(pe)
        if consumed:
            self._request_render()
        return consumed

    def _dispatch_key(self, qevent) -> bool:
        key_name = _KEY_NAMES.get(qevent.key(), "")
        if key_name == "Escape":
            self.cancel_active()
            return True

        mods = qevent.modifiers()
        ke = KeyEvent(
            key=key_name,
            shift=bool(mods & Qt.KeyboardModifier.ShiftModifier),
            ctrl=bool(mods & Qt.KeyboardModifier.ControlModifier),
            alt=bool(mods & Qt.KeyboardModifier.AltModifier),
        )
        consumed = self._active.handle_key(ke)
        if consumed:
            self._request_render()
        return consumed

    def _request_render(self) -> None:
        if self._active is not None and self._active.ctx is not None:
            self._active.ctx.request_render()
