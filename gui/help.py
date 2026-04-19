from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QWidget
)
from PyQt5.QtCore import Qt


class HotkeysDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⌨️ Keyboard Shortcuts")
        self.resize(500, 500)

        main_layout = QVBoxLayout(self)

        # Scroll area (tránh bị dài quá)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        content = QWidget()
        layout = QVBoxLayout(content)

        # Helper tạo section đẹp
        def section(title, text):
            box = QFrame()
            box.setStyleSheet("""
                QFrame {
                    background: #2b2b2b;
                    border-radius: 10px;
                    padding: 10px;
                }
            """)
            v = QVBoxLayout(box)

            lbl_title = QLabel(title)
            lbl_title.setStyleSheet("""
                font-size: 16px;
                font-weight: bold;
                color: #00d0ff;
            """)

            lbl_text = QLabel(text)
            lbl_text.setTextFormat(Qt.RichText)
            lbl_text.setStyleSheet("""
                font-size: 13px;
                color: #dddddd;
            """)
            lbl_text.setWordWrap(True)

            v.addWidget(lbl_title)
            v.addWidget(lbl_text)
            return box

        # Sections
        layout.addWidget(section("🎥 Camera Controls", """
        <b>Key T</b> : Top view<br>
        <b>Key G</b> : Bottom view<br>
        <b>Key F</b> : Front view<br>
        <b>Key B</b> : Back view<br>
        <b>Key R</b> : Right view<br>
        <b>Key L</b> : Left view<br>
        <b>I</b> : Isometric view
        """))

        layout.addWidget(section("🖱️ Mouse", """
        Left drag  : Rotate<br>
        Right drag : Zoom<br>
        Middle     : Pan
        """))

        layout.addWidget(section("📝 Annotation Tools", """
        <b>Key 1</b> : Add Text annotation<br>
        <b>Key 2</b> : Add Line annotation<br>
        <b>Key 3</b> : Move annotation<br>
        <b>Key 4</b> : Delete annotation
        """))

        layout.addWidget(section("⚙️ Other", """
        <b>Ctrl + O</b> : Open file<br>
        <b>Ctrl + S</b> : Save<br>
        <b>Esc</b> : Clear selection
        """))

        layout.addStretch()
        scroll.setWidget(content)

        # Close button
        btn_close = QPushButton("Close")
        btn_close.setStyleSheet("""
            QPushButton {
                background: #007acc;
                color: white;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #009cff;
            }
        """)
        btn_close.clicked.connect(self.close)

        main_layout.addWidget(scroll)
        main_layout.addWidget(btn_close, alignment=Qt.AlignRight)