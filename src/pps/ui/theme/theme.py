"""
Theme: tokens -> QSS + QPalette, for both a dark and a light variant. Accent
color is kept separate from the red/green/blue thickness-classification
colors used in the 3D view, so the two color systems never get visually
confused.
"""

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

DARK_TOKENS = {
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

LIGHT_TOKENS = {
    "bg0": "#f4f5f7",
    "bg1": "#e9ebef",
    "bg2": "#ffffff",
    "border": "#c7ccd4",
    "text": "#1c2027",
    "text_muted": "#6b7280",
    "accent": "#1f78e0",
    "accent_hover": "#3f8fe8",
    "danger": "#d23c3c",
    "success": "#1f9d63",
}

# Kept for callers that still import the old module-level name directly.
TOKENS = DARK_TOKENS


def get_tokens(mode: str) -> dict:
    return LIGHT_TOKENS if mode == "light" else DARK_TOKENS


def apply_theme(app: QApplication, mode: str = "dark") -> None:
    tokens = get_tokens(mode)
    app.setStyle("Fusion")
    app.setPalette(_build_palette(tokens))
    app.setStyleSheet(_build_qss(tokens))


def _build_palette(t: dict) -> QPalette:
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


def _build_qss(t: dict) -> str:
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
    QToolButton:enabled:hover {{
        background-color: {t["bg2"]};
        border-color: {t["border"]};
    }}
    QToolButton:enabled:checked {{
        background-color: {t["accent"]};
        border-color: {t["accent"]};
        color: #ffffff;
        font-weight: 600;
    }}
    QToolButton:disabled {{
        color: {t["text_muted"]};
        background: transparent;
        border-color: transparent;
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
