"""
Must be imported before anything imports Qt/qtpy/pyvistaqt.

Forces qtpy (used internally by pyvistaqt) to pick PySide6. Without this,
qtpy's auto-detection could pick a different Qt binding if one happened to
also be importable in the environment.
"""

import os

os.environ.setdefault("QT_API", "pyside6")
