"""
QApplication bootstrap: Hi-DPI policy, logging, dark palette base.

MainWindow is wired in here once it exists (Phase 6); for now this only
sets up the process-wide bits that must happen before any widget is
created.
"""

import logging

from pps.app import qt_env  # noqa: F401  (sets QT_API before Qt import)

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )


def create_app(argv: list) -> QApplication:
    """Return the QApplication, creating it with Hi-DPI handling configured.

    Safe to call when a QApplication already exists (e.g. under pytest-qt),
    in which case the existing instance is returned unchanged — the Hi-DPI
    rounding policy only has an effect if set before the QApplication is
    constructed, so it cannot be retrofitted onto an existing instance.
    """
    existing = QApplication.instance()
    if existing is not None:
        return existing

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(argv)
    app.setApplicationName("Jaconequipment - Tunnel Concrete Analyzer")
    app.setOrganizationName("TunnelAnalyzer")
    return app
