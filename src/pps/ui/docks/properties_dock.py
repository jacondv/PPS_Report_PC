"""
Properties dock: current file/project info, target thickness range, point
size. All responsive per plan §6.2 — QFormLayout with WrapLongRows/
ExpandingFieldsGrow, ElidedLabel for the (potentially long) filename.
"""

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QDockWidget,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pps.ui.widgets.elided_label import ElidedLabel
from pps.ui.widgets.spin_utils import select_all_on_focus


class PropertiesDock(QDockWidget):
    point_size_changed = Signal(int)

    def __init__(self, document, parent=None):
        super().__init__("Properties", parent)
        self.setObjectName("dock_properties")
        self.document = document

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content.setMinimumWidth(200)
        layout = QVBoxLayout(content)

        file_group = QGroupBox("File Information")
        file_form = QFormLayout(file_group)
        file_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        file_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        self.lbl_filename = ElidedLabel("No file loaded")
        self.lbl_project = QLabel("-")
        self.lbl_job = QLabel("-")
        self.lbl_time = QLabel("-")
        file_form.addRow("File:", self.lbl_filename)
        file_form.addRow("Project:", self.lbl_project)
        file_form.addRow("Job:", self.lbl_job)
        file_form.addRow("Time:", self.lbl_time)
        layout.addWidget(file_group)

        settings_group = QGroupBox("Analysis Settings")
        settings_form = QFormLayout(settings_group)

        self.spin_target_min = QDoubleSpinBox()
        self.spin_target_min.setRange(0, 9999)
        self.spin_target_min.setSuffix(" mm")
        select_all_on_focus(self.spin_target_min)
        self.spin_target_max = QDoubleSpinBox()
        self.spin_target_max.setRange(0, 9999)
        self.spin_target_max.setSuffix(" mm")
        select_all_on_focus(self.spin_target_max)
        settings_form.addRow("Min target thickness:", self.spin_target_min)
        settings_form.addRow("Max target thickness:", self.spin_target_max)

        # Recomputing/recoloring every layer on every keystroke is expensive
        # and jittery, so the actual document update (and the heavy re-sync
        # it triggers) is debounced 500ms after the user stops changing the
        # value. The min/max cross-bound (max must stay > min) is still
        # enforced immediately at the widget level, not debounced.
        self._targets_timer = QTimer(self)
        self._targets_timer.setSingleShot(True)
        self._targets_timer.setInterval(500)
        self._targets_timer.timeout.connect(self._apply_targets)
        self.spin_target_min.valueChanged.connect(self._on_min_spin_changed)
        self.spin_target_max.valueChanged.connect(self._on_max_spin_changed)
        layout.addWidget(settings_group)

        viz_group = QGroupBox("Visualization")
        viz_form = QFormLayout(viz_group)
        self.spin_point_size = QSpinBox()
        self.spin_point_size.setRange(1, 10)
        self.spin_point_size.setValue(2)
        select_all_on_focus(self.spin_point_size)
        self.spin_point_size.valueChanged.connect(self._on_point_size_spin_changed)
        viz_form.addRow("Point size:", self.spin_point_size)
        layout.addWidget(viz_group)

        layout.addStretch()
        scroll.setWidget(content)
        self.setWidget(scroll)

        document.reset.connect(self._on_document_reset)
        document.targets_changed.connect(self._on_document_targets_changed)

    def _on_document_reset(self) -> None:
        info = self.document.project_info
        if info is None:
            self.lbl_filename.setText("No file loaded")
            self.lbl_project.setText("-")
            self.lbl_job.setText("-")
            self.lbl_time.setText("-")
        else:
            self.lbl_filename.setText(info.original_filename)
            self.lbl_project.setText(info.project_name)
            self.lbl_job.setText(info.job_number)
            self.lbl_time.setText(info.formatted_time)

        self._set_targets_silently(self.document.target_min, self.document.target_max)

    def _on_document_targets_changed(self, target_min: float, target_max: float) -> None:
        self._set_targets_silently(target_min, target_max)

    def _set_targets_silently(self, target_min: float, target_max: float) -> None:
        self.spin_target_min.blockSignals(True)
        self.spin_target_max.blockSignals(True)
        self.spin_target_min.setValue(target_min)
        self.spin_target_max.setValue(target_max)
        self.spin_target_min.blockSignals(False)
        self.spin_target_max.blockSignals(False)

    def _on_min_spin_changed(self, value: float) -> None:
        """Min target must stay <= max target. If min is raised past the
        current max, max is pulled up to match it (rather than blocking the
        edit or popping an error dialog).

        This correction only reacts to the MIN spin's own changes — it must
        NOT also run off the MAX spin's valueChanged, otherwise editing max
        while it's equal to min fights the user: e.g. typing "70" over "60"
        passes through an intermediate value of "7" (below min=60), which
        would immediately get snapped back to 60 before the second digit is
        even typed, making it impossible to raise max at all.
        """
        if value > self.spin_target_max.value():
            self.spin_target_max.blockSignals(True)
            self.spin_target_max.setValue(value)
            self.spin_target_max.blockSignals(False)
        self._targets_timer.start()

    def _on_max_spin_changed(self, _value: float) -> None:
        self._targets_timer.start()

    def _apply_targets(self) -> None:
        min_value = self.spin_target_min.value()
        max_value = self.spin_target_max.value()
        if min_value > max_value:
            # Only reachable by directly typing a smaller max while min is
            # left alone (mid-typing dips are allowed, see _on_min_spin_changed) —
            # settle on the same rule once the debounce actually applies it.
            max_value = min_value
            self.spin_target_max.blockSignals(True)
            self.spin_target_max.setValue(max_value)
            self.spin_target_max.blockSignals(False)
        self.document.set_targets(min_value, max_value)

    def _on_point_size_spin_changed(self, value: int) -> None:
        self.point_size_changed.emit(value)

    def set_point_size_silently(self, value: int) -> None:
        """Reflect a point size change made elsewhere (Settings dialog)
        without re-emitting point_size_changed and re-triggering the sync
        that's already happening as a result of that change."""
        self.spin_point_size.blockSignals(True)
        self.spin_point_size.setValue(value)
        self.spin_point_size.blockSignals(False)
