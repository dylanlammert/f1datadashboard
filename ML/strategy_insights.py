
"""Reusable AI pit stop strategy insights for Ghost Racer."""

import pandas as pd

from ML.pit_window import (
    DB_PATH,
    DRY_COMPOUNDS,
    load_race_laps,
    recommend_pit_window,
)


def get_strategy_insights(
    session_id: int,
    driver: str,
    current_lap: int,
    db_path: str = DB_PATH,
) -> dict:
    """Estimate a driver's next pit stop using historical race data."""

    if not session_id:
        raise ValueError("Select a race first.")

    driver = driver.upper()
    current_lap = int(current_lap)

    laps = load_race_laps(session_id, db_path)

    if laps.attrs.get("any_rainfall"):
        raise ValueError("The current strategy model supports dry races only.")

    driver_laps = laps[laps["driver"] == driver]

    current = driver_laps[
        driver_laps["lap_number"] == current_lap
    ]

    if current.empty:
        raise ValueError(
            f"No lap {current_lap} data available for {driver}."
        )

    row = current.iloc[0]
    compound = str(row["compound"]).upper()

    if compound not in DRY_COMPOUNDS:
        raise ValueError("Only SOFT, MEDIUM and HARD tyres are supported.")

    if pd.isna(row["tyre_life"]):
        raise ValueError("Tyre life data is unavailable.")

    previous_compounds = set(
        driver_laps[
            driver_laps["lap_number"] <= current_lap
        ]["compound"].dropna().astype(str).str.upper()
    )

    must_change = len(previous_compounds & set(DRY_COMPOUNDS)) < 2

    recommendation = recommend_pit_window(
        session_id=session_id,
        driver=driver,
        current_lap=current_lap,
        compound=compound,
        tyre_life=int(row["tyre_life"]),
        must_change_compound=must_change,
        db_path=db_path,
    )

    return {
        "driver": driver,
        "session_id": session_id,
        "current_lap": current_lap,
        "current_compound": compound,
        "tyre_life": int(row["tyre_life"]),
        **recommendation,
    }
