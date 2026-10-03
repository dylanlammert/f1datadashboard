"""
Ghost Racer — Race Outcome Prediction  (GitHub issue #42)

"Develop a way to predict race outcomes."

Predicts the finishing order of a race from information known BEFORE the
lights go out:

    grid_position        where the driver starts (pit-lane start = back)
    driver_form          the driver's average finish over their last 5 races
    team_form            the team's average finish over its last 5 races (both cars)
    driver_gain          how many places the driver usually gains/loses vs. grid
    driver_dnf_rate      how often the driver retired in their last 10 races

All "form" features use ONLY races that happened earlier, so the model never
sees the result it is predicting.

The model starts from the grid and predicts how many places each driver will
GAIN or LOSE (a ridge regression on the features above):

    predicted finish = grid position + predicted change

Drivers are then sorted by that to give a predicted finishing order.

WHY THIS DESIGN: grid order alone is a very strong predictor in F1. Predicting
finishing position directly (we tried gradient boosting) over-trusted past
form and did WORSE than plain grid order. Predicting the change from the grid
keeps the grid as the anchor and only adjusts it. The design was chosen using
late-2023 races only, then tested on 2024.

HONEST TESTING (walk-forward):
For every 2024 race, the model is trained only on races before it and then
predicts it -- exactly how it would be used before a real race. It is compared
with the simple guess "everyone finishes where they started" (grid order).

Run from the project root:
    python -m ML.race_outcome            # backtest on 2024 + example prediction
"""

import sqlite3

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

from Services.database import DB_PATH

FEATURES = [
    "grid_position",
    "driver_form",
    "team_form",
    "driver_gain",
    "driver_dnf_rate",
]
FORM_RACES = 5  # how many past races "form" looks at
DNF_RACES = 10
MIN_TRAIN_RACES = 10  # don't predict until we've seen this many races

# teams that were renamed between seasons -- treat as the same team
TEAM_ALIASES = {"AlphaTauri": "RB", "Alfa Romeo": "Kick Sauber"}
FINISHED = {"Finished", "Lapped"}


# %% [1] LOAD RESULTS ---------------------------------------------------------
def race_order(conn: sqlite3.Connection) -> pd.DataFrame:
    """Every race in the database with its real calendar date/round.

    session_id order isn't reliable (races can be loaded in any order), so the
    round comes from FastF1's season calendar (cached after first use).
    """
    import fastf1

    sessions = pd.read_sql(
        "SELECT session_id, year, event_name FROM sessions WHERE session_type = 'Race'",
        conn,
    )
    calendars = []
    for year in sessions["year"].unique():
        schedule = fastf1.get_event_schedule(int(year), include_testing=False)
        calendars.append(
            pd.DataFrame(
                {
                    "year": int(year),
                    "event_name": schedule["EventName"],
                    "round": schedule["RoundNumber"].astype(int),
                    "date": pd.to_datetime(schedule["EventDate"]),
                }
            )
        )
    calendar = pd.concat(calendars, ignore_index=True)
    races = sessions.merge(calendar, on=["year", "event_name"], how="left")
    missing = races[races["date"].isna()]
    if len(missing):
        print("warning: no calendar date for", missing["event_name"].tolist())
    return races.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)


def load_results(db_path: str = DB_PATH) -> pd.DataFrame:
    """One row per driver per race, in calendar order, with the features."""
    conn = sqlite3.connect(db_path)
    races = race_order(conn)
    results = pd.read_sql(
        """
        SELECT r.session_id, r.driver_code, r.grid_position, r.finish_position,
               r.classified_position, r.status, d.team, d.full_name
        FROM results r
        JOIN drivers d ON d.session_id = r.session_id AND d.driver_code = r.driver_code
        """,
        conn,
    )
    conn.close()

    df = results.merge(races, on="session_id")
    # a driver who withdrew before the start never raced -- nothing to predict
    df = df[df["status"] != "Withdrew"].dropna(subset=["finish_position"])
    df["team"] = df["team"].replace(TEAM_ALIASES)
    field = df.groupby("session_id")["driver_code"].transform("count")
    # grid 0 / missing = pit-lane start = back of the grid
    df["grid_position"] = df["grid_position"].where(df["grid_position"] > 0, field)
    df["finish_position"] = df["finish_position"].astype(float)
    df["dnf"] = (~df["status"].isin(FINISHED)).astype(float)
    df["race_index"] = df["date"].rank(method="dense").astype(int)  # 1 = first race
    df = df.sort_values(["race_index", "finish_position"]).reset_index(drop=True)
    return add_form_features(df)


# %% [2] FORM FEATURES (past races only) -------------------------------------
def add_form_features(df: pd.DataFrame) -> pd.DataFrame:
    """Rolling averages over each driver's/team's PREVIOUS races.

    shift(1) is what keeps this honest: a race's own result is never used to
    describe the driver going into that race.
    """
    df = df.sort_values(["race_index"]).copy()
    by_driver = df.groupby("driver_code")
    df["driver_form"] = by_driver["finish_position"].transform(
        lambda s: s.shift(1).rolling(FORM_RACES, min_periods=1).mean()
    )
    df["gain"] = df["grid_position"] - df["finish_position"]
    df["driver_gain"] = by_driver["gain"].transform(
        lambda s: s.shift(1).rolling(FORM_RACES, min_periods=1).mean()
    )
    df["driver_dnf_rate"] = by_driver["dnf"].transform(
        lambda s: s.shift(1).rolling(DNF_RACES, min_periods=1).mean()
    )

    # team form: average finish of both cars per race, then rolled over races
    team_race = (
        df.groupby(["team", "race_index"])["finish_position"].mean().reset_index()
    )
    team_race["team_form"] = team_race.groupby("team")["finish_position"].transform(
        lambda s: s.shift(1).rolling(FORM_RACES, min_periods=1).mean()
    )
    df = df.merge(
        team_race[["team", "race_index", "team_form"]], on=["team", "race_index"]
    )

    # a driver/team's very first race has no history: fall back to neutral values
    mid_field = df.groupby("session_id")["driver_code"].transform("count") / 2
    df["driver_form"] = df["driver_form"].fillna(df["team_form"]).fillna(mid_field)
    df["team_form"] = df["team_form"].fillna(df["driver_form"])
    df["driver_gain"] = df["driver_gain"].fillna(0.0)
    df["driver_dnf_rate"] = df["driver_dnf_rate"].fillna(df["dnf"].mean())
    return df.sort_values(["race_index", "finish_position"]).reset_index(drop=True)


# %% [3] MODEL --------------------------------------------------------------------
def train(history: pd.DataFrame) -> Ridge:
    """Fit: places gained/lost vs. the grid, from the pre-race features."""
    model = Ridge(alpha=10.0)
    model.fit(history[FEATURES], history["finish_position"] - history["grid_position"])
    return model


def predicted_order(model: Ridge, race: pd.DataFrame) -> pd.DataFrame:
    """Predict one race and turn the scores into a finishing order 1..N."""
    race = race.copy()
    race["score"] = race["grid_position"] + model.predict(race[FEATURES])
    # ties broken by grid position
    race = race.sort_values(["score", "grid_position"])
    race["predicted_position"] = np.arange(1, len(race) + 1)
    return race


def explain(model: Ridge) -> pd.Series:
    """Places gained (+) or lost (-) per unit of each feature -- for slides/reports."""
    return pd.Series(-model.coef_, index=FEATURES).round(3)


# %% [4] HONEST BACKTEST ------------------------------------------------------
def backtest(df: pd.DataFrame, test_year: int = 2024) -> pd.DataFrame:
    """Walk forward through test_year: train on everything before each race,
    predict that race, compare with reality and with grid order."""
    rows = []
    for race_index in sorted(df.loc[df["year"] == test_year, "race_index"].unique()):
        history = df[df["race_index"] < race_index]
        if history["race_index"].nunique() < MIN_TRAIN_RACES:
            continue
        race = predicted_order(train(history), df[df["race_index"] == race_index])
        actual = race["finish_position"]
        grid_rank = race["grid_position"].rank(method="first")
        pred_top3 = set(race.nsmallest(3, "predicted_position")["driver_code"])
        grid_top3 = set(race.nsmallest(3, "grid_position")["driver_code"])
        real_top3 = set(race.nsmallest(3, "finish_position")["driver_code"])
        winner = race.loc[actual.idxmin(), "driver_code"]
        rows.append(
            {
                "race": race["event_name"].iloc[0].replace(" Grand Prix", ""),
                "model_mae": (race["predicted_position"] - actual).abs().mean(),
                "grid_mae": (grid_rank - actual).abs().mean(),
                "model_rank_corr": race["predicted_position"].corr(
                    actual, method="spearman"
                ),
                "grid_rank_corr": grid_rank.corr(actual, method="spearman"),
                "model_podium_hits": len(pred_top3 & real_top3),
                "grid_podium_hits": len(grid_top3 & real_top3),
                "model_winner": race.iloc[0]["driver_code"] == winner,
                "grid_winner": race.loc[race["grid_position"].idxmin(), "driver_code"]
                == winner,
            }
        )
    return pd.DataFrame(rows)


# %% [5] FOR THE APP -------------------------------------------------------------
def predict_race(session_id: int, db_path: str = DB_PATH) -> pd.DataFrame:
    """Predicted finishing order for one race, using only earlier races to train.

    Returns:
        DataFrame with driver_code, full_name, team, grid_position,
        predicted_position, and finish_position (the real result, if the race
        has happened -- so the app can show predicted vs. actual).
    """
    df = load_results(db_path)
    race = df[df["session_id"] == session_id]
    if race.empty:
        raise ValueError(f"session {session_id} has no results in the database")
    history = df[df["race_index"] < race["race_index"].iloc[0]]
    if history["race_index"].nunique() < MIN_TRAIN_RACES:
        raise ValueError(
            f"only {history['race_index'].nunique()} earlier races in the database; "
            f"need {MIN_TRAIN_RACES} to predict -- load more with ML.load_season_data"
        )
    out = predicted_order(train(history), race)
    return out[
        [
            "driver_code",
            "full_name",
            "team",
            "grid_position",
            "predicted_position",
            "finish_position",
        ]
    ].reset_index(drop=True)


def main():
    df = load_results()
    print(f"{df['session_id'].nunique()} races, {len(df)} driver results loaded\n")

    results = backtest(df)
    pd.set_option("display.width", 140)
    print("Walk-forward test on 2024 (each race predicted using only earlier races):")
    print(results.round(2).to_string(index=False))
    print("\nAverage over", len(results), "races        model    grid order")
    print(
        f"  position error (lower = better) {results['model_mae'].mean():6.2f}   {results['grid_mae'].mean():6.2f}"
    )
    print(
        f"  rank correlation (higher)       {results['model_rank_corr'].mean():6.2f}   {results['grid_rank_corr'].mean():6.2f}"
    )
    print(
        f"  podium drivers found (of 3)     {results['model_podium_hits'].mean():6.2f}   {results['grid_podium_hits'].mean():6.2f}"
    )
    print(
        f"  winner correct                  {results['model_winner'].mean():6.0%}   {results['grid_winner'].mean():6.0%}"
    )

    print("\nWhat the final model learned (places gained per unit, + = better):")
    print(explain(train(df)).to_string())

    last = df[df["race_index"] == df["race_index"].max()]["session_id"].iloc[0]
    pred = predict_race(int(last))
    print(
        f"\nExample — predicted vs. real top 10, {df[df['session_id'] == last]['event_name'].iloc[0]} {df[df['session_id'] == last]['year'].iloc[0]}:"
    )
    print(pred.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
