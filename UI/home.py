# basic test application
from PySide6.QtCore import Qt
from UI.Theme import theme
from ViewModels.raceSimulationVM import PlayControlsVM
from ViewModels.trackStatusVM import TrackStatusVM
from ViewModels.simulationGraphVM import SimulationCanvas
from ViewModels.sessionSelectorVM import SessionSelectorVM
from ViewModels.connectivityVM import ConnectivityVM
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
    QStyleFactory,
)

layoutColor: str = theme.info
gridMargin: int = 12
padding: int = 12
borderRadius: int = 20

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
                color: {theme.primaryText}      
        """
        )


class DriverCard(QFrame):
    """
    _UI element for the driver data being held within the driver placments area of the homepage_

    """

    def __init__(self, driverName, currentPlacement):
        super().__init__()


class TrackStatusCard(Card):
    """_creates a card that shows updated data from the trackStatusVM_"""

    def __init__(self, trackStatusVM: TrackStatusVM):
        super().__init__()
        self.statusStyles: dict = {
            "AllClear": theme.success,
            "Yellow": theme.warning,
            "Red": theme.danger,
            "VSCDeployed": theme.safety,
            "Idle": theme.info,
        }
        # self.setStyleSheet(f"""background-color: {theme.background}""")
        self.setStyleSheet("background-color: none")
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


class ComboBoxStyling(QComboBox):
    def __init__(self):
        super().__init__()
        self.setStyle(QStyleFactory.create("Fusion"))
        self.setStyleSheet(
            f"""
            QComboBox {{
                color: {theme.primaryText};
                border-radius: {borderRadius};
                padding: 2px;
            }}

            QComboBox::drop-down {{
                width: 14px;
                border: 1px solid {theme.secondaryText};

            }}
            """
        )


class PlayControlsUI(Card):
    """_Front-end for the PlayControls VM. this controls the user input for toggling play, scrubbing, and playback speed_

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
        self.SPEEDS: tuple = (1, 2, 4)
        # connect on duration change to the playControlsVM
        self.playControlsVM.updatedRaceDuration.connect(self.onDurationChange)
        self.playControlsVM.updatedTime.connect(self.onCurrentTimeChange)
        layout = QVBoxLayout(self)
        # scrub bar
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
        self.playButton.setFixedSize(40, 40)
        self.playButton.setStyleSheet(
            f"""background-color: {theme.background};
                color: {theme.primaryText};
                padding: {padding};
                border-radius: {borderRadius};
            """
        )
        """
        "QPushButton { padding: 6px 16px; border-radius: 6px;"
        "background-color: #e10600; color: white; font-weight: bold; }"
        "QPushButton:hover { background-color: #ff1e17; }"
        """

        self.playButton.clicked.connect(self._onClickPlay)

        # change playback speed
        self.speedBox = ComboBoxStyling()
        '''
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
        '''
        for s in self.SPEEDS:
            self.speedBox.addItem(f"{s}x", s)
        self.speedBox.setCurrentIndex(self.SPEEDS.index(1))
        self.speedBox.currentIndexChanged.connect(self._onPlaybackSpeedChanged)

        scrubRow.addWidget(self.playButton, alignment=Qt.AlignmentFlag.AlignVCenter)
        scrubRow.addWidget(self.speedBox)
        scrubRow.addWidget(self.currentTimeLabel)
        scrubRow.addWidget(self.scrubSlider, 1)
        scrubRow.addWidget(self.durationLabel)
        layout.addLayout(scrubRow)

    # on UI element change call viewModel.set{action} then have the set action updated a signal that the UI reads

    def _onClickPlay(self):
        """_send a signal to the playcontrolVM to stop the clock_"""
        print("user clicked play/pause")
        self.playControlsVM.togglePlay()
        if self.playControlsVM.getIsPlaying():
            self.playButton.setText("⏸")
        else:
            self.playButton.setText("▶")

    def _onSliderPressed(self):
        """_stop the playControls timer from updating the timer while the user is messing with the slider_"""
        # stop the slider from updating from currentTime changing
        self.playControlsVM.timer.blockSignals(True)
        self.sliderInUse = True

    def _onSliderReleased(self):
        """_unblock the playcontrols timer from updating_"""
        # allow the slider to update from currentTime changing
        self.playControlsVM.timer.blockSignals(False)
        self.sliderInUse = False

    def _onSliderValueChanged(self):
        """_set the playcontrolVM's timer to what the new value is_"""
        # take time that slider displays then set the currentTime in the playControls VM
        self.playControlsVM.setCurrentTime(self.scrubSlider.value())

    def _onPlaybackSpeedChanged(self, index=1):
        """_update the playControlsVM's variable for the playback speed to the new value up to 4x_"""
        print(f"playback speed changed to {self.speedBox.itemData(index)}")
        self.playControlsVM.setPlaybackSpeed(self.speedBox.itemData(index))
        # change playback speed

    def _formatTime(self, totalSeconds: float) -> str:
        """_Takes the arguement and converts it into a str that can be passed easily to the QLabel_

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
        # self.scrubSlider.blockSignals(True)
        self.raceDuration = newDuration
        self.formattedTime = self._formatTime(newDuration)
        self.scrubSlider.setRange(0, int(self.raceDuration))
        self.durationLabel.setText(self.formattedTime)
        # self.scrubSlider.blockSignals(False)


class HomePage(QWidget):
    """_Home page UI layout, instantiates different UI objects and places them on the homepage widget_"""

    def __init__(
        self,
        trackStatusViewModel: TrackStatusVM,
        playControlsViewModel: PlayControlsVM,
        sessionSelectorViewModel: SessionSelectorVM,
        conectivityViewModel: ConnectivityVM,
    ):
        super().__init__()
        # share the mem location of VMs
        self.trackStatusController = trackStatusViewModel
        self.playControlsController = playControlsViewModel
        self.sessionSelectorController = sessionSelectorViewModel

        # make a grid layout of 13x11ish
        # grid layout (rowstart, colstart, spanrows, spancols)
        gridLayout = QGridLayout(self)
        gridLayout.setSpacing(gridMargin)
        gridLayout.setSpacing(gridMargin)
        # setting the margins of the grid to a standard size
        gridLayout.setContentsMargins(gridMargin, gridMargin, gridMargin, gridMargin)
        # create the simulation frame
        driverSimFrame = DriverSIM(
            trackStatus=self.trackStatusController,
            playControlsController=self.playControlsController,
            sessionSelectorVM=self.sessionSelectorController,
        )
        gridLayout.addWidget(driverSimFrame, 1, 0, 3, 3)
        # create the session selector
        sessionFrame = SessionSelector(sessionSelectorViewModel, conectivityViewModel)
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
        self.playControlsController.fetchRaceDuration(
            self.sessionSelectorController.currentSessionID
        )


class DriverSIM(Card):
    """
    _UI for the visual race simulation where the drivers are placed on a graph and have their live gps data transmitted to move their vehicles_
    """

    def __init__(
        self,
        trackStatus: TrackStatusVM,
        playControlsController: PlayControlsVM,
        sessionSelectorVM: SessionSelectorVM,
    ):
        super().__init__()
        self.raceSimCanvas = SimulationCanvas(sessionSelectorVM=sessionSelectorVM)
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

    def __init__(
        self,
        sessionSelectorViewModel: SessionSelectorVM,
        conectivityViewModel: ConnectivityVM,
    ):
        super().__init__()
        self.sessionSelectorViewModel = sessionSelectorViewModel
        self.conectivityViewModel = conectivityViewModel
        self.conectivityViewModel.onlineChanged.connect(self.__onConnectionChange)
        self.sessionSelectorViewModel.availableListChanged.connect(
            self.__setAvailableYears
        )
        # self.sessionSelectorViewModel.availableList.connect(self.__setAvailableSessions)
        self.setMaximumHeight(50)
        # create and add a label for layout purposes
        layout = QHBoxLayout(self)
        layout.addWidget(QLabel("Current Session"))
        # year dropdown menu

        # TODO: insure that downloaded sessions are also in a separate section
        self.yearSelector = ComboBoxStyling()
        self.yearSelector.setPlaceholderText("Select Year")
        self.yearSelector.textActivated.connect(self.__setAvailableEvents)
        # seesion dropdown menu
        # TODO: on session selected load session into view
        self.eventSelector = ComboBoxStyling()
        self.eventSelector.setPlaceholderText("Select Event")
        self.eventSelector.textActivated.connect(self.__changeSimulatedSession)

        """
        TODO: for future implementation 
        self.sessionSelector = ComboBoxStyling()
        self.sessionSelector.setPlaceholderText("Select Session")
        """

        self.connectionLabel = QLabel("None")

        # call the connectivity setup after connectionLabel has been created
        self.conectivityViewModel.setup()

        layout.addWidget(self.yearSelector)
        layout.addWidget(self.eventSelector)
        # layout.addWidget(self.sessionSelector)
        layout.addWidget(self.connectionLabel)

        # self.yearSelector.currentIndexChanged.connect(self.onYearChanged)
        # self.sessionSelector.currentIndexChanged.connect(self.sessionSelectorVM.onSessionChanged)

        # def __updateComboBoxes(self):

    def __changeSimulatedSession(self) -> int:
        """_This runs when user selects a session within the race, it calls the sessionSelector method onRaceSelcted to start running a background thread to load the new
        race data_

        Return:
            _int_: _exits method block if yearText or eventText has no value_
        """
        # grab the text value from the QCombo boxes within the session Selector UI element
        yearText = self.yearSelector.currentText()
        eventText = self.eventSelector.currentText()

        # if empty exit
        if not yearText or not eventText:
            return 0

        # parsing the text into a dict
        sessionInfoDict: dict = {
            "year": int(yearText),
            "event_name": eventText,
            "session_type": "Race",
            "downloaded": not self.conectivityViewModel.isOnline,
        }
        # NOTE: debugging print statement remove in future issue
        print(f"sessionInfoDict: {sessionInfoDict}")
        # call sessionSelectorVM to start loading race data NOTE: Currently takes about 15 seconds to load on a intel i5 processor with 8G mem
        self.sessionSelectorViewModel.onRaceSelected(sessionInfoDict=sessionInfoDict)

    def __setAvailableYears(self) -> None:
        """
        _grabbing current year set from view model then sorting it to insure proper order, then add to yearSelector Combo Box UI element_
        """
        # print(f"home.py/__setAvailableYears : > attempting to set the session Selector Years value")
        # sort years earliest to latest
        years = sorted(self.sessionSelectorViewModel.currentYearSet)
        # clear previous data before appending new data
        self.yearSelector.clear()
        for year in years:
            self.yearSelector.addItem(str(year))

    def __setAvailableEvents(self, year: str) -> None:
        """
        set the eventSelector combobox depending on yearSelector text upon textActivated Signal update
        """
        yearInt = int(year)
        eventList: list = []
        # for each event in the available list put only the ones from selected year into event selector
        for event in self.sessionSelectorViewModel.availableList:
            if event["year"] == yearInt:
                # grab even_name from session
                eventName = event["event_name"]
                # if eventName is not in the list add it to the list
                if eventName not in eventList:
                    eventList.append(eventName)

        # clear and append items to selector combo box
        self.eventSelector.clear()
        self.eventSelector.addItems(eventList)

    # NOTE: future implementation because the code in loadsessionintodb doesn't dynamically allow any session type only race
    def __setAvailableSessions(self, year: str, event: str) -> None:
        """_set the sessionSelector combobox depending on year and event when eventSelector combox sends Signal update

        Args:
            year (str): _specified year used to search for available sessions_
            event (str): specified event used to search for available sessions
        """
        print("attempt to grab available sessions")

    def __onConnectionChange(self, isOnline: bool):
        """_updates the text of connectionLabel depending on if user has internet connection_

        Args:
            isOnline (bool): _value coming from a signal update from conectivityVM_
        """
        if isOnline:
            self.connectionLabel.setText("Online")
            self.connectionLabel.setStyleSheet(f"color: {theme.success}")
        else:
            self.connectionLabel.setText("Offline")
            self.connectionLabel.setStyleSheet(f"color: {theme.danger}")
