# report/templates/shotcrete_template.py

from pps.report.sections.project_section import ProjectSection
from pps.report.sections.result_section import ResultSection
from pps.report.sections.segment_notes_section import SegmentNotesSection
from pps.report.sections.distribution_section import DistributionSection
from pps.report.sections.image_section import ImageSection

from reportlab.platypus import PageBreak

class ShotcreteTemplate:

    def build(self, story, ctx):

        story += ProjectSection().build(ctx)
        story += ResultSection().build(ctx)
        story += SegmentNotesSection().build(ctx)
        story += DistributionSection().build(ctx)


        if ctx.get("screenshot_path"):
            story.append(PageBreak())
            story += ImageSection().build(ctx)

        return story