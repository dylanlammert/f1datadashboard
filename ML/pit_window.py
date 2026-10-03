"""
Ghost Racer — Pit Stop Window Estimator  (GitHub issue #25)

"Develop a function to estimate when a driver will need to go for a pit stop."

HOW IT WORKS
1. Tyre-wear model (a regression trained on the race's lap data):
     corrected_lap_time = driver_pace + compound_offset
                         + a[compound] x tyre_age + b[compound] x tyre_age^2
   (the squared term lets tyres fall off faster late in a stint)
   - "corrected" = fuel effect removed first. A car starts with ~110 kg of
     fuel and each 10 kg costs ~0.3 s/lap (numbers from our team doc), so
     early laps are slower because of fuel, not tyres. Without removing it,
     fuel burn hides tyre wear.
   - Only clean laps are used: green flag, no pit in/out, no lap 1, dry tyres.
2. Pit stop cost is measured from real stops at that track:
     (in-lap + out-lap) - 2 x the driver's normal lap.
3. A planner (dynamic programming) tries every combination of pit laps
   and compounds for the rest of the race — 1, 2 or 3 more stops — adding
   laps on each set of tyres + the pit stop cost. The cheapest plan wins,
   and its first stop is the recommendation.

WHY NOT ML/pace_model.py?
We tested it: it predicts the same time for SOFT, MEDIUM and HARD and almost
no slowdown as tyres age. It mostly learned which track/driver a lap belongs
to (which is how it gets 0.61 s error). So this file fits its own tyre model.

LIMITATIONS (flagged for the team):
- Dry races only (SOFT / MEDIUM / HARD).
- Doesn't plan around safety cars / undercuts / traffic.
- Tyre wear is learned from the whole race (like a team using practice data
  from that weekend). The backtest leaves the tested driver out.
- Compounds with fewer than 60 clean laps in a race aren't modelled.

RESULTS (6 races from 2023 in our DB, 60 real green-flag first stops):
median error 4 laps, 53% within 5 laps -- about the same as copying the
average stop lap of the other drivers. Best in Bahrain (median 3 laps) and
Miami (6.1 vs 10.3 laps for the copy-the-field guess), worst in Spain,
where teams stopped early for reasons tyre wear alone doesn't explain.
"""

import sqlite3

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from Services.dbhandler import DB_PATH

DRY_COMPOUNDS = ("SOFT", "MEDIUM", "HARD")
GREEN_FLAG = ("1", "['1']")
MIN_COMPOUND_LAPS = 60  # need this many clean laps on a compound to trust its wear
MAX_STOPS = 3  # most stops the planner will consider
DEFAULT_PIT_LOSS = 22.0  # seconds, only used if a race has no usable pit stops
FUEL_START_KG = 110.0  # from the team doc: cars get ~110 kg per race
SECONDS_PER_KG = 0.03  # from the team doc: ~10 kg = 0.3 s of pace


# %% [1] LOAD ONE RACE FROM THE DATABASE -----------------------------------------
def load_race_laps(session_id: int, db_path: str = DB_PATH) -> pd.DataFrame:
    """All laps of one race, with total_laps and whether it rained."""
    conn = sqlite3.connect(db_path)
    laps = pd.read_sql(
        """
        SELECT l.driver, l.lap_number, l.lap_time_seconds, l.compound,
               l.tyre_life, l.track_status, l.is_pit_lap, s.total_laps
        FROM laps l JOIN sessions s ON s.session_id = l.session_id
        WHERE l.session_id = ?
        ORDER BY l.driver, l.lap_number
        """,
        conn,
        params=(int(session_id),),
    )
    rain = conn.execute(
        "SELECT MAX(rainfall) FROM weather WHERE session_id = ?", (int(session_id),)
    ).fetchone()[0]
    conn.close()
    if laps.empty:
        raise ValueError(f"no laps for session_id {session_id} in the database")
    laps.attrs["any_rainfall"] = bool(rain)
    return laps


# %% [2] TYRE-WEAR MODEL --------------------------------------------------------
def fuel_corrected(laps: pd.DataFrame) -> pd.Series:
    """Lap time with the effect of fuel weight taken out."""
    fuel_kg = (
        FUEL_START_KG * (laps["total_laps"] - laps["lap_number"]) / laps["total_laps"]
    )
    return laps["lap_time_seconds"] - SECONDS_PER_KG * fuel_kg


def clean_stint_laps(laps: pd.DataFrame) -> pd.DataFrame:
    """Keep only laps that show real tyre performance."""
    d = (
        laps[
            (laps["is_pit_lap"] == 0)
            & (laps["track_status"].isin(GREEN_FLAG))
            & (laps["lap_number"] > 1)
            & (laps["compound"].isin(DRY_COMPOUNDS))
        ]
        .dropna(subset=["lap_time_seconds", "tyre_life"])
        .copy()
    )
    d["corrected"] = fuel_corrected(d)
    # drop traffic / mistakes: anything 3 s slower than the driver's usual lap
    d = d[d["corrected"] < d.groupby("driver")["corrected"].transform("median") + 3]
    return d


class TyreModel:
    """corrected_lap = driver_pace + compound_offset + a[c]*age + b[c]*age^2"""

    def fit(self, stint_laps: pd.DataFrame) -> "TyreModel":
        # a compound barely used in this race (e.g. 8 laps) gives nonsense wear
        # numbers, so we only model compounds with enough clean laps
        counts = stint_laps["compound"].value_counts()
        self.compounds = sorted(counts[counts >= MIN_COMPOUND_LAPS].index)
        stint_laps = stint_laps[stint_laps["compound"].isin(self.compounds)]
        X = self._features(stint_laps, drivers=sorted(stint_laps["driver"].unique()))
        self.reg = LinearRegression().fit(X, stint_laps["corrected"])
        coefs = dict(zip(X.columns, self.reg.coef_))
        self.lin = {c: coefs[f"age_{c}"] for c in self.compounds}
        self.quad = {
            c: max(0.0, coefs[f"age2_{c}"]) for c in self.compounds
        }  # wear can only speed up
        self.offset = {c: coefs.get(f"is_{c}", 0.0) for c in self.compounds}
        self.max_age = int(stint_laps["tyre_life"].max())
        # average wear per lap over a typical 20-lap stint (for display)
        self.wear_rate = {
            c: float(np.diff(self.lap_cost(c, [1, 21]))[0] / 20) for c in self.compounds
        }
        return self

    def _features(self, d: pd.DataFrame, drivers: list) -> pd.DataFrame:
        self.drivers = drivers
        X = pd.DataFrame(index=d.index)
        for drv in drivers[1:]:  # first driver = baseline
            X[f"drv_{drv}"] = (d["driver"] == drv).astype(float)
        for c in self.compounds:
            if c != self.compounds[0]:  # first compound = baseline
                X[f"is_{c}"] = (d["compound"] == c).astype(float)
            X[f"age_{c}"] = np.where(d["compound"] == c, d["tyre_life"], 0.0)
            X[f"age2_{c}"] = np.where(d["compound"] == c, d["tyre_life"] ** 2, 0.0)
        return X

    def lap_cost(self, compound: str, age) -> np.ndarray:
        """Seconds a lap costs on this compound at this tyre age (relative —
        driver pace and fuel are the same for every strategy, so they cancel)."""
        age = np.asarray(age, dtype=float)
        grid = np.arange(
            0, max(self.max_age, int(age.max()) if age.size else 0) + 2, dtype=float
        )
        curve = self.lin[compound] * grid + self.quad[compound] * grid**2
        curve = np.maximum.accumulate(curve)  # tyres never get faster with age
        return self.offset[compound] + np.interp(age, grid, curve)


# %% [3] PIT STOP COST ------------------------------------------------------------
def estimate_pit_loss(laps: pd.DataFrame) -> float:
    """Median time lost to a green-flag pit stop at this track, from real stops."""
    typical = (
        laps[(laps["is_pit_lap"] == 0) & (laps["track_status"].isin(GREEN_FLAG))]
        .groupby("driver")["lap_time_seconds"]
        .median()
    )
    losses = []
    for driver, d in laps.groupby("driver"):
        d = d.set_index("lap_number")
        for out_lap in d[(d["is_pit_lap"] == 1) & (d["tyre_life"] == 1)].index:
            in_lap = out_lap - 1
            if out_lap <= 1 or in_lap not in d.index or driver not in typical:
                continue
            both = d.loc[[in_lap, out_lap]]
            if (
                both["lap_time_seconds"].isna().any()
                or not both["track_status"].isin(GREEN_FLAG).all()
            ):
                continue
            losses.append(both["lap_time_seconds"].sum() - 2 * typical[driver])
    losses = [x for x in losses if 10 < x < 45]  # drop slow stops / bad data
    return float(np.median(losses)) if losses else DEFAULT_PIT_LOSS


# %% [4] THE PIT WINDOW FUNCTION --------------------------------------------------
def recommend_pit_window(
    session_id: int,
    driver: str,
    current_lap: int,
    compound: str,
    tyre_life: int,
    must_change_compound: bool = True,
    db_path: str = DB_PATH,
    tyre_model: TyreModel | None = None,
    pit_loss: float | None = None,
) -> dict:
    """Recommend the best lap for a driver's next pit stop.

    Args:
        session_id (int): which race (sessions.session_id)
        driver (str): 3-letter driver code, e.g. "VER"
        current_lap (int): the lap the driver has just completed
        compound (str): tyre they're on now: SOFT / MEDIUM / HARD
        tyre_life (int): how many laps old those tyres are
        must_change_compound (bool): F1 rule — in a dry race every driver must
            use two different compounds. Pass False once they already have.
        tyre_model / pit_loss: pass in to reuse (otherwise built from the DB)

    Returns:
        dict: recommended_pit_lap (None = stay out to the end), laps_until_pit,
              next_compound, full_plan (every planned stop), pit_loss_seconds,
              wear_per_lap, message
    """
    compound = compound.upper()
    if compound not in DRY_COMPOUNDS:
        raise ValueError(f"only dry compounds are supported, got {compound}")

    laps = load_race_laps(session_id, db_path)
    total_laps = int(laps["total_laps"].iloc[0])
    if tyre_model is None:
        tyre_model = TyreModel().fit(clean_stint_laps(laps))
    if pit_loss is None:
        pit_loss = estimate_pit_loss(laps)
    if compound not in tyre_model.compounds:
        raise ValueError(
            f"not enough {compound} laps in this race to learn its tyre wear"
        )

    n = total_laps - current_lap  # laps left to drive
    if n < 2:
        return _result(
            None,
            current_lap,
            None,
            pit_loss,
            tyre_model,
            compound,
            [],
            "Race is nearly over — no stop needed",
        )

    # cost of staying out on the current tyres for 1..n more laps
    stay_cum = np.concatenate(
        [
            [0.0],
            np.cumsum(tyre_model.lap_cost(compound, tyre_life + np.arange(1, n + 1))),
        ]
    )
    # cost of a fresh stint of length L on each compound
    fresh_cum = {
        c: np.concatenate(
            [[0.0], np.cumsum(tyre_model.lap_cost(c, np.arange(1, n + 1)))]
        )
        for c in tyre_model.compounds
    }

    # Dynamic programming: best[s][m][ch] = cheapest way to drive the last m laps
    # using at most s more stops, where ch = "already used a 2nd compound".
    INF = float("inf")
    best = [
        [[0.0 if (m == 0 and ch) else INF for ch in (0, 1)] for m in range(n + 1)]
        for _ in range(MAX_STOPS + 1)
    ]
    choice = [[[None, None] for _ in range(n + 1)] for _ in range(MAX_STOPS + 1)]
    for s_left in range(1, MAX_STOPS + 1):
        for m in range(1, n + 1):
            for ch in (0, 1):
                for c in tyre_model.compounds:
                    ch2 = 1 if (ch or c != compound) else 0
                    for L in range(1, m + 1):  # pit now, run L laps on c, then the rest
                        cost = pit_loss + fresh_cum[c][L] + best[s_left - 1][m - L][ch2]
                        if cost < best[s_left][m][ch]:
                            best[s_left][m][ch] = cost
                            choice[s_left][m][ch] = (c, L, ch2)
                best[s_left][m][ch] = (
                    min(best[s_left][m][ch], best[s_left - 1][m][ch])
                    if choice[s_left][m][ch] is None
                    else best[s_left][m][ch]
                )

    ch0 = 0 if must_change_compound else 1
    options = []  # (total, laps to stay out k)
    for k in range(1, n + 1):
        rest = (
            0.0 if k == n and ch0 else (INF if k == n else best[MAX_STOPS][n - k][ch0])
        )
        options.append((stay_cum[k] + rest, k))
    total, k = min(options)
    if total == INF or k == n:
        return _result(
            None,
            current_lap,
            None,
            pit_loss,
            tyre_model,
            compound,
            [],
            "Stay out — no more stops needed",
        )

    # rebuild the full plan from the DP choices
    plan, lap, m, ch, s_left = [], current_lap + k, n - k, ch0, MAX_STOPS
    while m > 0:
        c, L, ch = choice[s_left][m][ch]
        plan.append({"pit_lap": lap, "compound": c, "stint_laps": L})
        lap, m, s_left = lap + L, m - L, s_left - 1

    pit_lap, new_c = plan[0]["pit_lap"], plan[0]["compound"]
    laps_until = pit_lap - current_lap
    stops = f"{len(plan)}-stop plan"
    if laps_until <= 1:
        msg = f"BOX NOW — pit this lap for {new_c} ({stops})"
    elif laps_until <= 3:
        msg = f"Pit window open — box in {laps_until} laps (lap {pit_lap}) for {new_c} ({stops})"
    else:
        msg = f"Stay out — best pit lap is {pit_lap} (in {laps_until} laps) for {new_c} ({stops})"
    return _result(
        pit_lap, current_lap, new_c, pit_loss, tyre_model, compound, plan, msg
    )


def _result(pit_lap, current_lap, new_c, pit_loss, model, compound, plan, msg) -> dict:
    return {
        "recommended_pit_lap": pit_lap,
        "laps_until_pit": None if pit_lap is None else pit_lap - current_lap,
        "next_compound": new_c,
        "full_plan": plan,
        "pit_loss_seconds": round(pit_loss, 2),
        "wear_per_lap": round(model.wear_rate.get(compound, 0.0), 3),
        "message": msg,
    }


# %% [5] CHECK IT AGAINST REAL PIT STOPS ------------------------------------------
def backtest(db_path: str = DB_PATH, check_lap: int = 5) -> pd.DataFrame:
    """Ask at `check_lap` when each driver should make their FIRST stop, and
    compare with when they really did. The tyre model is re-fit WITHOUT the
    driver being tested (leave-one-driver-out), so it never sees their answer.
    Stops made under yellow/SC/VSC/red are skipped (those aren't wear-based).
    """
    conn = sqlite3.connect(db_path)
    session_ids = [
        r[0]
        for r in conn.execute("SELECT session_id FROM sessions ORDER BY session_id")
    ]
    conn.close()

    rows = []
    for sid in session_ids:
        laps = load_race_laps(sid, db_path)
        if laps.attrs["any_rainfall"]:
            print(f"session {sid}: skipped (rain during race)")
            continue
        stint_laps = clean_stint_laps(laps)
        pit_loss = estimate_pit_loss(laps)

        for driver, d in laps.groupby("driver"):
            d = d.set_index("lap_number")
            if check_lap not in d.index:
                continue
            start = d.loc[check_lap]
            if start["compound"] not in DRY_COMPOUNDS or pd.isna(start["tyre_life"]):
                continue
            outs = d[
                (d["is_pit_lap"] == 1) & (d["tyre_life"] == 1) & (d.index > check_lap)
            ].index
            if len(outs) == 0:
                continue
            actual = int(outs[0]) - 1
            if (
                not d.loc[actual - 1 : actual + 1, "track_status"]
                .isin(GREEN_FLAG)
                .all()
            ):
                continue
            model = TyreModel().fit(stint_laps[stint_laps["driver"] != driver])
            if start["compound"] not in model.compounds:
                continue
            rec = recommend_pit_window(
                sid,
                driver,
                check_lap,
                start["compound"],
                int(start["tyre_life"]),
                db_path=db_path,
                tyre_model=model,
                pit_loss=pit_loss,
            )
            if rec["recommended_pit_lap"] is None:
                continue
            rows.append(
                {
                    "session_id": sid,
                    "driver": driver,
                    "tyre": start["compound"],
                    "actual_pit_lap": actual,
                    "predicted_pit_lap": rec["recommended_pit_lap"],
                    "error_laps": rec["recommended_pit_lap"] - actual,
                }
            )
    return pd.DataFrame(rows)


def baseline_error(results: pd.DataFrame) -> float:
    """Simple comparison: guess the average first-stop lap of the OTHER drivers
    in that race (so the baseline doesn't see the answer either)."""
    g = results.groupby("session_id")["actual_pit_lap"]
    other_mean = (g.transform("sum") - results["actual_pit_lap"]) / (
        g.transform("count") - 1
    )
    return float((other_mean.round() - results["actual_pit_lap"]).abs().mean())


# %% [6] RUN IT --------------------------------------------------------------------
def main():
    laps = load_race_laps(1)
    model = TyreModel().fit(clean_stint_laps(laps))
    print(
        "2023 Bahrain — tyre wear learned from the data (seconds lost per lap of tyre age):"
    )
    for c in model.compounds:
        print(
            f"  {c:<7} wear {model.wear_rate[c]:.3f} s/lap | pace vs {model.compounds[0]}: {model.offset[c]:+.2f} s"
        )
    print(f"  pit stop cost: {estimate_pit_loss(laps):.1f} s\n")

    example = recommend_pit_window(
        session_id=1, driver="VER", current_lap=5, compound="SOFT", tyre_life=8
    )
    print("Example — VER, lap 5, 8-lap-old softs:")
    for k, v in example.items():
        print(f"  {k}: {v}")

    print("\nBacktest vs real first stops (leave-one-driver-out):")
    results = backtest()
    print(results.to_string(index=False))
    err = results["error_laps"].abs()
    print(f"\nDrivers tested: {len(results)}")
    print(
        f"Average error: {err.mean():.1f} laps | within 3 laps: {(err <= 3).mean():.0%}"
        f" | within 5 laps: {(err <= 5).mean():.0%}"
    )
    print(
        f"Baseline (guess the race's average stop lap): {baseline_error(results):.1f} laps"
    )


if __name__ == "__main__":
    main()
