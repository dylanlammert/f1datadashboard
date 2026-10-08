# basic test application
from PySide6.QtCore import Signal, Qt
from UI.Theme import theme
from ViewModels.raceSimulationVM import PlayControlsVM
from ViewModels.trackStatusVM import TrackStatusVM
from ViewModels.simulationGraphVM import SimulationCanvas
from ViewModels.sessionSelectorVM import SessionSelectorVM
from Services.dbhandler import DBhandler
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QFrame,
    QSlider,
    QComboBox,
    QPushButton,
    QStyleFactory
)

layoutColor: str = theme.info
gridMargin: int = 12
padding: int = 12
borderRadius: int= 20

"""
    TODO: 
    - move the scrubber to its own class
    - might make a vm for the scrubber 
    - flags to show visually on scrubber (race start, trackstatus changes, finish flag)
    - fix track clipping when user makes window smaller
"""


class Card(QFrame):
    """
    _Class that will provide the basic styling for each object on the homepage_
    """

    def __init__(self):
        super().__init__()
        self.setStyleSheet(
        f"""
                background-color: {theme.background};
                border-radius: {borderRadius};        
        """
        )


class DriverCard(QFrame):
    """
    _UI element for the driver data being held within the driver placments area of the homepage_

    """
    def __init__(self, driverName, currentPlacement):
        super().__init__()


class TrackStatusCard(Card):
    """_creates a card that shows updated data from the trackStatusVM_

    """

    def __init__(self, trackStatusVM: TrackStatusVM):
        super().__init__()
        self.statusStyles: dict = {"AllClear": theme.success, "Yellow": theme.warning, "Red" : theme.danger, "VSCDeployed" : theme.safety}
        #self.setStyleSheet(f"""background-color: {theme.background}""")
        self.setStyleSheet(f"background-color: none")
        self.setFixedHeight(50)
        self.setMaximumWidth(140)
        # share the mem location of the initialized VM
        self.trackStatusVM = trackStatusVM
        # stub info while waiting for race to load
        self.message: str = "No Data Loaded..."
        # formating layout
        layout = QHBoxLayout(self)
        # create the label that will be updated
        self.statusLabel = QLabel(self.message)

        layout.addWidget(self.statusLabel)

        # connect to the VM
        self.trackStatusVM.updatedTrackSafety.connect(self.onStatusChange)

    def onStatusChange(self, status: str):
        """_function that is called everytime the status is updated from the trackStatusVM_

        Args:
            status (str): _This is the track status that was sent from the trackStatusVM_
        """
        # set local message to the new status then update the label
        self.message = status
        self.statusLabel.setText(self.message)
        self.statusLabel.setStyleSheet(f"color: {self.statusStyles[self.message]}")


class PlayControlsUI(Card):
    """ _Front-end for the PlayControls VM. this controls the user input for toggling play, scrubbing, and playback speed_

    Args:
        Card: _basic styling_

    Methods:
        onClickPlay: _Toggle play/pause_
        onPlayBackSpeedChange: _Change the playback speed up to 4x_
        onCurrentTimeChange: _when the playControlsVM's timer updates it runs this code block_
        onDurationChange: _when the playCotnrolsVM's sessionDuration changes it runs this code block, this will fire when the session is changed_
    """
    def __init__(self, playControlsController: PlayControlsVM):
        super().__init__()
        self.setFixedHeight(60)
        self.playControlsVM = playControlsController
        self.raceDuration: float = 0.00
        self.formattedTime: str = "00:00:00"
        self.SPEEDS: tuple = (1,2,4)
        #connect on duration change to the playControlsVM
        self.playControlsVM.updatedRaceDuration.connect(self.onDurationChange)
        self.playControlsVM.updatedTime.connect(self.onCurrentTimeChange)
        layout = QVBoxLayout(self)
        #scrub bar
        scrubRow = QHBoxLayout()
        self.currentTimeLabel = QLabel("00:00")
        # ? I had to change this to Qt.Orientation.Horizontal to get it to compile for some reason. Apparently it's a newer change with PySide6?
        # create the slider NOTE: might want to make this it's own class later on
        self.scrubSlider = QSlider(Qt.Orientation.Horizontal)
        self.scrubSlider.setMinimumHeight(40)
        self.scrubSlider.setRange(0, 100)  # will be rescaled once duration is known
        self.durationLabel = QLabel(self.formattedTime)
        # set the signal changes
        self.scrubSlider.valueChanged.connect(self._onSliderValueChanged)
        self.scrubSlider.sliderPressed.connect(self._onSliderPressed)
        self.scrubSlider.sliderReleased.connect(self._onSliderReleased)
        # is slider being messed with 
        self.sliderInUse: bool = False

        # play functions
        
        # toggle play button
        self.playButton = QPushButton()
        self.playButton.setText("▶")
        self.playButton.setFixedSize(40,40)
        self.playButton.setStyleSheet(
            f"""background-color: {theme.background};
                color: {theme.primaryText};
                padding: {padding};
                border-radius: {borderRadius};
            """
            
        )
        '''
        "QPushButton { padding: 6px 16px; border-radius: 6px;"
        "background-color: #e10600; color: white; font-weight: bold; }"
        "QPushButton:hover { background-color: #ff1e17; }"
        '''

        self.playButton.clicked.connect(self._onClickPlay)
        

        # change playback speed
        self.speedBox = QComboBox()
        self.speedBox.setStyle(QStyleFactory.create("Fusion"))
        self.speedBox.setStyleSheet(
            f"""
            QComboBox {{
                color: {theme.primaryText};
                border-radius: {borderRadius};
                padding: 2px;
            }}

            QComboBox::drop-down {{
                width: 14px;
                border: none;
            }}
            """
        )
        for s in self.SPEEDS:
            self.speedBox.addItem(f"{s}x", s)
        self.speedBox.setCurrentIndex(self.SPEEDS.index(1))
        self.speedBox.currentIndexChanged.connect(self._onPlaybackSpeedChanged)

        scrubRow.addWidget(self.playButton, alignment= Qt.AlignmentFlag.AlignVCenter)
        scrubRow.addWidget(self.speedBox)
        scrubRow.addWidget(self.currentTimeLabel)
        scrubRow.addWidget(self.scrubSlider, 1)
        scrubRow.addWidget(self.durationLabel)
        layout.addLayout(scrubRow)
        
# on UI element change call viewModel.set{action} then have the set action updated a signal that the UI reads

    def _onClickPlay(self):
        """_send a signal to the playcontrolVM to stop the clock_

        """
        print("user clicked play/pause")
        self.playControlsVM.togglePlay()
        if self.playControlsVM.getIsPlaying():
            self.playButton.setText("⏸")
        else:
            self.playButton.setText("▶")

    def _onSliderPressed(self):
        """_stop the playControls timer from updating the timer while the user is messing with the slider_
        
        """
        # stop the slider from updating from currentTime changing
        self.playControlsVM.timer.blockSignals(True)
        self.sliderInUse = True
    def _onSliderReleased(self):
        """_unblock the playcontrols timer from updating_
        """
        # allow the slider to update from currentTime changing
        self.playControlsVM.timer.blockSignals(False)
        self.sliderInUse = False
    def _onSliderValueChanged(self):
        """_set the playcontrolVM's timer to what the new value is_
        """
        # take time that slider displays then set the currentTime in the playControls VM
        self.playControlsVM.setCurrentTime(self.scrubSlider.value())

    def _onPlaybackSpeedChanged(self, index = 1):
        """_update the playControlsVM's variable for the playback speed to the new value up to 4x_
        """
        print(f"playback speed changed to {self.speedBox.itemData(index)}")
        self.playControlsVM.setPlaybackSpeed(self.speedBox.itemData(index))
        #change playback speed

    def _formatTime(self, totalSeconds: float) -> str:
        """ _Takes the arguement and converts it into a str that can be passed easily to the QLabel_

        Args:
            totalSeconds (float): _the total seconds that need to be converted to a string_

        Returns:
            str: _formatted HH:MM:SS str value_
        """
        # round the total sescods into an easy to work with numbe
        totalSeconds = int(round(totalSeconds))
        # find the separate values for HH:MM:SS
        hours = totalSeconds // 3600
        minutes = (totalSeconds % 3600) // 60
        seconds = totalSeconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
   
    def onCurrentTimeChange(self, newCurrentTime):
        """_when current time changes from the playControlsVM's timer set the new current time to what it was just updated to _

        Args:
            newCurrentTime (_float_): _new time emitted by a signal within the playcontrolVM object_
        """
        time = self._formatTime(newCurrentTime)
        self.currentTimeLabel.setText(time)

    def onDurationChange(self, newDuration):
        #self.scrubSlider.blockSignals(True)
        self.raceDuration = newDuration
        self.formattedTime = self._formatTime(newDuration)
        self.scrubSlider.setRange(0, int(self.raceDuration))
        self.durationLabel.setText(self.formattedTime)
        #self.scrubSlider.blockSignals(False)

class HomePage(QWidget):
    """_Home page UI layout, instantiates different UI objects and places them on the homepage widget_

    """
    def __init__(self, trackStatusViewModel: TrackStatusVM, playControlsViewModel: PlayControlsVM, sessionSelectorViewModel: SessionSelectorVM ):
        super().__init__()
        # share the mem location of VMs
        self.trackStatusController = trackStatusViewModel
        self.playControlsController = playControlsViewModel
        self.sessionSelectorController = sessionSelectorViewModel
        # NOTE: hard coded, in future this should be held within sessionSelectorVM
        self.currentSessionID = 1
        
        # make a grid layout of 13x11ish
        # grid layout (rowstart, colstart, spanrows, spancols)
        gridLayout = QGridLayout(self)
        gridLayout.setSpacing(gridMargin)
        gridLayout.setSpacing(gridMargin)
        # setting the margins of the grid to a standard size
        gridLayout.setContentsMargins(gridMargin, gridMargin, gridMargin, gridMargin)
        # create the simulation frame
        driverSimFrame = DriverSIM(trackStatus = self.trackStatusController, playControlsController = self.playControlsController)
        gridLayout.addWidget(driverSimFrame, 1,0, 3, 3)
        # create the session selector
        sessionFrame = SessionSelector(sessionSelectorViewModel)
        gridLayout.addWidget(sessionFrame, 0, 0, 1, 3)
        # create the driver placement UI 
        driverStandingsFrame = DriverStandings()
        gridLayout.addWidget(driverStandingsFrame, 0, 3, 4, 1)
        # create the focussed driver telemetry card
        driverTelemetryCard1 = DriverTelemetry()
        gridLayout.addWidget(driverTelemetryCard1, 4, 0, 1, 4)
        # create the 2nd focussed driver telemetry card
        driverTelemetryCard2 = DriverTelemetry()
        gridLayout.addWidget(driverTelemetryCard2, 5, 0, 1, 4)
        # NOTE: this should not control this, make playControls fetch this on init call the playControlsVM to fetch the race duration
        self.playControlsController.fetchRaceDuration(self.currentSessionID)


class DriverSIM(Card):
    """
    _UI for the visual race simulation where the drivers are placed on a graph and have their live gps data transmitted to move their vehicles_
    """
    def __init__(self, trackStatus: TrackStatusVM, playControlsController: PlayControlsVM):
        super().__init__()
        self.raceSimCanvas = SimulationCanvas()
        self.setStyleSheet(f"""
            DriverSIM {{
               background-color: {theme.background}; 
               border-radius: {borderRadius};
            }}
        """)
        # self.setStyleSheet(f"background-color: {theme.info}")
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        # create the track status card that will sit inside of the race sim
        # create the playcontrols that will sit at the bottom row of the race sim
        self.playControlsUI = PlayControlsUI(playControlsController)
        # this will hold the simulated race
        layout.addWidget(self.raceSimCanvas)
        self.trackStatusCard = TrackStatusCard(trackStatus)
        self.trackStatusCard.setParent(self)
        self.trackStatusCard.raise_()
        self.raceSimCanvas.drawTrackOutline()
        layout.addWidget(self.playControlsUI)


class DriverStandings(Card):
    """
    _this holds all of the Driver Cards for a specified race_
    """
    def __init__(self):
        super().__init__()
        # create and add a label for layout purposes
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Driver Standings"))


class DriverTelemetry(Card):
    """
    _showcase the focussed driver's live telemetry_
    """
    def __init__(self):
        super().__init__()
        self.setMaximumHeight(100)
        # create and add a label for layout purposes
        layout = QHBoxLayout(self)
        layout.addWidget(QLabel("Driver Telemetry"))


class SessionSelector(Card):
    """
    _UI element that creates a few dropdown menus and submit button so the user can change sessions_
    """
    def __init__(self, sessionSelectorViewModel):
        super().__init__()
        self.sessionSelectorViewModel = sessionSelectorViewModel
        self.setMaximumHeight(50)
        # create and add a label for layout purposes
        layout = QHBoxLayout(self)
        layout.addWidget(QLabel("Current Session"))
        # year dropdown menu
        # TODO: insure that downloaded sessions are also in a separate section
        self.yearSelector = QComboBox()
        self.yearSelector.setPlaceholderText("Select Year")
        # seesion dropdown menu
        # TODO: on session selected load session into view
        self.eventSelector = QComboBox()
        self.eventSelector.setPlaceholderText("Select Event")

        self.sessionSelector = QComboBox()
        self.sessionSelector.setPlaceholderText("Select Session")

        self.connectionLabel = QLabel("Online")
        

        layout.addWidget(self.yearSelector)
        layout.addWidget(self.eventSelector)
        layout.addWidget(self.sessionSelector)


        # self.yearSelector.currentIndexChanged.connect(self.onYearChanged)
        # self.sessionSelector.currentIndexChanged.connect(self.sessionSelectorVM.onSessionChanged)
    def setAvailableYears(self):
        """
        grabs available years from fastf1 api call
        if sys.currentyear > most recent year in db then call fastf1 api to get new data
        """
        print("change years available for selection")
    def setAvailableSessions(self):
        """
        once yearSelector is chosen ask fastf1 api 
        """
        print("change sessions available for review")
        