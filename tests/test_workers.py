import numpy as np

from pps.app import workers as workers_module
from pps.app.workers import AreaMeasureWorker


def test_area_measure_worker_emits_result(qtbot, monkeypatch):
    monkeypatch.setattr(workers_module, "compute_area_m2", lambda points: 99.0)

    worker = AreaMeasureWorker("m1", np.zeros((3, 3)))
    with qtbot.waitSignal(worker.finished_ok, timeout=2000) as blocker:
        worker.start()

    assert blocker.args == ["m1", 99.0]


def test_area_measure_worker_emits_failure_on_exception(qtbot, monkeypatch):
    def boom(points):
        raise RuntimeError("bpa exploded")

    monkeypatch.setattr(workers_module, "compute_area_m2", boom)

    worker = AreaMeasureWorker("m2", np.zeros((3, 3)))
    with qtbot.waitSignal(worker.failed, timeout=2000) as blocker:
        worker.start()

    assert blocker.args[0] == "m2"
    assert "bpa exploded" in blocker.args[1]
