from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QWidget
)
from PySide6.QtCore import Qt

from pps_report.gui.theme import SURFACE, BORDER, TEXT, TEXT_MUTED, ACCENT, ACCENT_HOVER


class HotkeysDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.resize(500, 500)

        main_layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)

        def section(title, text):
            box = QFrame()
            box.setStyleSheet(f"""
                QFrame {{
                    background: {SURFACE};
                    border: 1px solid {BORDER};
                    border-radius: 8px;
                    padding: 10px;
                }}
            """)
            v = QVBoxLayout(box)

            lbl_title = QLabel(title)
            lbl_title.setStyleSheet(f"""
                font-size: 15px;
                font-weight: 600;
                color: {ACCENT};
            """)

            lbl_text = QLabel(text)
            lbl_text.setTextFormat(Qt.RichText)
            lbl_text.setStyleSheet(f"""
                font-size: 13px;
                color: {TEXT};
            """)
            lbl_text.setWordWrap(True)

            v.addWidget(lbl_title)
            v.addWidget(lbl_text)
            return box

        layout.addWidget(section("Camera Controls", """
        <b>Key T</b> : Top view<br>
        <b>Key G</b> : Bottom view<br>
        <b>Key F</b> : Front view<br>
        <b>Key B</b> : Back view<br>
        <b>Key R</b> : Right view<br>
        <b>Key L</b> : Left view<br>
        <b>I</b> : Isometric view
        """))

        layout.addWidget(section("Mouse", """
        Left drag  : Rotate<br>
        Right drag : Zoom<br>
        Middle     : Pan
        """))

        layout.addWidget(section("Annotation Tools", """
        <b>Key 1</b> : Add Text annotation<br>
        <b>Key 2</b> : Add Line annotation<br>
        <b>Key 3</b> : Move annotation<br>
        <b>Key 4</b> : Delete annotation<br>
        <b>Key 5</b> : Edit annotation style
        """))

        layout.addWidget(section("Other", """
        <b>Ctrl + O</b> : Open file<br>
        <b>Ctrl + E</b> : Export PDF report<br>
        <b>Esc</b> : Clear selection
        """))

        layout.addStretch()
        scroll.setWidget(content)

        btn_close = QPushButton("Close")
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT};
                color: white;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {ACCENT_HOVER};
            }}
        """)
        btn_close.clicked.connect(self.close)

        main_layout.addWidget(scroll)
        main_layout.addWidget(btn_close, alignment=Qt.AlignRight)
