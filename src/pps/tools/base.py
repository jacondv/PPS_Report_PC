"""
Tool framework: a normalized input event model plus the Tool ABC.

A Tool never touches Qt widgets or VTK objects directly except through
ToolContext — it never reaches into the viewport, MainWindow, or another
tool. All coordinates are VTK-convention physical pixels (origin
bottom-left), already corrected for devicePixelRatio by ToolManager.
"""

from abc import ABC
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, Optional


class PointerEventType(Enum):
    PRESS = auto()
    MOVE = auto()
    RELEASE = auto()
    DOUBLE_CLICK = auto()


class MouseButton(Enum):
    NONE = auto()
    LEFT = auto()
    RIGHT = auto()
    MIDDLE = auto()


@dataclass(frozen=True)
class PointerEvent:
    kind: PointerEventType
    x: float
    y: float
    button: MouseButton = MouseButton.NONE
    shift: bool = False
    ctrl: bool = False
    alt: bool = False


@dataclass(frozen=True)
class KeyEvent:
    key: str  # "Escape", "Return", "BackSpace", "Delete", ...
    shift: bool = False
    ctrl: bool = False
    alt: bool = False


class ToolContext:
    """The only thing a Tool is allowed to touch."""

    def __init__(
        self,
        document,
        viewport,
        overlay,
        undo_stack,
        set_status: Callable[[str], None],
        request_render: Callable[[], None],
    ):
        self.document = document
        self.viewport = viewport
        self.overlay = overlay
        self.undo_stack = undo_stack
        self.set_status = set_status
        self.request_render = request_render


class Tool(ABC):
    id: str = ""
    label: str = ""
    shortcut: str = ""
    cursor: Optional[str] = None  # see tools/manager._CURSOR_MAP

    def __init__(self):
        self._ctx: Optional[ToolContext] = None
        self._scratch = None

    # ------------------------------------------------------------------ lifecycle (called by ToolManager only)
    def activate(self, ctx: ToolContext) -> None:
        self._ctx = ctx
        self._scratch = ctx.overlay.scratch()
        self.on_activate()

    def deactivate(self) -> None:
        try:
            self.cancel()
        finally:
            if self._scratch is not None:
                self._scratch.clear()
            self.on_deactivate()
            self._ctx = None
            self._scratch = None

    # ------------------------------------------------------------------ override points
    def on_activate(self) -> None:
        pass

    def on_deactivate(self) -> None:
        pass

    def cancel(self) -> None:
        """Abort any in-progress multi-step state; return to idle. Called on
        ESC and whenever the tool is about to be deactivated."""

    def is_idle(self) -> bool:
        """True when the tool has no in-progress state (used to decide
        whether a first ESC just cancels, or should fall through to
        Navigate)."""
        return True

    def handle_pointer(self, event: PointerEvent) -> bool:
        return False

    def handle_key(self, event: KeyEvent) -> bool:
        return False

    def status_hint(self) -> str:
        return ""

    # ------------------------------------------------------------------ helpers for subclasses
    @property
    def ctx(self) -> Optional[ToolContext]:
        return self._ctx

    @property
    def scratch(self):
        return self._scratch
