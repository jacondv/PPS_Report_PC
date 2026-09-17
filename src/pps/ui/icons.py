"""
Icon loading: SVGs live under ui/icons/svg/ as flat black-on-transparent
artwork; load_icon() recolors them at load time to match the current theme
text color, so one icon file works for both Light and Dark without needing
two drawings or CSS-style `currentColor` tricks (QIcon doesn't do those).
"""

import os

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons", "svg")


def load_icon(name: str, color: str, size: int = 24) -> QIcon:
    """`name` is the SVG filename without extension, e.g. "navigate"."""
    path = os.path.join(_ICON_DIR, f"{name}.svg")
    renderer = QSvgRenderer(path)

    pixmap = QPixmap(QSize(size, size))
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), color)
    painter.end()

    return QIcon(pixmap)
