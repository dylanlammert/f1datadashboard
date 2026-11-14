from __future__ import annotations
import sys
from typing import TYPE_CHECKING
from PySide6.QtCore import QObject, Signal, QThreadPool, QRunnable
from Services.dbhandler import DBhandler


if TYPE_CHECKING:
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
    - might want to place the focusDriver updates in a thread because this will try to ping every .2 seconds right now and it is very slow
        - I would like to make an algorithm to smooth the animations might need this to be in homepage
    - get rid of old functions
    

"""
greenColor = "\033[92m"
resetColor = "\033[0m"
redColor = "\033[91m"

class BlockLoaderWorkerSignals(QObject):
    __allBlocksLoaded = Signal(bool)
    
    @property
    def finished_signal(self):
        return self.__allBlocksLoaded

    __driverStandingsBlockLoaded = Signal(list)

    @property
    def driverStandingsBlockChanged(self):
        return self.__driverStandingsBlockLoaded

    __driverTelemBlockLoaded = Signal(list)
    @property
    def driverTelemBlockChanged(self):
        return self.__driverTelemBlockLoaded

    __currentAvailablePlaybackLoaded = Signal(float)

    @property
    def currentAvailablePlaybackChanged(self):
        return self.__currentAvailablePlaybackLoaded

class BlockLoader(QRunnable):
    # this will be run off of session Selector Change

    def __init__(self, sessionID: int, signals: BlockLoaderWorkerSignals):
        super().__init__()
        self.signals = signals
        self.thread_pool = QThreadPool.globalInstance()
        self.sessionID = sessionID

    # signal to show playback controls how far the data has been loaded
    # NOTE: this needs to be a QRunnable worker then it needs to organize the data and send the signals off with the dictionaries
    def run(self):
        # SQLite connections are thread-bound by default. Create and close this
        # handler here so its connection belongs to the pool thread running us.
        dbHandler = DBhandler()
        # get total rows in db for session: (telem, laps)
        focusDriverEndFlag: bool = False
        driverStandingsEndFlag: bool = False
        self.lastLoadedLap: int = 0
        self.lastLoadedTime: float = 0.0
        try:
            # while at least 1 data block is still loading keep running
            while (focusDriverEndFlag != True) or (driverStandingsEndFlag != True):
                if not driverStandingsEndFlag:
                    lapData, self.lastLoadedLap, driverStandingsEndFlag = dbHandler.getLapsDataBlock(attributeList= ["driver", "team", "lap_number", "compound", "tyre_life", "position", "lap_start_time", "lap_end_time"], sessionID= self.sessionID, lastLoadedLap= self.lastLoadedLap )
                    if lapData:
                        self.signals.driverStandingsBlockChanged.emit(lapData)

                if not focusDriverEndFlag:
                    driverTelem, self.lastLoadedTime, focusDriverEndFlag = dbHandler.getTelemetryDataBlock(attributeList= ["driver_code","session_time", "x_pos", "y_pos", "distance_to_driver_ahead", "gear", "throttle", "brake", "drs", "speed", "rpm"], sessionID= self.sessionID, lastLoadedTime= self.lastLoadedTime)
                    if driverTelem:
                        self.signals.driverTelemBlockChanged.emit(driverTelem)

                    self.signals.currentAvailablePlaybackChanged.emit(self.lastLoadedTime)
        finally:
            self.signals.finished_signal.emit(True)
            dbHandler.close()

class FocusDriverVM(QObject):
    """_summary_

    Args:
        QObject (_type_): _description_

    Returns:
        _type_: _description_

    NOTE:
    this needs to:
        - update current focused driver as given by driver standings
        - update the home page with real values of live telemetry every x seconds
        - update a set of drivers each time the driver standings registers a click
    """
    # signal to update main UI data
    __currentDataLoaded = Signal(list)

    @property
    def currentDataChanged(self):
        return self.__currentDataLoaded

    # signal to show new drivers
    __currentFocusedDriversLoaded = Signal(set[str])

    @property
    def currentFocusedDriversChanged(self):
        return self.__currentFocusedDriversLoaded


    def __init__(self, signals: BlockLoaderWorkerSignals, playControlsVM: PlayControlsVM):
        super().__init__()
        self.dbHandler = DBhandler()
        self.focusedDrivers: set[str] = set()
        self.currentData: list[dict] = []
        self.sessionData: list[list[dict]] = []
        self.dataBlockSignals = signals
        self.dataBlockSignals.driverTelemBlockChanged.connect(self.__dataBlockLoaded)
        self.dataBlockSignals.finished_signal.connect(self.printLogger)
        self.lastUpdateTime: float = 0.00
        playControlsVM.updatedTime.connect(self.__clockTick)
        self.clockLimiter: float = .2

    def clearData(self):
        self.currentData.clear()
        self.focusedDrivers.clear()
        self.sessionData.clear()
        self.lastUpdateTime = 0.00

    def __clockTick(self, currentTime: float):
        # for each driver in self.focusedDrivers grab data from table
        if len(self.focusedDrivers) > 0: 
            if (currentTime < self.lastUpdateTime - self.clockLimiter) or (currentTime > (self.lastUpdateTime + self.clockLimiter)):
                # if there is a notable difference in time then update currentData
                self.updateCurrentData(currentTime= currentTime)



    def printLogger(self):
        """
        _helper function to debug the data block loader_
        """
        print(f"data block loaded new data into session data for focusDriverVM, length of data: {sys.getsizeof(self.sessionData)}")
        #print(f"{self.sessionData}")

    def __dataBlockLoaded(self, newData: list):
        self.sessionData.append(newData)
        return

    def updateCurrentData(self, currentTime):
        self.currentData.clear()
        for driverCode in self.focusedDrivers:
            driverData = self.searchDriverTelemetry(
                time=currentTime,
                driverCode=driverCode,
            )
            if driverData is not None:
                self.currentData.append(driverData)
        self.lastUpdateTime = currentTime
        self.currentDataChanged.emit(self.currentData)

    def searchDriverTelemetry(self, time: float, driverCode: str) -> dict | None:
        targetDriver = driverCode.strip().upper()
        latestSample = None
        latestSampleTime = float("-inf")

        for block in self.sessionData:
            for sample in block:
                sampleDriver = sample.get("driver_code")
                sampleTime = sample.get("session_time")
                if (
                    sampleDriver is None
                    or str(sampleDriver).strip().upper() != targetDriver
                    or not isinstance(sampleTime, (int, float))
                    or sampleTime > time
                ):
                    continue

                if sampleTime > latestSampleTime:
                    latestSample = sample
                    latestSampleTime = sampleTime

        return latestSample.copy() if latestSample is not None else None

    def toggleFocusDriver(self, driverToToggle: str) -> bool:
        """
        _allow user to select up to 2 focused drivers_
        """
        if driverToToggle in self.focusedDrivers:
            # driver is in set remove from set
            self.focusedDrivers.remove(driverToToggle)
            return False
        else:
            # if not in focused drivers attempt to add
            if(len(self.focusedDrivers) == 2):
                # set is full
                return False
            # add driver to set
            self.focusedDrivers.add(driverToToggle)
            return True
        
# need to get this to update before we can update the focus driver ui 
class DriverStandingsViewModel(QObject):
    """
    
        NOTE:
        this object needs to 
        - onclick of driver change focus driver 
        - update standings upon each lap change
        - update standings upon each driver ahead change
        - update each drivers position change
            start out at 0 then if driver position > then +1 if < then -1
        - update time behind leader
            we could limit this to be every x seconds or update the time on each lap
    """

    __standings_loaded = Signal(list)
    __focused_driver_loaded = Signal(dict)

    @property
    def standings_changed(self):
        return self.__standings_loaded

    @property
    def focused_driver_changed(self):
        return self.__focused_driver_loaded

    # NOTE: I feel like we don't need the DBhandler to be passed down so I am removing it
    def __init__(self, playControlsVM: PlayControlsVM, focusDriverVM: FocusDriverVM, signals: BlockLoaderWorkerSignals):
        super().__init__()
        self.dbhandler = DBhandler()
        self.__driver_data: list = []

        self.focusDriverVM = focusDriverVM
        self.dataBlockSignals = signals
        self.dataBlockSignals.driverStandingsBlockChanged.connect(self.__dataBlockLoaded)
        self.dataBlockSignals.finished_signal.connect(self.printLogger)

        playControlsVM.updatedTime.connect(self.__onClockUpdate)
        # initialize the standing data to be empty this is what the UI will use for updating
        # [position]{"driver code", "team", "time behind leader"}
        self.standingsData: list = []
        self.numDriver: int = 0
        self.currentLeaderEndLapTime: float = 0.00
        self.currentLeaderStartLapTime: float = 0.00
        self.currentLap: int = 0
        
    def clearData(self):
        self.__driver_data.clear()
        self.standingsData.clear()
        self.numDriver = 0
        self.currentLeaderEndLapTime = 0.00
        self.currentLeaderStartLapTime = 0.00
        self.currentLap = 0

    def __onClockUpdate(self, newTime: float):
        # NOTE: driver standings should update every clock tick
        # check if time is > time current lap end time then update standings
        if (newTime < self.currentLeaderStartLapTime) or (newTime > self.currentLeaderEndLapTime):
            # update standings format as list[0] leader then > from there
            currentLap = self.searchCurrentLap(newTime)
            if currentLap is None:
                return
            self.currentLap, self.currentLeaderStartLapTime, self.currentLeaderEndLapTime = currentLap
            # once current lap set, set standings data that will be sent to front end
            self.setStandingsData()
            self.standings_changed.emit(self.standingsData)
        return
    
    def setStandingsData(self):
        """_format the standings data and pass it to the front end_
        """
        driversOnLap: list[dict] = []
        for block in self.__driver_data:
            driversOnLap.extend(
                row for row in block if row.get("lap_number") == self.currentLap
            )

        driversOnLap.sort(
            key=lambda row: (
                row.get("position") is None,
                row.get("position") if row.get("position") is not None else float("inf"),
            )
        )
        self.standingsData = [
            {
                "position": row.get("position"),
                "driverCode": row.get("driver"),
                "team": row.get("team"),
                "timeBehind": (
                    row["lap_start_time"] - self.currentLeaderStartLapTime
                    if row.get("lap_start_time") is not None
                    else None
                ),
            }
            for row in driversOnLap
        ]

    def searchCurrentLap(self, time: float) -> tuple[int, float, float] | None:
        """_search for current lap of leading driver based on time given_
        Args:
            time (float): _current playback time_
        
        """
        for block in self.__driver_data:
            for lap in block:
                lapStart = lap.get("lap_start_time")
                lapEnd = lap.get("lap_end_time")
                if (
                    lap.get("position") == 1
                    and lapStart is not None
                    and lapEnd is not None
                    and lapStart <= time < lapEnd
                ):
                    return lap["lap_number"], lapStart, lapEnd

        print(
            f"{redColor} lap could not be found: either no more updates or buffer is not finished loading {resetColor}"
        )
        return None

    def printLogger(self):
        """
        _helper function to debug data block loader_
        """
        print(f"data block loaded new data into session data for DriverStandingsVM, length: {sys.getsizeof(self.__driver_data)}")
        for i in self.__driver_data:
            print(i[0])
        #print(f"{self.__driver_data}")


    def __dataBlockLoaded(self, newData: list):
        """_this loads the data block into the list as a whole block not as an individual level_

        Args:
            newData (list): _data block to be appended_
        """
        self.__driver_data.append(newData)
        return

    def onDriverToggled(self, driverCode: str) -> bool:
        driverAdded: bool = self.focusDriverVM.toggleFocusDriver(driverCode)
        return driverAdded

    def getFocusDrivers(self) -> set:
        return self.focusDriverVM.focusedDrivers
    
    # NOTE: Depriciate
    