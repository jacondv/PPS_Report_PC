"""
Preview a generated PDF report before saving it to its final location.
Uses Qt's PDF module (pdfium-based) rather than QtWebEngine, since it
doesn't need a GPU/GL context.
"""

from PySide6.QtWidgets import QDialog, QVBoxLayout, QDialogButtonBox
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView


class PdfPreviewDialog(QDialog):
    def __init__(self, pdf_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Report Preview")
        self.resize(900, 1000)

        layout = QVBoxLayout(self)

        self._document = QPdfDocument(self)
        self._document.load(pdf_path)

        self._view = QPdfView(self)
        self._view.setDocument(self._document)
        self._view.setPageMode(QPdfView.PageMode.MultiPage)
        self._view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        layout.addWidget(self._view)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, self)
        buttons.button(QDialogButtonBox.Save).setText("Save Report…")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
