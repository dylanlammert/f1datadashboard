import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget
from PySide6.QtWidgets import (
    QHBoxLayout,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QFrame,
    QLabel,
    QSizePolicy,
)
from PySide6.QtGui import QPalette, Qt

from UI.home import HomePage
from UI.dataAnalysisPage import GraphCanvasContainer
from UI.driverProfiles import DriverProfiles
from UI.login import LoginPage

# Import VMs
"""
NOTE: are we placing these to 'high' are we allowing too many objects to view these VM's
"""
from ViewModels.driverProfilesVM import DriverProfilesViewModel
from ViewModels.raceSimulationVM import PlayControlsVM
from ViewModels.trackStatusVM import TrackStatusVM
from ViewModels.sessionSelectorVM import SessionSelectorVM
from ViewModels.connectivityVM import ConnectivityVM

# import dbhandler
from Services.dbhandler import DBhandler
from Services.database import create_schema
from Services.api_handler import get_race

# import token checker
from Services.api_handler import isTokenValid
# font styles
from UI.Theme import DayTheme

"""
Global Vars
"""
theme = DayTheme()
currentPageIndex = 0
backgroundColor = "#1A1A1A"
"""
@brief This is is the class describing UI components of the main window
        launched on startup
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("F1 Data Analysis")
        self.dbHandler = DBhandler()
        # instantiate the VMs
        self.conectivityVM = ConnectivityVM()
        self.driverProfilesVM = DriverProfilesViewModel()
        self.sessionSelectorVM = SessionSelectorVM(conectivityModel=self.conectivityVM)
        self.playControlsVM = PlayControlsVM(sessionSelectorVM=self.sessionSelectorVM)
        self.trackStatusVM = TrackStatusVM(
            playControlsVM=self.playControlsVM, sessionSelectorVM=self.sessionSelectorVM
        )
        # set the main container
        mainContainer = QWidget()
        self.setCentralWidget(mainContainer)
        # initialize all view models
        # create initialize track status view model
        # self.monitorTrackStatus = TrackStatusVM()
        # make the layout horizontal
        mainContainerLayout = QHBoxLayout(mainContainer)

        # create the stack for the different pages
        self.stack = QStackedWidget()

        # create the main elements and pass down the switch page function
        self.sidebar = Sidebar(self.switch_page, self.conectivityVM, self.sessionSelectorVM)
        # changed the 1st self to try to pass down currentPageIndx
        self.home = HomePage(
            trackStatusViewModel=self.trackStatusVM,
            playControlsViewModel=self.playControlsVM,
            sessionSelectorViewModel=self.sessionSelectorVM,
            conectivityViewModel=self.conectivityVM,
        )
        self.settings = GraphCanvasContainer(session_selector=self.sessionSelectorVM)
        # Removed the dbHandler object since the UI shouldn't be exposed to it (traditionally). If there's a reason it was here,
        self.driverProfiles = DriverProfiles(self.driverProfilesVM)

        # add the pages to the stack
        self.stack.addWidget(self.home)
        self.stack.addWidget(self.settings)
        self.stack.addWidget(self.driverProfiles)

        # add the sidebar and stack to the maincontainerlayout
        mainContainerLayout.addWidget(self.sidebar)
        mainContainerLayout.addWidget(self.stack)

        # run the token check 
        self.refreshLoginButton()
    """
    @brief this function changes the current index of the stack to
           change the current widget being shown
    """

    def switch_page(self, index):
        self.stack.setCurrentIndex(index)

    # NOTE: could fix this to use less lines
    def refreshLoginButton(self):
        valid = isTokenValid()
        if valid is not None:
            self.sidebar.loginButton.setVisible(not valid)
            self.sessionSelectorVM.userLoggedIn = False
        if valid is None:
            self.sidebar.loginButton.setVisible(True)
            self.sessionSelectorVM.userLoggedIn = False


"""
@brief Create a sidebar menu that appears on the left side of the screen
@param utilize the QWidget super class to handle the initialization
@notes change the button creation, you are basically making the same button 
       over and over again just change to a function or smth
"""


class Sidebar(QFrame):
    def __init__(self, switch_page, connectivityVM ,sessionSelectorVM):
        super().__init__()
        self.setFixedWidth(150)
        # self.setMaximumWidth(150)
        # self.setMinimumWidth(40)
        self.setAutoFillBackground(True)
        self.setBackgroundRole(QPalette.ColorRole.Base)
        self.setStyleSheet(
            f"""
                background-color: {backgroundColor};
                border-radius: 12px;        
            """
        )

        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.loginButton = LoginButton(connectivityVM=connectivityVM, sessionSelectorVM = sessionSelectorVM)
        self.layout.addWidget(self.loginButton)
        changePageBtn = QPushButton("Home")
        # removes window auto focussing to this button on launch
        changePageBtn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        changePageBtn.clicked.connect(lambda: switch_page(0))
        self.layout.addWidget(changePageBtn)

        changePageBtn = QPushButton("Data Analysis")
        changePageBtn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        changePageBtn.clicked.connect(lambda: switch_page(1))
        self.layout.addWidget(changePageBtn)

        changePageBtn = QPushButton("Driver Profiles")
        changePageBtn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        changePageBtn.clicked.connect(lambda: switch_page(2))
        self.layout.addWidget(changePageBtn)

    def removeLoginButton(self):
        self.layout.removeWidget(self.loginButton)
        self.loginButton.deleteLater()
        return

    """
    @brief styling function to add a background color to current page
    """

    def updateHightlight(self):
        print("update button highlight")


class LoginButton(QFrame):
    def __init__(self, connectivityVM: ConnectivityVM, sessionSelectorVM = SessionSelectorVM):
        super().__init__()
        sectionLayout = QVBoxLayout(self)
        self.connectivityVM = connectivityVM
        self.sessionSelector = sessionSelectorVM
        self.loginStatus: str = "login to F1TV to access online sessions"

        self.setObjectName("loginBox")
        self.setStyleSheet(
            f"""
            #loginBox {{
                border: 2px solid {theme.secondaryText};
                border-radius: 12px;
            }}
            """)
        loginlabel = QLabel(self.loginStatus)
        loginlabel.setWordWrap(True)
        loginlabel.setMinimumHeight(loginlabel.fontMetrics().height() * 4)
        
        loginButton = QPushButton("Login")
        loginButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        loginButton.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {theme.info};
                border: none;
                border-radius: 12px;
                padding: 4px;
            }}
            """
        )
        loginButton.clicked.connect(self.openLogin)

        # add to section layout
        sectionLayout.addWidget(loginlabel)
        sectionLayout.addWidget(loginButton)

    def openLogin(self):
        self.loginPage = LoginPage(connectionStatus=self.connectivityVM)
        self.loginPage.form.loggedIn.connect(self.onLoggedIn)
        self.loginPage.show()

    def onLoggedIn(self, success: bool):
        self.sessionSelector.userLoggedin = success

def _main():
    app = QApplication(sys.argv)
    # TODO: work on loading correct font
    #Theme.loadFonts()
    #app.setFont(Theme.fontStyles.qfont())
    # ! The app will not load without this. It needs to have a race loaded into the DB or everything breaks.
    if not Path("./f1_data.db"):
        create_schema()
        get_race(2026, "Japanese Grand Prix", "R")
     
    window = MainWindow()
    window.resize(700, 300)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    _main()
