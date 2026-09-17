"""
Settings dialog: app-wide display preferences (theme, thickness
classification colors, default point size). Backed by AppSettings
(QSettings) — separate from any one Document/.ppsproj, and separate from
the per-session "Point size" live slider in Properties dock (Settings holds
the persisted *default* used the next time a layer is (re)colored).
"""

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from pps.app.settings import AppSettings, THEME_DARK, THEME_LIGHT
from pps.ui.widgets.spin_utils import select_all_on_focus

_SWATCH_SIZE = 28


class _ColorSwatchButton(QPushButton):
    """A normal-styled push button carrying a colored square icon that
    represents its assigned color; click opens a QColorDialog to change it.

    Deliberately shows the color as an icon rather than via the button's own
    `background-color`: the latter fights the app theme's QSS (hover/pressed
    states repaint the real background), so the color never read reliably.
    """

    _ICON_MARGIN = 6

    def __init__(self, hex_color: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(_SWATCH_SIZE, _SWATCH_SIZE)
        self.setIconSize(QSize(_SWATCH_SIZE - self._ICON_MARGIN, _SWATCH_SIZE - self._ICON_MARGIN))
        self._hex_color = hex_color
        self._apply_icon()
        self.clicked.connect(self._pick_color)

    def _apply_icon(self) -> None:
        size = self.iconSize()
        pixmap = QPixmap(size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setPen(QColor("#333a47"))
        painter.setBrush(QColor(self._hex_color))
        painter.drawRect(0, 0, size.width() - 1, size.height() - 1)
        painter.end()
        self.setIcon(QIcon(pixmap))

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._hex_color), self, "Choose color")
        if color.isValid():
            self._hex_color = color.name()
            self._apply_icon()

    @property
    def hex_color(self) -> str:
        return self._hex_color


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.settings = settings

        layout = QVBoxLayout(self)

        appearance_group = QGroupBox("Appearance")
        appearance_form = QFormLayout(appearance_group)

        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Dark", THEME_DARK)
        self.theme_combo.addItem("Light", THEME_LIGHT)
        index = self.theme_combo.findData(settings.theme)
        self.theme_combo.setCurrentIndex(max(index, 0))
        appearance_form.addRow("Theme:", self.theme_combo)

        self.point_size_spin = QSpinBox()
        self.point_size_spin.setRange(1, 10)
        self.point_size_spin.setValue(settings.point_size)
        select_all_on_focus(self.point_size_spin)
        appearance_form.addRow("Point size:", self.point_size_spin)

        layout.addWidget(appearance_group)

        colors_group = QGroupBox("Thickness Classification Colors")
        colors_form = QFormLayout(colors_group)
        colors_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.swatch_below = _ColorSwatchButton(settings.color_below)
        self.swatch_within = _ColorSwatchButton(settings.color_within)
        self.swatch_above = _ColorSwatchButton(settings.color_above)

        colors_form.addRow("< Target Min:", self.swatch_below)
        colors_form.addRow("Target Min – Target Max:", self.swatch_within)
        colors_form.addRow("> Target Max:", self.swatch_above)

        layout.addWidget(colors_group)

        view3d_group = QGroupBox("3D View")
        view3d_form = QFormLayout(view3d_group)
        view3d_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        # Independent of Theme: this is what gets baked into the PDF
        # report's viewport screenshot, so it needs its own explicit control.
        self.swatch_background = _ColorSwatchButton(settings.background_color)
        view3d_form.addRow("Background:", self.swatch_background)

        layout.addWidget(view3d_group)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        self.settings.apply_updates(
            theme=self.theme_combo.currentData(),
            point_size=self.point_size_spin.value(),
            color_below=self.swatch_below.hex_color,
            color_within=self.swatch_within.hex_color,
            color_above=self.swatch_above.hex_color,
            background_color=self.swatch_background.hex_color,
        )
        self.accept()
