"""Pit-stop duration tracking utilities for FastF1 lap data.

GitHub issue #26:
"Develop a function to track how long a driver has been in pitstop."
"""

from __future__ import annotations

import pandas as pd


_REQUIRED_COLUMNS = {"Driver", "LapNumber", "PitInTime", "PitOutTime"}


def get_pit_stop_durations(
    laps: pd.DataFrame, driver: str | None = None
) -> pd.DataFrame:
    """Return completed pit stops and their pit-lane durations.

    FastF1 records ``PitInTime`` on the lap where a driver enters the pit lane
    and ``PitOutTime`` on the following lap. This function pairs those values
    per driver and calculates the elapsed time in seconds.

    Args:
        laps: FastF1 session laps DataFrame.
        driver: Optional three-letter driver code such as ``"VER"``.
            When omitted, pit stops for all drivers are returned.

    Returns:
        A DataFrame with:
        ``Driver``, ``PitLap``, ``PitInTime``, ``PitOutTime``,
        and ``PitDurationSeconds``.

        Only completed pit stops are returned. A driver who enters the pits but
        never records a later ``PitOutTime`` is not treated as a completed stop.

    Raises:
        ValueError: If the required FastF1 columns are missing.
    """
    missing = _REQUIRED_COLUMNS.difference(laps.columns)
    if missing:
        raise ValueError(
            "laps is missing required column(s): " + ", ".join(sorted(missing))
        )

    data = laps[["Driver", "LapNumber", "PitInTime", "PitOutTime"]].copy()

    if driver is not None:
        driver = driver.upper()
        data = data[data["Driver"].astype(str).str.upper() == driver]

    if data.empty:
        return pd.DataFrame(
            columns=[
                "Driver",
                "PitLap",
                "PitInTime",
                "PitOutTime",
                "PitDurationSeconds",
            ]
        )

    data = data.sort_values(["Driver", "LapNumber"])
    data["NextPitOutTime"] = data.groupby("Driver")["PitOutTime"].shift(-1)

    stops = data[data["PitInTime"].notna() & data["NextPitOutTime"].notna()].copy()

    stops["PitDurationSeconds"] = (
        stops["NextPitOutTime"] - stops["PitInTime"]
    ).dt.total_seconds()

    # Guard against malformed/out-of-order timing data.
    stops = stops[stops["PitDurationSeconds"] >= 0].copy()

    stops = stops.rename(
        columns={
            "LapNumber": "PitLap",
            "NextPitOutTime": "PitOutTimeMatched",
        }
    )

    result = stops[
        [
            "Driver",
            "PitLap",
            "PitInTime",
            "PitOutTimeMatched",
            "PitDurationSeconds",
        ]
    ].rename(columns={"PitOutTimeMatched": "PitOutTime"})

    return result.reset_index(drop=True)


def get_driver_pit_time_at(laps: pd.DataFrame, driver: str, current_time) -> float:
    """Return how many seconds the driver has spent in the current pit visit.

    Args:
        laps: FastF1 session laps DataFrame.
        driver: Three-letter driver code such as ``"VER"``.
        current_time: Session-relative time as a pandas Timedelta, Python
            timedelta, or a value accepted by ``pandas.to_timedelta``.

    Returns:
        Seconds elapsed in the active pit visit. Returns ``0.0`` when the
        driver is not currently between a recorded pit entry and pit exit.

    Notes:
        Completed stops use the same FastF1 pairing as
        :func:`get_pit_stop_durations`.
    """
    missing = _REQUIRED_COLUMNS.difference(laps.columns)
    if missing:
        raise ValueError(
            "laps is missing required column(s): " + ", ".join(sorted(missing))
        )

    now = pd.to_timedelta(current_time)
    data = laps[["Driver", "LapNumber", "PitInTime", "PitOutTime"]].copy()
    data = data[data["Driver"].astype(str).str.upper() == driver.upper()]
    data = data.sort_values("LapNumber")

    if data.empty:
        return 0.0

    data["NextPitOutTime"] = data["PitOutTime"].shift(-1)

    for _, row in data[data["PitInTime"].notna()].iterrows():
        pit_in = row["PitInTime"]
        pit_out = row["NextPitOutTime"]

        if pd.isna(pit_out):
            if now >= pit_in:
                return max(0.0, (now - pit_in).total_seconds())
            continue

        if pit_in <= now < pit_out:
            return max(0.0, (now - pit_in).total_seconds())

    return 0.0
