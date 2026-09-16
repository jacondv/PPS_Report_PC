from PySide6.QtWidgets import QApplication

from pps.app.application import create_app


def test_create_app_reuses_existing_instance(qtbot):
    # pytest-qt's qtbot fixture already created a QApplication; create_app()
    # must not try to construct a second one (PySide6 raises if it does).
    before = QApplication.instance()
    assert before is not None

    app = create_app([])

    assert app is before
