"""The default tool: consumes nothing, lets VTK's own camera style handle
every mouse/keyboard event (orbit, pan, zoom)."""

from pps.tools.base import Tool


class NavigateTool(Tool):
    id = "navigate"
    label = "Navigate"
    shortcut = "V"
    cursor = None

    def status_hint(self) -> str:
        return "Left-drag: rotate  |  Right-drag/wheel: zoom  |  Middle-drag: pan"
