#!/usr/bin/env python3
"""
Tunnel Concrete Thickness Analyzer
===================================

A desktop application for analyzing shotcrete (sprayed concrete) thickness 
in tunnel construction using point cloud data.

Features:
- Load and visualize PLY point cloud files with custom distance fields
- Interactive 3D visualization with selection tools
- Calculate surface area and volume based on thickness data
- Generate PDF reports with statistics and histograms

Usage:
    python main.py

Requirements:
    pip install -r requirements.txt

Author: Tunnel Analyzer Team
Version: 1.0
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

REQUIRED = [
    "PyQt5",
    "pyvista",
    "pyvistaqt",
    "numpy",
    "plyfile",
    "reportlab",
    "matplotlib",
    "scipy"
]

def check_dependencies():
    missing = []

    for lib in REQUIRED:
        try:
            __import__(lib)
        except ImportError:
            missing.append(lib)

    if missing:
        print("Missing dependencies:", missing)
        print("Please install with: pip install -r requirements.txt")
        sys.exit(1)

    print("All dependencies met.")


def main():
    """Main entry point."""
    # Check dependencies
    check_dependencies()
    
    # Import after checking dependencies
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QFont
    
    # Enable High DPI scaling
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("Tunnel Concrete Thickness Analyzer")
    app.setOrganizationName("TunnelAnalyzer")
    
    # Set default font
    font = QFont("Arial", 10)
    app.setFont(font)
    
    # Set style
    app.setStyle("Fusion")
    
    # Apply stylesheet
    stylesheet = """
    QMainWindow {
        background-color: #f5f5f5;
    }
    QGroupBox {
        font-weight: bold;
        border: 1px solid #ccc;
        border-radius: 5px;
        margin-top: 10px;
        padding-top: 10px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px;
        color: #333;
    }
    QPushButton {
        background-color: #3182ce;
        color: white;
        border: none;
        padding: 8px 15px;
        border-radius: 4px;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #2c5282;
    }
    QPushButton:pressed {
        background-color: #2b4b7a;
    }
    QPushButton:disabled {
        background-color: #a0aec0;
    }
    QPushButton:checked {
        background-color: #2f855a;
    }
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
        padding: 5px;
        border: 1px solid #ccc;
        border-radius: 3px;
        background-color: white;
    }
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
        border-color: #3182ce;
    }
    QListWidget {
        border: 1px solid #ccc;
        border-radius: 3px;
        background-color: white;
    }
    QProgressBar {
        border: 1px solid #ccc;
        border-radius: 3px;
        text-align: center;
    }
    QProgressBar::chunk {
        background-color: #3182ce;
    }
    QStatusBar {
        background-color: #2d3748;
        color: white;
    }
    QToolBar {
        background-color: #e2e8f0;
        border-bottom: 1px solid #ccc;
        spacing: 5px;
        padding: 5px;
    }
    QMenuBar {
        background-color: #f7fafc;
        border-bottom: 1px solid #e2e8f0;
    }
    QMenuBar::item:selected {
        background-color: #e2e8f0;
    }
    QMenu {
        background-color: white;
        border: 1px solid #ccc;
    }
    QMenu::item:selected {
        background-color: #ebf8ff;
    }
    """
    app.setStyleSheet(stylesheet)
    
    # Create and show main window
    from gui.main_window import MainWindow
    window = MainWindow()
    window.showMaximized()
    
    # Run application
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
