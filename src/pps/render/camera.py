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


def get_camera_state(plotter) -> dict:
    """Capture enough of the vtkCamera to restore the same view later."""
    cam = plotter.camera
    return {
        "position": tuple(cam.position),
        "focal_point": tuple(cam.focal_point),
        "up": tuple(cam.up),
        "parallel_scale": cam.parallel_scale,
        "view_angle": cam.view_angle,
    }


def set_camera_state(plotter, state: dict) -> None:
    cam = plotter.camera
    cam.position = tuple(state["position"])
    cam.focal_point = tuple(state["focal_point"])
    cam.up = tuple(state["up"])
    cam.parallel_scale = state["parallel_scale"]
    cam.view_angle = state["view_angle"]
    plotter.render()
