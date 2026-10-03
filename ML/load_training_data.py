"""
Loads several race sessions into the local database so there's enough
data to train the pace-prediction model on. Run this once (or whenever
you want more training data) before running train_pace_model.py.
"""

import fastf1
from Services.dbhandler import DBhandler

# A handful of 2023 races — mix of tracks so the model sees varied
# conditions (different tire deg, temps, straights vs. corners).
RACES_TO_LOAD = [
    (2023, "Bahrain", "R"),
    (2023, "Saudi Arabia", "R"),
    (2023, "Australia", "R"),
    (2023, "Miami", "R"),
    (2023, "Monaco", "R"),
    (2023, "Spain", "R"),
    (2023, "Silverstone", "R"),
    (2023, "Monza", "R"),
]


def main():
    handler = DBhandler()
    for year, event, session_type in RACES_TO_LOAD:
        print(f"Loading {year} {event} {session_type}...")
        try:
            session = fastf1.get_session(year, event, session_type)
            handler.loadSessionIntoDB(session)
        except Exception as e:
            print(f"  Skipped {year} {event}: {e}")
    handler.close()


if __name__ == "__main__":
    main()
