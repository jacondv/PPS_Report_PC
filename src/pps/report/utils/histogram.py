# report/utils/histogram.py

import matplotlib.pyplot as plt
import os
import tempfile

def create_histogram(dist, tmin, tmax):

    fig, ax = plt.subplots(figsize=(8,5))

    centers = (dist.histogram_bins[:-1] + dist.histogram_bins[1:]) / 2
    width = dist.histogram_bins[1] - dist.histogram_bins[0]

    ax.bar(centers, dist.histogram_counts, width=width)

    ax.axvline(tmin, linestyle="--")
    ax.axvline(tmax, linestyle="--")

    path = os.path.join(tempfile.gettempdir(), "hist.png")
    plt.savefig(path)
    plt.close(fig)

    return path