# report/styles/style_factory.py

from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER

class StyleFactory:

    @staticmethod
    def build():
        styles = getSampleStyleSheet()

        styles.add(ParagraphStyle(
            name="Title_Custom",
            fontSize=22,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#1a365d")
        ))

        styles.add(ParagraphStyle(
            name="Heading_Custom",
            fontSize=14,
            textColor=colors.HexColor("#1a365d")
        ))

        return styles