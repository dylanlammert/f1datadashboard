"""Validate fuel estimates against cached real F1 telemetry."""

import argparse

import fastf1
import pandas as pd

from graphs.fuel_telemetry import estimate_remaining_fuel


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2023)
    parser.add_argument("--race", default="Bahrain")
    parser.add_argument("--drivers", nargs="+", default=["VER", "PER", "ALO", "HAM"])
    args = parser.parse_args()

    fastf1.Cache.enable_cache("Services/f1_cache")
    fastf1.Cache.offline_mode(True)

    session = fastf1.get_session(args.year, args.race, "R")
    session.load(
        laps=True,
        telemetry=True,
        weather=False,
        messages=False,
    )

    print(f"\nRace: {args.year} {args.race}")
    print("Driver | Valid | Invalid | Max Gap | Fuel Left | Result")

    failures = 0

    for code in args.drivers:
        try:
            driver_laps = session.laps[
                session.laps["Driver"] == code
            ]
            if driver_laps.empty:
                raise ValueError("No racing laps found")

            start = driver_laps["LapStartTime"].dropna().min()
            end = driver_laps["Time"].dropna().max()

            driver_number = str(
                session.get_driver(code)["DriverNumber"]
            )
            raw = session.car_data[driver_number]

            racing = raw[raw["Time"].between(start, end)].copy()
            valid = racing[
                racing["Throttle"].between(0, 100)
            ].copy()

            data = pd.DataFrame({
                "session_time": valid["Time"].dt.total_seconds(),
                "throttle": valid["Throttle"],
            })

            max_gap = data["session_time"].diff().max()
            result = estimate_remaining_fuel(data)
            fuel_left = result["estimated_remaining_fuel_kg"].iloc[-1]

            print(
                f"{code:6} | {len(valid):5} | "
                f"{len(racing) - len(valid):7} | "
                f"{max_gap:7.2f}s | {fuel_left:8.2f}kg | PASS"
            )
        except (ValueError, KeyError, IndexError) as exc:
            failures += 1
            print(f"{code:6} | FAILED: {exc}")

    print(f"\nResult: {len(args.drivers) - failures}/{len(args.drivers)} passed")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
