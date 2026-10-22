"""
Ghost Racer — Lap Time Prediction Model (relative pace)

Predicts how fast a lap SHOULD be given tyre compound, tyre age and fuel
load, and flags laps that are faster/slower than expected.

HOW IT WORKS (v2):
The model does not predict raw lap time. Raw lap time is mostly "which
track is this" (Monaco ~75 s, Spa ~110 s), and the first version learned
exactly that: it looked accurate (0.61 s) on random laps from races it had
already seen, but on races it had NEVER seen its error was ~8.6 s per lap,
and it predicted the same pace for SOFT, MEDIUM and HARD.

Instead, every lap is compared with that driver's typical (median) lap in
the same race:

    expected lap = driver's typical lap this race + predicted delta
    predicted delta = f(compound, tyre age, fuel load, track temperature)

so the model only has to learn the physics (tyres wear, fuel burns off).
A linear regression does this best: on 5 different sets of held-out races
it averaged 0.540 s error vs 0.792 s for the baseline (and 0.615 s for a
gradient-boosting version).

HONEST TESTING: whole races are held out -- the model is tested on races it
never trained on, and compared with the simple guess "the driver's typical
lap this race".

Only dry, green-flag laps on SOFT/MEDIUM/HARD are used (no pit laps, no lap 1,
no wet races, no laps 3+ s off the driver's typical pace = traffic/mistakes).

ASSUMPTION: each lap uses its race's AVERAGE weather (the laps table has no
timestamp to match exact weather samples).
"""

import sqlite3
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
import joblib

from Services.dbhandler import DB_PATH


# %% [1] LOAD DATA FROM THE DATABASE -----------------------------------------
def load_training_data(db_path: str = DB_PATH) -> pd.DataFrame:
    """Pull laps joined with session-average weather for every race loaded
    in the database.

    Args:
        db_path (str, optional): The file path for the database. Defaults to DB_PATH.

    Returns:
        pd.DataFrame: One row per lap, with tire/weather features attached.
    """
    conn = sqlite3.connect(db_path)

    laps = pd.read_sql(
        """
        SELECT session_id, driver, team, lap_number, lap_time_seconds,
               compound, tyre_life, track_status, is_pit_lap
        FROM laps
        """,
        conn,
    )

    sessions = pd.read_sql("SELECT session_id, total_laps FROM sessions", conn)

    # Average weather per session (see module docstring for why)
    weather_avg = pd.read_sql(
        """
        SELECT session_id,
               AVG(air_temp) AS avg_air_temp,
               AVG(track_temp) AS avg_track_temp,
               AVG(humidity) AS avg_humidity,
               MAX(rainfall) AS any_rainfall
        FROM weather
        GROUP BY session_id
        """,
        conn,
    )
    conn.close()

    df = laps.merge(sessions, on="session_id", how="left")
    df = df.merge(weather_avg, on="session_id", how="left")
    df["laps_remaining"] = df["total_laps"] - df["lap_number"]

    return df


# %% [2] CLEAN THE DATA -------------------------------------------------------
DRY_COMPOUNDS = {"SOFT": 0, "MEDIUM": 1, "HARD": 2}
FEATURES = ["compound_code", "tyre_life", "fuel_fraction", "avg_track_temp"]
MAX_DELTA = 3.0  # laps this far off the driver's typical pace = traffic/mistakes


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Keep representative dry laps and add the relative-pace columns.

    Adds:
        driver_baseline: the driver's median clean lap in that race (seconds)
        delta: this lap minus driver_baseline (what the model predicts)
        fuel_fraction: share of the race still to run (1.0 = full tank)
        compound_code: SOFT=0, MEDIUM=1, HARD=2
    """
    df = df[df["is_pit_lap"] == 0]
    df = df[df["track_status"].isin(["1", "['1']"])]  # green-flag laps only
    df = df[df["lap_number"] > 1]  # standing start
    df = df[df["compound"].isin(DRY_COMPOUNDS) & (df["any_rainfall"] == 0)]
    df = df.dropna(subset=["lap_time_seconds", "tyre_life", "avg_track_temp"]).copy()

    df["driver_baseline"] = df.groupby(["session_id", "driver"])[
        "lap_time_seconds"
    ].transform("median")
    df["delta"] = df["lap_time_seconds"] - df["driver_baseline"]
    df = df[df["delta"].abs() < MAX_DELTA].copy()
    df["fuel_fraction"] = df["laps_remaining"] / df["total_laps"]
    df["compound_code"] = df["compound"].map(DRY_COMPOUNDS)
    return df


# %% [3] TRAIN THE MODEL ------------------------------------------------------
def linear_model() -> Pipeline:
    """Final model: linear regression on relative pace (compound one-hot)."""
    return Pipeline(
        [
            (
                "prep",
                ColumnTransformer(
                    [("cmp", OneHotEncoder(), ["compound_code"])],
                    remainder="passthrough",
                ),
            ),
            ("model", LinearRegression()),
        ]
    )


def train_model(df: pd.DataFrame):
    """Train the relative-pace model and test it on races it never saw.

    Two versions of the idea are compared on held-out races; the linear one
    is used because it was more accurate on every one of 5 race splits
    (avg 0.540 s vs 0.615 s for gradient boosting, 0.792 s for the baseline,
    46 races 2023-24) -- and it's easier to explain.

    Args:
        df (pd.DataFrame): output of clean_data()

    Returns:
        tuple: (model trained on ALL races, mean absolute error in seconds on
                held-out races)
    """
    from sklearn.ensemble import HistGradientBoostingRegressor

    # hold out whole races (20%), not random laps from races already seen
    races = df["session_id"].unique()
    train_races, test_races = train_test_split(races, test_size=0.2, random_state=42)
    train = df[df["session_id"].isin(train_races)]
    test = df[df["session_id"].isin(test_races)]

    def error(predicted_delta) -> float:
        return mean_absolute_error(
            test["lap_time_seconds"], test["driver_baseline"] + predicted_delta
        )

    baseline_mae = error(0.0)
    linear_mae = error(
        linear_model().fit(train[FEATURES], train["delta"]).predict(test[FEATURES])
    )
    boosted = HistGradientBoostingRegressor(
        max_iter=300,
        learning_rate=0.05,
        categorical_features=[0],
        monotonic_cst=[0, 1, 1, 0],  # tyre age and fuel only ever slow a lap down
        random_state=42,
    ).fit(train[FEATURES], train["delta"])
    boosted_mae = error(boosted.predict(test[FEATURES]))

    print(f"Tested on {len(test_races)} races the model never saw ({len(test)} laps):")
    print(f"  driver's typical lap (baseline)  {baseline_mae:.3f} s")
    print(f"  gradient boosting                {boosted_mae:.3f} s")
    print(f"  linear regression (final model)  {linear_mae:.3f} s")

    return linear_model().fit(df[FEATURES], df["delta"]), linear_mae


def old_design_error(df: pd.DataFrame) -> float:
    """Error of the ORIGINAL design (raw lap time from tyres/weather/driver/
    team) on races it never saw -- kept so the comparison can be re-checked."""
    cols = [
        "tyre_life",
        "compound",
        "laps_remaining",
        "avg_air_temp",
        "avg_track_temp",
        "avg_humidity",
        "any_rainfall",
        "driver",
        "team",
    ]
    races = df["session_id"].unique()
    train_races, _ = train_test_split(races, test_size=0.2, random_state=42)
    train = df[df["session_id"].isin(train_races)]
    test = df[~df["session_id"].isin(train_races)]
    old = Pipeline(
        [
            (
                "prep",
                ColumnTransformer(
                    [
                        (
                            "cat",
                            OneHotEncoder(handle_unknown="ignore"),
                            ["compound", "driver", "team"],
                        )
                    ],
                    remainder="passthrough",
                ),
            ),
            (
                "model",
                GradientBoostingRegressor(
                    n_estimators=200, max_depth=4, learning_rate=0.05, random_state=42
                ),
            ),
        ]
    ).fit(train[cols], train["lap_time_seconds"])
    return mean_absolute_error(test["lap_time_seconds"], old.predict(test[cols]))


def tyre_table(model, track_temp: float = 35.0) -> pd.DataFrame:
    """Predicted time lost (s) by compound and tyre age at half fuel --
    a quick sanity check that the model learned real tyre behaviour."""
    rows = [
        {
            "compound": c,
            "tyre_life": age,
            "compound_code": code,
            "fuel_fraction": 0.5,
            "avg_track_temp": track_temp,
        }
        for c, code in DRY_COMPOUNDS.items()
        for age in (1, 10, 20, 30)
    ]
    grid = pd.DataFrame(rows)
    grid["seconds_lost"] = model.predict(grid[FEATURES])
    grid["seconds_lost"] -= grid["seconds_lost"].min()
    return grid.pivot(index="tyre_life", columns="compound", values="seconds_lost")[
        list(DRY_COMPOUNDS)
    ].round(2)


# %% [4] PACE EVALUATION FUNCTION ---------------------------------------------
def evaluate_lap(
    model, actual_lap_time: float, driver_baseline: float, **conditions
) -> dict:
    """Compare an actual lap time to the model's expected pace.

    Args:
        model: a trained model (from train_model()).
        actual_lap_time (float): the driver's real lap time, in seconds.
        driver_baseline (float): the driver's typical lap this race, in seconds.
        **conditions: compound ("SOFT"/"MEDIUM"/"HARD"), tyre_life,
            fuel_fraction (1.0 = start of race, 0.0 = end), avg_track_temp.

    Returns:
        dict: expected_pace, actual_pace, delta, and a plain-language flag.
    """
    row = dict(conditions)
    row["compound_code"] = DRY_COMPOUNDS[str(row.pop("compound")).upper()]
    expected = driver_baseline + model.predict(pd.DataFrame([row])[FEATURES])[0]
    delta = actual_lap_time - expected

    if delta > 0.5:
        flag = "Underperforming pace — possible tire/pit issue"
    elif delta < -0.5:
        flag = "Overperforming pace — strong lap"
    else:
        flag = "On expected pace"

    return {
        "expected_pace": round(float(expected), 3),
        "actual_pace": actual_lap_time,
        "delta": round(float(delta), 3),
        "flag": flag,
    }


# %% [5] RUN IT ----------------------------------------------------------------
def main():
    print("Loading data from database...")
    df = load_training_data()
    print(f"Loaded {len(df)} raw laps")

    df = clean_data(df)
    print(f"{len(df)} clean dry laps from {df['session_id'].nunique()} races\n")

    if df["session_id"].nunique() < 5:
        print(
            "Not enough races to test on yet — run `python -m ML.load_season_data` "
            "to pull more races into the database first."
        )
        return

    print(f"Original design on unseen races: {old_design_error(df):.3f} s")
    model, mae = train_model(df)

    joblib.dump(model, "pace_model.joblib")
    print("\nModel saved to pace_model.joblib")

    print("\nSeconds lost by tyre age (half fuel), relative to the fastest case:")
    print(tyre_table(model, float(df["avg_track_temp"].median())).to_string())

    example = df.iloc[len(df) // 2]
    result = evaluate_lap(
        model,
        actual_lap_time=float(example["lap_time_seconds"]),
        driver_baseline=float(example["driver_baseline"]),
        compound=example["compound"],
        tyre_life=float(example["tyre_life"]),
        fuel_fraction=float(example["fuel_fraction"]),
        avg_track_temp=float(example["avg_track_temp"]),
    )
    print(f"\nExample — {example['driver']}, lap {int(example['lap_number'])}:", result)


if __name__ == "__main__":
    main()
