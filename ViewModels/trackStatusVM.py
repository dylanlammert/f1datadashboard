from PySide6.QtCore import QObject, Signal
from Services.dbhandler import DBhandler
from ViewModels.raceSimulationVM import PlayControlsVM
from ViewModels.sessionSelectorVM import SessionSelectorVM


class TrackStatusVM(QObject):
    """
    TODO:
        - refactor track status fetch functions to work with getting info from the db
        - add currentIndex and approxTime to the vars on init
        - add logic to determine if track is wet or dry
        - refactor so that I can't directly pull the data from properties
        - This is not properly updating the loading text on the UI after the scrubber is set back to before the race starts
    """

    # Signals
    __updatedTrackSafety = Signal(str)
    __updatedTrackSurface = Signal(str)

    @property
    def updatedTrackSafety(self):
        return self.__updatedTrackSafety

    @property
    def updatedTrackSurface(self):
        return self.__updatedTrackSurface

    def __init__(
        self, playControlsVM: PlayControlsVM, sessionSelectorVM: SessionSelectorVM
    ):
        super().__init__()
        # on init set Signals and class vars to normal
        self.currentTrackSafety: str = "session data not loaded..."
        self.currentTrackSurface = "normal"
        # NOTE: This won't be accurate once entry_id's are deleted and re-inserted we should propbably change entry_id search to table_index search
        self.currentIndex: int = 1
        # NOTE: flagged for depreciation once playcontrolsVM updates all viewModels
        self.currentTime: float = 0.00
        # bounds for the current status
        self.lastStatusChangeTime: float | None = 0.0
        self.nextStatusChangeTime: float | None = 0.0
        self.playControlsVM = playControlsVM
        self.sessionSelectorVM = sessionSelectorVM
        # on playcontrol _tick for clock run _onCurrentTimeChange function
        self.playControlsVM.updatedTime.connect(self._onCurrentTimeChange)

        # create a new DBhandler for fetching track info
        """
            NOTE: Read only
        """
        self.dbHandler = DBhandler()

    def _onCurrentTimeChange(self, newCurrentTime):
        """_a function that gets called whenever the clock in playControlsVM gets incremented.
            makes a call to fetchSafetyStatus if the current time is ouside of current status bounds_

        Args:
            newCurrentTime (_float_): _This is the currentTime that was sent from the updatedTime signal
                                       within the playControlsVM_
        """
        # if newCurrentTime < self.lastStatusChangeTime then the scrubber has been used to go back in time
        if (newCurrentTime < self.lastStatusChangeTime) or (
            newCurrentTime >= self.nextStatusChangeTime
        ):
            # fetch safety status based off of time
            print(
                f"trackStatusVM.py/TrackStatusVM/_onCurrentTimeChange: Fetch status via time newCurrentTime: {newCurrentTime}, lastStatusChangeTime: {self.lastStatusChangeTime}"
            )
            self.fetchSafetyStatus(searchData=newCurrentTime, searchBy="time")
            # realistically I should search by time. If the person searches via entry_id but they are not at the next entry then time is more acurate. It would basically have to update multiple times

    def _getNextChangeTime(self, entryID: int) -> float:
        """_helper function to get the time at which a new status change happens_

        Args:
            entryID (_int_): _this is the currentIndex that is tracked_

        Returns:
            _float_: _time of next status change in seconds_
            _float_: _float representation of infinity if there is no next row, this can be used as an end-flag for sessionID_
        """
        row = self.dbHandler.getDataFromTable(
            tableName="trackStatus",
            searchBy="entry_id",
            searchData=entryID + 1,
            attributeNameTuple=("time",),
            sessionID=self.sessionSelectorVM.currentSessionID,
        )
        if row is not None:
            # next change time for track status
            return row[0]
        else:
            # no more trackStatus changes within the session
            return float("inf")

    def _setSurfaceStatus(self, newStatus: str):
        """_helper function to set the local surface status and also send a signal out to other VMs_

        Args:
            newStatus (str): _new surface status to be emitted_

        NOTE: currently not using this function, need to create a function to estimate surface status from weather data
        """
        # this could affect 2 views in the Front end so may add a Signal
        if newStatus != self.currentTrackSurface:
            self.currentTrackSurface = newStatus
            self.updatedTrackSurface.emit(newStatus)

    def setSafetyStatus(self, newStatus: str):
        """_helper function to set the local safety status and also send a signal to other VMs_

        Args:
            newStatus (str): _this is the new status that was grabbed from database_
        """
        # might need to run a check that newstatus is an accepted status
        if newStatus != self.currentTrackSafety:
            self.currentTrackSafety = newStatus
            self.updatedTrackSafety.emit(newStatus)

    def getSafetyStatus(self):
        """_helper function that grabs safety status from local variable_

        Returns:
            _str_: _current safety status_
        """
        return self.currentTrackSafety

    def getSurfaceStatus(self):
        """_helper function that grabs the surface status from the local variable_

        Returns:
            _str_: _current message held within local surface status_
        """
        return self.currentTrackSurface

    def fetchSafetyStatus(self, searchData, searchBy):
        """_grabs data from the dbHandler and calls to set the safety status_

        Args:
            searchData (_float | int_): _the value that is being used to search_
            searchBy (_str_): _string value of the manner being searched_
        """
        # data needed from trackStatus Table
        columns = ("entry_id", "session_id", "time", "track_safety_status", "message")
        # fetch status from DB
        # creates a tuple to search through
        newStatus = self.dbHandler.getDataFromTable(
            tableName="trackStatus",
            searchBy=searchBy,
            searchData=searchData,
            attributeNameTuple=columns,
            sessionID=self.sessionSelectorVM.currentSessionID,
        )

        # ! newStatus being None is causing a CTD. This needs to be handled elegantly in the future.
        """
        if newStatus is None:
            return None
        """

        # set data to idle
        if newStatus is None:
            self.setSafetyStatus("Idle")
            self.lastStatusChangeTime = 0.00
            self.currentIndex = (
                self.dbHandler.getFirstIndexOfTrackStatus()
            )  # start of session
            self.nextStatusChangeTime = self._getNextChangeTime(self.currentIndex)
        else:
            # grab next change time from table status
            self.currentIndex = newStatus[0]
            self.nextStatusChangeTime = self._getNextChangeTime(self.currentIndex)
            self.lastStatusChangeTime = newStatus[2]
            self.setSafetyStatus(newStatus[4])
            self.currentIndex += self.currentIndex

    def fetchSurfaceStatus(self):
        # fetch status from DB
        # newStatus = dbHandler.getSafetyStatus()
        # stub value need to wright a try except block for getting data from db
        self.setSurfaceStatus("test")
