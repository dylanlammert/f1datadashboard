from PySide6.QtNetwork import QNetworkInformation
from PySide6.QtCore import QObject, Signal

""" 
    NOTE: 
        - may need to run this on a thread    
"""
class ConnectivityVM(QObject):
    #signals
    __onlineChanged = Signal(bool)

    @property
    def onlineChanged(self):
        return self.__onlineChanged
    
    def __init__(self):
        super().__init__()
        self.isOnline = True
        if QNetworkInformation.loadDefaultBackend():
            self._info = QNetworkInformation.instance()
            self._info.reachabilityChanged.connect(self._onReachability)
            self._onReachability(self._info.reachability())

    def _onReachability(self, reachability):
        online = reachability in (
            QNetworkInformation.Reachability.Online,
            QNetworkInformation.Reachability.Site,
        )
        if online != self.isOnline:
            self.isOnline = online
            self.onlineChanged.emit(online)