# report/templates/shotcrete_template.py

from report.sections.project_section import ProjectSection
from report.sections.result_section import ResultSection
from report.sections.distribution_section import DistributionSection
from report.sections.image_section import ImageSection

from reportlab.platypus import PageBreak

class ShotcreteTemplate:

    def build(self, story, ctx):

        story += ProjectSection().build(ctx)
        story += ResultSection().build(ctx)
        story += DistributionSection().build(ctx)


        if ctx.get("screenshot_path"):
            story.append(PageBreak())
            story += ImageSection().build(ctx)

        return story