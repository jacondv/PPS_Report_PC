from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import QDialog, QToolTip
from .annotation_base import Annotation
from PyQt5.QtWidgets import QVBoxLayout, QLabel, QTextEdit, QDialogButtonBox
from PyQt5.QtGui import QColor

class TextAnnotationDialog(QDialog):
    def __init__(self, parent=None, initial_text="", initial_color=QColor(0, 0, 0), initial_size=14):
        super().__init__(parent)
        self.setWindowTitle("Text Annotation")
        self.setModal(True)
        self.resize(420, 320)

        self._color = initial_color

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        label = QLabel("Enter annotation text:")
        layout.addWidget(label)

        self.text_edit = QTextEdit(self)
        self.text_edit.setPlainText(initial_text)
        self.text_edit.setFixedHeight(160)
        layout.addWidget(self.text_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        
    def properties(self):
        return {
            "text": self.text_edit.toPlainText().strip(),
        }

class TextAnnotation(Annotation):
    name = "text"
    STATE_START = 0
    STATE_END = 1
    def __init__(self, viewer):
        super().__init__(viewer)
        self.text = None
        self.state = self.STATE_START

    def on_activate(self):
        self.viewer.setCursor(Qt.IBeamCursor)
        self._active = True

    def on_deactivate(self):
        self._active = False
        self.viewer.unsetCursor()
        self.text = None
        self.state = self.STATE_START
        self.viewer._clear_annotation_preview()
        self.viewer._restore_camera()
        self.viewer._reset_toolbar_buttons()  # 🔥 FIX button vẫn active

    def on_finish(self):
        self.viewer.annotation_manager.activate(None)

    def on_cancel(self):
        self.viewer.annotation_manager.activate(None)

    def on_mouse_move(self, x, y):
        self.annotation["text_position"] = (int(x), int(y))
        self.annotation["text"] = self.text
        if self.text is not None:
            self.viewer._update_text_preview(self.annotation)
    
    def create_annotation(self):
        viewer = self.viewer
        style = viewer._current_annotation_style()

        annotation = self.annotation.copy()


        actor = viewer._create_text_actor(annotation)
        
        annotation["actor"] = actor

        viewer._annotations.append({
            "layer_name": viewer._annotation_layer_name,
            "annotation": annotation,
        })

        viewer.signals.annotation_added.emit(
            viewer._annotation_layer_name,
            {
                "action": "add",
                "annotation": annotation,
            }
        )

    def on_left_click(self, x, y):
        if not self._active:
            return

        viewer = self.viewer
        if self.state == self.STATE_START:
            dialog = TextAnnotationDialog(parent=viewer)
            if dialog.exec_() != QDialog.Accepted:
                self.on_cancel()
                return

            props = dialog.properties()
            self.text = props.get("text", "").strip()
            if self.text is None or self.text == "":
                self.on_cancel()
                return

            self.state = self.STATE_END

            style = viewer._current_annotation_style()
            self.annotation.update({
                "type": "text",
                "text": self.text,
                "color": style["color"],
                "font_size": style["font_size"],
                "text_position": (int(x), int(y)),
            })
            
            return


        self.create_annotation()

        self.on_finish()

   