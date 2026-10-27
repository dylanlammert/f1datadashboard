from PySide6.QtCore import QObject, Signal
from Services.dbhandler import DBhandler
from ViewModels.raceSimulationVM import PlayControlsVM




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
        
        
        


    