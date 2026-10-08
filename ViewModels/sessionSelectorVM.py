from PySide6.QtCore import QObject, Signal
from Services.dbhandler import DBhandler
from ViewModels.connectivityVM import ConnectivityVM
import pandas as pd
from Services.api_handler import get_schedule_by_year
from PySide6.QtNetwork import QNetworkInformation
from PySide6.QtCore import QObject, Signal

"""
    
NOTE:
    - Should we place known available fastf1 sessions within the database this would lower the memory costs for running
      currently I have this file calling the fastf1api to get a list of available sessions, this takes a lot of computing power
      and load times would be longer.
    - work on connecting the connectivityVM next initialize it in main
"""

class SessionSelectorVM(QObject):
    # Signals
    __currentSessionID = Signal(int)
    __onlineChanged = Signal(bool)
    
    @property
    def onlineChanged(self):
        return self.__onlineChanged
    

    @property
    def currentSessionID(self):
        return self.__currentSessionID
    
    # first year that the fast f1 data is logged
    FIRST_YEAR = 2018
    
    def __init__(self):
        super().__init__()
        self.isOnline = True
        self.localSessions: list[dict] = {}
        self.onlineSessions: list[dict]
        self.connectivityVM = ConnectivityVM()
        self.connectivityVM.onlineChanged.connect(self.onConnectionUpdate)

    def onRaceSelected(self, sessionInfoList):
        """_When the race is selected, load race into db then change the currentSessionID to that sessionID

        Args:
           sessionID (int): _session_
        """
        newSessionID = self.__createSessionInstance(sessionInfoList)
        self.currentSessionID = newSessionID
        self.currentSessionID.emit(newSessionID)

    def onConnectionUpdate(self, newConnectionStatus: bool):
        self.fetchAvailableRaces

    # NOTE: we need a way to only call fastf1 api every week or so after last call for faster speeds I think 
    #       for right now I can hold a var in mem if empty then check fastf1 api so it only calls on first load of session selector
    def fetchAvailableRaces(self, currentOnlineSessions) -> list[dict]:
        """_fetches a list of available sessions from the f1 api and if user doesn't have acces to that data then return a list of
            downloaded sessions_

        Returns:
            list[dict]: _available session the user can load to simulates_
        """
        # NOTE: need to insure this function returns list of dicts
        downloadedSessions: list[dict] = DBhandler.getSessionsFromDB()
        availableFastF1Sessions: list[dict] = []
        if(self.hasfastF1Access == False):
            # if user doesn't have internet only show the races that are already in the database
            return downloadedSessions

        # checks if already loaded the available sessions from fastf1 api
        if currentOnlineSessions: 
            return currentOnlineSessions
        

        # this is going to be used to mark if we have a race downloaded 
        downloadedKeys: set = set()
        # for each session in downloaded sessions add the key to downloaded keys
        for session in downloadedSessions:
            key = (session["year"], session["event_name"], session["session_type"])
            downloadedKeys.add(key)
        
        

        # limit available races to before today
        # todays timestamp
        todaysTimestamp = pd.Timestamp.now(tz = "UTC")

        try: 
            # for each year from beginning of Fastf1 support to next year
            for year in range(2018, todaysTimestamp.year + 1):
                yearSchedule = get_schedule_by_year(year)
                yearSchedule = yearSchedule[yearSchedule["F1ApiSupport"] == True]

                for _, event in yearSchedule.iterrows():
                    for index in range(1,6):
                        sessionName = event[f"Session{index}"]
                        sessionDate = event[f"Session{index}DateUtc"]

                        # we only want data before todays date and we want to make sure we aren't trying to fetch incomplete data
                        if (sessionName == "" or sessionName == None) or (pd.isna(sessionDate)) or sessionDate > todaysTimestamp:
                            continue 

                        # append this session to the available races list
                        availableFastF1Sessions.append({
                            "year": year,
                            "event_name": event["EventName"],
                            "session_type": event["Session[1-5]"],
                            "downloaded": (year, event["EventName"], event["Session[1-5]"]) in downloadedKeys,
                        })

        except Exception:
            # can't get the data from fast f1 api return the downloaded sessions
            return downloadedSessions
        # can get the data from fast f1 api return available fastf1 sessions
        return availableFastF1Sessions
                

        
        
    
    def __createSessionInstance(sessionInfoList: list) -> int:
        """_this will search the db and if the session is not loaded it will fetch the session from the fastf1 api if the user is online_

        Args:
            sessionInfoList (list): _[year, sessionName]_

        Returns:
            int: _this is the sessionID for the specified sessionInfo_
        """

        
if __name__ == "__main__":
    # test to insure you can see the fast f1 sessions
    print("testing sessionSelectorVM")