
"""Interactive historical race strategy What-If Simulator."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QSpinBox, QPushButton, QPlainTextEdit,
)

from ML.pit_window import load_race_laps
from ML.strategy_what_if import (
    compare_pit_strategies,
    get_supported_compounds,
)


class AIWhatIfPanel(QWidget):
    """Compare a custom pit stop against an optimized baseline."""

    def __init__(self, session_id=0, parent=None):
        super().__init__(parent)
        self.session_id = 0
        self.laps = None
        self.total_laps = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        title = QLabel("AI RACE STRATEGY WHAT-IF SIMULATOR")
        title.setObjectName("simTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "Compare custom pit stops using historical tyre-wear estimates"
        )
        subtitle.setObjectName("simSubtitle")
        layout.addWidget(subtitle)

        driver_row = QHBoxLayout()
        driver_row.addWidget(QLabel("Driver"))
        self.driver_picker = QComboBox()
        self.driver_picker.setMinimumWidth(95)
        driver_row.addWidget(self.driver_picker)

        self.previous_driver = QPushButton("<")
        self.next_driver = QPushButton(">")
        for button in (self.previous_driver, self.next_driver):
            button.setFixedWidth(32)
            driver_row.addWidget(button)

        driver_row.addStretch()
        layout.addLayout(driver_row)

        lap_row = QHBoxLayout()
        lap_row.addWidget(QLabel("Current lap"))
        self.current_lap = QSpinBox()
        self.current_lap.setRange(1, 1)
        lap_row.addWidget(self.current_lap)

        lap_row.addWidget(QLabel("Custom pit lap"))
        self.custom_pit_lap = QSpinBox()
        self.custom_pit_lap.setRange(2, 2)
        lap_row.addWidget(self.custom_pit_lap)

        lap_row.addStretch()
        layout.addLayout(lap_row)

        tyre_row = QHBoxLayout()
        tyre_row.addWidget(QLabel("Next tyres"))
        self.compound_picker = QComboBox()
        self.compound_picker.setMinimumWidth(110)
        tyre_row.addWidget(self.compound_picker)

        self.previous_compound = QPushButton("<")
        self.next_compound = QPushButton(">")
        for button in (
            self.previous_compound,
            self.next_compound,
        ):
            button.setFixedWidth(32)
            tyre_row.addWidget(button)

        tyre_row.addStretch()
        layout.addLayout(tyre_row)

        self.compare_button = QPushButton("Compare Strategies")
        layout.addWidget(self.compare_button)

        self.results = QPlainTextEdit()
        self.results.setObjectName("simResults")
        self.results.setReadOnly(True)
        self.results.setPlainText("Select a race to begin.")
        layout.addWidget(self.results, 1)

        footer = QLabel(
            "Historical simulation only. Costs are relative model "
            "estimates, not predicted finishing times or positions."
        )
        footer.setObjectName("simSubtitle")
        footer.setWordWrap(True)
        layout.addWidget(footer)

        self.setStyleSheet("""
            AIWhatIfPanel {
                background-color: #1e1e1e;
                color: #eeeeee;
            }
            QLabel {
                color: #eeeeee;
                font-size: 13px;
            }
            QLabel#simTitle {
                color: #50dfca;
                font-size: 19px;
                font-weight: bold;
            }
            QLabel#simSubtitle {
                color: #a0a0b0;
                font-size: 12px;
            }
            QPlainTextEdit#simResults {
                background-color: #252533;
                color: #eeeeee;
                border: none;
                border-radius: 8px;
                padding: 12px;
                font-size: 13px;
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
                padding: 8px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #20a99e;
            }
            QPushButton:disabled {
                background-color: #45455c;
            }
        """)

        self.previous_driver.clicked.connect(
            lambda: self._cycle(self.driver_picker, -1)
        )
        self.next_driver.clicked.connect(
            lambda: self._cycle(self.driver_picker, 1)
        )
        self.previous_compound.clicked.connect(
            lambda: self._cycle(self.compound_picker, -1)
        )
        self.next_compound.clicked.connect(
            lambda: self._cycle(self.compound_picker, 1)
        )
        self.driver_picker.currentTextChanged.connect(
            self._update_driver
        )
        self.current_lap.valueChanged.connect(
            self._update_pit_range
        )
        self.compare_button.clicked.connect(self.compare)

        self.set_session(session_id)

    def _cycle(self, picker, direction):
        count = picker.count()
        if count:
            picker.setCurrentIndex(
                (picker.currentIndex() + direction) % count
            )

    def set_session(self, session_id):
        """Load drivers and available compounds for a race."""
        self.session_id = int(session_id or 0)
        self.laps = None
        self.total_laps = 0
        self.compare_button.setEnabled(False)
        self.driver_picker.clear()
        self.compound_picker.clear()

        if not self.session_id:
            self.results.setPlainText("Select a race to begin.")
            return

        try:
            laps = load_race_laps(self.session_id)
            compounds = get_supported_compounds(self.session_id)

            if not compounds:
                raise ValueError(
                    "No supported dry tyre compounds for this race."
                )

            self.laps = laps
            self.total_laps = int(laps["total_laps"].iloc[0])
            drivers = sorted(
                laps["driver"].dropna().astype(str).unique()
            )

            self.compound_picker.addItems(list(compounds))
            self.driver_picker.addItems(drivers)

            self.compare_button.setEnabled(
                bool(drivers) and self.total_laps > 2
            )
            self._update_driver()

            self.results.setPlainText(
                "Choose a driver, current lap, pit lap and "
                "tyres. Then click Compare Strategies."
            )

        except Exception as exc:
            self.laps = None
            self.results.setPlainText(
                f"Unable to load simulator: {exc}"
            )

    def _update_driver(self, _text=None):
        if self.laps is None:
            return

        driver = self.driver_picker.currentText()
        rows = self.laps[self.laps["driver"] == driver]

        if rows.empty:
            self.compare_button.setEnabled(False)
            return

        maximum = min(
            int(rows["lap_number"].max()),
            self.total_laps - 2,
        )
        self.current_lap.setRange(1, max(1, maximum))
        self.current_lap.setValue(min(5, max(1, maximum)))
        self._update_pit_range()

    def _update_pit_range(self, _value=None):
        if self.total_laps < 3:
            return

        minimum = self.current_lap.value() + 1
        maximum = self.total_laps - 1
        self.custom_pit_lap.setRange(minimum, maximum)
        self.custom_pit_lap.setValue(
            min(maximum, max(minimum, self.current_lap.value() + 8))
        )

    def compare(self):
        try:
            result = compare_pit_strategies(
                session_id=self.session_id,
                driver=self.driver_picker.currentText(),
                current_lap=self.current_lap.value(),
                custom_pit_lap=self.custom_pit_lap.value(),
                custom_compound=self.compound_picker.currentText(),
            )

            def plan_text(plan):
                if not plan:
                    return "No additional stops"
                return "\n".join(
                    f"  Lap {stop['pit_lap']}: {stop['compound']}"
                    for stop in plan
                )

            output = (
                f"DRIVER: {result['driver']}\n"
                f"CURRENT LAP: {result['current_lap']}\n\n"
                "OPTIMIZED STRATEGY\n"
                f"{plan_text(result['baseline_plan'])}\n\n"
                "YOUR CUSTOM STRATEGY\n"
                f"{plan_text(result['custom_plan'])}\n\n"
                "ESTIMATED TIME DIFFERENCE\n"
                f"+{result['estimated_extra_seconds']:.2f} seconds\n\n"
                f"Baseline model cost: "
                f"{result['baseline_model_cost']:.2f} s\n"
                f"Custom model cost: "
                f"{result['custom_model_cost']:.2f} s\n"
                f"Pit stop loss estimate: "
                f"{result['pit_loss_seconds']:.2f} s\n\n"
                f"{result['description']}"
            )
            self.results.setPlainText(output)

        except Exception as exc:
            self.results.setPlainText(
                f"Simulation unavailable: {exc}"
            )
