class AnnotationManager:
    def __init__(self):
        self.annotations = {}
        self.active_annotation = None

    def register(self, name, annotation):
        self.annotations[name] = annotation

    def activate(self, name):
        new_annotation = self.annotations.get(name)

        # annotation không tồn tại
        if name is not None and new_annotation is None:
            return

        # toggle off nếu click lại annotation đang active
        if self.active_annotation == new_annotation:
            self.active_annotation.on_deactivate()
            self.active_annotation = None
            return

        # deactivate annotation cũ
        if self.active_annotation:
            self.active_annotation.on_deactivate()

        self.active_annotation = new_annotation

        if self.active_annotation:
            self.active_annotation.on_activate()
            # This is a workaround to fix the issue where the camera interaction is still active after activating an annotation.
            self.active_annotation.viewer._iren.SetInteractorStyle(None)

