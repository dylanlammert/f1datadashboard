
"""Wet-weather driver performance graph for Ghost Racer."""

import sqlite3
from pathlib import Path

from matplotlib.figure import Figure

from graphs.themes import BACKGROUND, GRID_LINE, TEXT, MUTED_TEXT
from ML.wet_weather_analysis import analyze_wet_weather
from Services.dbhandler import DB_PATH


def build_wet_weather_figure(session_id: int) -> Figure:
    """Compare relative pace on intermediate tyres across rainfall states."""

    fig = Figure(figsize=(12, 7), facecolor=BACKGROUND)
    ax = fig.add_subplot(111, facecolor=BACKGROUND)

    if not session_id:
        _placeholder(ax, "Select a race to view wet-weather analysis.")
        return fig

    try:
        results = analyze_wet_weather(session_id)
    except ValueError as exc:
        _placeholder(ax, f"Analysis unavailable: {exc}")
        return fig

    if results.empty:
        _placeholder(ax, "Not enough comparable wet-weather laps.")
        return fig

    results = results.sort_values(
        "relative_rain_advantage_s", ascending=True
    )

    drivers = results["driver"].tolist()
    values = results["relative_rain_advantage_s"].tolist()

    labels = [
        (
            f"{row.driver}   "
            f"({int(row.rain_laps)} rain / "
            f"{int(row.no_rain_laps)} no rain)"
        )
        for row in results.itertuples()
    ]

    colors = [
        "#43bfb7" if value >= 0 else "#e58a69"
        for value in values
    ]

    ax.barh(
        range(len(drivers)),
        values,
        color=colors,
        height=0.72,
    )

    ax.set_yticks(range(len(drivers)))
    ax.set_yticklabels(labels, fontsize=9, color=TEXT)

    ax.axvline(
        0,
        color=GRID_LINE,
        linewidth=1.5,
    )

    with sqlite3.connect(
        f"file:{Path(DB_PATH).resolve().as_posix()}?mode=ro",
        uri=True,
    ) as db:
        race = db.execute(
            "SELECT year, event_name FROM sessions WHERE session_id = ?",
            (int(session_id),),
        ).fetchone()

    race_name = (
        f"{race[0]} {race[1]}"
        if race else f"Session {session_id}"
    )

    ax.set_title(
        f"{race_name}\nDriver Performance During Recorded Rainfall",
        color=TEXT,
        fontsize=14,
        pad=14,
    )

    ax.set_xlabel(
        "Relative rain advantage (seconds, higher is better)",
        color=TEXT,
        fontsize=11,
        labelpad=12,
    )

    ax.tick_params(
        axis="x",
        colors=MUTED_TEXT,
        labelsize=9,
    )

    ax.tick_params(axis="y", length=0)

    ax.grid(
        axis="x",
        color=GRID_LINE,
        alpha=0.4,
    )

    ax.set_axisbelow(True)

    for spine in ax.spines.values():
        spine.set_visible(False)

    max_abs = max(
        max(abs(value) for value in values),
        0.1,
    )

    ax.set_xlim(
        -max_abs * 1.2,
        max_abs * 1.2,
    )

    fig.subplots_adjust(
        left=0.32,
        right=0.95,
        top=0.86,
        bottom=0.26,
    )

    fig.text(
        0.5,
        0.075,
        "INTERMEDIATE tyres only | Same-lap peer comparisons | "
        "Green-flag, non-pit laps",
        color=MUTED_TEXT,
        ha="center",
        fontsize=9,
    )

    fig.text(
        0.5,
        0.045,
        "No recorded rain does not necessarily mean a dry track. "
        "Results describe these races, not overall driver skill.",
        color=MUTED_TEXT,
        ha="center",
        fontsize=8,
    )

    return fig


def _placeholder(ax, message: str) -> None:
    """Display a helpful message when analysis is unavailable."""

    ax.set_axis_off()

    ax.text(
        0.5,
        0.55,
        "WET-WEATHER DRIVER ANALYSIS",
        transform=ax.transAxes,
        color=TEXT,
        fontsize=17,
        fontweight="bold",
        ha="center",
    )

    ax.text(
        0.5,
        0.42,
        message,
        transform=ax.transAxes,
        color=MUTED_TEXT,
        fontsize=11,
        ha="center",
        wrap=True,
    )
