"""
Centralized light theme — colors and QSS for the whole application.
"""

BG = "#f7f8fa"
SURFACE = "#ffffff"
BORDER = "#d8dee4"
BORDER_SUBTLE = "#e6e9ed"
TEXT = "#1f2933"
TEXT_MUTED = "#65727e"
ACCENT = "#0ea5e9"
ACCENT_HOVER = "#0284c7"
ACCENT_PRESSED = "#0369a1"
DISABLED = "#c3cbd2"
SUCCESS = "#2f855a"

STYLESHEET = f"""
* {{
    font-family: "Segoe UI", Arial, sans-serif;
}}

QMainWindow, QDialog, QWidget {{
    background-color: {BG};
    color: {TEXT};
}}

QGroupBox {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 12px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: {TEXT};
}}

QPushButton {{
    background-color: {ACCENT};
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 6px;
    font-weight: 600;
    text-align: left;
}}
QPushButton:hover {{ background-color: {ACCENT_HOVER}; }}
QPushButton:pressed {{ background-color: {ACCENT_PRESSED}; }}
QPushButton:disabled {{ background-color: {DISABLED}; color: #f4f5f6; }}
QPushButton:checked {{ background-color: {SUCCESS}; }}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit {{
    padding: 5px 7px;
    border: 1px solid {BORDER};
    border-radius: 5px;
    background-color: {SURFACE};
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QTextEdit:focus {{
    border-color: {ACCENT};
}}
QLineEdit:read-only {{
    background-color: {BG};
    color: {TEXT_MUTED};
}}

QListWidget {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    background-color: {SURFACE};
    outline: none;
}}
QListWidget::item {{
    padding: 4px 2px;
    border-radius: 4px;
}}
QListWidget::item:selected {{
    background-color: #e3f2fd;
    color: {TEXT};
}}
QListWidget::item:hover {{
    background-color: {BORDER_SUBTLE};
}}

QProgressBar {{
    border: 1px solid {BORDER};
    border-radius: 5px;
    text-align: center;
    background-color: {SURFACE};
}}
QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 5px;
}}

QStatusBar {{
    background-color: {SURFACE};
    color: {TEXT_MUTED};
    border-top: 1px solid {BORDER};
}}

QToolBar {{
    background-color: {SURFACE};
    border-bottom: 1px solid {BORDER};
    spacing: 6px;
    padding: 6px;
}}
QToolBar QToolButton {{
    border-radius: 5px;
    padding: 4px;
}}
QToolBar QToolButton:hover {{
    background-color: {BORDER_SUBTLE};
}}

QMenuBar {{
    background-color: {SURFACE};
    border-bottom: 1px solid {BORDER};
}}
QMenuBar::item:selected {{ background-color: {BORDER_SUBTLE}; }}

QMenu {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
}}
QMenu::item {{ padding: 6px 20px; }}
QMenu::item:selected {{ background-color: #e3f2fd; }}

QScrollBar:vertical {{
    background: {BG};
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 5px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {TEXT_MUTED}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

QToolTip {{
    background-color: {TEXT};
    color: white;
    border: none;
    padding: 4px 8px;
    border-radius: 4px;
}}
"""


def apply_theme(app):
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
