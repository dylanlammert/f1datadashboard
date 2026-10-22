"""Automated tests for seasonal tyre performance."""

import unittest
from unittest.mock import patch

import pandas as pd

from ML.seasonal_pit_analysis import compare_seasonal_tyre_wear


class SeasonalPitAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.sessions = pd.DataFrame(
            [
                ("Bahrain Grand Prix", 2023, 1, "Race"),
                ("Bahrain Grand Prix", 2024, 2, "Race"),
                ("Other Grand Prix", 2023, 3, "Race"),
            ],
            columns=["event_name", "year", "session_id", "session_type"],
        )

        self.laps = {
            1: self.make_laps(100.0, 102.0),
            2: self.make_laps(98.0, 99.0),
        }

    @staticmethod
    def make_laps(fresh, older):
        laps = pd.DataFrame(
            [
                {
                    "driver": "VER",
                    "compound": "HARD",
                    "tyre_life": age,
                    "corrected": fresh if age <= 5 else older,
                }
                for age in (3, 4, 5, 12, 13, 14)
            ]
        )
        laps.attrs["any_rainfall"] = False
        return laps

    def analyze(self, min_laps=3):
        with (
            patch(
                "ML.seasonal_pit_analysis.pd.read_sql_query",
                return_value=self.sessions.copy(),
            ),
            patch(
                "ML.seasonal_pit_analysis.load_race_laps",
                side_effect=lambda session_id, db_path: self.laps[session_id],
            ),
            patch(
                "ML.seasonal_pit_analysis.clean_stint_laps",
                side_effect=lambda laps: laps.copy(),
            ),
        ):
            return compare_seasonal_tyre_wear(
                db_path=":memory:",
                min_laps=min_laps,
            )

    def test_correct_seasonal_change(self):
        result = self.analyze()
        self.assertEqual(len(result), 1)

        row = result.iloc[0]
        self.assertEqual(row["event_name"], "Bahrain Grand Prix")
        self.assertEqual(row["driver"], "VER")
        self.assertEqual(row["compound"], "HARD")
        self.assertAlmostEqual(row["slowdown_2023_s"], 2.0)
        self.assertAlmostEqual(row["slowdown_2024_s"], 1.0)
        self.assertAlmostEqual(row["change_s"], -1.0)

    def test_minimum_lap_requirement(self):
        result = self.analyze(min_laps=4)
        self.assertTrue(result.empty)

    def test_rainy_race_excluded(self):
        self.laps[2].attrs["any_rainfall"] = True
        result = self.analyze()
        self.assertTrue(result.empty)


if __name__ == "__main__":
    unittest.main()
