
"""Interactive historical pit stop strategy panel for Ghost Racer."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QSpinBox, QPushButton, QPlainTextEdit,
)

from ML.pit_window import load_race_laps
from ML.strategy_insights import get_strategy_insights


class AIStrategyPanel(QWidget):
    """Display pit stop recommendations for a selected race and driver."""

    def __init__(self, session_id=0, parent=None):
        super().__init__(parent)
        self.session_id = 0
        self.laps = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        title = QLabel("AI PIT STOP STRATEGY")
        title.setObjectName("strategyTitle")
        layout.addWidget(title)

        subtitle = QLabel("Historical race strategy simulation")
        subtitle.setObjectName("strategySubtitle")
        layout.addWidget(subtitle)

        controls = QHBoxLayout()
        controls.setSpacing(12)

        controls.addWidget(QLabel("Driver"))
        self.driver_picker = QComboBox()
        self.driver_picker.setMinimumWidth(110)
        controls.addWidget(self.driver_picker)

        self.previous_driver = QPushButton("<")
        self.previous_driver.setFixedWidth(32)
        self.previous_driver.setToolTip("Previous driver")
        controls.addWidget(self.previous_driver)

        self.next_driver = QPushButton(">")
        self.next_driver.setFixedWidth(32)
        self.next_driver.setToolTip("Next driver")
        controls.addWidget(self.next_driver)

        controls.addWidget(QLabel("Current lap"))
        self.lap_picker = QSpinBox()
        self.lap_picker.setRange(1, 1)
        controls.addWidget(self.lap_picker)

        self.calculate_button = QPushButton("Calculate Strategy")
        controls.addWidget(self.calculate_button)
        controls.addStretch()

        layout.addLayout(controls)

        self.results = QPlainTextEdit()
        self.results.setReadOnly(True)
        self.results.setPlainText("Select a race to begin.")
        self.results.setObjectName("strategyResults")
        layout.addWidget(self.results, 1)

        footer = QLabel(
            "Uses race-wide tyre degradation and pit loss estimates. "
            "The model learns from completed race data."
        )
        footer.setObjectName("strategySubtitle")
        footer.setWordWrap(True)
        layout.addWidget(footer)

        self.setStyleSheet("""
            AIStrategyPanel {
                background-color: #1e1e1e;
                color: #eeeeee;
            }
            QLabel {
                color: #eeeeee;
                font-size: 13px;
            }
            QLabel#strategyTitle {
                color: #50dfca;
                font-size: 21px;
                font-weight: bold;
            }
            QLabel#strategySubtitle {
                color: #a0a0b0;
                font-size: 12px;
            }
            QPlainTextEdit#strategyResults {
                background-color: #252533;
                border-radius: 8px;
                padding: 18px;
                font-size: 15px;
            }
            QComboBox, QSpinBox {
                background-color: #292936;
                color: white;
                border: 1px solid #45455c;
                border-radius: 5px;
                padding: 6px;
            }
            QPushButton {
                background-color: #168e85;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 9px 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #20a99e;
            }
            QPushButton:disabled {
                background-color: #45455c;
            }
        """)

        self.driver_picker.currentTextChanged.connect(
            self._update_lap_range
        )
        self.previous_driver.clicked.connect(
            lambda: self._cycle_driver(-1)
        )
        self.next_driver.clicked.connect(
            lambda: self._cycle_driver(1)
        )
        self.calculate_button.clicked.connect(self.calculate)
        self.set_session(session_id)

    def _cycle_driver(self, direction):
        count = self.driver_picker.count()
        if count:
            index = (self.driver_picker.currentIndex() + direction) % count
            self.driver_picker.setCurrentIndex(index)

    def set_session(self, session_id):
        """Reload available drivers whenever the selected race changes."""
        self.session_id = int(session_id or 0)
        self.laps = None
        self.driver_picker.clear()
        self.calculate_button.setEnabled(False)

        if not self.session_id:
            self.results.setPlainText("Select a race to begin.")
            return

        try:
            self.laps = load_race_laps(self.session_id)
        except Exception as exc:
            self.results.setPlainText(f"Unable to load race data: {exc}")
            return

        drivers = sorted(
            self.laps["driver"].dropna().astype(str).unique()
        )
        self.driver_picker.addItems(drivers)
        self.calculate_button.setEnabled(bool(drivers))
        self._update_lap_range()
        self.results.setPlainText(
            "Select a driver and lap, then calculate the strategy."
        )

    def _update_lap_range(self, _text=None):
        if self.laps is None:
            return

        driver = self.driver_picker.currentText()
        selected = self.laps[self.laps["driver"] == driver]

        if selected.empty:
            self.lap_picker.setRange(1, 1)
            return

        maximum = int(selected["lap_number"].max())
        self.lap_picker.setRange(1, maximum)
        self.lap_picker.setValue(min(5, maximum))

    def calculate(self):
        driver = self.driver_picker.currentText()
        if not self.session_id or not driver:
            self.results.setPlainText("Select a race and driver first.")
            return

        try:
            result = get_strategy_insights(
                session_id=self.session_id,
                driver=driver,
                current_lap=self.lap_picker.value(),
            )

            plan = result["full_plan"]
            plan_lines = [
                f"Stop {index}: Lap {stop['pit_lap']} | "
                f"{stop['compound']} | {stop['stint_laps']} stint laps"
                for index, stop in enumerate(plan, 1)
            ]

            recommendation = result["recommended_pit_lap"]
            pit_lap = (
                str(recommendation)
                if recommendation is not None
                else "No further stop"
            )

            details = [
                f"Driver: {driver}",
                f"Current lap: {result['current_lap']}",
                f"Current tyres: {result['current_compound']}",
                f"Tyre age: {result['tyre_life']} laps",
                "",
                f"RECOMMENDED PIT LAP: {pit_lap}",
                f"NEXT TYRES: {result['next_compound'] or 'None'}",
                f"ESTIMATED PIT LOSS: {result['pit_loss_seconds']} seconds",
                "",
                result["message"],
                "",
                "FULL STRATEGY PLAN",
                *(plan_lines or ["No additional stops"]),
            ]

            self.results.setPlainText("\n".join(details))

        except Exception as exc:
            self.results.setPlainText(
                f"Strategy unavailable for this selection: {exc}"
            )
