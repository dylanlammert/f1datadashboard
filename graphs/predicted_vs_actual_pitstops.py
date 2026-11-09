
"""
Graph: Predicted vs Actual First Pit Stop

Compares the model's recommended first pit lap with the driver's
actual first pit lap in a race session.
"""

import matplotlib

if __name__ == "__main__":
    matplotlib.use("Agg")

import pandas as pd
from matplotlib.figure import Figure

from ML.pit_window import (
    load_race_laps,
    recommend_pit_window,
    clean_stint_laps,
    TyreModel,
    estimate_pit_loss,
)


def collect_pit_stop_comparison(session_id: int, drivers: list[str] | None = None) -> pd.DataFrame:
    """Collect actual vs predicted first pit stop laps for selected drivers."""
    laps = load_race_laps(session_id)

    if drivers is None:
        drivers = sorted(laps["driver"].dropna().unique())

    pit_loss = estimate_pit_loss(laps)
    rows = []

    for code in drivers:
        driver_laps = laps[laps["driver"] == code].sort_values("lap_number")
        if driver_laps.empty:
            continue

        start_lap = driver_laps[driver_laps["lap_number"] == 5]
        if start_lap.empty:
            continue
        start_lap = start_lap.iloc[0]

        stops = driver_laps[
            (driver_laps["is_pit_lap"] == 1)
            & (driver_laps["lap_number"] > 5)
        ]
        if stops.empty:
            continue

        # First flagged pit lap is the driver's first pit entry.
        actual_pit_lap = int(stops["lap_number"].min())

        other_laps = clean_stint_laps(laps[laps["driver"] != code])
        if other_laps.empty:
            continue

        tyre_model = TyreModel().fit(other_laps)

        prediction = recommend_pit_window(
            session_id,
            code,
            5,
            str(start_lap["compound"]),
            int(start_lap["tyre_life"]),
            tyre_model=tyre_model,
            pit_loss=pit_loss,
        )

        predicted_pit_lap = prediction["recommended_pit_lap"]
        if predicted_pit_lap is None:
            continue

        rows.append(
            {
                "driver": code,
                "actual_pit_lap": actual_pit_lap,
                "predicted_pit_lap": int(predicted_pit_lap),
                "error": abs(int(predicted_pit_lap) - actual_pit_lap),
            }
        )

    if not rows:
        raise ValueError("No pit stop comparison data could be generated.")

    return pd.DataFrame(rows).sort_values("actual_pit_lap").reset_index(drop=True)


def build_pit_stop_comparison_figure(session_id: int, drivers: list[str] | None = None):
    """Build the comparison graph and return both figure and data."""
    data = collect_pit_stop_comparison(session_id, drivers)

    fig = Figure(figsize=(11, max(6, 1.6 + len(data) * 0.46)))
    ax = fig.add_subplot(111)

    positions = list(range(len(data)))
    bar_height = 0.34

    ax.barh(
        [i - bar_height / 2 for i in positions],
        data["actual_pit_lap"],
        height=bar_height,
        label="Actual",
    )
    ax.barh(
        [i + bar_height / 2 for i in positions],
        data["predicted_pit_lap"],
        height=bar_height,
        label="Predicted",
    )

    max_lap = int(
        max(data["actual_pit_lap"].max(), data["predicted_pit_lap"].max())
    )

    for i, row in data.iterrows():
        ax.text(
            max_lap + 0.8,
            i,
            f"Error: {int(row['error'])} laps",
            va="center",
            fontsize=9,
        )

    ax.set_yticks(positions)
    ax.set_yticklabels(data["driver"])
    ax.invert_yaxis()

    ax.set_xlim(0, max_lap + 12)
    ax.set_xlabel("Pit Stop Lap Number")
    ax.set_ylabel("")
    ax.set_title(f"First Pit Stop Comparison (Session {session_id})", pad=10)
    ax.legend(loc="upper right")
    ax.grid(True, axis="x", alpha=0.3)
    ax.set_axisbelow(True)

    fig.tight_layout()
    return fig, data


if __name__ == "__main__":
    fig, data = build_pit_stop_comparison_figure(1, ["VER", "PER", "ALO", "HAM"])
    fig.savefig("predicted_vs_actual_pitstops.png", dpi=150)
    print(data.to_string(index=False))
    print("Saved predicted_vs_actual_pitstops.png")
