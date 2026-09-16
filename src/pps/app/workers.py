"""
Background QThread workers. AreaMeasureWorker keeps the BPA surface-area
calculation (a few seconds on a real cloud) off the UI thread; MainWindow
(Phase 6) owns instances of it so they outlive whichever tool requested
the calculation.
"""

from PySide6.QtCore import QThread, Signal

from pps.core.analysis import compute_area_m2, run_analysis


class CalculationWorker(QThread):
    """Runs run_analysis() (area/volume + thickness distribution) off the
    UI thread — ports CalculationWorker from the old gui/main_window.py."""

    finished_ok = Signal(object, object)  # CalculationResult, ThicknessDistribution
    failed = Signal(str)
    progress = Signal(int)

    def __init__(self, points, distances, target_min: float, target_max: float, parent=None):
        super().__init__(parent)
        self.points = points
        self.distances = distances
        self.target_min = target_min
        self.target_max = target_max

    def run(self) -> None:
        try:
            self.progress.emit(10)
            calc, dist = run_analysis(self.points, self.distances, self.target_min, self.target_max)
            self.progress.emit(100)
            self.finished_ok.emit(calc, dist)
        except Exception as exc:
            self.failed.emit(str(exc))


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
