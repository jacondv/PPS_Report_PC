from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors


class SegmentNotesSection:

    def build(self, ctx):
        layers = ctx.get("visible_layers", [])
        notes = [l for l in layers if getattr(l, "annotations", [])]
        if not notes:
            return []

        s = ctx["styles"]
        story = []

        story.append(Paragraph("3. SEGMENT NOTES", s["Heading_Custom"]))
        story.append(Spacer(1, 10))

        rows = []
        for layer in notes:
            title = Paragraph(f"<b>➤ {layer.name}</b>", s["BodyText"])
            annotation_text = "<br/><br/>".join(
                ann["text"].replace("\n", "<br/>") for ann in layer.annotations
            )
            text = Paragraph(annotation_text, s["BodyText"])
            rows.append([title, text])

        table = Table(rows, colWidths=[150, 340])
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
            ("BOX", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e0")),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))

        story.append(table)
        story.append(Spacer(1, 18))
        return story
