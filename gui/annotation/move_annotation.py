from PyQt5.QtCore import Qt
from .annotation_base import Annotation
import vtk


class MoveAnnotation(Annotation):

    def __init__(self, viewer):
        super().__init__(viewer)
        self._picker = vtk.vtkPropPicker()

        self._selected_item = None
        self._dragging = False
        self._start_x = 0
        self._start_y = 0

    # =========================
    # ACTIVATE
    # =========================
    def on_activate(self):
        self._active = True
        self.viewer.setCursor(Qt.SizeAllCursor)

    def on_deactivate(self):
        self._active = False
        self.viewer.unsetCursor()
        self.viewer._restore_camera()
        self.viewer._reset_toolbar_buttons()
        self._clear()

    def on_finish(self):
        self.viewer.annotation_manager.activate(None)

    def on_cancel(self):
        self.viewer.annotation_manager.activate(None)

    def _clear(self):
        self._selected_item = None
        self._dragging = False


    def _move_annotation(self, ann, dx, dy):
        if ann.get("type") == "text":
            actor = ann.get("actor")
            actor.SetPosition(dx, dy)
            
        if ann.get("type") == "line_text":
            actor = ann.get("actor")
            annotation = ann
            points = annotation["points"]
            for i, p in enumerate(points):
                points[i] = (p[0] + dx, p[1] + dy)
            
            annotation["points"] = points

            self.viewer._update_line_text_preview(annotation)



    # =========================
    # PICK
    # =========================
    def on_left_click(self, x, y):

        viewer = self.viewer

        self._picker.Pick(x, y, 0, viewer._overlay_renderer)
        actor = self._picker.GetViewProp()

        if actor is None:
            return

        for item in viewer._annotations:
            ann = item["annotation"]

            ann_actor = ann.get("actor")

            # single
            if ann_actor == actor:
                self._selected_item = item
                break

            # multi (dict)
            if isinstance(ann_actor, dict):
                if actor in ann_actor.values():
                    self._selected_item = item
                    break

        if self._selected_item is None:
            return

        self._dragging = True
        self._start_x = x
        self._start_y = y

    # =========================
    # DRAG
    # =========================
    def on_mouse_move(self, x, y):

        if not self._dragging or not self._selected_item:
            return

        ann = self._selected_item["annotation"]
        
        if ann.get("type") == "text":
            actor = ann.get("actor")
            actor.SetPosition(x,y)

        if ann.get("type") == "line_text":
            actors = ann.get("actor")
            actors["line_actor"].SetPosition(x,y)
            actors["text_actor"].SetPosition(x,y)
            self._move_annotation(ann,x,y)

    # =========================
    # RELEASE
    # =========================
    def on_left_release(self, x, y):

        if not self._dragging:
            return

        self._dragging = False
        self._clear()

        self.on_finish()