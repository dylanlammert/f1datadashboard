
"""Historical pit strategy what-if comparisons for Ghost Racer."""

from functools import lru_cache
from math import inf

import numpy as np
import pandas as pd

from ML.pit_window import (
    DB_PATH,
    DRY_COMPOUNDS,
    MAX_STOPS,
    TyreModel,
    clean_stint_laps,
    estimate_pit_loss,
    load_race_laps,
)



def get_supported_compounds(
    session_id: int,
    db_path: str = DB_PATH,
) -> tuple[str, ...]:
    """Return dry tyre compounds supported by the race's fitted model."""
    if not session_id:
        return ()

    laps = load_race_laps(session_id, db_path)

    if laps.attrs.get("any_rainfall"):
        return ()

    model = TyreModel().fit(clean_stint_laps(laps))

    return tuple(
        compound
        for compound in DRY_COMPOUNDS
        if compound in model.compounds
    )


def compare_pit_strategies(
    session_id: int,
    driver: str,
    current_lap: int,
    custom_pit_lap: int,
    custom_compound: str,
    db_path: str = DB_PATH,
) -> dict:
    """Compare a forced first stop against an optimized strategy.

    Remaining stops are optimized using the same tyre model and pit loss.
    Time differences are model estimates, not finishing-time predictions.
    """
    if not session_id:
        raise ValueError("Select a race first.")

    driver = driver.upper().strip()
    current_lap = int(current_lap)
    custom_pit_lap = int(custom_pit_lap)
    custom_compound = custom_compound.upper().strip()

    laps = load_race_laps(session_id, db_path)

    if laps.attrs.get("any_rainfall"):
        raise ValueError("The simulator supports dry races only.")

    selected = laps[
        (laps["driver"] == driver)
        & (laps["lap_number"] == current_lap)
    ]

    if selected.empty:
        raise ValueError("Driver or current lap is unavailable.")

    row = selected.iloc[0]
    current_compound = str(row["compound"]).upper()

    if current_compound not in DRY_COMPOUNDS:
        raise ValueError("Current tyres must be SOFT, MEDIUM or HARD.")

    if pd.isna(row["tyre_life"]):
        raise ValueError("Tyre age is unavailable.")

    tyre_age = int(row["tyre_life"])
    total_laps = int(row["total_laps"])
    remaining = total_laps - current_lap

    if not current_lap < custom_pit_lap < total_laps:
        raise ValueError(
            "Custom pit lap must be after the current lap "
            "and before the final lap."
        )

    model = TyreModel().fit(clean_stint_laps(laps))
    compounds = tuple(model.compounds)

    if current_compound not in compounds:
        raise ValueError("Not enough data for the current tyre compound.")

    if custom_compound not in compounds:
        raise ValueError(
            f"Not enough data to simulate {custom_compound} tyres."
        )

    pit_loss = estimate_pit_loss(laps)

    previous = set(
        laps[
            (laps["driver"] == driver)
            & (laps["lap_number"] <= current_lap)
        ]["compound"].dropna().astype(str).str.upper()
    )

    used_two_compounds = len(previous & set(DRY_COMPOUNDS)) >= 2

    @lru_cache(maxsize=None)
    def optimize(n, compound, age, rule_satisfied, stops_left):
        """Return minimum model cost and relative pit-stop plan."""
        if n == 0:
            return (0.0, ()) if rule_satisfied else (inf, ())

        curve = np.cumsum(
            model.lap_cost(compound, age + np.arange(1, n + 1))
        )

        best_cost = float(curve[-1]) if rule_satisfied else inf
        best_plan = ()

        if stops_left == 0:
            return best_cost, best_plan

        for k in range(1, n):
            before_stop = float(curve[k - 1])

            for next_compound in compounds:
                next_rule = (
                    rule_satisfied
                    or next_compound != current_compound
                )

                later_cost, later_plan = optimize(
                    n - k,
                    next_compound,
                    0,
                    next_rule,
                    stops_left - 1,
                )

                cost = before_stop + pit_loss + later_cost

                if cost < best_cost:
                    best_cost = cost
                    best_plan = ((k, next_compound),) + tuple(
                        (k + offset, name)
                        for offset, name in later_plan
                    )

        return best_cost, best_plan

    baseline_cost, baseline_steps = optimize(
        remaining,
        current_compound,
        tyre_age,
        used_two_compounds,
        MAX_STOPS,
    )

    k = custom_pit_lap - current_lap

    before_custom_stop = float(
        np.sum(
            model.lap_cost(
                current_compound,
                tyre_age + np.arange(1, k + 1),
            )
        )
    )

    later_cost, later_steps = optimize(
        remaining - k,
        custom_compound,
        0,
        used_two_compounds or custom_compound != current_compound,
        MAX_STOPS - 1,
    )

    custom_cost = before_custom_stop + pit_loss + later_cost

    if not np.isfinite(baseline_cost):
        raise ValueError("No valid baseline strategy was found.")

    if not np.isfinite(custom_cost):
        raise ValueError(
            "No valid custom strategy satisfies the tyre rules."
        )

    custom_steps = ((k, custom_compound),) + tuple(
        (k + offset, name)
        for offset, name in later_steps
    )

    def format_plan(steps):
        return [
            {
                "pit_lap": current_lap + offset,
                "compound": name,
            }
            for offset, name in steps
        ]

    return {
        "driver": driver,
        "session_id": session_id,
        "current_lap": current_lap,
        "current_compound": current_compound,
        "custom_pit_lap": custom_pit_lap,
        "custom_compound": custom_compound,
        "baseline_plan": format_plan(baseline_steps),
        "custom_plan": format_plan(custom_steps),
        "baseline_model_cost": round(baseline_cost, 2),
        "custom_model_cost": round(custom_cost, 2),
        "estimated_extra_seconds": round(
            max(0.0, custom_cost - baseline_cost), 2
        ),
        "pit_loss_seconds": round(pit_loss, 2),
        "description": (
            "Historical simulation using race-wide tyre wear "
            "and pit stop estimates. Does not predict race position."
        ),
    }
