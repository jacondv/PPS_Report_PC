"""
Must be imported before anything imports Qt/qtpy/pyvistaqt.

Forces qtpy (used internally by pyvistaqt) to pick PySide6, even though
PyQt5 may also be installed in the same environment (kept around so the
old UI branch keeps working). Without this, qtpy's auto-detection can pick
whichever binding happens to be importable first.
"""

import os

os.environ.setdefault("QT_API", "pyside6")
