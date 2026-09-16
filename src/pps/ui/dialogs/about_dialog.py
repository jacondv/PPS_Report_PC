from PySide6.QtWidgets import QMessageBox


def show_about(parent=None) -> None:
    QMessageBox.about(
        parent,
        "About Tunnel Analyzer",
        "Tunnel Concrete Thickness Analyzer\n\n"
        "Analysis of sprayed concrete thickness in tunnel engineering "
        "from Point Cloud (.ply)\n\n"
        "Version 3.0 — PySide6 rewrite",
    )
