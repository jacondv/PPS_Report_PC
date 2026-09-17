"""
PropertiesDock target min/max: the document update (and the expensive full
layer re-sync it triggers) is debounced 500ms after the user stops changing
the value. Min target must stay <= max target: if min is raised past the
current max, max snaps up to match it, rather than popping a validation
error dialog.
"""

from pps.scene.document import Document
from pps.ui.docks.properties_dock import PropertiesDock


def test_target_change_is_debounced_not_applied_immediately(qtbot):
    document = Document()
    dock = PropertiesDock(document)
    qtbot.addWidget(dock)
    document.target_min = 40.0
    document.target_max = 60.0

    dock.spin_target_max.setValue(70.0)

    assert document.target_max == 60.0  # not yet applied

    qtbot.wait(700)

    assert document.target_max == 70.0


def test_rapid_changes_within_debounce_window_apply_once_with_final_value(qtbot):
    document = Document()
    dock = PropertiesDock(document)
    qtbot.addWidget(dock)

    calls = []
    document.targets_changed.connect(lambda mn, mx: calls.append((mn, mx)))

    dock.spin_target_max.setValue(65.0)
    qtbot.wait(100)
    dock.spin_target_max.setValue(70.0)
    qtbot.wait(700)

    assert calls == [(dock.spin_target_min.value(), 70.0)]


def test_min_target_raised_past_max_pulls_max_up_to_match(qtbot):
    document = Document()
    dock = PropertiesDock(document)
    qtbot.addWidget(dock)
    dock.spin_target_min.setValue(40.0)
    dock.spin_target_max.setValue(60.0)

    dock.spin_target_min.setValue(90.0)  # min > max

    assert dock.spin_target_max.value() == 90.0
    assert dock.spin_target_min.value() == dock.spin_target_max.value()


def test_min_equal_to_max_is_allowed(qtbot):
    document = Document()
    dock = PropertiesDock(document)
    qtbot.addWidget(dock)
    dock.spin_target_min.setValue(40.0)
    dock.spin_target_max.setValue(60.0)

    dock.spin_target_min.setValue(60.0)  # min == max, should not be rejected

    assert dock.spin_target_min.value() == 60.0
    assert dock.spin_target_max.value() == 60.0


def test_raising_max_while_equal_to_min_is_not_clobbered_mid_edit(qtbot):
    """Regression: min==max, then typing a bigger max passes through an
    intermediate value below min (e.g. "7" on the way to "70") — that dip
    must not get instantly snapped back to min, or the second digit can
    never be typed."""
    document = Document()
    dock = PropertiesDock(document)
    qtbot.addWidget(dock)
    dock.spin_target_min.setValue(60.0)
    dock.spin_target_max.setValue(60.0)

    dock.spin_target_max.setValue(7.0)  # mid-typing dip below min
    assert dock.spin_target_max.value() == 7.0  # not forced back to 60

    dock.spin_target_max.setValue(70.0)  # final typed value
    assert dock.spin_target_max.value() == 70.0
    assert dock.spin_target_min.value() == 60.0


def test_max_left_below_min_after_debounce_settles_to_min(qtbot):
    """If the user stops editing with max still below min (didn't finish
    typing a bigger value), the debounced apply — not live typing —
    resolves it by pulling max up to min."""
    document = Document()
    dock = PropertiesDock(document)
    qtbot.addWidget(dock)
    dock.spin_target_min.setValue(60.0)
    dock.spin_target_max.setValue(60.0)

    dock.spin_target_max.setValue(7.0)
    qtbot.wait(700)

    assert dock.spin_target_max.value() == 60.0
    assert document.target_max == 60.0
