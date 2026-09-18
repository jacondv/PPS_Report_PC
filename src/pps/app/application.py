"""
QApplication bootstrap: Hi-DPI policy, logging, dark palette base.

MainWindow is wired in here once it exists (Phase 6); for now this only
sets up the process-wide bits that must happen before any widget is
created.
"""

import logging
import logging.handlers
import os
import sys

from pps.app import qt_env  # noqa: F401  (sets QT_API before Qt import)

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

_LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
_MAX_LOG_BYTES = 2 * 1024 * 1024
_LOG_BACKUP_COUNT = 3


def log_directory() -> str:
    """Per-user, per-OS directory for log files — matches the
    "TunnelAnalyzer" organization scope AppSettings' QSettings already uses,
    computed without depending on a QApplication existing yet (this runs
    before create_app() so the app/organization name aren't set on
    QCoreApplication until afterwards)."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "TunnelAnalyzer", "logs")


def configure_logging(level: int = logging.INFO) -> str:
    """Log to both the console and a rotating file under the user's app
    data directory, so diagnosing a reported issue doesn't depend on the
    app having been launched from a terminal. Returns the log file path.

    Safe to call more than once (e.g. under tests importing main) — clears
    any handlers this previously installed first rather than stacking
    duplicates.
    """
    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        if getattr(handler, "_pps_managed", False):
            root.removeHandler(handler)

    formatter = logging.Formatter(_LOG_FORMAT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console._pps_managed = True
    root.addHandler(console)

    log_dir = log_directory()
    log_path = os.path.join(log_dir, "app.log")
    try:
        os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_path, maxBytes=_MAX_LOG_BYTES, backupCount=_LOG_BACKUP_COUNT, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        file_handler._pps_managed = True
        root.addHandler(file_handler)
    except OSError:
        # Read-only/locked user profile, etc. — console logging still
        # works, so don't prevent the app from starting over this.
        logging.getLogger(__name__).warning("Could not open log file %s", log_path, exc_info=True)

    return log_path


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
