"""
Dark, technical theme: tokens -> QSS + QPalette. Accent color is kept
separate from the red/green/blue thickness-classification colors used in
the 3D view, so the two color systems never get visually confused.
"""

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

TOKENS = {
    "bg0": "#14171c",       # window background
    "bg1": "#1b1f27",       # panel/dock background (matches Viewport.BACKGROUND_COLOR)
    "bg2": "#242933",       # input/list background
    "border": "#333a47",
    "text": "#dfe3ea",
    "text_muted": "#8b94a3",
    "accent": "#3b9dff",
    "accent_hover": "#5aade9",
    "danger": "#ff5d5d",
    "success": "#3ecf8e",
}


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setPalette(_build_palette())
    app.setStyleSheet(_build_qss())


def _build_palette() -> QPalette:
    t = TOKENS
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(t["bg0"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(t["bg2"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(t["bg1"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(t["bg1"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(t["bg2"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(t["accent"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(t["text_muted"]))
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(t["text_muted"])
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(t["text_muted"])
    )
    return palette


def _build_qss() -> str:
    t = TOKENS
    return f"""
    QWidget {{
        background-color: {t["bg0"]};
        color: {t["text"]};
        font-size: 10pt;
    }}
    QMainWindow, QDockWidget {{
        background-color: {t["bg0"]};
    }}
    QDockWidget {{
        titlebar-close-icon: none;
        border: 1px solid {t["border"]};
    }}
    QDockWidget::title {{
        background-color: {t["bg1"]};
        padding: 4px 6px;
        border-bottom: 1px solid {t["border"]};
    }}
    QGroupBox {{
        border: 1px solid {t["border"]};
        border-radius: 4px;
        margin-top: 12px;
        padding-top: 8px;
        font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 8px;
        padding: 0 4px;
        color: {t["text_muted"]};
    }}
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit, QListWidget {{
        background-color: {t["bg2"]};
        border: 1px solid {t["border"]};
        border-radius: 3px;
        padding: 3px 5px;
        selection-background-color: {t["accent"]};
    }}
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QTextEdit:focus {{
        border-color: {t["accent"]};
    }}
    QListWidget::item:selected {{
        background-color: {t["accent"]};
        color: #ffffff;
    }}
    QPushButton {{
        background-color: {t["bg2"]};
        border: 1px solid {t["border"]};
        border-radius: 4px;
        padding: 6px 12px;
    }}
    QPushButton:hover {{
        border-color: {t["accent"]};
    }}
    QPushButton:pressed {{
        background-color: {t["bg1"]};
    }}
    QPushButton:disabled {{
        color: {t["text_muted"]};
    }}
    QToolBar {{
        background-color: {t["bg1"]};
        border: none;
        spacing: 3px;
        padding: 3px;
    }}
    QToolButton {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: 4px;
        padding: 4px;
    }}
    QToolButton:hover {{
        background-color: {t["bg2"]};
        border-color: {t["border"]};
    }}
    QToolButton:checked {{
        background-color: {t["accent"]};
        color: #ffffff;
    }}
    QMenuBar {{
        background-color: {t["bg1"]};
        border-bottom: 1px solid {t["border"]};
    }}
    QMenuBar::item:selected {{
        background-color: {t["bg2"]};
    }}
    QMenu {{
        background-color: {t["bg1"]};
        border: 1px solid {t["border"]};
    }}
    QMenu::item:selected {{
        background-color: {t["accent"]};
        color: #ffffff;
    }}
    QStatusBar {{
        background-color: {t["bg1"]};
        border-top: 1px solid {t["border"]};
    }}
    QProgressBar {{
        border: 1px solid {t["border"]};
        border-radius: 3px;
        text-align: center;
        background-color: {t["bg2"]};
    }}
    QProgressBar::chunk {{
        background-color: {t["accent"]};
    }}
    QScrollArea {{
        border: none;
    }}
    QScrollBar:vertical {{
        background: {t["bg1"]};
        width: 10px;
    }}
    QScrollBar::handle:vertical {{
        background: {t["border"]};
        border-radius: 4px;
        min-height: 20px;
    }}
    QSplitter::handle {{
        background-color: {t["border"]};
    }}
    """
