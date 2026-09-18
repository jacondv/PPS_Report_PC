"""Results dock: calculation output, thickness distribution, progress."""

from PySide6.QtWidgets import (
    QDockWidget,
    QFormLayout,
    QGroupBox,
    QLabel,
    QProgressBar,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class ResultsDock(QDockWidget):
    def __init__(self, parent=None):
        super().__init__("Results", parent)
        self.setObjectName("dock_results")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content.setMinimumWidth(200)
        layout = QVBoxLayout(content)

        results_group = QGroupBox("Analysis Results")
        form = QFormLayout(results_group)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        self.lbl_area = QLabel("-")
        self.lbl_target_coverage = QLabel("-")
        self.lbl_volume = QLabel("-")
        self.lbl_mean_thickness = QLabel("-")
        self.lbl_min_thickness = QLabel("-")
        self.lbl_max_thickness = QLabel("-")
        self.lbl_std_thickness = QLabel("-")
        self.lbl_num_points = QLabel("-")
        form.addRow("Surface Area (m²):", self.lbl_area)
        form.addRow("Target Coverage (m²):", self.lbl_target_coverage)
        form.addRow("Volume (m³):", self.lbl_volume)
        form.addRow("Mean Thickness (mm):", self.lbl_mean_thickness)
        form.addRow("Min Thickness (mm):", self.lbl_min_thickness)
        form.addRow("Max Thickness (mm):", self.lbl_max_thickness)
        form.addRow("Std Deviation:", self.lbl_std_thickness)
        form.addRow("Number of Points:", self.lbl_num_points)
        layout.addWidget(results_group)

        dist_group = QGroupBox("Thickness Distribution")
        dist_layout = QVBoxLayout(dist_group)
        self.lbl_below = QLabel("-")
        self.lbl_within = QLabel("-")
        self.lbl_above = QLabel("-")
        dist_layout.addWidget(QLabel("Below Target:"))
        dist_layout.addWidget(self.lbl_below)
        dist_layout.addWidget(QLabel("Within Target:"))
        dist_layout.addWidget(self.lbl_within)
        dist_layout.addWidget(QLabel("Above Target:"))
        dist_layout.addWidget(self.lbl_above)
        layout.addWidget(dist_group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        layout.addStretch()
        scroll.setWidget(content)
        self.setWidget(scroll)

    def set_busy(self, busy: bool) -> None:
        """Indeterminate ("marquee") mode while calculating — the worker
        only ever reports two progress steps, so a determinate 0-100 bar
        just looks stuck for however long the real work takes."""
        if busy:
            self.progress_bar.setRange(0, 0)
            self.progress_bar.setVisible(True)
        else:
            self.progress_bar.setVisible(False)
            self.progress_bar.setRange(0, 100)

    def show_result(self, calc, dist) -> None:
        self.lbl_area.setText(f"{calc.surface_area_m2:.1f}")
        self.lbl_target_coverage.setText(f"{calc.area_reached_target_m2:.1f}")
        self.lbl_volume.setText(f"{calc.volume_m3:.1f}")
        self.lbl_mean_thickness.setText(f"{calc.mean_thickness_mm:.0f}")
        self.lbl_min_thickness.setText(f"{calc.min_thickness_mm:.0f}")
        self.lbl_max_thickness.setText(f"{calc.max_thickness_mm:.0f}")
        self.lbl_std_thickness.setText(f"{calc.std_thickness_mm:.0f}")
        self.lbl_num_points.setText(f"{calc.num_points:,}")

        self.lbl_below.setText(f"{dist.below_target:,} points ({dist.below_target_percent:.1f}%)")
        self.lbl_within.setText(f"{dist.within_target:,} points ({dist.within_target_percent:.1f}%)")
        self.lbl_above.setText(f"{dist.above_target:,} points ({dist.above_target_percent:.1f}%)")

    def clear_result(self) -> None:
        for label in (
            self.lbl_area, self.lbl_target_coverage, self.lbl_volume,
            self.lbl_mean_thickness, self.lbl_min_thickness, self.lbl_max_thickness,
            self.lbl_std_thickness, self.lbl_num_points,
            self.lbl_below, self.lbl_within, self.lbl_above,
        ):
            label.setText("-")
