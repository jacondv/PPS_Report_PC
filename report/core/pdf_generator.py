# report/generator/pdf_generator.py

from reportlab.platypus import SimpleDocTemplate
from reportlab.lib.pagesizes import A4

from report.templates.shotcrete_template import ShotcreteTemplate
from report.styles.style_factory import StyleFactory

class PDFGenerator:

    def __init__(self, output_path):
        self.output_path = output_path
        self.template = ShotcreteTemplate()
        self.styles = StyleFactory.build()

    def generate(self, ctx):

        doc = SimpleDocTemplate(
            self.output_path,
            pagesize=A4,
            rightMargin=20,
            leftMargin=20,
            topMargin=20,
            bottomMargin=20
        )

        story = []
        ctx["styles"] = self.styles

        story = self.template.build(story, ctx)

        doc.build(story)

        return self.output_path