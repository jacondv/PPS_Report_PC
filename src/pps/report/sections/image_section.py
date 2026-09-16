from reportlab.platypus import Paragraph, Image, Spacer
from reportlab.lib import colors

class ImageSection:

    def build(self, ctx):

        story = []
        s = ctx["styles"]

        story.append(Paragraph(
            "5. 3D VIEW",
            s["Heading_Custom"]
        ))

        story.append(Spacer(1, 10))

        path = ctx.get("screenshot_path")

        # =========================
        # SAFETY CHECK
        # =========================
        if not path:
            story.append(Paragraph(
                "No 3D screenshot available.",
                s["Normal"]
            ))
            return story

        # =========================
        # IMAGE BLOCK (CENTER + CLEAN)
        # =========================
        try:
            img = Image(path)

            # Auto scale giữ ratio (IMPORTANT)
            max_width = 500
            max_height = 350

            img.drawWidth = max_width
            img.drawHeight = max_height

            story.append(img)

        except Exception as e:

            story.append(Paragraph(
                f"Failed to load image: {str(e)}",
                s["Normal"]
            ))

        story.append(Spacer(1, 12))

        return story