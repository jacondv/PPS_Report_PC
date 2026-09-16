import numpy as np

from pps.app import workers as workers_module
from pps.app.workers import CalculationWorker


def test_calculation_worker_emits_result(qtbot, monkeypatch):
    sentinel_calc, sentinel_dist = object(), object()
    monkeypatch.setattr(
        workers_module, "run_analysis", lambda p, d, tmin, tmax: (sentinel_calc, sentinel_dist)
    )

    worker = CalculationWorker(np.zeros((3, 3)), np.zeros(3), 40.0, 60.0)
    with qtbot.waitSignal(worker.finished_ok, timeout=2000) as blocker:
        worker.start()

    assert blocker.args == [sentinel_calc, sentinel_dist]


def test_calculation_worker_emits_failure(qtbot, monkeypatch):
    def boom(p, d, tmin, tmax):
        raise ValueError("bad data")

    monkeypatch.setattr(workers_module, "run_analysis", boom)

    worker = CalculationWorker(np.zeros((3, 3)), np.zeros(3), 40.0, 60.0)
    with qtbot.waitSignal(worker.failed, timeout=2000) as blocker:
        worker.start()

    assert "bad data" in blocker.args[0]
