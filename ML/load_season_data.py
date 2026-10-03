"""
Loads whole F1 seasons of RACES into the local database, for the race
outcome model (#42). One season is only ~22 races / ~440 results, so we
load a couple of seasons.

Skips car telemetry, so each race is a small download.

Safe to stop and re-run:
- races already in the database are skipped, so if it hangs on a download,
  press Ctrl+C (or close the terminal) and run it again -- it carries on
  from where it stopped
- a race that fails to load is reported at the end instead of stopping the run

Run from the project root:
    python -m ML.load_season_data              # 2023 and 2024
    python -m ML.load_season_data 2023 2024 2025
"""

import sqlite3
import sys

import fastf1
import pandas as pd

from Services.database import DB_PATH, create_schema, load_session_into_db

DEFAULT_YEARS = [2023, 2024]


def already_loaded(year: int, event_name: str, db_path: str = DB_PATH) -> bool:
    """True if this race already has results in the database."""
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        """
        SELECT COUNT(*) FROM sessions s
        JOIN results r ON r.session_id = s.session_id
        WHERE s.year = ? AND s.event_name = ?
        """,
        (year, event_name),
    ).fetchone()
    conn.close()
    return row[0] > 0


def light_session(year: int, rnd: int):
    """Load a race WITHOUT car telemetry (~80 MB per race we never store).

    load_session_into_db() only uses laps, results, weather, track status and
    session status -- none of which need telemetry. It calls session.load()
    itself (which would download telemetry), so after our light load we make
    that second call a no-op.
    """
    session = fastf1.get_session(year, rnd, "R")
    session.load(laps=True, telemetry=False, weather=True, messages=True)
    session.load = lambda *args, **kwargs: None
    return session


def load_seasons(years: list[int], db_path: str = DB_PATH) -> None:
    create_schema(db_path)
    failed = []
    loaded = skipped = 0
    for year in years:
        schedule = fastf1.get_event_schedule(year, include_testing=False)
        for _, event in schedule.iterrows():
            name, rnd = event["EventName"], int(event["RoundNumber"])
            if pd.Timestamp(event["EventDate"]) > pd.Timestamp.now():
                continue  # race hasn't happened yet
            if already_loaded(year, name, db_path):
                skipped += 1
                continue
            print(f"\n=== {year} round {rnd}: {name} ===", flush=True)
            try:
                load_session_into_db(light_session(year, rnd), db_path)
                loaded += 1
            except Exception as e:  # keep going -- one bad race shouldn't stop the run
                print(
                    f"  !! skipped {year} {name}: {type(e).__name__}: {e}", flush=True
                )
                failed.append(f"{year} {name}")

    print("\n" + "=" * 60)
    print(f"Loaded {loaded} new races, {skipped} were already in the database.")
    if failed:
        print(f"{len(failed)} races failed to load (re-run later to retry):")
        for race in failed:
            print("  -", race)
    conn = sqlite3.connect(db_path)
    races, results = conn.execute(
        "SELECT COUNT(DISTINCT session_id), COUNT(*) FROM results"
    ).fetchone()
    conn.close()
    print(f"Database now has {races} races with results ({results} driver results).")


if __name__ == "__main__":
    years = [int(y) for y in sys.argv[1:]] or DEFAULT_YEARS
    load_seasons(years)
