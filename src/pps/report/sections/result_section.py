from reportlab.platypus import Paragraph, Table, Spacer, TableStyle
from reportlab.lib import colors

class ResultSection:

    def build(self, ctx):

        r = ctx["calculation_result"]
        s = ctx["styles"]

        story = []

        # =========================
        # Section title
        # =========================
        story.append(Paragraph(
            "2. ANALYSIS RESULTS",
            s["Heading_Custom"]
        ))

        story.append(Spacer(1, 10))

        # =========================
        # MAIN METRICS (highlight block)
        # =========================
        main_data = [
            ["Surface Area", f"{r.surface_area_m2:.4f}", "m²"],
            ["Volume", f"{r.volume_m3:.6f}", "m³"],
        ]

        main_table = Table(
            main_data,
            colWidths=[180, 150, 100]
        )

        main_table.setStyle(TableStyle([

            # padding
            ("TOPPADDING", (0,0), (-1,-1), 8),
            ("BOTTOMPADDING", (0,0), (-1,-1), 8),

            # grid soft
            ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#cbd5e0")),

            # label column
            ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#f7fafc")),
            ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
            ("TEXTCOLOR", (0,0), (0,-1), colors.HexColor("#2d3748")),

            # value column highlight
            ("FONTNAME", (1,0), (1,-1), "Helvetica-Bold"),
            ("TEXTCOLOR", (1,0), (1,-1), colors.HexColor("#1a202c")),

            ("ALIGN", (1,0), (-1,-1), "CENTER"),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ]))

        story.append(main_table)
        story.append(Spacer(1, 14))

        # =========================
        # THICKNESS STATISTICS (secondary block)
        # =========================
        stat_data = [
            ["Mean Thickness", f"{r.mean_thickness_mm:.2f} mm"],
            ["Min Thickness", f"{r.min_thickness_mm:.2f} mm"],
            ["Max Thickness", f"{r.max_thickness_mm:.2f} mm"],
            ["Std Deviation", f"{r.std_thickness_mm:.2f} mm"],
            ["Total Points", f"{r.num_points:,}"],
        ]

        stat_table = Table(
            stat_data,
            colWidths=[220, 210]
        )

        stat_table.setStyle(TableStyle([

            # spacing
            ("TOPPADDING", (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),

            # grid light
            ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#e2e8f0")),

            # label style
            ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#f7fafc")),
            ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
            ("TEXTCOLOR", (0,0), (0,-1), colors.HexColor("#4a5568")),

            # value style
            ("FONTNAME", (1,0), (1,-1), "Helvetica"),
            ("TEXTCOLOR", (1,0), (1,-1), colors.HexColor("#1a202c")),

            ("ALIGN", (1,0), (1,-1), "CENTER"),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ]))

        story.append(stat_table)
        story.append(Spacer(1, 18))

        return story