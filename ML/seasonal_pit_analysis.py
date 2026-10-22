"""Compare tyre performance across F1 seasons.

This analysis measures observed changes in tyre slowdown.
It does not identify or prove physical car modifications.
"""

import sqlite3

import pandas as pd

from ML.pit_window import DB_PATH, clean_stint_laps, load_race_laps


def compare_seasonal_tyre_wear(db_path=DB_PATH, min_laps=3):
    """Compare 2023 vs 2024 tyre slowdown at shared race circuits."""

    with sqlite3.connect(db_path) as connection:
        races = pd.read_sql_query(
            """
            SELECT event_name, year, session_id
            FROM sessions
            WHERE session_type = 'Race'
              AND year IN (2023, 2024)
            ORDER BY event_name, year
            """,
            connection,
        )

    # Only compare Grand Prix events available in both seasons.
    shared = races.groupby("event_name")["year"].nunique()
    shared = shared[shared == 2].index
    races = races[races["event_name"].isin(shared)]

    frames = []

    for race in races.itertuples(index=False):
        laps = load_race_laps(int(race.session_id), db_path)

        # Our existing model is intended for dry racing.
        if laps.attrs.get("any_rainfall", False):
            continue

        clean = clean_stint_laps(laps)

        # Compare relatively fresh and older tyres.
        clean = clean[
            clean["compound"].isin(["SOFT", "MEDIUM", "HARD"])
            & (clean["tyre_life"].between(3, 5) | clean["tyre_life"].between(12, 15))
        ].copy()

        if clean.empty:
            continue

        clean["age_group"] = clean["tyre_life"].apply(
            lambda age: "fresh" if age <= 5 else "older"
        )
        clean["event_name"] = race.event_name
        clean["year"] = int(race.year)

        frames.append(
            clean[
                [
                    "event_name",
                    "year",
                    "driver",
                    "compound",
                    "age_group",
                    "corrected",
                ]
            ]
        )

    columns = [
        "event_name",
        "driver",
        "compound",
        "slowdown_2023_s",
        "slowdown_2024_s",
        "change_s",
    ]

    if not frames:
        return pd.DataFrame(columns=columns)

    data = pd.concat(frames, ignore_index=True)

    grouped = (
        data.groupby(["event_name", "year", "driver", "compound", "age_group"])[
            "corrected"
        ]
        .agg(["count", "median"])
        .reset_index()
    )

    # Require enough clean laps in each tyre-age group.
    grouped = grouped[grouped["count"] >= min_laps]

    paired_ages = grouped.pivot(
        index=["event_name", "year", "driver", "compound"],
        columns="age_group",
        values="median",
    )

    if not {"fresh", "older"}.issubset(paired_ages.columns):
        return pd.DataFrame(columns=columns)

    paired_ages = paired_ages.dropna(subset=["fresh", "older"])

    # Positive means older tyres are slower than fresh tyres.
    paired_ages["slowdown"] = paired_ages["older"] - paired_ages["fresh"]

    seasons = paired_ages["slowdown"].unstack("year")

    if not {2023, 2024}.issubset(seasons.columns):
        return pd.DataFrame(columns=columns)

    seasons = seasons.dropna(subset=[2023, 2024])

    seasons = seasons.rename(
        columns={
            2023: "slowdown_2023_s",
            2024: "slowdown_2024_s",
        }
    )

    seasons["change_s"] = seasons["slowdown_2024_s"] - seasons["slowdown_2023_s"]

    return (
        seasons.reset_index()[columns]
        .sort_values(["event_name", "compound", "driver"])
        .reset_index(drop=True)
    )


def main():
    comparisons = compare_seasonal_tyre_wear()

    print("SEASONAL TYRE PERFORMANCE ANALYSIS")
    print("=" * 45)
    print(f"Matched driver/tyre comparisons: {len(comparisons)}")

    if comparisons.empty:
        print("Not enough comparable data.")
        return

    print("\nChanges by tyre compound:")
    print(
        comparisons.groupby("compound")["change_s"]
        .agg(["count", "median", "mean"])
        .round(3)
        .to_string()
    )

    print("\nChanges by Grand Prix:")
    print(
        comparisons.groupby("event_name")["change_s"]
        .agg(["count", "median"])
        .round(3)
        .to_string()
    )

    print("\nInterpretation:")
    print("Negative change = less measured tyre slowdown in 2024.")
    print("Positive change = more measured tyre slowdown in 2024.")
    print("These differences do NOT prove car upgrades.")
    print("Weather, track conditions and strategy remain confounders.")
    print("No changes have been made to pit stop predictions.")


if __name__ == "__main__":
    main()
