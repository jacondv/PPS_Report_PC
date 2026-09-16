"""
Properties dock: current file/project info, target thickness range, point
size. All responsive per plan §6.2 — QFormLayout with WrapLongRows/
ExpandingFieldsGrow, ElidedLabel for the (potentially long) filename.
"""

from PySide6.QtCore import Signal
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
        self.spin_target_max = QDoubleSpinBox()
        self.spin_target_max.setRange(0, 9999)
        self.spin_target_max.setSuffix(" mm")
        settings_form.addRow("Min target thickness:", self.spin_target_min)
        settings_form.addRow("Max target thickness:", self.spin_target_max)
        self.spin_target_min.valueChanged.connect(self._on_targets_changed)
        self.spin_target_max.valueChanged.connect(self._on_targets_changed)
        layout.addWidget(settings_group)

        viz_group = QGroupBox("Visualization")
        viz_form = QFormLayout(viz_group)
        self.spin_point_size = QSpinBox()
        self.spin_point_size.setRange(1, 10)
        self.spin_point_size.setValue(2)
        self.spin_point_size.valueChanged.connect(self.point_size_changed)
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
        for spin, value in ((self.spin_target_min, target_min), (self.spin_target_max, target_max)):
            spin.blockSignals(True)
            spin.setValue(value)
            spin.blockSignals(False)

    def _on_targets_changed(self, _value: float) -> None:
        self.document.set_targets(self.spin_target_min.value(), self.spin_target_max.value())
