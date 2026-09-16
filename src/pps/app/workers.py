"""
Background QThread workers. AreaMeasureWorker keeps the BPA surface-area
calculation (a few seconds on a real cloud) off the UI thread; MainWindow
(Phase 6) owns instances of it so they outlive whichever tool requested
the calculation.
"""

from PySide6.QtCore import QThread, Signal

from pps.core.analysis import compute_area_m2


class AreaMeasureWorker(QThread):
    finished_ok = Signal(str, float)  # measurement_id, area_m2
    failed = Signal(str, str)  # measurement_id, error message

    def __init__(self, measurement_id: str, points, parent=None):
        super().__init__(parent)
        self._measurement_id = measurement_id
        self._points = points

    def run(self) -> None:
        try:
            area_m2 = compute_area_m2(self._points)
        except Exception as exc:
            self.failed.emit(self._measurement_id, str(exc))
            return
        self.finished_ok.emit(self._measurement_id, float(area_m2))
