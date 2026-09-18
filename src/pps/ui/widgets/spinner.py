"""A small rotating-arc busy spinner (no image assets needed) — shown next
to long-running actions like Calculate so it's obvious the app is working,
not stuck, on a slow point cloud."""

from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

_TICK_MS = 40
_STEP_DEG = 18
_ARC_SPAN_DEG = 300 * 16  # QPainter angles are in 1/16th of a degree


class Spinner(QWidget):
    """Always occupies its slot in the layout (e.g. a QToolBar via
    addWidget()) — hiding/showing the widget itself would toggle the
    visibility of the QWidgetAction QToolBar wraps it in, which doesn't
    reliably resync afterwards. Instead it stays visible and simply draws
    nothing while idle."""

    def __init__(self, parent=None, size: int = 18, color: str = "#2563eb"):
        super().__init__(parent)
        self._angle = 0
        self._active = False
        self._color = QColor(color)
        self._size = size
        self.setFixedSize(size, size)
        self._timer = QTimer(self)
        self._timer.setInterval(_TICK_MS)
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        self._angle = 0
        self._active = True
        self._timer.start()
        self.update()

    def stop(self) -> None:
        self._timer.stop()
        self._active = False
        self.update()

    def set_color(self, color: str) -> None:
        self._color = QColor(color)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt override
        return QSize(self._size, self._size)

    def _tick(self) -> None:
        self._angle = (self._angle + _STEP_DEG) % 360
        self.update()

    def paintEvent(self, _event) -> None:
        if not self._active:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen_width = max(2, self.width() // 9)
        pen = QPen(self._color)
        pen.setWidth(pen_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        margin = pen_width
        rect = QRectF(margin, margin, self.width() - 2 * margin, self.height() - 2 * margin)
        start_angle = -self._angle * 16
        painter.drawArc(rect, start_angle, _ARC_SPAN_DEG)
        painter.end()
