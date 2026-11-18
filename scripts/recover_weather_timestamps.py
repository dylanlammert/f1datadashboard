
"""Recover missing lap timestamps for 2024 wet-weather races.

Usage:
    python scripts/recover_weather_timestamps.py
    python scripts/recover_weather_timestamps.py --apply

Preview mode makes no database changes.
Apply mode creates a verified backup before updating missing timestamps.
"""

import argparse
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime
from pathlib import Path

import fastf1
import pandas as pd

from Services.dbhandler import DB_PATH


@contextmanager
def db_connection(*args, **kwargs):
    with closing(sqlite3.connect(*args, **kwargs)) as db:
        with db:
            yield db


def recover(db_path, apply=False):
    source = Path(db_path).resolve()

    if not source.is_file():
        raise FileNotFoundError(source)

    with db_connection(
        f"file:{source.as_posix()}?mode=ro", uri=True
    ) as db:
        sessions = db.execute("""
            SELECT session_id, event_name
            FROM sessions
            WHERE year = 2024 AND session_type = 'Race'
        """).fetchall()

        targets = [
            (sid, name)
            for sid, name in sessions
            if "canadian grand prix" in name.casefold()
            or "paulo grand prix" in name.casefold()
        ]

        updates_by_session = {}

        for sid, name in targets:
            stored = db.execute("""
                SELECT driver, lap_number, lap_time_seconds,
                       lap_start_time, lap_end_time
                FROM laps
                WHERE session_id = ?
            """, (sid,)).fetchall()

            missing = [
                row for row in stored
                if row[3] is None and row[4] is None
            ]

            if any(
                (row[3] is None) != (row[4] is None)
                for row in stored
            ):
                raise ValueError(
                    f"Session {sid} contains partially missing timestamps."
                )

            if not missing:
                print(f"{name}: Already complete")
                continue

            print(f"Checking {name}...")

            session = fastf1.get_session(2024, name, "R")
            session.load(
                telemetry=False,
                weather=False,
                messages=False,
            )

            original = {}

            for _, lap in session.laps.iterrows():
                key = (
                    str(lap["Driver"]),
                    int(lap["LapNumber"]),
                )

                if key in original:
                    raise ValueError(f"Duplicate FastF1 lap: {key}")

                original[key] = lap

            stored_keys = [
                (str(row[0]), int(row[1]))
                for row in stored
            ]

            if (
                len(stored_keys) != len(set(stored_keys))
                or set(stored_keys) != set(original)
            ):
                raise ValueError(
                    f"Lap records do not match for {name}."
                )

            updates = []

            for driver, number, lap_seconds, start, end in missing:
                lap = original[(str(driver), int(number))]

                start_time = lap["LapStartTime"]
                end_time = lap["Time"]

                if pd.isna(start_time) or pd.isna(end_time):
                    raise ValueError(
                        f"Missing original timing: {driver}, lap {number}"
                    )

                original_lap = lap["LapTime"]

                if (
                    lap_seconds is not None
                    and pd.notna(original_lap)
                    and abs(
                        float(lap_seconds)
                        - original_lap.total_seconds()
                    ) > 0.05
                ):
                    raise ValueError(
                        f"Lap duration mismatch: {driver}, lap {number}"
                    )

                updates.append((
                    float(start_time.total_seconds()),
                    float(end_time.total_seconds()),
                    sid,
                    driver,
                    number,
                ))

            updates_by_session[sid] = updates
            print(f"{name}: {len(updates)} timestamps recoverable")

    count = sum(map(len, updates_by_session.values()))

    if not count:
        print("No missing timestamps require recovery.")
        return

    if not apply:
        print(f"\nPREVIEW: {count} laps eligible for recovery.")
        print("Run with --apply to back up and update the database.")
        return

    backup = source.parent.parent / (
        f"{source.stem}_before_timestamp_recovery_"
        f"{datetime.now():%Y%m%d_%H%M%S}{source.suffix}"
    )

    if backup.exists():
        raise FileExistsError(backup)

    with db_connection(
        f"file:{source.as_posix()}?mode=ro", uri=True
    ) as src:
        with db_connection(backup) as dst:
            src.backup(dst)

    with db_connection(backup) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Backup integrity check failed.")

    print("Verified backup:", backup)

    with db_connection(source) as db:
        for sid, updates in updates_by_session.items():
            cursor = db.executemany("""
                UPDATE laps
                SET lap_start_time = ?,
                    lap_end_time = ?
                WHERE session_id = ?
                  AND driver = ?
                  AND lap_number = ?
                  AND lap_start_time IS NULL
                  AND lap_end_time IS NULL
            """, updates)

            if cursor.rowcount != len(updates):
                raise ValueError(
                    f"Unexpected update count for session {sid}"
                )

        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Database integrity check failed.")

    print(f"SUCCESS: Recovered {count} lap timestamps.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--db", default=DB_PATH)
    args = parser.parse_args()

    recover(args.db, apply=args.apply)
