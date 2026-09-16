"""
Report generation modules.
"""

from pps.report.core.html_pdf_generator import HTMLPDFGenerator
from pps.report.core.pdf_generator import PDFGenerator as LegacyPDFGenerator

PDFGenerator = HTMLPDFGenerator

__all__ = ['PDFGenerator', 'HTMLPDFGenerator', 'LegacyPDFGenerator']

__all__ = ['PDFGenerator']