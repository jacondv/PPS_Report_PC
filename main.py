#!/usr/bin/env python3
"""
Tunnel Concrete Thickness Analyzer — entry point.

Thin on purpose: real app wiring lives in pps.app / pps.ui so it can be
imported and tested without going through this script. Kept at the repo
root (rather than only `python -m pps`) because PyInstaller's build.spec
expects a root-level script.
"""

import os
import sys

if not getattr(sys, "frozen", False):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from pps.app.application import configure_logging, create_app  # noqa: E402
from pps.ui.theme import apply_theme  # noqa: E402
from pps.ui.main_window import MainWindow  # noqa: E402


def main() -> None:
    configure_logging()
    app = create_app(sys.argv)
    apply_theme(app)

    window = MainWindow()
    window.showMaximized()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
