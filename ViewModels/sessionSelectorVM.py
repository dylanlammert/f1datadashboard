from PySide6.QtCore import QObject, Signal
from Services.dbhandler import DBhandler
from ViewModels.connectivityVM import ConnectivityVM
import pandas as pd
from Services.api_handler import get_schedule_by_year, get_race
import traceback

"""
    
NOTE:
    - Should we place known available fastf1 sessions within the database this would lower the memory costs for running
      currently I have this file calling the fastf1api to get a list of available sessions, this takes a lot of computing power
      and load times would be longer.
"""


class SessionSelectorVM(QObject):
    # Signals
    __currentSessionIDChanged = Signal(int)
    __availableListChanged = Signal(object)

    @property
    def availableListChanged(self):
        return self.__availableListChanged

    @property
    def currentSessionIDChanged(self):
        return self.__currentSessionIDChanged

    # first year that the fast f1 data is logged
    FIRST_YEAR = 2018
    # make the Timezone UTC then strip the UTC tag off of the timestamp
    TODAY = pd.Timestamp.now(tz="UTC").tz_localize(None)
    CURRENT_YEAR = TODAY.year

    def __init__(self, conectivityModel: ConnectivityVM):
        super().__init__()
        self.dbHandler = DBhandler()
        self.currentSessionID: int = 0
        self.localSessions: list[dict] = self.dbHandler.getSessionsFromDB()
        print(self.localSessions)
        self.onlineSessions: list[dict] = []
        # NOTE: CURRENTLY ON THIS
        self.availableList: list[dict] = []
        self.currentYearSet: set = set()
        # share the mem location of the model init in main
        self.connectivityVM = conectivityModel
        self.connectivityVM.onlineChanged.connect(self.onConnectionUpdate)

    # helper functions
    def __formatYearList(self, sessionList):
        self.currentYearSet.clear()
        for session in sessionList:
            # sets ignore duplicates
            self.currentYearSet.add(session["year"])

    def onRaceSelected(self, sessionInfoDict):
        """_When the race is selected, load race into db then change the currentSessionID to that sessionID_

        Args:
           sessionInfoList (list): _year,sessionName,sessionType_
        """
        if sessionInfoDict["downloaded"]:
            newSessionID = self.dbHandler.getSessionID(
                tableName="sessions",
                year=sessionInfoDict["year"],
                eventName=sessionInfoDict["event_name"],
                sessionType=sessionInfoDict["session_type"],
            )
        else:
            newSessionID = self.__createSessionInstance(sessionInfoDict)
        self.currentSessionID = newSessionID
        self.currentSessionIDChanged.emit(newSessionID)

    def onConnectionUpdate(self, newConnectionStatus: bool):
        # emit the real list that the view needs to display
        sessionList = self.fetchAvailableRaces()
        self.availableList = sessionList
        print("SessionSelectorVM/onConnectionUpdate : > emiting new list")
        self.availableListChanged.emit(sessionList)

    # NOTE: we need a way to only call fastf1 api every week or so after last call for faster speeds I think
    #       for right now I can hold a var in mem if empty then check fastf1 api so it only calls on first load of session selector
    def fetchAvailableRaces(self) -> list[dict]:
        """_fetches a list of available sessions from the f1 api and if user doesn't have acces to that data then return a list of
            downloaded sessions_

        Returns:
            list[dict]: _available session the user can load to simulates_
        """
        # NOTE: need to insure this function returns list of dicts
        availableFastF1Sessions: list[dict] = []
        if not self.connectivityVM.isOnline:
            # if user doesn't have internet only show the races that are already in the database
            print("fetchAvailableRaces : > user is offline ")
            # TODO: change the years to local session years
            self.__formatYearList(self.localSessions)
            return self.localSessions

        # checks if already loaded the available sessions from fastf1 api
        if len(self.onlineSessions) > 0:
            print("fetchAvailableRaces : > Online sessions are already loaded")
            self.__formatYearList(self.onlineSessions)
            return self.onlineSessions

        # this is going to be used to mark if we have a race downloaded
        downloadedKeys: set = set()
        # for each session in downloaded sessions add the key to downloaded keys
        for session in self.localSessions:
            key = (session["year"], session["event_name"], session["session_type"])
            downloadedKeys.add(key)

        # limit available races to before today
        print("fetchAvailableRaces : > try to load races from api")
        try:
            self.currentYearSet.clear()
            # for each year from beginning of Fastf1 support to next year
            for year in range(self.FIRST_YEAR, self.CURRENT_YEAR + 1):
                yearSchedule = get_schedule_by_year(year)
                yearSchedule = yearSchedule[yearSchedule["F1ApiSupport"] == True]
                for _, event in yearSchedule.iterrows():
                    for index in range(1, 6):
                        sessionName = event[f"Session{index}"]
                        sessionDate = event[f"Session{index}DateUtc"]

                        # we only want data before todays date and we want to make sure we aren't trying to fetch incomplete data
                        if (
                            (sessionName == "" or sessionName is None)
                            or (pd.isna(sessionDate))
                            or sessionDate > self.TODAY
                        ):
                            continue

                        # append this session to the available races list
                        availableFastF1Sessions.append(
                            {
                                "year": year,
                                "event_name": event["EventName"],
                                "session_type": sessionName,
                                "downloaded": (year, event["EventName"], sessionName)
                                in downloadedKeys,
                            }
                        )
                if year not in self.currentYearSet:
                    self.currentYearSet.add(year)
            # print(f"Loaded F1 Sessions Are: > \n {availableFastF1Sessions}")

        except Exception:
            # can't get the data from fast f1 api return the downloaded sessions
            print(
                f"can't get the data from the fastf1 api returning: {self.localSessions}"
            )
            traceback.print_exc()
            # TODO: add local session years to the year set
            self.currentYearSet.clear()
            self.__formatYearList(self.localSessions)
            return self.localSessions
        # can get the data from fast f1 api return available fastf1 sessions
        self.onlineSessions = availableFastF1Sessions
        return availableFastF1Sessions

    def __createSessionInstance(self, sessionInfoDict: dict) -> int:
        """_this will search the db and if the session is not loaded it will fetch the session from the fastf1 api if the user is online_

        Args:
            sessionInfoList (list): _[year, sessionName, sessionType]_

        Returns:
            int: _this is the sessionID for the specified sessionInfo_
        """
        # TODO: before we can handle session_type we need to make a code converter
        session_id = get_race(sessionInfoDict["year"], sessionInfoDict["event_name"])
        return session_id


if __name__ == "__main__":
    # test to insure you can see the fast f1 sessions
    print("testing sessionSelectorVM")
