from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from Services.dbhandler import DBhandler
from ViewModels.raceSimulationVM import PlayControlsVM

"""
NOTE:
    - it looks like this only show final standing, It should show an updated standing based on driver telem not results. 
      results I think should only be used for our ML for a correctness score

OUTLINE: 
    - load needed driver data to the standings VM (not all of the data in telemetry is needed for the vm)
    - might need a buffer to only load the next ~10 min of data for faster load times. I think I might have to make a buffer loader for the sim graph.
    - Focused driver will load more data for specified driver and it will have to calculate a few values

TODO:
    - make a function to determine driver current place
        - every lap we get an official position of driver but that can change mid lap and won't update till next lap
        - we do have access to driver in front of DRIVERCODE, so what I am thinking is keep a list of [driver code] then if
          driver in front != list[indx - 1] then your position went up, update the list order. then update difference between 
          beginning position.
    - 
    

"""
class blockLoader(QObject):

    # signal driver standings block ready 
    __driverStandingsBlockLoaded = Signal(list[dict])

    @property
    def driverStandingsBlockChanged(self):
        return self.__driverStandingsBlockLoaded

    # signal driver telemetry block ready 
    __driverTelemBlockLoaded = Signal(dict[str[dict]])

    @property
    def driverTelemBlockChanged(self):
        return self.__driverTelemBlockLoaded

    def __init__(self):
        super().__init__()

    def loadLivePlaybackSessionData(self):
        return

class FocusDriverVM(QObject):
    # signal to update main UI data
    __currentDataLoaded = Signal(list[dict])

    @property
    def currentDataChanged(self):
        return self.__currentDataLoaded

    # signal to show new drivers
    __currentFocusedDriversLoaded = Signal(set[str])

    @property
    def currentFocusedDriversChanged(self):
        return self.__currentFocusedDriversLoaded


    def __init__(self, playControlsVM: PlayControlsVM):
        super().__init__()
        self.dbHandler = DBhandler()
        self.focusedDrivers: set[str]
        self.currentData: dict


    def __clockTick(self):
        # for each driver in self.focusedDrivers grab data from table
        if len(self.focusedDrivers):
            for driver in self.focusedDrivers:
                self.dbHandler.getDataFromTable()
            return

    def toggleFocusDriver(self, driverToToggle: str):
        """
        _allow user to select up to 2 focused drivers_
        """
        if driverToToggle in self.focusedDrivers:
            # driver is in set remove from set
            self.focusedDrivers.remove(driverToToggle)
        else:
            # if not in focused drivers attempt to add
            if(len(self.focusedDrivers) == 2):
                # set is full
                return
            # add driver to set
            self.focusedDrivers.add(driverToToggle)
        
        
        

class DriverStandingsViewModel(QObject):
    """Provides race-based driver standings to the UI."""

    __standings_loaded = Signal(list)
    __focused_driver_loaded = Signal(dict)

    @property
    def standings_changed(self):
        return self.__standings_loaded

    @property
    def focused_driver_changed(self):
        return self.__focused_driver_loaded

    def __init__(self, dbhandler: DBhandler | None = None, playControlsVM: PlayControlsVM | None = None):
        super().__init__()
        self.dbhandler = dbhandler if dbhandler is not None else DBhandler()
        self.__driver_data = []
        self.__focused_driver = None
        self.playControlsVM = playControlsVM
        self.playControlsVM.updatedTime.connect(self.onClockUpdate)


    def __onClockUpdate(self, newTime: float):
        # NOTE: driver standings should update every clock tick
        
        return
    
    def get_driver_data(self) -> list[dict]:
        return [row.copy() for row in self.__driver_data]

    def set_driver_data(self, data: list[dict]) -> None:
        self.__driver_data = [row.copy() for row in data]
        self.__standings_loaded.emit(self.get_driver_data())

        if self.__focused_driver is not None:
            self.fetch_focused_driver_data()

    def fetch_driver_data(self, year: int) -> list[dict]:
        """Load driver standings for a season from race results."""
        query = """
            SELECT
                r.driver_code,
                COALESCE(MAX(d.full_name), r.driver_code) AS full_name,
                COALESCE(SUM(r.points), 0) AS total_points
            FROM results r
            JOIN sessions s ON s.session_id = r.session_id
            LEFT JOIN drivers d
                ON d.session_id = r.session_id
                AND d.driver_code = r.driver_code
            WHERE s.year = ? AND s.session_type = 'Race'
            GROUP BY r.driver_code
            ORDER BY total_points DESC, r.driver_code ASC
        """

        rows = self.dbhandler.conn.execute(query, (int(year),)).fetchall()

        standings = [
            {
                "position": index,
                "driver_code": row[0],
                "full_name": row[1],
                "points": float(row[2]),
            }
            for index, row in enumerate(rows, start=1)
        ]

        self.set_driver_data(standings)
        return self.get_driver_data()

    def set_focused_driver(self, driver_code: str) -> dict:
        self.__focused_driver = driver_code.strip().upper()
        return self.fetch_focused_driver_data()

    def get_focused_driver_data(self) -> dict:
        """
            - will need to run a diff sql exec script to grab more data from telem
                - position from lap can also build from telem person in front of
                - rpm val
                - speed
                - brake bool
                - drs val
                - throttle val for meter
                - x, y pos
                - gear
        """
        for row in self.__driver_data:
            if row["driver_code"] == self.__focused_driver:
                return row.copy()
        return {}

    def fetch_focused_driver_data(self) -> dict:
        focused = self.get_focused_driver_data()
        self.__focused_driver_loaded.emit(focused)
        return focused
