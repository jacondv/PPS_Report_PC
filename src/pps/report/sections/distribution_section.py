from reportlab.platypus import Paragraph, Spacer, Image
from reportlab.lib import colors

import matplotlib.pyplot as plt
import tempfile
import os


class DistributionSection:

    def _create_chart(self, d, tmin, tmax):

        fig, ax = plt.subplots(figsize=(8, 4.5))

        labels = [
            f"< {tmin}",
            f"{tmin}-{tmax}",
            f"> {tmax}"
        ]

        values = [
            d.below_target,
            d.within_target,
            d.above_target
        ]

        colors_list = ["#fc8181", "#68d391", "#f6e05e"]

        bars = ax.bar(labels, values, color=colors_list)

        # value labels on top
        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width()/2,
                height,
                f"{int(height)}",
                ha='center',
                va='bottom',
                fontsize=10
            )

        ax.set_title("Thickness Distribution", fontsize=14, fontweight="bold")
        ax.set_ylabel("Number of Points")

        ax.grid(axis='y', linestyle='--', alpha=0.3)

        plt.tight_layout()

        path = os.path.join(tempfile.gettempdir(), "dist_chart.png")
        plt.savefig(path, dpi=150)
        plt.close(fig)

        return path

    def build(self, ctx):

        d = ctx["thickness_distribution"]
        tmin = ctx["target_min"]
        tmax = ctx["target_max"]
        s = ctx["styles"]

        story = []

        # =========================
        # TITLE
        # =========================
        story.append(Paragraph(
            "3. THICKNESS DISTRIBUTION",
            s["Heading_Custom"]
        ))

        story.append(Spacer(1, 10))

        # =========================
        # CHART ONLY (NO TABLE)
        # =========================
        chart_path = self._create_chart(d, tmin, tmax)

        story.append(Image(chart_path, width=500, height=300))

        story.append(Spacer(1, 12))

        return story