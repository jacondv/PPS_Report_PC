#!/usr/bin/env python3
"""
Tunnel Concrete Thickness Analyzer — entry point.

Thin on purpose: real app wiring lives in pps.app / pps.ui so it can be
imported and tested without going through this script. Kept at the repo
root (rather than only `python -m pps`) because PyInstaller's build.spec
expects a root-level script.
"""

import logging
import os
import sys

if not getattr(sys, "frozen", False):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from pps.app.application import configure_logging, create_app  # noqa: E402
from pps.app.settings import AppSettings  # noqa: E402
from pps.ui.theme import apply_theme  # noqa: E402
from pps.ui.main_window import MainWindow  # noqa: E402

logger = logging.getLogger(__name__)


def _install_excepthook() -> None:
    """Log uncaught exceptions to the file log instead of letting them only
    flash past in a console window the user may not even have open."""
    default_hook = sys.excepthook

    def _hook(exc_type, exc_value, exc_tb):
        logger.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))
        default_hook(exc_type, exc_value, exc_tb)

    sys.excepthook = _hook


def main() -> None:
    log_path = configure_logging()
    _install_excepthook()
    logger.info("Starting Tunnel Concrete Thickness Analyzer — log file: %s", log_path)

    app = create_app(sys.argv)
    logger.info("QApplication created")
    apply_theme(app, AppSettings().theme)
    logger.info("Theme applied; constructing MainWindow…")

    window = MainWindow()
    logger.info("MainWindow constructed; showing…")
    window.showMaximized()
    logger.info("MainWindow shown; entering event loop")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
