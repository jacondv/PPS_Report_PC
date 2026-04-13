"""
Report generation modules.
"""

from report.core.html_pdf_generator import HTMLPDFGenerator
from report.core.pdf_generator import PDFGenerator as LegacyPDFGenerator

PDFGenerator = HTMLPDFGenerator

__all__ = ['PDFGenerator', 'HTMLPDFGenerator', 'LegacyPDFGenerator']

__all__ = ['PDFGenerator']