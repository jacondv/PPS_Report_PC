"""Opens the bundled HTML user guide (docs/help — screenshots and text
baked into one self-contained file) in the system's default browser."""

import os

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox

_GUIDE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "help", "user_guide.html")


def open_user_guide(parent=None) -> None:
    path = os.path.normpath(_GUIDE_PATH)
    if not os.path.isfile(path):
        QMessageBox.warning(parent, "User Guide", f"Guide file not found:\n{path}")
        return
    QDesktopServices.openUrl(QUrl.fromLocalFile(path))
