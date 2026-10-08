# Imports
import fastf1
from Services.dbhandler import DBhandler
import pandas as pd
from fastf1.events import EventSchedule

"""
    TODO: 
        - If f1cache contains > 5 items delete last used item
"""

def get_schedule_by_year(year: int, testing: bool = False) -> EventSchedule:
    """When passed a year as an int, will return the name of the events.
    Should be called to gain a list of events in a year

    Args:
        year (int): Year to grab the event schedule for
        testing (bool): Whether to include testing races. Defaults to False.

    Returns:
        EventSchedule: The full event schedule of the year
    """
    yearlySchedule = fastf1.get_event_schedule(year, include_testing=testing)
    return yearlySchedule
    # Names will need to be pushed to frontend for selection.


def get_race(year: int, event_name: str, type: str = "R") -> None:
    """Will get a race from fastf1's API AND load it into the database

    Args:
        year (int): The year the event took place
        event_name (str): The name of the event
        type (str, optional): What type of race to grab. Types: 'FP1', 'FP2', 'FP3', 'Q', 'R'. Defaults to "R".
    """
    handler = DBhandler()
    try:
        handler.loadSessionIntoDB(fastf1.get_session(year, event_name, type))
    finally:
        handler.close()


# Helper/Debug Functions
def _get_event_names(schedule: EventSchedule) -> pd.Series | None:
    """Helper function for getting a list of names. Scaffolded to help with frontend

    Args:
        schedule (EventSchedule): The yearly event schedule

    Returns:
        _type_: _description_
    """
    return schedule.get("EventName")

def _main():
    get_race(2026, "Japanese Grand Prix", "R")
    handler = DBhandler()
    handler.previewDB()
    handler.close()
    return 0


# Obligatory
if __name__ == "__main__":
    _main()
