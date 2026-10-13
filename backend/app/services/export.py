import csv
import io
import textwrap

import matplotlib

matplotlib.use("Agg")  # headless backend; must be set before pyplot is imported

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

YEARLY_FIELDS = ["year", "HWN", "HWF", "HWD", "HWM", "HWA", "low_quality"]
EVENT_FIELDS = ["start", "end", "days", "peak_tmax", "mean_exceedance"]


def to_csv(analysis: dict) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    years = analysis["years"]
    out.write(f"# Heatwave analysis: {analysis['region']['label']}, {years['start']}-{years['end']}\n")
    for sentence in analysis["insights"]:
        out.write(f"# {sentence}\n")
    out.write("\n")
    writer.writerow(YEARLY_FIELDS)
    for row in analysis["yearly"]:
        writer.writerow(["" if row[f] is None else row[f] for f in YEARLY_FIELDS])
    out.write("\n")
    writer.writerow(EVENT_FIELDS)
    for event in analysis["events"]:
        writer.writerow([str(event[f]) for f in EVENT_FIELDS])
    return out.getvalue()


def _plot_metric(ax, chart: dict, metric: str, title: str, unit: str) -> None:
    years = chart["years"]
    series = chart["series"][metric]
    ax.bar(years, [v or 0 for v in series["values"]], color="#e8743b", label=title)
    ax.plot(years, series["rolling5"], color="#7a2e0e", linewidth=2, label="5-year average")
    if any(v is not None for v in series["trendline"]):
        ax.plot(years, series["trendline"], color="#333333", linestyle="--", label="Linear trend")
    ax.set_title(title)
    ax.set_ylabel(unit)
    ax.legend(loc="upper left", fontsize=8)


def to_pdf(analysis: dict) -> bytes:
    buffer = io.BytesIO()
    years = analysis["years"]
    with PdfPages(buffer) as pdf:
        fig = plt.figure(figsize=(8.27, 11.69))  # A4 portrait
        lines = [f"Heatwave analysis — {analysis['region']['label']}", f"{years['start']}–{years['end']}", ""]
        lines += ["Insights:"] + [f"• {w}" for s in analysis["insights"] for w in textwrap.wrap(s, 95)]
        lines += ["", "Caveats:"] + [f"– {w}" for c in analysis["caveats"] for w in textwrap.wrap(c, 95)]
        fig.text(0.06, 0.95, "\n".join(lines), va="top", fontsize=9, family="DejaVu Sans")
        pdf.savefig(fig)
        plt.close(fig)

        fig, axes = plt.subplots(2, 1, figsize=(8.27, 11.69))
        _plot_metric(axes[0], analysis["chart"], "HWF", "Heatwave days per year", "days")
        _plot_metric(axes[1], analysis["chart"], "HWN", "Heatwave events per year", "events")
        fig.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)
    return buffer.getvalue()
