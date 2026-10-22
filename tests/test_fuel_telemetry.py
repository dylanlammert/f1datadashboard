"""Automated tests for the telemetry-based fuel graph."""

import unittest
from unittest.mock import patch

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from graphs.fuel_telemetry import (
    estimate_remaining_fuel,
    plot_estimated_fuel,
)


class FuelTelemetryTests(unittest.TestCase):
    def test_full_throttle(self):
        data = pd.DataFrame(
            {
                "session_time": [0, 1, 2],
                "throttle": [100, 100, 100],
            }
        )

        result = estimate_remaining_fuel(data)

        expected = 110 - 2 / 36

        self.assertAlmostEqual(
            result["estimated_remaining_fuel_kg"].iloc[-1],
            expected,
        )

    def test_variable_time_intervals(self):
        data = pd.DataFrame(
            {
                "session_time": [0, 2, 5],
                "throttle": [0, 50, 100],
            }
        )

        result = estimate_remaining_fuel(data)

        first_interval = 2 * (0 + 0.25) / (2 * 36)
        second_interval = 3 * (0.25 + 1) / (2 * 36)

        expected = 110 - first_interval - second_interval

        self.assertAlmostEqual(
            result["estimated_remaining_fuel_kg"].iloc[-1],
            expected,
        )

    def test_zero_throttle(self):
        data = pd.DataFrame(
            {
                "session_time": [0, 1, 2],
                "throttle": [0, 0, 0],
            }
        )

        result = estimate_remaining_fuel(data)

        self.assertAlmostEqual(
            result["estimated_remaining_fuel_kg"].iloc[-1],
            110.0,
        )

    def test_invalid_throttle_rejected(self):
        data = pd.DataFrame(
            {
                "session_time": [0, 1],
                "throttle": [50, 120],
            }
        )

        with self.assertRaises(ValueError):
            estimate_remaining_fuel(data)

    def test_missing_telemetry_rejected(self):
        data = pd.DataFrame(
            {
                "session_time": [0, 1],
            }
        )

        with self.assertRaises(ValueError):
            estimate_remaining_fuel(data)

    def test_large_telemetry_gap_rejected(self):
        data = pd.DataFrame(
            {
                "session_time": [0, 11],
                "throttle": [50, 50],
            }
        )

        with self.assertRaises(ValueError):
            estimate_remaining_fuel(data)

    def test_fuel_never_negative(self):
        data = pd.DataFrame(
            {
                "session_time": [0, 10],
                "throttle": [100, 100],
            }
        )

        result = estimate_remaining_fuel(
            data,
            initial_fuel_kg=0.01,
        )

        self.assertEqual(
            result["estimated_remaining_fuel_kg"].iloc[-1],
            0.0,
        )

    def test_graph_generation(self):
        data = pd.DataFrame(
            {
                "session_time": [0, 1, 2, 3],
                "throttle": [0, 50, 100, 75],
            }
        )

        with patch(
            "graphs.fuel_telemetry.load_driver_telemetry",
            return_value=data,
        ):
            fig, ax, result = plot_estimated_fuel(
                session_id=1,
                driver_code="VER",
            )

        try:
            self.assertEqual(len(ax.lines), 1)
            self.assertEqual(len(ax.lines[0].get_xdata()), 4)
            self.assertLess(
                result["estimated_remaining_fuel_kg"].iloc[-1],
                110.0,
            )
        finally:
            plt.close(fig)


if __name__ == "__main__":
    unittest.main()
