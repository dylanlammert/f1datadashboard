from __future__ import annotations
import math
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter, MaxNLocator, MultipleLocator
from Services.dbhandler import DBhandler
from graphs.graph_metrics import Metric, MetricSpec
from graphs.themes import ACCENT, BACKGROUND, MUTED_TEXT, style_axes_dark


def _format_session_time(x: int, _pos=None) -> str:
    """Formats session time into a readable string

    Args:
        x (int): The time (in seconds) to convert
        _pos (optional): MatPlotLib passed argument. Not sure what it does, but it's required and graphs will not generate if it's removed. Defaults to None.

    Returns:
        str: The formatted time text
    """
    h, rem = divmod(int(x), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}"


class GenericGraphFactory:
    # ? Since telemetry can be a shit ton of rows, we're limiting the maximum data points
    MAX_POINTS = 5000
    # ? How many drivers to show on graphs (keeps it clean), goes from top to bottom
    DEFAULT_DRIVER_COUNT = 22

    def __init__(self, db: DBhandler):
        self._db = db

    def build(
        self, metric: Metric, session_id: int, drivers: list[str] | None = None
    ) -> Figure:
        spec = metric.spec
        fig = Figure(figsize=(10, 5), layout="tight", facecolor=BACKGROUND)
        ax = fig.add_subplot(111, facecolor=BACKGROUND)
        plotted = False

        if spec.per_driver:
            roster = self._db.getSessionDrivers(session_id)
            roster = (
                [r for r in roster if r[0] in drivers]
                if drivers
                else roster[: self.DEFAULT_DRIVER_COUNT]
            )
            seen_colors = set()

            for code, color in roster:
                df = self._db.getMetricSeries(spec, session_id, driver=code)
                # ? Helps support teammates, they'll get double dash
                style = "--" if color in seen_colors else "-"
                seen_colors.add(color)
                # ? `|=` is similar to `+=` but allows an in-place or operation between sets. Super helpful, but I know it's not common, so I'm including this explanation :)
                plotted |= self._draw(
                    ax, df, spec, label=code, color=color, linestyle=style
                )
            if plotted:
                ax.legend(loc="best")
        else:
            df = self._db.getMetricSeries(spec, session_id)
            plotted = self._draw(ax, df, spec, label=spec.label)

        if not plotted:
            ax.text(
                0.5,
                0.5,
                "No Data For This Session",
                ha="center",
                va="center",
                transform=ax.transAxes,
                color=MUTED_TEXT,
            )

        ax.set_title(spec.label)
        ax.set_xlabel("Session Time")
        ax.set_ylabel(f"{spec.label} ({spec.unit})" if spec.unit else spec.label)
        # ? The major ticker is every 10 minutes
        ax.xaxis.set_major_locator(MultipleLocator(600))
        ax.xaxis.set_major_formatter(FuncFormatter(_format_session_time))
        if spec.step:
            ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        if spec.invert_y:
            ax.invert_yaxis()
        style_axes_dark(ax)
        fig.text(
            0.99,
            0.01,
            "auto-generated - unvetted",
            ha="right",
            fontsize=7,
            color=MUTED_TEXT,
        )
        return fig

    def _draw(
        self, ax, df, spec: MetricSpec, *, label, color=None, linestyle="-"
    ) -> bool:
        if df.empty:
            return False
        color = color or ACCENT
        stride = max(1, math.ceil(len(df) / self.MAX_POINTS))
        df = df.iloc[::stride]
        if spec.step:
            ax.step(
                df["t"],
                df["y"],
                where="post",
                label=label,
                color=color,
                linestyle=linestyle,
            )
        else:
            ax.plot(df["t"], df["y"], label=label, color=color, linestyle=linestyle)
        return True
