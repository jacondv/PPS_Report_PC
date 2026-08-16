#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PySide6 USB Data Copier
Linux only

Features
--------
- Detect USB plug/unplug automatically
- Show GUI when USB inserted
- Browse nested folders
- Select folders/files to copy
- Copy to selected USB drive
- Progress bar
- Background service style

Install
-------
pip install PySide6

Run
---
python3 usb_data_copier.py

Optional:
python3 usb_data_copier.py /path/to/data
"""

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path

from PySide6.QtCore import (
    Qt,
    QTimer,
    QThread,
    Signal,
)
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFileSystemModel,
    QTreeView,
    QComboBox,
    QTextEdit,
    QMessageBox,
    QProgressBar,
    QHeaderView,
    QAbstractItemView,
)


# ============================================================
# CONFIG
# ============================================================

SOURCE_DATA_PATH = "/home/user/data"

SCAN_INTERVAL_MS = 2000

# ============================================================


def fmt_size(n):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def calc_size(path: Path):
    if path.is_file():
        return path.stat().st_size

    total = 0

    try:
        for f in path.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
    except:
        pass

    return total


def detect_usb_drives():

    drives = []

    try:
        result = subprocess.run(
            ["lsblk", "-J", "-o", "NAME,MOUNTPOINT,LABEL,SIZE,TRAN,RM"],
            capture_output=True,
            text=True,
            timeout=5
        )

        data = json.loads(result.stdout)

        def walk(devices):

            for dev in devices:

                tran = dev.get("tran") or ""
                rm = str(dev.get("rm") or "0")
                mp = dev.get("mountpoint") or ""

                if mp and (tran == "usb" or rm == "1"):

                    label = dev.get("label") or dev.get("name")

                    try:
                        st = shutil.disk_usage(mp)
                        free = fmt_size(st.free)
                        total = fmt_size(st.total)
                    except:
                        free = "?"
                        total = "?"

                    drives.append({
                        "label": label,
                        "mount": mp,
                        "free": free,
                        "total": total,
                    })

                if dev.get("children"):
                    walk(dev["children"])

        walk(data.get("blockdevices", []))

    except Exception:
        pass

    return drives


# ============================================================
# COPY THREAD
# ============================================================

class CopyThread(QThread):

    progress = Signal(int)
    log = Signal(str)
    finished_ok = Signal()
    error = Signal(str)

    def __init__(self, items, dst_root):
        super().__init__()

        self.items = items
        self.dst_root = Path(dst_root)

        self.total_bytes = 0
        self.copied_bytes = 0

        self.cancelled = False

    def run(self):

        try:

            self.total_bytes = sum(calc_size(p) for p in self.items)

            for item in self.items:

                if self.cancelled:
                    return

                dst = self.dst_root / item.name

                self.log.emit(f"Copying: {item.name}")

                self.copy_item(item, dst)

            self.progress.emit(100)
            self.finished_ok.emit()

        except Exception as ex:
            self.error.emit(str(ex))

    def copy_item(self, src: Path, dst: Path):

        if self.cancelled:
            return

        if src.is_file():

            shutil.copy2(str(src), str(dst))

            self.copied_bytes += src.stat().st_size

            self.update_progress()

        elif src.is_dir():

            dst.mkdir(parents=True, exist_ok=True)

            for child in src.iterdir():

                if self.cancelled:
                    return

                self.copy_item(child, dst / child.name)

    def update_progress(self):

        if self.total_bytes <= 0:
            return

        pct = int(self.copied_bytes * 100 / self.total_bytes)

        self.progress.emit(pct)

    def cancel(self):
        self.cancelled = True


# ============================================================
# MAIN WINDOW
# ============================================================

class MainWindow(QWidget):

    def __init__(self, source_path):

        super().__init__()

        self.source_root = Path(source_path)

        self.usb_drives = []

        self.copy_thread = None

        self.init_ui()

        self.refresh_usb()

        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_usb)
        self.timer.start(SCAN_INTERVAL_MS)

    # ========================================================

    def init_ui(self):

        self.setWindowTitle("USB Data Copier")

        self.resize(1400, 900)

        QApplication.setStyle("Fusion")

        self.setStyleSheet("""
            QWidget {
                font-size: 16px;
            }

            QPushButton {
                min-height: 42px;
                padding: 8px 18px;
            }

            QComboBox {
                min-height: 40px;
            }

            QTreeView {
                alternate-background-color: #f5f5f5;
            }
        """)

        root = QVBoxLayout(self)

        # ====================================================
        # TOP
        # ====================================================

        top = QHBoxLayout()

        lbl = QLabel("USB DRIVE")

        self.combo_usb = QComboBox()

        self.btn_refresh = QPushButton("Refresh")

        self.btn_refresh.clicked.connect(self.refresh_usb)

        top.addWidget(lbl)
        top.addWidget(self.combo_usb, 1)
        top.addWidget(self.btn_refresh)

        root.addLayout(top)

        # ====================================================
        # TREE
        # ====================================================

        self.model = QFileSystemModel()

        self.model.setRootPath(str(self.source_root))

        self.tree = QTreeView()

        self.tree.setModel(self.model)

        self.tree.setRootIndex(
            self.model.index(str(self.source_root))
        )

        self.tree.setSelectionMode(
            QAbstractItemView.ExtendedSelection
        )

        self.tree.setAlternatingRowColors(True)

        self.tree.setAnimated(True)

        self.tree.setSortingEnabled(True)

        self.tree.header().setSectionResizeMode(
            0,
            QHeaderView.Stretch
        )

        root.addWidget(self.tree, 1)

        # ====================================================
        # BUTTONS
        # ====================================================

        btns = QHBoxLayout()

        self.btn_copy = QPushButton("COPY TO USB")

        self.btn_cancel = QPushButton("CANCEL")

        self.btn_cancel.setEnabled(False)

        self.btn_copy.clicked.connect(self.start_copy)

        self.btn_cancel.clicked.connect(self.cancel_copy)

        btns.addStretch()

        btns.addWidget(self.btn_cancel)

        btns.addWidget(self.btn_copy)

        root.addLayout(btns)

        # ====================================================
        # PROGRESS
        # ====================================================

        self.progress = QProgressBar()

        self.progress.setValue(0)

        root.addWidget(self.progress)

        # ====================================================
        # LOG
        # ====================================================

        self.log = QTextEdit()

        self.log.setReadOnly(True)

        root.addWidget(self.log, 1)

    # ========================================================

    def add_log(self, txt):

        self.log.append(txt)

    # ========================================================

    def refresh_usb(self):

        prev = set(d["mount"] for d in self.usb_drives)

        self.usb_drives = detect_usb_drives()

        now = set(d["mount"] for d in self.usb_drives)

        self.combo_usb.clear()

        for d in self.usb_drives:

            self.combo_usb.addItem(
                f"{d['label']} [{d['mount']}] "
                f"{d['free']} free",
                d
            )

        # Auto show if new USB inserted
        if now - prev:
            self.show()
            self.raise_()
            self.activateWindow()

    # ========================================================

    def get_selected_items(self):

        indexes = self.tree.selectionModel().selectedRows()

        paths = []

        for idx in indexes:

            p = Path(self.model.filePath(idx))

            paths.append(p)

        return paths

    # ========================================================

    def start_copy(self):

        items = self.get_selected_items()

        if not items:

            QMessageBox.warning(
                self,
                "No Selection",
                "Please select folders/files."
            )

            return

        idx = self.combo_usb.currentIndex()

        if idx < 0:

            QMessageBox.warning(
                self,
                "No USB",
                "Please insert USB drive."
            )

            return

        usb = self.combo_usb.itemData(idx)

        dst = usb["mount"]

        names = "\n".join([p.name for p in items])

        ret = QMessageBox.question(
            self,
            "Confirm",
            f"Copy these items to:\n\n{dst}\n\n{names}"
        )

        if ret != QMessageBox.Yes:
            return

        self.progress.setValue(0)

        self.btn_copy.setEnabled(False)

        self.btn_cancel.setEnabled(True)

        self.copy_thread = CopyThread(items, dst)

        self.copy_thread.progress.connect(
            self.progress.setValue
        )

        self.copy_thread.log.connect(
            self.add_log
        )

        self.copy_thread.finished_ok.connect(
            self.copy_finished
        )

        self.copy_thread.error.connect(
            self.copy_error
        )

        self.copy_thread.start()

    # ========================================================

    def cancel_copy(self):

        if self.copy_thread:
            self.copy_thread.cancel()

            self.add_log("Cancelled.")

    # ========================================================

    def copy_finished(self):

        self.btn_copy.setEnabled(True)

        self.btn_cancel.setEnabled(False)

        self.add_log("Done.")

        QMessageBox.information(
            self,
            "Done",
            "Copy completed."
        )

    # ========================================================

    def copy_error(self, msg):

        self.btn_copy.setEnabled(True)

        self.btn_cancel.setEnabled(False)

        QMessageBox.critical(
            self,
            "Error",
            msg
        )

    # ========================================================

    def closeEvent(self, event):

        # Hide instead of close
        self.hide()

        event.ignore()


# ============================================================
# MAIN
# ============================================================
def main():

    global SOURCE_DATA_PATH

    if len(sys.argv) > 1:
        SOURCE_DATA_PATH = sys.argv[1]

    # BEFORE QApplication()
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    os.environ["QT_SCALE_FACTOR"] = "2"

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)

    win = MainWindow(SOURCE_DATA_PATH)

    win.hide()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()