"""
A QLabel that elides its text (middle) instead of forcing the layout wide
or overflowing — used for filenames/paths so a long one never breaks the
responsive dock layout. Full text is always available via tooltip.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QLabel, QSizePolicy


class ElidedLabel(QLabel):
    def __init__(self, text: str = "", parent=None, elide_mode=Qt.TextElideMode.ElideMiddle):
        super().__init__(parent)
        self._full_text = text
        self._elide_mode = elide_mode
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._update_elided_text()

    def setText(self, text: str) -> None:  # noqa: N802 (Qt override)
        self._full_text = text
        self.setToolTip(text)
        self._update_elided_text()

    def text(self) -> str:  # noqa: N802 (Qt override)
        return self._full_text

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        self._update_elided_text()

    def _update_elided_text(self) -> None:
        metrics = QFontMetrics(self.font())
        elided = metrics.elidedText(self._full_text, self._elide_mode, self.width())
        super().setText(elided)
