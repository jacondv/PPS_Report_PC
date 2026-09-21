# build.spec — PyInstaller spec for the PySide6 app under src/pps.
#
# Two different resource-lookup conventions are bundled here on purpose,
# matching how the code actually looks things up at runtime:
#   1. pps.utils.path_helper.resource_path() (used by the PDF report code
#      for report/assets, report/templates, report/packages/wkhtmltox) and
#      _find_wkhtmltopdf() both look for a TOP-LEVEL "report/" folder next
#      to the exe (or under _internal/) — NOT nested under "pps/".
#   2. pps.ui.icons.load_icon() and pps.ui.dialogs.user_guide.open_user_guide()
#      resolve their files relative to their own module's __file__, so
#      those must be bundled at the matching in-package path
#      ("pps/ui/icons/svg", "pps/ui/help") so the frozen module's __file__
#      based join still finds them under _internal/.
#
# See src/pps/utils/path_helper.py and src/pps/ui/icons.py for the exact
# lookup logic if either of these ever need to change.

import os

from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

SRC = os.path.join("src", "pps")

datas = [
    (os.path.join(SRC, "report", "assets"), os.path.join("report", "assets")),
    (os.path.join(SRC, "report", "templates"), os.path.join("report", "templates")),
    (os.path.join(SRC, "report", "packages"), os.path.join("report", "packages")),
    (os.path.join(SRC, "ui", "icons", "svg"), os.path.join("pps", "ui", "icons", "svg")),
    (os.path.join(SRC, "ui", "help"), os.path.join("pps", "ui", "help")),
    ("sample", "sample"),
    ("assets", "assets"),
]
datas += collect_data_files("open3d")

hiddenimports = [
    "PySide6.QtSvg",
    "PySide6.QtPrintSupport",
    "vtkmodules",
    "vtkmodules.all",
    "vtkmodules.util.misc",
    "vtkmodules.util.numpy_support",
    "pyvista",
    "pyvistaqt",
    "open3d",
    "pdfkit",
    "jinja2",
    "matplotlib",
    "matplotlib.backends.backend_agg",
    "reportlab",
    "plyfile",
    "scipy",
]
hiddenimports += collect_submodules("open3d")

a = Analysis(
    ["main.py"],
    pathex=[".", "src"],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=["."],
    runtime_hooks=[],
    excludes=["PyQt5"],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="Jacon PPS Report",
    debug=False,
    console=True,
    icon="assets/icon.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="Jacon PPS Report",
)
