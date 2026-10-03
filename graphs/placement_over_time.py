"""
Graph: Placement over Time  (GitHub issue #44)

Shows every driver's race position on every lap of a session.

Design (so 20 lines stay readable):
- every driver is drawn as a thin grey line for context
- a few drivers are HIGHLIGHTED in their team colour and labelled at the end
  of their line (default: the podium). Teammates share a team colour, so the
  second driver of a team is drawn dashed -- identity is never colour alone.
- P1 is at the top, lap 0 is the starting grid
- a driver who retired gets an "x" where their line stops

Data comes from DBhandler.getLapPositions(), which reads the laps.position
and results tables (#29). build_placement_figure() returns a matplotlib
Figure, so the Data Analysis page can embed it later with
matplotlib.backends.backend_qtagg.FigureCanvasQTAgg(fig).

Run it on its own:
    python -m graphs.placement_over_time                 # session 1, podium highlighted
    python -m graphs.placement_over_time 1 ALO HAM LEC   # pick drivers to highlight
"""

import os
import sys

import matplotlib

if __name__ == "__main__":
    matplotlib.use("Agg")  # standalone run just saves a PNG
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
import matplotlib.patheffects as pe

# colours match the app's dark theme (main.py backgroundColor = #1A1A1A)
BACKGROUND = "#1A1A1A"
CONTEXT_LINE = "#4E4E58"  # every non-highlighted driver
GRID_LINE = "#2C2C34"
TEXT = "#ECECEC"
MUTED_TEXT = "#9A9AA6"


def default_highlight(lapPositions: dict[str, dict], count: int = 3) -> list[str]:
    """The top `count` finishers (e.g. the podium)."""
    finishers = [
        (info["finish"], code)
        for code, info in lapPositions.items()
        if info.get("finish") is not None
    ]
    return [code for _, code in sorted(finishers)[:count]]


def build_placement_figure(
    lapPositions: dict[str, dict],
    title: str = "Placement over Time",
    highlight: list[str] | None = None,
) -> Figure:
    """Draw the placement-over-time chart.

    Args:
        lapPositions (dict): output of DBhandler.getLapPositions(sessionID)
        title (str): chart title, e.g. "2023 Bahrain Grand Prix"
        highlight (list[str] | None): driver codes to colour and label.
            None = the podium. Keep it to about 4 or fewer so it stays readable.

    Returns:
        Figure: a matplotlib Figure (not shown -- caller decides where it goes)
    """
    if not lapPositions:
        raise ValueError(
            "no lap positions for this session -- reload it with DBhandler.loadSessionIntoDB"
        )
    if highlight is None:
        highlight = default_highlight(lapPositions)
    highlight = [code for code in highlight if code in lapPositions]

    fieldSize = max(max(info["positions"]) for info in lapPositions.values())
    lastLap = max(max(info["laps"]) for info in lapPositions.values())

    fig = Figure(figsize=(12, 7), facecolor=BACKGROUND)
    ax = fig.add_subplot(111, facecolor=BACKGROUND)
    fig.subplots_adjust(left=0.07, right=0.86, top=0.88, bottom=0.17)

    def finishedLap(info: dict) -> bool:
        return info["laps"][-1] >= lastLap - 1  # lapped cars finish a lap early

    def retired(info: dict) -> bool:
        return (info.get("classified") or "").isalpha() or not finishedLap(info)

    # 1) context: everyone in grey, drawn first so highlights sit on top
    for code, info in lapPositions.items():
        if code in highlight:
            continue
        ax.plot(
            info["laps"], info["positions"], color=CONTEXT_LINE, linewidth=1.1, zorder=1
        )
        if retired(info):
            ax.plot(
                info["laps"][-1],
                info["positions"][-1],
                marker="x",
                color=CONTEXT_LINE,
                markersize=7,
                markeredgewidth=1.6,
                zorder=1,
            )

    # 2) highlighted drivers in team colour, teammates dashed
    teamsSeen: dict[str, int] = {}
    legendHandles = []
    for code in highlight:
        info = lapPositions[code]
        color = info.get("color") or TEXT
        teamIndex = teamsSeen.get(info.get("team"), 0)
        teamsSeen[info.get("team")] = teamIndex + 1
        style = "-" if teamIndex == 0 else (0, (4, 2))
        ring = [
            pe.Stroke(linewidth=5, foreground=BACKGROUND),
            pe.Normal(),
        ]  # surface ring
        ax.plot(
            info["laps"],
            info["positions"],
            color=color,
            linewidth=2.4,
            linestyle=style,
            zorder=3,
            path_effects=ring,
        )

        endLap, endPos = info["laps"][-1], info["positions"][-1]
        if retired(info):
            ax.plot(
                endLap,
                endPos,
                marker="x",
                color=color,
                markersize=10,
                markeredgewidth=2.4,
                zorder=4,
            )
            label = f"{code}  DNF"
        else:
            ax.plot(
                endLap,
                endPos,
                marker="o",
                color=color,
                markersize=8,
                zorder=4,
                markeredgecolor=BACKGROUND,
                markeredgewidth=1.5,
            )
            label = f"{code}  P{info['finish'] if info.get('finish') else endPos}"
        # direct label in text colour (the coloured marker beside it carries identity)
        ax.annotate(
            label,
            (endLap, endPos),
            xytext=(10, 0),
            textcoords="offset points",
            va="center",
            color=TEXT,
            fontsize=11,
            fontweight="bold",
            annotation_clip=False,
            zorder=5,
        )

        grid = info.get("grid")
        legendText = f"{code} — {info.get('team') or ''}"
        if grid:
            legendText += f"  (started P{grid})"
        legendHandles.append(
            Line2D(
                [0], [0], color=color, linewidth=2.4, linestyle=style, label=legendText
            )
        )

    # 3) axes: P1 at the top, lap 0 = grid
    ax.set_ylim(fieldSize + 0.6, 0.4)
    ax.set_yticks(range(1, fieldSize + 1))
    ax.set_yticklabels([f"P{p}" for p in range(1, fieldSize + 1)], fontsize=9)
    ax.set_xlim(0, lastLap + 0.5)
    step = 5 if lastLap <= 60 else 10
    xticks = [0] + list(range(step, lastLap + 1, step))
    ax.set_xticks(xticks)
    ax.set_xticklabels(["Grid"] + [str(t) for t in xticks[1:]], fontsize=9)
    ax.set_xlabel("Lap", color=MUTED_TEXT, fontsize=11)
    ax.set_ylabel("Race position", color=MUTED_TEXT, fontsize=11)
    ax.tick_params(colors=MUTED_TEXT, length=0)
    ax.grid(axis="y", color=GRID_LINE, linewidth=0.6, zorder=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    fig.suptitle(
        f"Placement over Time — {title}",
        x=0.07,
        y=0.96,
        ha="left",
        color=TEXT,
        fontsize=16,
        fontweight="bold",
    )
    fig.text(
        0.07,
        0.905,
        "Grey = rest of the field   ·   x = retired",
        color=MUTED_TEXT,
        fontsize=10,
    )
    if legendHandles:
        legend = ax.legend(
            handles=legendHandles,
            loc="upper center",
            bbox_to_anchor=(0.5, -0.1),
            ncol=len(legendHandles) if len(legendHandles) <= 3 else 2,
            frameon=False,
            fontsize=10,
        )
        for text in legend.get_texts():
            text.set_color(TEXT)
    return fig


def placement_figure_for_session(
    sessionID: int, highlight: list[str] | None = None, dbHandler=None
) -> Figure:
    """Fetch the data for one session from the database and build the figure."""
    from Services.dbhandler import DBhandler

    handler = dbHandler or DBhandler()
    try:
        row = handler.conn.execute(
            "SELECT year, event_name FROM sessions WHERE session_id = ?", (sessionID,)
        ).fetchone()
        title = f"{row[0]} {row[1]}" if row else f"Session {sessionID}"
        return build_placement_figure(
            handler.getLapPositions(sessionID), title, highlight
        )
    finally:
        if dbHandler is None:
            handler.close()


def _main():
    sessionID = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    highlight = [code.upper() for code in sys.argv[2:]] or None
    fig = placement_figure_for_session(sessionID, highlight)
    path = f"placement_session{sessionID}.png"
    fig.savefig(path, dpi=150, facecolor=BACKGROUND)
    print(f"Saved {os.path.abspath(path)}")
    if hasattr(os, "startfile"):  # Windows: open it
        os.startfile(path)
    return 0


if __name__ == "__main__":
    _main()
