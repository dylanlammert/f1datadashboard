from __future__ import annotations
from PySide6.QtWidgets import (
    QLabel,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QFrame,
    QSizePolicy,
    QScrollArea,
    QGridLayout,
    QComboBox,
    QStackedWidget
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from UI.Theme import theme
from ViewModels.driverProfilesVM import DriverProfilesViewModel

# ? Layouts to match home.py's layout. None of these should be used elsewhere.
_gridMargin: int = 12
_padding: int = 12
_borderRadius: int = 20

class Card(QFrame):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(
            f"""
                background-color: {theme.background};
                border-radius: {_borderRadius}px;
            """
        )

class SearchableDriverDropdown(QComboBox):
    def __init__(self, driver_codes: list[str]):
        super().__init__()
        self.setEditable(True)
        self.addItems(driver_codes)

        completer = self.completer()
        if completer:
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self.setStyleSheet(
            f"""
            QComboBox {{
                background-color: #21212e;
                color: {theme.primaryText};
                border-radius: 8px;
                padding: 6px 12px;
                font-weight: bold;
            }}
            QComboBox QAbstractItemView {{
                background-color: #16161f;
                color: {theme.primaryText};
                selection-background-color: {theme.info};
            }}
            """
        )

class ModeHeaderBar(QWidget):
    __compare_mode_toggled = Signal(bool)

    @property
    def compare_mode_toggled(self):
        return self.__compare_mode_toggled

    def __init__(self):
        super().__init__()
        self.is_compare_mode = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Driver Profiles")
        title.setStyleSheet("color: {theme.primaryText}; font-size: 16px; font-weight: bold;")

        self.toggle_button = QPushButton(" Compare Drivers")
        self.toggle_button.setCheckable(True)
        self.toggle_button.setFixedHeight(32)
        self.toggle_button.setStyleSheet(
            f"""
            QPushButton {{
                background-color: #21212e;
                color: {theme.primaryText};
                border-radius: 8px;
                padding: 4px 12px;
                font-weight: bold;
            }}
            QPushButton:checked {{
                background-color: {theme.info};
                color: #ffffff;
            }}
            """
        )
        self.toggle_button.toggled.connect(self._on_toggled)

        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(self.toggle_button)

    def _on_toggled(self, checked: bool):
        self.is_compare_mode = checked
        self.toggle_button.setText(" Exit Comparison" if checked else " Compare Drivers")
        self.__compare_mode_toggled.emit(checked)

# Top nav bar. This should probably be a search bar in hindsight, but I like the design of this right now so we're going with it.
class DriverNavBar(Card):
    __driver_selected = Signal(str)

    @property
    def selected_driver_changed(self):
        return self.__driver_selected

    def __init__(self, driver_codes: list[str]):
        super().__init__()

        self.setFixedHeight(64)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(_padding, _padding, _padding, _padding)
        layout.setSpacing(10)

        title_label = QLabel("Drivers")
        title_label.setStyleSheet(f"color: {theme.primaryText}; font-weight: bold; font-size: 14px;")
        layout.addWidget(title_label)

        # ? Scrollable container for drivers
        driver_container = QHBoxLayout()
        driver_container.setSpacing(6)
        driver_container.setContentsMargins(0, 0, 0, 0)

        for driver in driver_codes:
            btn = QPushButton(driver)
            btn.setFixedSize(50, 36)
            btn.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: #21212e;
                    color: {theme.primaryText};
                    border-radius: 10px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {theme.info}
                }}
                """
            )
            btn.clicked.connect(lambda checked=False, code=driver: self._on_driver_button_clicked(code))
            driver_container.addWidget(btn)

        container_widget = QWidget()
        container_widget.setLayout(driver_container)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(container_widget)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setStyleSheet("background: transparent;")

        layout.addWidget(scroll_area)

    def _on_driver_button_clicked(self, code):
        self.selected_driver_changed.emit(code)


# Left side, contains a picture, the name of the driver, and their biography
class DriverAboutSection(Card):
    __driver_bio = Signal(str)
    __driver_name = Signal(str)
    __driver_img = Signal(str)

    @property
    def driver_bio_changed(self):
        return self.__driver_bio

    @property
    def driver_name_changed(self):
        return self.__driver_name

    @property
    def driver_image_changed(self):
        return self.__driver_img

    def __init__(self, view_model: DriverProfilesViewModel):
        super().__init__()
        self.view_model = view_model

        layout = QVBoxLayout(self)
        layout.setContentsMargins(_padding, _padding, _padding, _padding)
        layout.setSpacing(12)

        self.image_holder = QLabel()
        self.image_holder.setFixedSize(100, 100)
        self.image_holder.setPixmap(QPixmap("images/Driver_Not_found.jpg"))

        self.name = QLabel("SELECT A DRIVER")
        self.name.setStyleSheet(f"color: {theme.primaryText}; font-size: 18px; font-weight: bold;")

        about_title = QLabel("BIOGRAPHY")
        about_title.setStyleSheet(f"color: {theme.secondaryText}; font-weight: bold; font-size: 12px;")

        self.about_text = QLabel("Click on a driver above to view their biography and stats.")
        self.about_text.setWordWrap(True)
        self.about_text.setStyleSheet(f"color: {theme.primaryText}; line-height: 1.4;")
        self.about_text.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.about_text)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setStyleSheet("background: transparent;")

        layout.addWidget(self.image_holder, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.name, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(about_title, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(scroll_area)

    def update_bio(self, bio_text: str) -> None:
        self.about_text.setText(bio_text)

    def update_name(self, driver_name: str) -> None:
        self.name.setText(driver_name)

    def update_img(self, pixmap: QPixmap) -> None:
        self.image_holder.setPixmap(pixmap)


# Right side, contains their placement history and their career stats
class DriverStatsSection(Card):
    def __init__(self, view_model: DriverProfilesViewModel):
        super().__init__()
        self.view_model = view_model

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(_padding, _padding, _padding, _padding)
        self.main_layout.setSpacing(12)

        placements_title = QLabel("Recent Placements")
        placements_title.setStyleSheet(f"color: {theme.secondaryText}; font-weight: bold; font-size: 12px;")
        self.main_layout.addWidget(placements_title)

        # TODO: Pull this from Viewmodel later
        placement_history = [8, 1, 2, 1, 4]
        location_history = ["London", "Paris", "Norway", "Quatar", "Turkey"]
        formatted_cards = self.view_model.get_formatted_placements(placement_history, location_history)

        race_history = QHBoxLayout()
        race_history.setSpacing(8)

        for placement_str, location_str in formatted_cards:
            card_frame = QFrame()
            card_frame.setFixedSize(75, 75)
            card_frame.setStyleSheet(
                f"""
                background-color: #21212e;
                border-radius: 12px;
                """
            )
            card_layout = QVBoxLayout(card_frame)
            card_layout.setContentsMargins(4, 4, 4, 4)

            placement_label = QLabel(placement_str)
            placement_label.setStyleSheet(f"color: {theme.info}; font-weight: bold; font-size: 16px;")
            placement_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            location_label = QLabel(location_str)
            location_label.setStyleSheet(f"color: {theme.secondaryText}; font-size: 11px;")
            location_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            card_layout.addWidget(placement_label)
            card_layout.addWidget(location_label)
            
            race_history.addWidget(card_frame)

        race_history.addStretch()
        
        race_widget = QWidget()
        race_widget.setLayout(race_history)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(race_widget)
        scroll_area.setFixedHeight(95)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setStyleSheet("background: transparent;")
        self.main_layout.addWidget(scroll_area)

        self.career_stats_layout = QGridLayout()
        self.career_placeholder = QLabel("Select a driver to view career statistics.")
        self.career_placeholder.setStyleSheet(f"color: {theme.secondaryText};")
        self.career_stats_layout.addWidget(self.career_placeholder, 0, 0)

        career_stats_widget = QWidget()
        career_stats_widget.setLayout(self.career_stats_layout)

        career_stats_scroll = QScrollArea()
        career_stats_scroll.setWidgetResizable(True)
        career_stats_scroll.setWidget(career_stats_widget)
        career_stats_scroll.setFrameShape(QFrame.Shape.NoFrame)
        career_stats_scroll.setStyleSheet(f"background: transparent;")

        self.main_layout.addWidget(career_stats_scroll)

    def update_stats(self, driver_stats: dict[str, str]) -> None:
        while self.career_stats_layout.count():
            item = self.career_stats_layout.takeAt(0)

            # ? PyLance was being an ass about "None" not having .deleteLater() despite a very elegant assert statement (assert item is not None)
            # ?     so now we have to deal with this and it's ugly and I hate it with all my heart <3
            if item is not None and item.widget():
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

        career_stats_title = QLabel("Career Stats")
        career_stats_title.setStyleSheet(f"color: {theme.primaryText}; font-size: 14px; font-weight: bold;")
        self.career_stats_layout.addWidget(career_stats_title, 0, 0, 1, 2, alignment=Qt.AlignmentFlag.AlignCenter)

        for row_idx, (label_text, value_text) in enumerate(driver_stats.items(), start=1):
            label = QLabel(label_text)
            label.setStyleSheet(f"color: {theme.secondaryText}; font-size: 13px;")

            value = QLabel(str(value_text))
            value.setStyleSheet(f"color: {theme.primaryText}; font-size: 13px; font-weight: bold;")

            grid_row = row_idx * 2
            self.career_stats_layout.addWidget(label, grid_row, 0, alignment=Qt.AlignmentFlag.AlignLeft)
            self.career_stats_layout.addWidget(value, grid_row, 1, alignment=Qt.AlignmentFlag.AlignRight)

            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setStyleSheet(f"background-color: #21212e; max-height: 1px")
            self.career_stats_layout.addWidget(line, grid_row + 1, 0, 1, 2)

    def add_header_widget(self, widget: QWidget):
        """Helper to insert a widget to the top of the main card.

        Args:
            widget (QWidget): The QWidget object to insert
        """
        self.main_layout.insertWidget(0, widget)

class DriverProfiles(QWidget):
    def __init__(self, view_model: DriverProfilesViewModel):
        super().__init__()
        self.view_model = view_model
        self.driver_codes = self.view_model.get_driver_codes()

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(_gridMargin, _gridMargin, _gridMargin, _gridMargin)

        self.header_bar = ModeHeaderBar()
        main_layout.addWidget(self.header_bar)

        self.nav_bar = DriverNavBar(self.driver_codes)
        main_layout.addWidget(self.nav_bar)

        grid_widget = QWidget()
        self.grid = QGridLayout(grid_widget)
        self.grid.setSpacing(_gridMargin)
        self.grid.setContentsMargins(0, 0, 0, 0)

        self.left_stack = QStackedWidget()

        # Left Page 0: Biography Section
        self.driver_about_section = DriverAboutSection(self.view_model)
        self.left_stack.addWidget(self.driver_about_section)

        # Left Page 1: Driver A Stats Card (with Dropdown)
        self.driver_a_stats_section = DriverStatsSection(self.view_model)
        self.dropdown_a = SearchableDriverDropdown(self.driver_codes)
        self.driver_a_stats_section.add_header_widget(self.dropdown_a)
        self.left_stack.addWidget(self.driver_a_stats_section)

        self.grid.addWidget(self.left_stack, 0, 0)

        self.driver_b_stats_section = DriverStatsSection(self.view_model)
        self.dropdown_b = SearchableDriverDropdown(self.driver_codes)
        self.driver_b_stats_section.add_header_widget(self.dropdown_b)
        self.dropdown_b.hide()

        self.grid.addWidget(self.driver_b_stats_section, 0, 1)

        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 1)

        main_layout.addWidget(grid_widget)

        self.header_bar.compare_mode_toggled.connect(self._set_compare_mode)

        self.nav_bar.selected_driver_changed.connect(self.view_model.select_driver)
        self.dropdown_a.currentTextChanged.connect(self.view_model.select_driver)
        self.nav_bar.selected_driver_changed.connect(self.dropdown_a.setCurrentText)
        self.dropdown_b.currentTextChanged.connect(self.view_model.select_driver_b)

        self.view_model.bio_changed.connect(self.driver_about_section.update_bio)
        self.view_model.name_changed.connect(self.driver_about_section.update_name)
        self.view_model.img_changed.connect(self.driver_about_section.update_img)
        self.view_model.stats_changed.connect(self.driver_a_stats_section.update_stats)

        self.view_model.stats_changed.connect(self.driver_b_stats_section.update_stats)

    def _set_compare_mode(self, enabled: bool) -> None:
        if enabled:
            self.nav_bar.hide()
            self.left_stack.setCurrentIndex(1)
            self.dropdown_b.show()

            self.view_model.stats_changed.disconnect(self.driver_b_stats_section.update_stats)
            self.view_model.stats_b_changed.connect(self.driver_b_stats_section.update_stats)

        else:
            self.nav_bar.show()
            self.left_stack.setCurrentIndex(0)
            self.dropdown_b.hide()

            # Right side switches from Driver B → Driver A/current driver
            self.view_model.stats_b_changed.disconnect(self.driver_b_stats_section.update_stats)
            self.view_model.stats_changed.connect(self.driver_b_stats_section.update_stats)