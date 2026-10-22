import sys

from PySide6.QtCore import Signal, Qt, QProcess, QProcessEnvironment
from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
)

from ViewModels.connectivityVM import ConnectivityVM


class LoginPage(QWidget):
    """Login popup. Shows the login form, or a prompt if there's no internet."""

    def __init__(self, connectionStatus: ConnectivityVM):
        super().__init__()
        self.connectionStatus = connectionStatus

        self.setWindowTitle("F1 Login")
        self.setWindowFlag(Qt.Dialog)  # opens as a popup window
        self.setWindowModality(Qt.ApplicationModal)  # blocks the main window
        self.resize(360, 260)

        layout = QVBoxLayout(self)
        self.prompt = ConnectionPrompt(connectionStatus=self.connectionStatus)
        self.form = LoginForm()
        layout.addWidget(self.prompt)
        layout.addWidget(self.form)

        self.form.loggedIn.connect(self.close)  # close popup after success

    # NOTE: Go based off of the signal from connectivityVM


class ConnectionPrompt(QFrame):
    """If the user is disconnected from the internet, ask them to connect."""

    def __init__(self, connectionStatus: ConnectivityVM):
        super().__init__()
        connectionStatus.onlineChanged.connect(self.connectionMessage)
        layout = QVBoxLayout(self)

        self.label = QLabel(
            "No internet connection.\nConnect to the internet to log in."
        )
        self.connectionMessage(isConnected=connectionStatus.isOnline)
        self.label.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.label)

    def connectionMessage(self, isConnected: bool):
        if isConnected:
            message = ""
        else:
            message = "No internet connection.\nConnect to the internet to log in."
        self.label.setText(message)


class LoginForm(QFrame):
    """Ask for login credentials, then hand them to FastF1."""

    loggedIn = Signal(bool)

    def __init__(self):
        super().__init__()

        # runs FastF1's auth command without freezing the UI
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.finished.connect(self.onFinished)

        layout = QVBoxLayout(self)

        self.emailInput = QLineEdit()
        self.emailInput.setPlaceholderText("Formula 1 account email")

        self.passwordInput = QLineEdit()
        self.passwordInput.setPlaceholderText("Password")
        self.passwordInput.setEchoMode(QLineEdit.Password)
        self.passwordInput.returnPressed.connect(self.login)

        self.loginBtn = QPushButton("Log in")
        self.loginBtn.clicked.connect(self.login)

        self.statusLabel = QLabel("")
        self.statusLabel.setWordWrap(True)

        layout.addWidget(QLabel("Sign in with your Formula 1 account"))
        layout.addWidget(self.emailInput)
        layout.addWidget(self.passwordInput)
        layout.addWidget(self.loginBtn)
        layout.addWidget(self.statusLabel)
        self.process.readyRead.connect(self.onOutput)

    def login(self):
        email = self.emailInput.text().strip()
        password = self.passwordInput.text()

        if not email or not password:
            self.statusLabel.setText("Enter your email and password.")
            return
        if self.process.state() != QProcess.NotRunning:
            return  # already logging in

        # FastF1 reads these two variables (only this subprocess gets them)
        env = QProcessEnvironment.systemEnvironment()

        env.insert("FASTF1_AUTH_METHOD", "password")
        env.insert("F1_USERNAME", email)
        env.insert("F1_PASSWORD", password)
        self.process.setProcessEnvironment(env)

        self.passwordInput.clear()  # don't keep the password in the UI
        self.loginBtn.setEnabled(False)
        self.statusLabel.setText("Logging in...")

        self.process.start(
            sys.executable, ["-u", "-m", "fastf1", "auth", "f1tv", "--authenticate"]
        )
        self.process.closeWriteChannel()

    def onOutput(self):
        text = bytes(self.process.readAllStandardOutput()).decode(errors="ignore")
        self.statusLabel.setText(text.strip()[-300:])
        print(f"\033[31m{text}\033[0m")

    def onFinished(self, exitCode, exitStatus):
        self.loginBtn.setEnabled(True)
        if exitCode == 0:
            self.statusLabel.setText("Logged in!")
            self.loggedIn.emit(True)
        else:
            output = bytes(self.process.readAllStandardOutput()).decode(errors="ignore")
            self.statusLabel.setText("Login failed:\n" + output.strip()[-300:])
