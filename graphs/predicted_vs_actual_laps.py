"""Issue #100: Compare predicted and actual F1 lap times."""

from pathlib import Path

import joblib
from matplotlib.figure import Figure

from ML.pace_model import FEATURES, clean_data, load_training_data
from Services.dbhandler import DB_PATH
from graphs.themes import BACKGROUND, GRID_LINE, TEXT


def build_lap_comparison_figure(
    session_id: int,
    driver_code: str,
    db_path=DB_PATH,
    model_path="pace_model.joblib",
):
    """Build a predicted-versus-actual lap time graph."""

    model_path = Path(model_path)

    if not model_path.is_file():
        raise FileNotFoundError(
            f"Trained pace model not found: {model_path}"
        )

    # Load existing race data without changing the database.
    data = clean_data(load_training_data(str(db_path)))

    laps = data[
        (data["session_id"] == session_id)
        & (data["driver"] == driver_code.upper())
    ].sort_values("lap_number").copy()

    if laps.empty:
        raise ValueError(
            f"No clean laps found for {driver_code}, session {session_id}"
        )

    # Reuse the existing trained relative-pace model.
    model = joblib.load(model_path)

    laps["predicted_lap_time"] = (
        laps["driver_baseline"].to_numpy()
        + model.predict(laps[FEATURES])
    )

    laps["prediction_error"] = (
        laps["lap_time_seconds"]
        - laps["predicted_lap_time"]
    )

    mae = laps["prediction_error"].abs().mean()

    # Build a Matplotlib figure compatible with the dashboard.
    fig = Figure(figsize=(11, 6), facecolor=BACKGROUND)
    ax = fig.add_subplot(111, facecolor=BACKGROUND)

    ax.plot(
        laps["lap_number"],
        laps["lap_time_seconds"],
        label="Actual Lap Time",
        linewidth=2,
        color="#38BDF8",
    )

    ax.plot(
        laps["lap_number"],
        laps["predicted_lap_time"],
        label="Predicted Lap Time",
        linewidth=2,
        linestyle="--",
        color="#F59E0B",
    )

    ax.set_title(
        f"Predicted vs Actual Lap Times\n"
        f"{driver_code.upper()} | Session {session_id}",
        color=TEXT,
    )

    ax.set_xlabel("Lap Number", color=TEXT)
    ax.set_ylabel("Lap Time (seconds)", color=TEXT)
    ax.tick_params(colors=TEXT)
    ax.grid(True, color=GRID_LINE, alpha=0.4)

    legend = ax.legend()
    for label in legend.get_texts():
        label.set_color("black")

    ax.text(
        0.02, 0.02,
        f"Sample MAE: {mae:.3f} seconds",
        transform=ax.transAxes,
        color=TEXT,
    )

    fig.tight_layout()

    return fig, laps
