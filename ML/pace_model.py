"""
Ghost Racer — Lap Time Prediction Model

Reads race data out of the local database (built by Services/database.py)
instead of calling the FastF1 API directly, and trains a model that
predicts a driver's expected lap time given tire age, tire compound, and
weather conditions. Comparing a real lap time to this prediction is what
flags a driver as over/under-performing their expected pace.

ASSUMPTION / SIMPLIFICATION (flagged for the team):
The `laps` table doesn't store an absolute elapsed-time-into-race value,
so we can't precisely match a lap to the exact weather sample at that
moment. Instead, each lap is joined to its session's AVERAGE weather
conditions (temp, humidity, whether it rained at all during the race).
This is fine for a first model — weather is usually fairly stable within
a race — but a dedicated timestamp on laps would let us do this more
precisely later.
"""

import sqlite3
import pandas as pd
import numpy as np
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
def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Remove laps that aren't representative of normal racing pace.

    Args:
        df (pd.DataFrame): Raw joined lap data from load_training_data().

    Returns:
        pd.DataFrame: Cleaned data ready for feature/target split.
    """
    df = df[df["is_pit_lap"] == 0]
    df = df[df["track_status"].isin(["1", "['1']"])]  # green-flag laps only
    df = df.dropna(subset=["lap_time_seconds"])

    median_lap = df["lap_time_seconds"].median()
    df = df[df["lap_time_seconds"] < median_lap * 1.5]
    df = df.dropna(subset=["tyre_life", "compound", "avg_air_temp", "avg_track_temp"])

    return df


# %% [3] TRAIN THE MODEL ------------------------------------------------------
def train_model(df: pd.DataFrame):
    """Train and compare a linear regression baseline against gradient
    boosting, returning whichever performs better.

    Args:
        df (pd.DataFrame): Cleaned training data from clean_data().

    Returns:
        tuple: (best_model_pipeline, mae_of_best_model)
    """
    feature_cols = [
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
    target_col = "lap_time_seconds"

    X = df[feature_cols]
    y = df[target_col]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    categorical_cols = ["compound", "driver", "team"]
    preprocessor = ColumnTransformer(
        [("cat", OneHotEncoder(handle_unknown="ignore"), categorical_cols)],
        remainder="passthrough",
    )

    linear_pipeline = Pipeline([("prep", preprocessor), ("model", LinearRegression())])
    linear_pipeline.fit(X_train, y_train)
    linear_mae = mean_absolute_error(y_test, linear_pipeline.predict(X_test))
    print(f"Linear Regression MAE: {linear_mae:.3f} seconds")

    gb_pipeline = Pipeline(
        [
            ("prep", preprocessor),
            (
                "model",
                GradientBoostingRegressor(
                    n_estimators=200, max_depth=4, learning_rate=0.05, random_state=42
                ),
            ),
        ]
    )
    gb_pipeline.fit(X_train, y_train)
    gb_mae = mean_absolute_error(y_test, gb_pipeline.predict(X_test))
    print(f"Gradient Boosting MAE: {gb_mae:.3f} seconds")

    if gb_mae < linear_mae:
        print("Using Gradient Boosting as the final model")
        return gb_pipeline, gb_mae
    print("Using Linear Regression as the final model")
    return linear_pipeline, linear_mae


# %% [4] PACE EVALUATION FUNCTION ---------------------------------------------
def evaluate_lap(model, actual_lap_time: float, **conditions) -> dict:
    """Compare an actual lap time to the model's expected pace.

    Args:
        model: A trained pipeline (from train_model()).
        actual_lap_time (float): The driver's real lap time, in seconds.
        **conditions: tyre_life, compound, laps_remaining, avg_air_temp,
            avg_track_temp, avg_humidity, any_rainfall, driver, team.

    Returns:
        dict: expected_pace, actual_pace, delta, and a plain-language flag.
    """
    input_df = pd.DataFrame([conditions])
    expected = model.predict(input_df)[0]
    delta = actual_lap_time - expected

    if delta > 0.5:
        flag = "Underperforming pace — possible tire/pit issue"
    elif delta < -0.5:
        flag = "Overperforming pace — strong lap"
    else:
        flag = "On expected pace"

    return {
        "expected_pace": round(expected, 3),
        "actual_pace": actual_lap_time,
        "delta": round(delta, 3),
        "flag": flag,
    }


# %% [5] RUN IT ----------------------------------------------------------------
def main():
    print("Loading data from database...")
    df = load_training_data()
    print(f"Loaded {len(df)} raw laps")

    df = clean_data(df)
    print(f"{len(df)} laps remain after cleaning")

    if len(df) < 50:
        print(
            "Not much data to train on yet — run load_training_data.py "
            "to pull more races into the database first."
        )
        return

    model, mae = train_model(df)

    joblib.dump(model, "pace_model.joblib")
    print("Model saved to pace_model.joblib")

    example = df.iloc[0]
    result = evaluate_lap(
        model,
        actual_lap_time=example["lap_time_seconds"],
        tyre_life=example["tyre_life"],
        compound=example["compound"],
        laps_remaining=example["laps_remaining"],
        avg_air_temp=example["avg_air_temp"],
        avg_track_temp=example["avg_track_temp"],
        avg_humidity=example["avg_humidity"],
        any_rainfall=example["any_rainfall"],
        driver=example["driver"],
        team=example["team"],
    )
    print("\nExample evaluation:", result)


if __name__ == "__main__":
    main()
