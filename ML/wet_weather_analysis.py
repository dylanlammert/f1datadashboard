
"""Wet-weather driver comparisons using historical F1 race data."""

import sqlite3

import numpy as np
import pandas as pd

from Services.dbhandler import DB_PATH


def _median_absolute_deviation(values):
    """Measure consistency around a driver's median relative pace."""
    values = np.asarray(values, dtype=float)
    median = np.median(values)
    return float(np.median(np.abs(values - median)))


def analyze_wet_weather(
    session_id: int,
    db_path: str = DB_PATH,
    compound: str = "INTERMEDIATE",
    min_peers: int = 5,
    min_samples: int = 5,
) -> pd.DataFrame:
    """Compare driver pace during rain and no recorded rain.

    Comparisons use drivers on the same race lap, tyre compound,
    and rainfall condition.

    Smaller relative pace gaps indicate faster performance.
    Results are descriptive, not driver-skill predictions.
    """

    with sqlite3.connect(
        f"file:{db_path}?mode=ro", uri=True
    ) as db:
        laps = pd.read_sql_query(
            """
            SELECT session_id, driver, lap_number,
                   lap_end_time, lap_time_seconds,
                   compound, track_status, is_pit_lap
            FROM laps
            WHERE session_id = ?
            """,
            db,
            params=(int(session_id),),
        )

        weather = pd.read_sql_query(
            """
            SELECT session_id, sample_time, rainfall
            FROM weather
            WHERE session_id = ?
            """,
            db,
            params=(int(session_id),),
        )

    if laps.empty or weather.empty:
        raise ValueError("Race lap or weather data is unavailable.")

    laps["time_s"] = pd.to_numeric(
        laps["lap_end_time"], errors="coerce"
    )

    weather["time_s"] = pd.to_timedelta(
        weather["sample_time"], errors="coerce"
    ).dt.total_seconds()

    laps = laps.dropna(subset=["time_s"])
    weather = weather.dropna(subset=["time_s"])

    if laps.empty or weather.empty:
        raise ValueError("No usable lap or weather timestamps.")

    matched = pd.merge_asof(
        laps.sort_values("time_s"),
        weather.sort_values("time_s"),
        on="time_s",
        by="session_id",
        direction="nearest",
        tolerance=90.0,
    )

    clean = matched[
        matched["lap_time_seconds"].notna()
        & matched["rainfall"].isin([0, 1])
        & (matched["lap_number"] > 1)
        & (matched["lap_time_seconds"] > 0)
        & (matched["is_pit_lap"] == 0)
        & matched["track_status"].isin(["1", "['1']"])
        & (matched["compound"] == compound.upper())
    ].copy()

    grouping = [
        "session_id", "lap_number", "compound", "rainfall"
    ]

    clean["peer_count"] = clean.groupby(
        grouping
    )["driver"].transform("nunique")

    clean = clean[clean["peer_count"] >= min_peers].copy()

    if clean.empty:
        raise ValueError("Not enough comparable racing laps.")

    clean["peer_median_s"] = clean.groupby(
        grouping
    )["lap_time_seconds"].transform("median")

    clean["relative_pace_s"] = (
        clean["lap_time_seconds"] - clean["peer_median_s"]
    )

    summary = (
        clean.groupby(["driver", "rainfall"])["relative_pace_s"]
        .agg(
            laps="size",
            median_gap_s="median",
            consistency_mad_s=_median_absolute_deviation,
        )
        .reset_index()
    )

    rain = summary[
        summary["rainfall"] == 1
    ].set_index("driver").drop(columns="rainfall")

    no_rain = summary[
        summary["rainfall"] == 0
    ].set_index("driver").drop(columns="rainfall")

    report = rain.add_prefix("rain_").join(
        no_rain.add_prefix("no_rain_"),
        how="inner",
    )

    report = report[
        (report["rain_laps"] >= min_samples)
        & (report["no_rain_laps"] >= min_samples)
    ].copy()

    report["relative_rain_advantage_s"] = (
        report["no_rain_median_gap_s"]
        - report["rain_median_gap_s"]
    )

    report = report.sort_values(
        "relative_rain_advantage_s",
        ascending=False,
    )

    return report.reset_index()
