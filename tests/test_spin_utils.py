"""
select_all_on_focus: clicking into a spin box should select its whole
value, ready to type over.

Regression: the filter was originally installed on spin_box.lineEdit(),
but QAbstractSpinBox does not use a Qt focus-proxy relationship to its
internal line edit — QEvent.FocusIn is delivered to the spin box widget
itself (spin_box.focusProxy() is None) — so that line edit filter never
saw FocusIn and selectAll() never ran.
"""

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDoubleSpinBox

from pps.ui.widgets.spin_utils import select_all_on_focus


def test_clicking_into_spin_box_selects_its_full_value(qtbot):
    spin = QDoubleSpinBox()
    spin.setRange(-999, 999)
    spin.setValue(123.0)
    select_all_on_focus(spin)
    qtbot.addWidget(spin)
    spin.show()
    qtbot.waitExposed(spin)

    assert spin.lineEdit().selectedText() == ""

    QTest.mouseClick(spin, Qt.MouseButton.LeftButton)
    qtbot.wait(50)

    assert spin.lineEdit().selectedText() == spin.lineEdit().text()
