# build.spec
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.', 'src'],
    binaries=[],
    datas=[
        ('src/pps_report/gui', 'gui'),
        ('src/pps_report/core', 'core'),
        ('src/pps_report/report', 'report'),
        ('src/pps_report/utils', 'utils'),
        ('sample', 'sample'),
        ('assets', 'assets'),
    ],
    hiddenimports=[
        'shiboken6',
        'PySide6.QtPrintSupport',
        'vtkmodules',
        'vtkmodules.all',
        'vtkmodules.util.misc',
        'vtkmodules.util.numpy_support',
        'pyvista',
        'pyvistaqt',
        'pdfkit',
        'jinja2',
    ],
    hookspath=['.'],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name='Jacon PPS Report Generator',
    debug=False,
    console=True,
    icon='assets/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='Jacon PPS Report Generator',
)
