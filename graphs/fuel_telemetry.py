"""Telemetry-based estimated fuel consumption graph.

Uses throttle readings and elapsed time from FastF1 telemetry.

IMPORTANT:
Fuel values are simulated estimates, not measured F1 fuel levels.
The formula is a simplified model and has not been calibrated
against real fuel consumption data.
"""

import sqlite3
from contextlib import closing
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


# Use the database in the root of the project.
DB_PATH = Path(__file__).resolve().parents[1] / "f1_data.db"

# Simplified fuel-flow constant from the project's existing model.
# This is an assumption, not a measured F1 fuel-consumption rate.
MAX_FUEL_FLOW_KG_S = 1.0 / 36.0

# Avoid estimating fuel consumption across missing telemetry intervals.
MAX_SAMPLE_GAP_SECONDS = 10.0


def load_driver_telemetry(
    session_id: int, driver_code: str, db_path=DB_PATH
) -> pd.DataFrame:
    """Load throttle readings for one driver in a selected session.

    Returns session timestamps and throttle values from the telemetry table.
    The database must already contain imported telemetry for this session.
    """
    db_path = Path(db_path)

    if not db_path.is_file():
        raise FileNotFoundError(f"Database not found: {db_path}")

    # Read the existing telemetry table without modifying database records.
    with closing(sqlite3.connect(str(db_path))) as conn:
        table_exists = conn.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'live_driver_telemetry'
            """
        ).fetchone()

        if not table_exists:
            raise ValueError(
                "Telemetry table is missing. Dylan's telemetry integration is required."
            )

        # Parameterized SQL prevents user-provided values from altering the query.
        # Ordering by session_time is required for time-based fuel estimation.
        telemetry = pd.read_sql_query(
            """
            SELECT session_time, throttle
            FROM live_driver_telemetry
            WHERE session_id = ?
              AND driver_code = ?
            ORDER BY session_time
            """,
            conn,
            params=(session_id, driver_code.upper()),
        )

    if telemetry.empty:
        raise ValueError(
            f"No telemetry available for {driver_code} in session {session_id}."
        )

    return telemetry


def estimate_remaining_fuel(
    telemetry: pd.DataFrame, initial_fuel_kg: float = 110.0
) -> pd.DataFrame:
    """Estimate remaining fuel from throttle and elapsed session time.

    Uses a simplified throttle-based flow model and trapezoidal integration.
    Results are illustrative estimates rather than real fuel measurements.
    """
    # The initial fuel value is configurable, but limited to 110 kg.
    if not 0 < initial_fuel_kg <= 110:
        raise ValueError("Initial fuel must be between 0 and 110 kg.")

    required = {"session_time", "throttle"}

    if not required.issubset(telemetry.columns):
        raise ValueError("Missing session_time or throttle column.")

    # Work on a copy to avoid modifying the original telemetry DataFrame.
    data = telemetry[["session_time", "throttle"]].copy()

    # Convert values to numbers so invalid input can be detected.
    data["session_time"] = pd.to_numeric(data["session_time"], errors="coerce")
    data["throttle"] = pd.to_numeric(data["throttle"], errors="coerce")

    if data.isna().any().any():
        raise ValueError("Telemetry contains missing or invalid values.")

    # FastF1 represents throttle position as a percentage from 0 to 100.
    if not data["throttle"].between(0, 100).all():
        raise ValueError("Throttle must be between 0 and 100.")

    # Ensure chronological ordering and retain one reading per timestamp.
    data = (
        data.sort_values("session_time")
        .drop_duplicates("session_time", keep="last")
        .reset_index(drop=True)
    )

    if len(data) < 2:
        raise ValueError("At least two telemetry samples are required.")

    # Calculate the actual elapsed time between consecutive measurements.
    data["delta_time_s"] = data["session_time"].diff().fillna(0.0)

    # Large telemetry gaps would make the fuel estimate unreliable.
    if (data["delta_time_s"] > MAX_SAMPLE_GAP_SECONDS).any():
        raise ValueError(
            "Telemetry gap exceeds 10 seconds. Cannot estimate across missing data."
        )

    # Normalize throttle from 0-100 percent to a 0-1 fraction.
    throttle_fraction = data["throttle"] / 100.0

    # Estimate instantaneous fuel flow using the existing simplified model.
    # Fuel flow (kg/s) = (normalized throttle ** 2) / 36.
    data["fuel_rate_kg_s"] = (throttle_fraction**2) * MAX_FUEL_FLOW_KG_S

    # Use the average of two neighboring fuel rates (trapezoidal integration)
    # instead of assuming a constant rate over the entire interval.
    average_rate = (data["fuel_rate_kg_s"] + data["fuel_rate_kg_s"].shift(1)) / 2.0

    # Fuel consumed in each interval = average flow rate * elapsed seconds.
    data["fuel_used_kg"] = (average_rate * data["delta_time_s"]).fillna(0.0)

    # Add interval consumption to estimate the total fuel used so far.
    data["cumulative_fuel_used_kg"] = data["fuel_used_kg"].cumsum()

    # Subtract estimated consumption from the assumed starting fuel.
    # Prevent estimates from falling below zero kilograms.
    data["estimated_remaining_fuel_kg"] = (
        initial_fuel_kg - data["cumulative_fuel_used_kg"]
    ).clip(lower=0.0)

    # Start the graph timeline at zero, regardless of session timestamp.
    data["elapsed_seconds"] = data["session_time"] - data["session_time"].iloc[0]

    return data


def plot_estimated_fuel(
    session_id: int, driver_code: str, initial_fuel_kg: float = 110.0, db_path=DB_PATH
):
    """Generate a line graph of estimated remaining fuel over time."""
    # Load telemetry for the selected driver, then estimate fuel remaining.
    telemetry = load_driver_telemetry(
        session_id=session_id, driver_code=driver_code, db_path=db_path
    )

    fuel_data = estimate_remaining_fuel(
        telemetry=telemetry, initial_fuel_kg=initial_fuel_kg
    )

    # Minutes are easier to interpret than raw seconds on the graph.
    elapsed_minutes = fuel_data["elapsed_seconds"] / 60.0

    fig, ax = plt.subplots(figsize=(12, 6))

    ax.plot(
        elapsed_minutes,
        fuel_data["estimated_remaining_fuel_kg"],
        linewidth=2,
        label=f"{driver_code.upper()} - Estimated Fuel",
    )

    # Clearly label the results as estimates, not measured fuel levels.
    ax.set_title(
        f"Estimated Fuel Remaining - {driver_code.upper()}\n"
        f"Session {session_id} | Simplified throttle model"
    )

    ax.set_xlabel("Elapsed telemetry time (minutes)")
    ax.set_ylabel("Estimated remaining fuel (kg)")
    ax.set_ylim(0, initial_fuel_kg * 1.05)

    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()

    # Return the graph and calculated data for reuse or automated testing.
    return fig, ax, fuel_data


if __name__ == "__main__":
    print("Fuel telemetry graph module loaded.")
    print(
        "Use plot_estimated_fuel(session_id, driver_code) "
        "when telemetry data is available."
    )
