from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class MetricSpec:
    """Contains the underlying definitions for each graph:
    - Label: A human-readable label for the Y-axis of each graph
    - Table: Which DB table contains the data
    - Column: What column in the table contains the data
    - Time Column: What column in the table contains the time data
    - Unit: Optional, tells what unit the graph is in (Default: "")
    - Per Driver: Optional, whether data is graphed per driver or not (Default: False)
    - Driver Column: Optional, what column the driver code is stored in (Default: "driver_code")
    - Step: Optional, whether to use a step plot or not (Default: False)
    - Invert Y: Optional, whether the Y-axis should be inverted or not (Default: False)
    - Time is Next: Optional, whether time is a timedelta string (Default: False)
    """

    # ? This has a lot of entries since our databases are so vastly different from one another lmfao
    label: str
    table: str
    column: str
    time_column: str
    unit: str = ""
    per_driver: bool = False
    driver_column: str = "driver_code"
    step: bool = False
    invert_y: bool = False
    time_is_text: bool = False


class Metric(Enum):
    """Add new members to this class to represent each object the user can graph. Partially vetted."""

    # ? Entries follow format:
    # ?     ENTRY = MetricSpec([DATA FOR EACH APPLICABLE ENTRY])

    # ? Weather entries
    AIR_TEMP = MetricSpec(
        "Air temperature", "weather", "air_temp", "sample_time", "°C", time_is_text=True
    )
    TRACK_TEMP = MetricSpec(
        "Track temperature",
        "weather",
        "track_temp",
        "sample_time",
        "°C",
        time_is_text=True,
    )
    HUMIDITY = MetricSpec(
        "Humidity", "weather", "humidity", "sample_time", "%", time_is_text=True
    )
    RAINFALL = MetricSpec(
        "Rainfall (0/1)",
        "weather",
        "rainfall",
        "sample_time",
        step=True,
        time_is_text=True,
    )

    # ? Track Status Changes
    TRACK_STATUS = MetricSpec(
        "Track status code", "trackStatus", "track_safety_status", "time", step=True
    )

    # ? Laps
    LAP_TIME = MetricSpec(
        "Lap time",
        "laps",
        "lap_time_seconds",
        "lap_end_time",
        "s",
        per_driver=True,
        driver_column="driver",
    )
    POSITION = MetricSpec(
        "Race position",
        "laps",
        "position",
        "lap_end_time",
        per_driver=True,
        driver_column="driver",
        step=True,
        invert_y=True,
    )
    TYRE_LIFE = MetricSpec(
        "Tyre life",
        "laps",
        "tyre_life",
        "lap_end_time",
        "laps",
        per_driver=True,
        driver_column="driver",
    )  # I'm dying putting the 'y' in Tire /ᐠ ¬`‸´¬ マ

    # ? Telemetry
    SPEED = MetricSpec(
        "Speed",
        "live_driver_telemetry",
        "speed",
        "session_time",
        "km/h",
        per_driver=True,
    )
    THROTTLE = MetricSpec(
        "Throttle",
        "live_driver_telemetry",
        "throttle",
        "session_time",
        "%",
        per_driver=True,
    )
    RPM = MetricSpec(
        "RPM", "live_driver_telemetry", "rpm", "session_time", per_driver=True
    )
    GEAR = MetricSpec(
        "Gear",
        "live_driver_telemetry",
        "gear",
        "session_time",
        per_driver=True,
        step=True,
    )
    BRAKE = MetricSpec(
        "Brake (0/1)",
        "live_driver_telemetry",
        "brake",
        "session_time",
        per_driver=True,
        step=True,
    )

    @property
    def spec(self) -> MetricSpec:
        return self.value
