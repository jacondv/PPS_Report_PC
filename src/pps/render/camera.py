"""Camera view presets — same behavior as PointCloudViewer's view_* methods."""


def reset_view(plotter) -> None:
    plotter.reset_camera()
    plotter.view_isometric()


def view_top(plotter) -> None:
    plotter.view_yx(-1)


def view_bottom(plotter) -> None:
    plotter.view_yx(render=False)
    plotter.camera.Roll(180)


def view_front(plotter) -> None:
    plotter.view_yz(-1)


def view_back(plotter) -> None:
    plotter.view_yz()


def view_right(plotter) -> None:
    plotter.view_xz()


def view_left(plotter) -> None:
    plotter.view_xz(-1)


def view_iso(plotter) -> None:
    plotter.view_isometric(render=False)
    plotter.camera.Azimuth(180)
