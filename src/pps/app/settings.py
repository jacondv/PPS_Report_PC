"""
Persisted, app-wide display preferences: theme (Light/Dark), the three
thickness-classification colors, and default point size.

These are user preferences, not project data — they live in QSettings (like
window geometry) rather than in Document/.ppsproj, so they carry over
between files/projects and across sessions.
"""

from PySide6.QtCore import QObject, QSettings, Signal

THEME_DARK = "dark"
THEME_LIGHT = "light"

DEFAULT_THEME = THEME_LIGHT
DEFAULT_COLOR_BELOW = "#ff0000"   # thickness < target_min
DEFAULT_COLOR_WITHIN = "#00ff00"  # target_min <= thickness <= target_max
DEFAULT_COLOR_ABOVE = "#0000ff"   # thickness > target_max
DEFAULT_POINT_SIZE = 2
# Independent of the UI theme (Light/Dark): this color is what actually
# ends up in the PDF report's viewport screenshot, so it must stay
# under its own explicit control rather than following the UI chrome.
DEFAULT_BACKGROUND_COLOR = "#1b1f27"
DEFAULT_AUTO_OPEN_PDF = True
DEFAULT_REPORT_TITLE = "SHOTCRETE THICKNESS REPORT"
DEFAULT_REPORT_LOGO_PATH = ""  # empty = use the bundled Jacon logo

_SETTINGS_GROUP = "display"


class AppSettings(QObject):
    """Thin QSettings wrapper; emits `changed` after any value is written so
    listeners (MainWindow) can re-apply theme/colors/point size in one
    place."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings = QSettings("TunnelAnalyzer", "TunnelConcreteThicknessAnalyzer")

    def _get(self, key: str, default, value_type):
        return self._settings.value(f"{_SETTINGS_GROUP}/{key}", default, type=value_type)

    def _set(self, key: str, value) -> None:
        self._settings.setValue(f"{_SETTINGS_GROUP}/{key}", value)
        self.changed.emit()

    @property
    def theme(self) -> str:
        return str(self._get("theme", DEFAULT_THEME, str))

    @theme.setter
    def theme(self, value: str) -> None:
        self._set("theme", value)

    @property
    def color_below(self) -> str:
        return str(self._get("color_below", DEFAULT_COLOR_BELOW, str))

    @color_below.setter
    def color_below(self, value: str) -> None:
        self._set("color_below", value)

    @property
    def color_within(self) -> str:
        return str(self._get("color_within", DEFAULT_COLOR_WITHIN, str))

    @color_within.setter
    def color_within(self, value: str) -> None:
        self._set("color_within", value)

    @property
    def color_above(self) -> str:
        return str(self._get("color_above", DEFAULT_COLOR_ABOVE, str))

    @color_above.setter
    def color_above(self, value: str) -> None:
        self._set("color_above", value)

    @property
    def point_size(self) -> int:
        return int(self._get("point_size", DEFAULT_POINT_SIZE, int))

    @point_size.setter
    def point_size(self, value: int) -> None:
        self._set("point_size", int(value))

    @property
    def background_color(self) -> str:
        return str(self._get("background_color", DEFAULT_BACKGROUND_COLOR, str))

    @background_color.setter
    def background_color(self, value: str) -> None:
        self._set("background_color", value)

    @property
    def auto_open_pdf_after_export(self) -> bool:
        return bool(self._get("auto_open_pdf_after_export", DEFAULT_AUTO_OPEN_PDF, bool))

    @auto_open_pdf_after_export.setter
    def auto_open_pdf_after_export(self, value: bool) -> None:
        self._set("auto_open_pdf_after_export", bool(value))

    @property
    def report_title(self) -> str:
        return str(self._get("report_title", DEFAULT_REPORT_TITLE, str))

    @report_title.setter
    def report_title(self, value: str) -> None:
        self._set("report_title", value)

    @property
    def report_logo_path(self) -> str:
        return str(self._get("report_logo_path", DEFAULT_REPORT_LOGO_PATH, str))

    @report_logo_path.setter
    def report_logo_path(self, value: str) -> None:
        self._set("report_logo_path", value)

    def apply_updates(self, **values) -> None:
        """Write several settings at once, emitting `changed` only once —
        used by SettingsDialog so accepting the dialog doesn't trigger a
        theme/color re-apply per individual field."""
        for key, value in values.items():
            self._settings.setValue(f"{_SETTINGS_GROUP}/{key}", value)
        self.changed.emit()
