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
    """Install on any QAbstractSpinBox (QSpinBox/QDoubleSpinBox).

    QAbstractSpinBox does NOT use a Qt focus-proxy relationship to its
    internal line edit — QEvent.FocusIn is delivered to the spin box widget
    itself (confirmed by tracing events; `spin_box.focusProxy()` is None) —
    so the filter must be installed there, not on `spin_box.lineEdit()`.
    """
    filter_ = _SelectAllOnFocusFilter(spin_box)
    spin_box.installEventFilter(filter_)
    spin_box._select_all_filter = filter_  # keep a strong reference alive
