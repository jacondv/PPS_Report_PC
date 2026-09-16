from reportlab.platypus import Paragraph, Table, Spacer, TableStyle
from reportlab.lib import colors

class ProjectSection:

    def build(self, ctx):

        p = ctx["project_info"]
        s = ctx["styles"]

        story = []

        # =========================
        # Title
        # =========================
        story.append(Paragraph(
            "1. PROJECT INFORMATION",
            s["Heading_Custom"]
        ))

        story.append(Spacer(1, 8))

        # =========================
        # Data (clean label/value layout)
        # =========================
        data = [
            ["Project Name", p.project_name],
            ["Job Number", p.job_number],
            ["Scan Time", p.formatted_time],
            ["Source File", p.original_filename],
        ]

        table = Table(
            data,
            colWidths=[140, 320],
            hAlign="LEFT"
        )

        # =========================
        # Style (IMPORTANT PART)
        # =========================
        table.setStyle(TableStyle([

            # padding (VERY IMPORTANT for readability)
            ("TOPPADDING", (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("LEFTPADDING", (0,0), (-1,-1), 10),
            ("RIGHTPADDING", (0,0), (-1,-1), 10),

            # grid soft (không quá đậm)
            ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#e2e8f0")),

            # label column style
            ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#f7fafc")),
            ("TEXTCOLOR", (0,0), (0,-1), colors.HexColor("#4a5568")),
            ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),

            # value column style
            ("TEXTCOLOR", (1,0), (1,-1), colors.HexColor("#1a202c")),
            ("FONTNAME", (1,0), (1,-1), "Helvetica"),

            # alignment
            ("ALIGN", (0,0), (0,-1), "LEFT"),
            ("ALIGN", (1,0), (1,-1), "LEFT"),

            # vertical alignment
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),

        ]))

        story.append(table)

        # =========================
        # spacing after section
        # =========================
        story.append(Spacer(1, 18))

        return story