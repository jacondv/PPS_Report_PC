"""Numeric-input UX helper: select the whole value when a spin box gains
focus (click or Tab), so typing immediately overwrites it instead of
inserting at the cursor position — the behavior users expect from fields
like "filter from/to" or "target min/max"."""

from PySide6.QtCore import QEvent, QObject, QTimer


class _SelectAllOnFocusFilter(QObject):
    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Type.FocusIn:
            QTimer.singleShot(0, obj.selectAll)
        return False


def select_all_on_focus(spin_box) -> None:
    """Install on any QAbstractSpinBox (QSpinBox/QDoubleSpinBox). Focus is
    proxied to the box's internal QLineEdit, so the filter is installed
    there rather than on the spin box widget itself."""
    line_edit = spin_box.lineEdit()
    filter_ = _SelectAllOnFocusFilter(line_edit)
    line_edit.installEventFilter(filter_)
    spin_box._select_all_filter = filter_  # keep a strong reference alive
