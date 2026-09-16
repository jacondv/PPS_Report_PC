"""
Overlay renderer (VTK layer 1) helpers.

Every tool owns exactly one ScratchGroup for its in-progress preview actors
(vertices, edges, rubber-band rectangle, ...). Clearing it is the ONE thing
that must always happen when a tool deactivates — Tool.deactivate() in
tools/base.py does this unconditionally, so a tool can never leak an actor
onto the screen after it stops being active.
"""

import vtk


class ScratchGroup:
    """A disposable set of actors on one renderer."""

    def __init__(self, renderer):
        self._renderer = renderer
        self._actors = []

    def add(self, actor):
        self._renderer.AddActor(actor)
        self._actors.append(actor)
        return actor

    def clear(self) -> None:
        for actor in self._actors:
            try:
                self._renderer.RemoveActor(actor)
            except Exception:
                pass
        self._actors = []

    def __len__(self) -> int:
        return len(self._actors)


class Overlay:
    """Owns the overlay renderer's shared HUD text and hands out scratch
    groups for tool previews."""

    def __init__(self, renderer):
        self.renderer = renderer

        self._hud = vtk.vtkTextActor()
        self._hud.SetPosition(10, 10)
        prop = self._hud.GetTextProperty()
        prop.SetFontSize(13)
        prop.SetColor(1.0, 1.0, 0.3)
        prop.SetBold(True)
        prop.SetShadow(True)
        self._hud.SetInput("")
        self._hud.SetVisibility(False)
        self.renderer.AddActor(self._hud)

    def set_hud_text(self, text: str) -> None:
        self._hud.SetInput(text or "")
        self._hud.SetVisibility(bool(text))

    def scratch(self) -> ScratchGroup:
        return ScratchGroup(self.renderer)
