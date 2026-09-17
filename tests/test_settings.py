"""AppSettings: persisted theme/color/point-size preferences."""

from pps.app.settings import AppSettings, THEME_DARK, THEME_LIGHT


def test_defaults_when_nothing_persisted_yet(qtbot):
    settings = AppSettings()
    # Reset to known defaults in case a previous manual run of the app
    # (or an earlier test) persisted different values to the real registry.
    settings.apply_updates(
        theme=THEME_DARK,
        color_below="#ff0000",
        color_within="#00ff00",
        color_above="#0000ff",
        point_size=2,
    )

    assert settings.theme == THEME_DARK
    assert settings.color_below == "#ff0000"
    assert settings.color_within == "#00ff00"
    assert settings.color_above == "#0000ff"
    assert settings.point_size == 2


def test_setters_persist_and_are_read_back(qtbot):
    settings = AppSettings()
    settings.theme = THEME_LIGHT
    settings.color_below = "#112233"
    settings.point_size = 5

    reloaded = AppSettings()
    assert reloaded.theme == THEME_LIGHT
    assert reloaded.color_below == "#112233"
    assert reloaded.point_size == 5

    # restore defaults so other tests aren't affected by ordering
    settings.apply_updates(theme=THEME_DARK, color_below="#ff0000", point_size=2)


def test_apply_updates_emits_changed_exactly_once(qtbot):
    settings = AppSettings()
    calls = []
    settings.changed.connect(lambda: calls.append(1))

    settings.apply_updates(theme=THEME_LIGHT, point_size=7, color_above="#abcdef")

    assert len(calls) == 1
    assert settings.theme == THEME_LIGHT
    assert settings.point_size == 7
    assert settings.color_above == "#abcdef"

    settings.apply_updates(theme=THEME_DARK, point_size=2, color_above="#0000ff")
