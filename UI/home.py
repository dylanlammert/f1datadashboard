# basic test application
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from UI.Theme import theme, fontStyles
from ViewModels.raceSimulationVM import PlayControlsVM
from ViewModels.trackStatusVM import TrackStatusVM
from ViewModels.simulationGraphVM import SimulationCanvas
from ViewModels.sessionSelectorVM import SessionSelectorVM
from ViewModels.connectivityVM import ConnectivityVM
from ViewModels.driverStandingsVM import (
    DriverStandingsViewModel,
    FocusDriverVM,
)
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
    QProgressBar,
    QScrollArea,
    QSizePolicy,
)

layoutColor: str = theme.info
gridMargin: int = 12
padding: int = 12
borderRadius: int = 20
labelPadding: int = 2

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


class TrackStatusCard(Card):
    """_creates a card that shows updated data from the trackStatusVM_"""

    def __init__(self, trackStatusVM: TrackStatusVM):
        super().__init__()
        self.statusStyles: dict = {
            "AllClear": theme.success,
            "Yellow": theme.warning,
            "Red": theme.danger,
            "VSCDeployed": theme.safety,
            "SCDeployed": theme.safety,
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
    """_styling for the combo boxes_

    Args:
        QComboBox (Pyside6 Object): _init. to the super class_
    """

    dropDownWidth = 24

    def __init__(self):
        super().__init__()
        self.setStyle(QStyleFactory.create("Fusion"))
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        chevronPath = Path(__file__).resolve().parent / "images" / "downChevron.png"
        self.setStyleSheet(
            f"""
            QComboBox {{
                color: {theme.primaryText};
                border: none;
                border-bottom: 1px solid {theme.primaryText};
                border-radius: 0;
                padding: 2px;
            }}

            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: {self.dropDownWidth}px;
                border: none;
            }}
            QComboBox::down-arrow {{
                image: none;
            }}
            """
        )
        self.chevronLabel = QLabel(self)
        self.chevronLabel.setPixmap(QPixmap(str(chevronPath)))
        self.chevronLabel.setScaledContents(True)
        self.chevronLabel.setFixedSize(18, 18)
        self.chevronLabel.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        horizontalOffset = (self.dropDownWidth - self.chevronLabel.width()) // 2
        self.chevronLabel.move(
            self.width() - self.dropDownWidth + horizontalOffset,
            (self.height() - self.chevronLabel.height()) // 2,
        )


# NOTE: fix issue with buffer UI
class RaceMarkerSlider(QSlider):
    def __init__(self, orientation):
        super().__init__(orientation)
        self.raceStartTime: float | None = None
        self.raceEndTime: float | None = None
        self.startLabel, self.startLine = self._createMarker("S", theme.success)
        self.finishLabel, self.finishLine = self._createMarker("F", theme.danger)
        self.rangeChanged.connect(self._onRangeChanged)

    def _createMarker(self, labelText: str, color: str) -> tuple[QLabel, QFrame]:
        label = QLabel(labelText, self)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFixedSize(12, 12)
        label.setStyleSheet(
            f"color: {color}; background: transparent; font-size: 9px; font-weight: bold;"
        )
        line = QFrame(self)
        line.setFixedWidth(2)
        line.setStyleSheet(f"background-color: {color}; border: none;")
        for marker in (label, line):
            marker.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        label.hide()
        line.hide()
        return label, line

    def setRaceMarkers(
        self, raceStartTime: float | None, raceEndTime: float | None
    ) -> None:
        self.raceStartTime = raceStartTime
        self.raceEndTime = raceEndTime
        self._positionMarkers()

    def _onRangeChanged(self, minimum: int, maximum: int) -> None:
        self._positionMarkers()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._positionMarkers()

    def _positionMarkers(self) -> None:
        valueRange = self.maximum() - self.minimum()
        if valueRange <= 0 or self.width() <= 0:
            return

        markerWidth = max(0, self.width() - 13)
        for markerTime, label, line in (
            (self.raceStartTime, self.startLabel, self.startLine),
            (self.raceEndTime, self.finishLabel, self.finishLine),
        ):
            if markerTime is None:
                label.hide()
                line.hide()
                continue

            markerTime = max(self.minimum(), min(markerTime, self.maximum()))
            markerX = 6 + round(
                (markerTime - self.minimum()) / valueRange * markerWidth
            )
            labelX = max(0, min(self.width() - label.width(), markerX - 6))
            lineX = max(0, min(self.width() - line.width(), markerX - 1))
            label.move(labelX, 0)
            line.setGeometry(lineX, 12, 2, max(0, self.height() - 12))
            label.show()
            line.show()


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
        self.setFixedHeight(68)
        # VMs
        self.playControlsVM = playControlsController
        self.raceDuration: float = 0.00
        self.driverRaceTime: float = 0.00
        self.availablePlaybackTime: float = 0.00
        self.formattedTime: str = "00:00:00"
        self.SPEEDS: tuple = (1, 2, 4)
        # connect on duration change to the playControlsVM
        self.playControlsVM.updatedRaceDuration.connect(self.onDurationChange)
        self.playControlsVM.updatedDriverRaceTime.connect(self.onDriverRaceTimeChange)
        self.playControlsVM.updatedRaceMarkers.connect(self.onRaceMarkersChange)
        self.playControlsVM.updatedTime.connect(self.onCurrentTimeChange)
        # show buffer available
        self.playControlsVM.updatedPlaybackBuffer.connect(self.onBufferUpdated)
        layout = QVBoxLayout(self)
        # scrub bar
        scrubRow = QHBoxLayout()
        self.currentTimeLabel = QLabel("00:00:00")
        self.currentTimeLabel.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.currentTimeLabel.setFixedWidth(
            self.currentTimeLabel.fontMetrics().horizontalAdvance("00:00:00")
        )
        # ? I had to change this to Qt.Orientation.Horizontal to get it to compile for some reason. Apparently it's a newer change with PySide6?
        # create the slider NOTE: might want to make this it's own class later on
        self.scrubSlider = RaceMarkerSlider(Qt.Orientation.Horizontal)
        self.scrubSlider.setMinimumHeight(28)
        self.scrubSlider.setTracking(True)
        self.scrubSlider.setRange(0, 100)  # will be rescaled once duration is known
        self.durationLabel = QLabel(self.formattedTime)
        self.bufferProgress = QProgressBar()
        self.bufferProgress.setRange(0, 1000)
        self.bufferProgress.setTextVisible(False)
        self.bufferProgress.setFixedHeight(4)
        self.bufferProgress.setStyleSheet(
            f"""
            QProgressBar {{
                background-color: {theme.tertiaryText};
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {theme.info};
                border-radius: 2px;
            }}
            """
        )
        self.scrubSlider.setStyleSheet(
            f"""
            QSlider::groove:horizontal {{
                background: {theme.tertiaryText};
                border: none;
                height: 4px;
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background-color: {theme.primaryText};
                border: 1px solid {theme.background};
                width: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }}
            QSlider::chunk {{
                background-color: {theme.primaryText};
            }}
            """
        )
        sliderLayout = QVBoxLayout()
        sliderLayout.setContentsMargins(6, 0, 6, 0)
        sliderLayout.setSpacing(0)
        sliderLayout.addWidget(self.scrubSlider)
        sliderLayout.addWidget(self.bufferProgress)
        sliderContainer = QWidget()
        sliderContainer.setLayout(sliderLayout)
        # set the signal changes
        self.scrubSlider.valueChanged.connect(self._onSliderValueChanged)
        self.scrubSlider.sliderPressed.connect(self._onSliderPressed)
        self.scrubSlider.sliderReleased.connect(self._onSliderReleased)
        # is slider being messed with
        self.sliderInUse: bool = False
        self.wasPlayingBeforeScrub: bool = False

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
        self.playControlsVM.updatedPlayingStatus.connect(self.updatePlayButtonValue)
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
        scrubRow.addWidget(sliderContainer, 1)
        scrubRow.addWidget(self.durationLabel)
        layout.addLayout(scrubRow)

    # on UI element change call viewModel.set{action} then have the set action updated a signal that the UI reads

    def _onClickPlay(self):
        """_send a signal to the playcontrolVM to stop the clock_"""
        print("user clicked play/pause")
        self.playControlsVM.togglePlay()

    def updatePlayButtonValue(self, toggleValue):
        if toggleValue:
            self.playButton.setText("⏸")
        else:
            self.playButton.setText("▶")

    def _onSliderPressed(self):
        """Pause playback while scrubbing so timer ticks cannot overwrite the seek."""
        self.sliderInUse = True
        self.wasPlayingBeforeScrub = self.playControlsVM.getIsPlaying()
        if self.wasPlayingBeforeScrub:
            self.playControlsVM.togglePlay()
            self.playButton.setText("▶")

    def _onSliderReleased(self):
        """Resume playback after scrubbing if it was playing before the drag."""
        self.sliderInUse = False
        if self.wasPlayingBeforeScrub:
            self.playControlsVM.togglePlay()
            self.playButton.setText("⏸")
        self.wasPlayingBeforeScrub = False

    def _onSliderValueChanged(self, value: int):
        """Send each slider change to the playback VM so its consumers update."""
        self.playControlsVM.setCurrentTime(float(value))

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
        if not self.sliderInUse:
            wasBlocked = self.scrubSlider.blockSignals(True)
            self.scrubSlider.setValue(round(newCurrentTime))
            self.scrubSlider.blockSignals(wasBlocked)

    def onDurationChange(self, newDuration):
        # self.scrubSlider.blockSignals(True)
        self.raceDuration = newDuration
        self.formattedTime = self._formatTime(newDuration)
        self.scrubSlider.setRange(0, int(self.raceDuration))
        self.durationLabel.setText(self.formattedTime)

    def onDriverRaceTimeChange(self, newDriverRaceTime: float):
        self.driverRaceTime = max(0.0, newDriverRaceTime)
        self.onBufferUpdated(self.availablePlaybackTime)

    def onRaceMarkersChange(self, raceStartTime: float, raceEndTime: float):
        self.scrubSlider.setRaceMarkers(
            raceStartTime if raceStartTime >= 0 else None,
            raceEndTime if raceEndTime >= 0 else None,
        )
        # self.scrubSlider.blockSignals(False)

    def onBufferUpdated(self, newTime: float):
        self.availablePlaybackTime = max(0.0, min(newTime, self.driverRaceTime))
        if self.driverRaceTime > 0:
            progress = round(self.availablePlaybackTime / self.driverRaceTime * 1000)
            self.bufferProgress.setValue(progress)
        else:
            self.bufferProgress.setValue(0)
        return


class HomePage(QWidget):
    """_Home page UI layout, instantiates different UI objects and places them on the homepage widget_"""

    def __init__(
        self,
        trackStatusViewModel: TrackStatusVM,
        playControlsViewModel: PlayControlsVM,
        sessionSelectorViewModel: SessionSelectorVM,
        conectivityViewModel: ConnectivityVM,
        driverStandingsVM: DriverStandingsViewModel,
        focusDriverVM: FocusDriverVM,
    ):
        super().__init__()
        # share the mem location of VMs
        self.trackStatusController = trackStatusViewModel
        self.playControlsController = playControlsViewModel
        self.sessionSelectorController = sessionSelectorViewModel
        self.driverStandingsVM = driverStandingsVM
        self.focusDriverVM = focusDriverVM

        # make a grid layout of 13x11ish
        # grid layout (rowstart, colstart, spanrows, spancols)
        gridLayout = QGridLayout(self)
        gridLayout.setSpacing(gridMargin)
        gridLayout.setSpacing(gridMargin)
        # setting the margins of the grid to a standard size
        gridLayout.setContentsMargins(gridMargin, gridMargin, gridMargin, gridMargin)
        # Reserve flexible vertical space for the simulation instead of its controls.
        for row in (1, 2, 3):
            gridLayout.setRowStretch(row, 1)
        for column in (0, 1, 2):
            gridLayout.setColumnStretch(column, 1)
        # create the simulation frame
        driverSimFrame = DriverSIM(
            trackStatus=self.trackStatusController,
            playControlsController=self.playControlsController,
            sessionSelectorVM=self.sessionSelectorController,
        )
        gridLayout.addWidget(driverSimFrame, 1, 0, 3, 2)
        # create the session selector
        sessionFrame = SessionSelector(sessionSelectorViewModel, conectivityViewModel)
        gridLayout.addWidget(sessionFrame, 0, 0, 1, 2)
        # create the driver placement UI
        driverStandingsFrame = DriverStandings(driverStandingsVM=self.driverStandingsVM)
        gridLayout.addWidget(driverStandingsFrame, 0, 2, 4, 2)
        # create the focussed driver telemetry card
        self.driverTelemetryCards = [DriverTelemetry(), DriverTelemetry()]
        for row, telemetryCard in enumerate(self.driverTelemetryCards, start=4):
            gridLayout.addWidget(telemetryCard, row, 0, 1, 4)
        self.focusDriverVM.currentDataChanged.connect(self.updateFocusedDriverTelemetry)
        # NOTE: this should not control this, make playControls fetch this on init call the playControlsVM to fetch the race duration
        self.playControlsController.fetchRaceDuration(
            self.sessionSelectorController.currentSessionID
        )

    def updateFocusedDriverTelemetry(self, currentData: list[dict]) -> None:
        for index, telemetryCard in enumerate(self.driverTelemetryCards):
            data = currentData[index] if index < len(currentData) else None
            telemetryCard.updateTelemetry(data)


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
        self.raceSimCanvas.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.raceSimCanvas.setMinimumSize(0, 0)
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
        layout.addWidget(self.raceSimCanvas, 1)
        self.trackStatusCard = TrackStatusCard(trackStatus)
        self.trackStatusCard.setParent(self)
        self.trackStatusCard.raise_()
        layout.addWidget(self.playControlsUI)


class DriverCard(QPushButton):
    """_card to hold driver data within the driver standings ui component_

    Args:
        Card (_type_): _description_

    NOTE:
    * This needs to be a button to update the focused driver VM aswell
    * If a single driver card is clicked it needs to ask the VM to change focusDrivers if it does then it needs to change the color of the card
    *
    """

    def __init__(
        self,
        driverCode: str,
        driverFullName: str,
        driverTeam: str,
        timeBehind: float | str | None,
        position: int,
        positionDifference: int,
    ):
        super().__init__()
        self.setMinimumHeight(40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(f"Focus {driverCode}")
        self.setToolTip(f"Focus on {driverCode}")
        self.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {theme.background};
                border: none;
                border-radius: {borderRadius}px;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {theme.info};
            }}
            QPushButton[focused="true"] {{
                background-color: {theme.info};
            }}
            QPushButton:focus {{
                border: 1px solid {theme.info};
            }}
            """
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(padding, 6, padding, 6)
        layout.setSpacing(padding)

        teamLabel = QLabel(driverTeam or "Unknown team")
        teamLabel.setStyleSheet(
            f"background: transparent; color: {theme.secondaryText};"
        )

        gapLabel = QLabel(self._formatGap(timeBehind, position))
        gapLabel.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        gapLabel.setStyleSheet(
            f"background: transparent; color: {theme.primaryText}; font-weight: bold;"
        )

        layout.addLayout(self._positionDataContainer(position, positionDifference))
        layout.addLayout(self._driverContainer(driverCode, driverFullName))
        layout.addWidget(teamLabel, 1)
        layout.addWidget(gapLabel)

    def setFocused(self, focused: bool) -> None:
        self.setProperty("focused", focused)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    @staticmethod
    def _formatGap(timeBehind: float | str | None, position: int) -> str:
        if position == 1:
            return "LEADER"
        if timeBehind is None:
            return "--"
        if isinstance(timeBehind, (int, float)):
            return f"+{timeBehind:.3f}s"
        return str(timeBehind)

    @staticmethod
    def _driverContainer(driverCode: str, driverFullName: str) -> QVBoxLayout:
        driverLayout = QVBoxLayout()
        driverLayout.setContentsMargins(0, 0, 0, 0)
        driverLayout.setSpacing(0)

        driverLabel = QLabel(driverCode)
        driverLabel.setStyleSheet(
            f"background: transparent; color: {theme.primaryText}; font-weight: bold;"
        )
        driverNameLabel = QLabel(driverFullName)
        driverNameLabel.setStyleSheet(
            f"background: transparent; color: {theme.secondaryText}; font-size: 10px;"
        )

        driverLayout.addWidget(driverLabel)
        driverLayout.addWidget(driverNameLabel)
        return driverLayout

    @staticmethod
    def _positionDataContainer(
        currentPosition: int, positionDifference: int | None
    ) -> QHBoxLayout:
        positionLayout = QHBoxLayout()
        positionLayout.setSpacing(2)

        positionLabel = QLabel(str(currentPosition))
        positionLabel.setFixedWidth(24)
        positionLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        positionLabel.setStyleSheet(
            f"background: transparent; color: {theme.primaryText}; font-weight: bold;"
        )

        if positionDifference is None or positionDifference == 0:
            differenceText = "-"
            differenceColor = theme.secondaryText
            tooltip = "No position change"
        elif positionDifference > 0:
            differenceText = f"\u2191{positionDifference}"
            differenceColor = theme.success
            tooltip = f"Gained {positionDifference} positions"
        else:
            differenceText = f"\u2193{abs(positionDifference)}"
            differenceColor = theme.danger
            tooltip = f"Lost {abs(positionDifference)} positions"

        positionDifferenceLabel = QLabel(differenceText)
        positionDifferenceLabel.setStyleSheet(
            f"background: transparent; color: {differenceColor}; font-size: 10px;"
        )
        positionDifferenceLabel.setToolTip(tooltip)

        positionLayout.addWidget(positionLabel)
        positionLayout.addWidget(positionDifferenceLabel)
        return positionLayout


class DriverStandings(Card):
    """
    _this holds all of the Driver Cards for a specified race_
    """

    def __init__(self, driverStandingsVM: DriverStandingsViewModel):
        super().__init__()
        self.driverStandingsVM = driverStandingsVM
        layout = QVBoxLayout(self)
        title = QLabel("Driver Standings")
        title.setStyleSheet(
            f"background: transparent; color: {theme.primaryText}; font-weight: bold;"
        )
        layout.addWidget(title)

        self.standingsList = QVBoxLayout()
        self.standingsList.setContentsMargins(0, 0, 0, 0)
        self.standingsList.setSpacing(6)
        self.standingsContainer = QWidget()
        self.standingsContainer.setStyleSheet("background: transparent;")
        self.standingsContainer.setLayout(self.standingsList)

        scrollArea = QScrollArea()
        scrollArea.setWidgetResizable(True)
        scrollArea.setFrameShape(QFrame.Shape.NoFrame)
        scrollArea.setStyleSheet("background: transparent;")
        scrollArea.setWidget(self.standingsContainer)
        layout.addWidget(scrollArea)

        self._showEmptyState()
        self.driverStandingsVM.standings_changed.connect(self.standingsBuilder)

    def standingsBuilder(self, standingsList: list):
        self._clearStandings()
        if not standingsList:
            self._showEmptyState()
            return

        currentFocusDrivers = self.driverStandingsVM.getFocusDrivers()
        for position, driver in enumerate(standingsList, start=1):
            driverCode = driver.get("driverCode", driver.get("driver_code")) or "???"
            team = driver.get("team") or "Unknown team"
            timeBehind = driver.get("timeBehind", driver.get("time_behind"))
            driverFullName = driver.get("driverName")
            positionDifference = driver.get("positionDifference")
            driverCard = DriverCard(
                driverCode=str(driverCode),
                driverFullName=str(driverFullName),
                driverTeam=str(team),
                timeBehind=timeBehind,
                position=driver.get("position", position),
                positionDifference=positionDifference,
            )
            if driverCode in currentFocusDrivers:
                driverCard.setFocused(True)

            driverCard.clicked.connect(
                lambda _checked=False, code=str(driverCode), card=driverCard: (
                    card.setFocused(self.driverStandingsVM.onDriverToggled(code))
                )
            )
            self.standingsList.addWidget(driverCard)
        self.standingsList.addStretch()

    def _clearStandings(self) -> None:
        while self.standingsList.count():
            item = self.standingsList.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _showEmptyState(self) -> None:
        emptyLabel = QLabel("No driver standings available.")
        emptyLabel.setWordWrap(True)
        emptyLabel.setStyleSheet(
            f"background: transparent; color: {theme.secondaryText};"
        )
        self.standingsList.addWidget(emptyLabel)
        self.standingsList.addStretch()


# UI helper
def _telemetryLabel(
    text: str, size: int = 11, color: str | None = None, bold: bool = False
) -> QLabel:
    """_small helper so every label in the telemetry card shares the same font and a transparent background_"""
    label = QLabel(text)
    label.setStyleSheet(
        f"""
        background: transparent;
        color: {color or theme.secondaryText};
        font-size: {size}px;
        font-weight: {"bold" if bold else "normal"};
        """
    )
    return label


# UI helper classes for driver telemetry
class StatCard(QWidget):
    """_a small caption above a big value, with an optional unit ([SPEED] KM/H)_"""

    def __init__(
        self,
        title: str,
        value: str = "--",
        unit: str = "",
        valueColor: str | None = None,
        valueSize: int = 28,
    ):
        super().__init__()
        self.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(_telemetryLabel(title.upper(), 10))

        valueRow = QHBoxLayout()
        valueRow.setSpacing(4)
        self.valueLabel = _telemetryLabel(
            value, valueSize, valueColor or theme.primaryText, bold=True
        )
        valueRow.addWidget(self.valueLabel, alignment=Qt.AlignmentFlag.AlignBottom)
        if unit:
            valueRow.addWidget(
                _telemetryLabel(unit, 11), alignment=Qt.AlignmentFlag.AlignBottom
            )
        valueRow.addStretch()
        layout.addLayout(valueRow)

    def setValue(self, value: str) -> None:
        self.valueLabel.setText(value)


class MeterBar(QWidget):
    """_labelled progress bar with a percent readout (THROTTLE PRESSURE 75%)_"""

    def __init__(self, title: str, color: str):
        super().__init__()
        self.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.addWidget(_telemetryLabel(title.upper(), 10, color, bold=True))
        header.addStretch()
        self.percentLabel = _telemetryLabel("0%", 10, color, bold=True)
        header.addWidget(self.percentLabel)
        layout.addLayout(header)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        self.bar.setStyleSheet(
            f"""
            QProgressBar {{
                background-color: {theme.tertiaryText};
                border: none;
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 4px;
            }}
            """
        )
        layout.addWidget(self.bar)

    def setPercent(self, percent: float) -> None:
        percent = max(0, min(100, int(round(percent))))
        self.bar.setValue(percent)
        self.percentLabel.setText(f"{percent}%")


class DriverRow(QHBoxLayout):
    def __init__(self):
        super().__init__()

        self.setSpacing(padding)

        self.driverBadge = QLabel("No Driver")
        self.driverBadge.setStyleSheet(
            f"""
            background-color: {theme.success};
            color: #0B0E14;
            font-size: 12px;
            font-weight: bold;
            padding: 4px 12px;
            border-radius: 6px;
            """
        )

        self.competitorLabel = QLabel("Closest Competitor| --")
        self.competitorLabel.setStyleSheet(
            f"""
            background-color: transparent;
            color: {theme.secondaryText};
            font-size: 12px;
            padding: 4px 12px;
            border: 1px solid {theme.info};
            border-radius: 6px;
            """
        )

        self.addWidget(self.driverBadge)
        self.addWidget(self.competitorLabel)
        self.fastestLap = self.__lapBlock("Fastest Lap")
        self.currentLapTime = self.__lapBlock("Current Lap")
        # NOTE is this the best way to build this out?
        self.addLayout(self.fastestLap[0])
        self.addLayout(self.currentLapTime[0])
        self.addStretch()

    # builder for the lap data in driver telem top right side
    def __lapBlock(
        self, title: str, color: str = theme.secondaryText
    ) -> tuple[QVBoxLayout, QLabel]:
        layout = QVBoxLayout()
        layout.setSpacing(labelPadding)
        layout.addWidget(
            _telemetryLabel(title, 10), alignment=Qt.AlignmentFlag.AlignRight
        )
        lapValue = _telemetryLabel("__:__", fontStyles.text, color, bold=True)
        layout.addWidget(lapValue, alignment=Qt.AlignmentFlag.AlignRight)
        return layout, lapValue

    def updateTelemetry() -> None:
        print("stub")


class DataRow(QHBoxLayout):
    def __init__(self):
        super().__init__()

        self.setSpacing(padding)
        self.speedCard = StatCard("Speed", "__", "KM/H")
        self.gearCard = StatCard("Gear", "__", valueColor=theme.success)
        self.rpmCard = StatCard("RPM", "__", valueSize=20)
        self.throttleMeter = MeterBar("Throttle Pressure", theme.success)
        self.breakCard = StatCard("Brakes", "--", valueColor=theme.danger)
        self.drsCard = StatCard("DRS", "--", valueColor=theme.warning)
        self.addWidget(self.speedCard)
        self.addWidget(self.gearCard)
        self.addWidget(self.rpmCard)
        self.addWidget(self.throttleMeter)
        self.addWidget(self.breakCard)
        self.addWidget(self.drsCard)


class DriverTelemetry(Card):
    """
    _showcase the focussed driver's live telemetry_

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

    def __init__(self):
        super().__init__()
        self.setMaximumHeight(100)
        layout = QVBoxLayout(self)

        self.driverRow = DriverRow()
        layout.addLayout(self.driverRow)

        self.dataRow = DataRow()
        layout.addLayout(self.dataRow)

    # builder for the lap data in driver telem top right side
    def __lapBlock(
        self, title: str, color: str = theme.secondaryText
    ) -> tuple[QVBoxLayout, QLabel]:
        layout = QVBoxLayout()
        layout.setSpacing(labelPadding)
        layout.addWidget(
            _telemetryLabel(title, 10), alignment=Qt.AlignmentFlag.AlignRight
        )
        lapValue = _telemetryLabel("__:__", fontStyles.text, color, bold=True)
        layout.addWidget(lapValue, alignment=Qt.AlignmentFlag.AlignRight)
        return layout, lapValue

    def updateTelemetry(self, data: dict | None) -> None:
        if not data:
            self.driverRow.driverBadge.setText("No Driver")
            self.driverRow.competitorLabel.setText("Closest Competitor | --")
            self.dataRow.speedCard.setValue("--")
            self.dataRow.gearCard.setValue("--")
            self.dataRow.rpmCard.setValue("--")
            self.dataRow.throttleMeter.setPercent(0)
            self.dataRow.breakCard.setValue("--")
            self.dataRow.drsCard.setValue("--")
            return

        driverCode = data.get("driver_code") or "Unknown Driver"
        self.driverRow.driverBadge.setText(str(driverCode))
        distance = data.get("distance_to_driver_ahead")
        self.driverRow.competitorLabel.setText(
            "Closest Competitor | "
            + (f"{distance:.1f}" if isinstance(distance, (int, float)) else "--")
        )
        self.dataRow.speedCard.setValue(self._formatValue(data.get("speed")))
        self.dataRow.gearCard.setValue(self._formatValue(data.get("gear")))
        self.dataRow.rpmCard.setValue(self._formatValue(data.get("rpm")))

        throttle = data.get("throttle")
        self.dataRow.throttleMeter.setPercent(
            throttle if isinstance(throttle, (int, float)) else 0
        )
        brake = data.get("brake")
        self.dataRow.breakCard.setValue(
            "--" if brake is None else "ON" if brake else "OFF"
        )
        drs = data.get("drs")
        self.dataRow.drsCard.setValue("--" if drs is None else "ON" if drs else "OFF")

    @staticmethod
    def _formatValue(value) -> str:
        if value is None:
            return "--"
        if isinstance(value, float):
            return f"{value:.0f}"
        return str(value)


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
        layout.addStretch(1)
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
            "downloaded": any(
                s["year"] == int(yearText)
                and s["event_name"] == eventText
                and s["session_type"] == "Race"
                for s in self.sessionSelectorViewModel.localSessions
            ),
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
