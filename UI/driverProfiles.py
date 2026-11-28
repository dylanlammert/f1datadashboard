from __future__ import annotations
from pathlib import Path
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
    QStackedWidget,
    QButtonGroup,
    QStyleFactory
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QResizeEvent
from UI.Theme import theme
from ViewModels.driverProfilesVM import DriverProfilesViewModel

# ? Layouts to match home.py's layout. None of these should be used outside this code ideally.
_gridMargin: int = 12
_padding: int = 12
_borderRadius: int = 20

# ? Colors for titles, buttons, dropdowns, etc.
_surface: str = "#21212e"
_surface_hover: str = "#2b2b3b"
_on_accent: str = "#0B0E14"

_chevron_path = Path(__file__).resolve().parent / "images" / "downChevron.png"

_SCROLL_QSS = f"""
    QScrollArea {{ background: transparent; border: none; }}
    QScrollBar:vertical {{ width: 6px; background: transparent; margin: 0; }}
    QScrollBar::handle:vertical {{
        background: {_surface}; border-radius: 3px; min-height: 24px;
    }}
    QScrollBar:horizontal {{ height: 6px; background: transparent; margin: 0; }}
    QScrollBar::handle:horizontal {{
        background: {_surface}; border-radius: 3px; min-width: 24px;
    }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
"""

def _caption(text: str, color: str = theme.secondaryText, size: int = 10, bold: bool = True) -> QLabel:
    """Makes a small uppercase label. Pretty much the same thing as `_telemetryLabel` in home.py"""
    label = QLabel(text.upper())
    label.setStyleSheet(
        f"""
        background: transparent;
        color: {color};
        font-size: {size}px;
        font-weight: {"bold" if bold else "normal"};
        """
    )
    return label

def _make_scroll_area(widget: QWidget, horizontal: bool = False) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setWidget(widget)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setStyleSheet(_SCROLL_QSS)
    if horizontal:
        area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    else:
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    return area

class Card(QFrame):
    """Setup for the cards to use for layouts"""

    def __init__(self):
        super().__init__()
        # ? This fixes an issue with QSS cascading down because of not having a name
        self.setObjectName("card")
        self.setStyleSheet(
            f"""
                QFrame#card {{
                    background-color: {theme.background};
                    border-radius: {_borderRadius}px;
                }}
            """
        )

class StatTile(QFrame):
    def __init__(self, label_text: str, value_text: str, highlight: bool = False):
        super().__init__()
        self.setObjectName("statTile")
        border = f"1px solid {theme.success}" if highlight else "none"
        self.setStyleSheet(
            f"""
            QFrame#statTile {{
                background-color: {_surface};
                border: {border};
                border-radius: 12px;
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)

        layout.addWidget(_caption(label_text))

        value = QLabel(str(value_text))
        value_color = theme.success if highlight else theme.primaryText
        value.setStyleSheet(
            f"""
                background: transparent;
                color: {value_color};
                font-size: 20px;
                font-weight: bold;
            """
        )
        layout.addWidget(value)


class SearchableDriverDropdown(QComboBox):
    """Dropdown menu for the head-to-head comparison view"""

    _dropdown_width = 24

    def __init__(self, driver_codes: list[str]):
        super().__init__()
        self.setStyle(QStyleFactory.create("Fusion"))
        # ? Allows the user to edit text and adds the list of driver codes (VER, HAM, etc.) to the dropdown
        self.setEditable(True)
        self.addItems(driver_codes)

        self.setCurrentIndex(-1)
        line_edit = self.lineEdit()
        if line_edit:
            line_edit.setPlaceholderText("Select Driver")

        # ? Autocompleter implementation
        completer = self.completer()
        if completer:
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        # ? QSS to make it look ⋆˙⟡ stunning ✧˖°.
        self.setStyleSheet(
            f"""
            QComboBox {{
                background-color: {_surface};
                color: {theme.primaryText};
                border: none;
                border-radius: 8px;
                padding: 6px 12px;
                font-weight: bold;
            }}
            QComboBox:hover {{
                background-color: {_surface_hover};
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: {self._dropdown_width}px;
                border: none;
            }}
            QComboBox::down-arrow {{
                image: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: #16161f;
                color: {theme.primaryText};
                border: none;
                outline: 0;
                selection-background-color: {theme.info};
            }}
            """
        )

        self.chevron_label = QLabel(self)
        self.chevron_label.setPixmap(QPixmap(str(_chevron_path)))
        self.chevron_label.setScaledContents(True)
        self.chevron_label.setFixedSize(18, 18)
        self.chevron_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )

    def resizeEvent(self, e: QResizeEvent) -> None:
        super().resizeEvent(e)
        offset = (self._dropdown_width - self.chevron_label.width()) // 2
        self.chevron_label.move(
            self.width() - self._dropdown_width + offset,
            (self.height() - self.chevron_label.height()) // 2,
        )


class ModeHeaderBar(QWidget):
    """Object that allows swapping between comparison view and normal view"""

    # ? Private signal with property to read from
    __compare_mode_toggled = Signal(bool)
    __seasonal_mode_toggled = Signal(bool)

    @property
    def compare_mode_toggled(self):
        return self.__compare_mode_toggled

    @property
    def seasonal_mode_toggled(self):
        return self.__seasonal_mode_toggled

    def __init__(self):
        super().__init__()
        # ? Starts in single driver view
        self.is_compare_mode = False
        self.is_seasonal_mode = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Driver Profiles")
        title.setStyleSheet(
            f"""
            color: {theme.primaryText}; 
            font-size: 16px; 
            font-weight: bold;
            """
        )

        def _button_formatting_factory(button: QPushButton):
            """Helper function that applies formatting rules for buttons"""
            button.setCheckable(True)
            button.setFixedHeight(32)
            # TODO: Add Hover Effect
            button.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {_surface};
                    color: {theme.primaryText};
                    border: none;
                    border-radius: 8px;
                    padding: 4px 12px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {_surface_hover};
                }}
                QPushButton:checked {{
                    background-color: {theme.info};
                    color: #ffffff;
                }}
                """
            )

        self.seasonal_mode_toggle_button = QPushButton(" Career Mode")
        _button_formatting_factory(self.seasonal_mode_toggle_button)
        self.seasonal_mode_toggle_button.toggled.connect(self._on_seasonal_toggled)

        self.compare_toggle_button = QPushButton(" Compare Drivers")
        _button_formatting_factory(self.compare_toggle_button)
        self.compare_toggle_button.toggled.connect(self._on_compare_toggled)

        # ? Places the "Driver Profile" text in the top left and then puts the button in the top right
        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(self.seasonal_mode_toggle_button)
        layout.addWidget(self.compare_toggle_button)

    def _on_compare_toggled(self, checked: bool):
        """Helper function to swap between single view and comparison view

        Args:
            checked (bool): _description_
        """
        self.is_compare_mode = checked
        self.compare_toggle_button.setText(
            " Exit Comparison" if checked else " Compare Drivers"
        )
        self.__compare_mode_toggled.emit(checked)

    def _on_seasonal_toggled(self, checked: bool):
        self.is_seasonal_mode = checked
        self.seasonal_mode_toggle_button.setText(
            " Seasonal Mode" if checked else " Career Mode"
        )
        self.__seasonal_mode_toggled.emit(checked)


# TODO: Possibly change to a search bar later? Depends on how many drivers get loaded in.
class DriverNavBar(Card):
    """Top nav bar"""

    # ? Private signal and property to read from
    __driver_selected = Signal(str)

    @property
    def selected_driver_changed(self):
        return self.__driver_selected

    def __init__(self, driver_codes: list[str]):
        super().__init__()
        self.setFixedHeight(72)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        # ? This can probably be simplified to not use global values (padding is almost certainly the wrong one, but it's just (12, 12, 12, 12) anyways :shrug:)
        layout.setContentsMargins(_padding, _padding, _padding, _padding)
        layout.setSpacing(10)

        layout.addWidget(_caption("Drivers", color=theme.primaryText, size=12))

        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}

        # ? Scrollable container for drivers
        driver_container = QHBoxLayout()
        driver_container.setSpacing(6)
        driver_container.setContentsMargins(0, 0, 0, 0)

        for driver in driver_codes:
            btn = QPushButton(driver)
            btn.setCheckable(True)
            btn.setFixedSize(50, 36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {_surface};
                    color: {theme.primaryText};
                    border: none;
                    border-radius: 10px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {_surface_hover};
                }}
                QPushButton:checked {{
                    background-color: {theme.info};
                    color: #ffffff;
                }}
                """
            )
            btn.clicked.connect(
                lambda checked=False, code=driver: self._on_driver_button_clicked(code)
            )
            self._button_group.addButton(btn)
            self._buttons[driver] = btn
            driver_container.addWidget(btn)

        container_widget = QWidget()
        container_widget.setStyleSheet("background: transparent;")
        container_widget.setLayout(driver_container)

        layout.addWidget(_make_scroll_area(container_widget, horizontal=True))

    def set_selected(self, code: str) -> None:
        """Highlights the button with the passed `code`"""
        button = self._buttons.get(code)
        if button is not None:
            button.setChecked(True)
            return
        # ? We have to remove the exclusive tag to uncheck buttons
        self._button_group.setExclusive(False)
        for btn in self._buttons.values():
            btn.setChecked(False)
        self._button_group.setExclusive(True)

    # ? Just a helper to emit the signal as changed.
    def _on_driver_button_clicked(self, code):
        self.selected_driver_changed.emit(code)


class DriverAboutSection(Card):
    """Left side image, name, and bio of driver in single view"""

    # ? Private signals and properties to read them from
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
        # ? Since no driver is selected initially, I'm just displaying the placeholder image
        self.image_holder.setPixmap(QPixmap("images/Driver_Not_found.jpg"))

        self.name = QLabel("SELECT A DRIVER")
        self.name.setStyleSheet(
            f"""
            background: transparent;
            color: {theme.primaryText}; 
            font-size: 18px; 
            font-weight: bold;
            """
        )

        self.code_badge = QLabel("")
        self.code_badge.setStyleSheet(
            f"""
            background-color: {theme.success};
            color: {_on_accent};
            font-size: 12px;
            font-weight: bold;
            padding: 4px 12px;
            border-radius: 6px;
            """
        )
        self.code_badge.hide()

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet(
            f"""
            background-color: {_surface};
            max-height: 1px;
            border: none;
            """
        )

        self.about_text = QLabel(
            "Click on a driver above to view their biography and stats."
        )
        self.about_text.setWordWrap(True)
        self.about_text.setStyleSheet(
            f"""
            background: transparent;
            color: {theme.primaryText};
            font-size: 13px;
            """
        )
        self.about_text.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )

        layout.addWidget(self.image_holder, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.name, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.code_badge, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(divider)
        layout.addWidget(_caption("Biography"), alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(_make_scroll_area(self.about_text))

    # ? Helpers to update the displayed text
    def update_bio(self, bio_text: str) -> None:
        self.about_text.setText(bio_text)

    def update_name(self, driver_name: str) -> None:
        self.name.setText(driver_name)

    def update_img(self, pixmap: QPixmap) -> None:
        self.image_holder.setPixmap(pixmap)

    def update_code(self, driver_code: str) -> None:
        self.code_badge.setText(driver_code)
        self.code_badge.setVisible(bool(driver_code))


class DriverStatsSection(Card):
    """Stat section card on the right side of the view"""

    def __init__(self, view_model: DriverProfilesViewModel, title: str = "Career Stats", columns: int = 2):
        super().__init__()
        self.view_model = view_model
        self._columns = columns

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(_padding, _padding, _padding, _padding)
        self.main_layout.setSpacing(12)

        self.title_label = _caption(title, color=theme.primaryText, size=12)
        self.main_layout.addWidget(self.title_label)

        self.stats_grid = QGridLayout()
        self.stats_grid.setContentsMargins(0, 0, 0, 0)
        self.stats_grid.setSpacing(10)
        for col in range(self._columns):
            self.stats_grid.setColumnStretch(col, 1)
        self._show_placeholder()

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addLayout(self.stats_grid)
        content_layout.addStretch()

        self.main_layout.addWidget(_make_scroll_area(content), 1)

    def set_title(self, title: str) -> None:
        self.title_label.setText(title.upper())

    def _show_placeholder(self) -> None:
        placeholder = QLabel("Select a driver to view their stats.")
        placeholder.setStyleSheet(
            f"""
            background: transparent;
            color: {theme.secondaryText};
            """
        )
        self.stats_grid.addWidget(placeholder, 0, 0, 1, self._columns)

    def _clear_grid(self) -> None:
        while (item := self.stats_grid.takeAt(0)) is not None:
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def update_stats(self, driver_stats: dict[str, str], winners: set[str] | None = None) -> None:
        self._clear_grid()

        if not driver_stats:
            self._show_placeholder()
            return

        winners = winners or set()
        for index, (label_text, value_text) in enumerate(driver_stats.items()):
            row, col = divmod(index, self._columns)
            tile = StatTile(label_text, value_text, highlight=label_text in winners)
            self.stats_grid.addWidget(tile, row, col)

    def add_header_widget(self, widget: QWidget):
        """Helper to insert a widget to the top of the main card.

        Args:
            widget (QWidget): The QWidget object to insert
        """
        self.main_layout.insertWidget(0, widget)


class DriverProfiles(QWidget):
    """Master view for the driver profile page"""

    def __init__(self, view_model: DriverProfilesViewModel):
        super().__init__()
        self.view_model = view_model
        self.driver_codes = self.view_model.get_driver_codes()

        self._stats_a: dict[str, str] = {}
        self._stats_b: dict[str, str] = {}

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(
            _gridMargin, _gridMargin, _gridMargin, _gridMargin
        )

        # ? Header bar
        self.header_bar = ModeHeaderBar()
        main_layout.addWidget(self.header_bar)

        # ? Nav bar
        self.nav_bar = DriverNavBar(self.driver_codes)
        main_layout.addWidget(self.nav_bar)

        grid_widget = QWidget()
        self.grid = QGridLayout(grid_widget)
        self.grid.setSpacing(_gridMargin)
        self.grid.setContentsMargins(0, 0, 0, 0)

        self.left_stack = QStackedWidget()

        # ? Sets the about section
        self.driver_about_section = DriverAboutSection(self.view_model)
        self.left_stack.addWidget(self.driver_about_section)

        # ? Sets the stat section
        self.driver_a_stats_section = DriverStatsSection(self.view_model)
        self.dropdown_a = SearchableDriverDropdown(self.driver_codes)
        self.driver_a_stats_section.add_header_widget(self.dropdown_a)
        self.left_stack.addWidget(self.driver_a_stats_section)

        self.grid.addWidget(self.left_stack, 0, 0)

        # ? The rest of this handles comparison view logistics
        self.driver_b_stats_section = DriverStatsSection(self.view_model)
        self.dropdown_b = SearchableDriverDropdown(self.driver_codes)
        self.driver_b_stats_section.add_header_widget(self.dropdown_b)
        self.dropdown_b.hide()

        self.grid.addWidget(self.driver_b_stats_section, 0, 1)

        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 1)

        main_layout.addWidget(grid_widget)

        self.header_bar.compare_mode_toggled.connect(self._set_compare_mode)

        self.dropdown_a.currentTextChanged.connect(self._driver_selector_helper)
        self.nav_bar.selected_driver_changed.connect(self.dropdown_a.setCurrentText)
        self.dropdown_b.currentTextChanged.connect(self._driver_b_selector_helper)

        # ? Helps refresh the UI whenever the seasonal toggle is checked
        self.header_bar.seasonal_mode_toggled.connect(self._on_seasonal_mode_toggled)

        self.view_model.bio_changed.connect(self.driver_about_section.update_bio)
        self.view_model.name_changed.connect(self.driver_about_section.update_name)
        self.view_model.img_changed.connect(self.driver_about_section.update_img)
        
        self.view_model.stats_changed.connect(self._on_stats_a)
        self.view_model.stats_b_changed.connect(self._on_stats_b)

    def _set_compare_mode(self, enabled: bool) -> None:
        """Helper function for toggling comparison mode

        Args:
            enabled (bool): If enabled, compare mode is toggled on. Otherwise, it toggles off.
        """
        if enabled:
            self.nav_bar.hide()
            self.left_stack.setCurrentIndex(1)
            self.dropdown_b.show()
        else:
            self.nav_bar.show()
            self.left_stack.setCurrentIndex(0)
            self.dropdown_b.hide()

        self._render_stats()

    def _on_stats_a(self, stats: dict) -> None:
        self._stats_a = stats
        self._render_stats()

    def _on_stats_b(self, stats: dict) -> None:
        self._stats_b = stats
        self._render_stats()

    def _render_stats(self) -> None:
        if not self.header_bar.is_compare_mode:
            self.driver_a_stats_section.update_stats(self._stats_a)
            self.driver_b_stats_section.update_stats(self._stats_a)
            return

        wins_a, wins_b = self.view_model.compare_stats(self._stats_a, self._stats_b)
        self.driver_a_stats_section.update_stats(self._stats_a, wins_a)
        self.driver_b_stats_section.update_stats(self._stats_b, wins_b)

    def _driver_selector_helper(self, driver_code: str) -> None:
        seasonal = self.header_bar.is_seasonal_mode
        self.view_model.select_driver(driver_code, seasonal)

    def _driver_b_selector_helper(self, driver_code: str) -> None:
        seasonal = self.header_bar.is_seasonal_mode
        self.view_model.select_driver_b(driver_code, seasonal)

    def _refresh_stat_titles(self, seasonal: bool) -> None:
        title = "Seasonal Stats" if seasonal else "Career Stats"
        self.driver_a_stats_section.set_title(title)
        self.driver_b_stats_section.set_title(title)

    # ? Leaving `checked` in here despite it not being accessed. I can't remember if PySide6 wants the connection here regardless of if it's used or not.
    def _on_seasonal_mode_toggled(self, checked: bool) -> None:
        self._refresh_stat_titles(checked)

        current_driver = self.dropdown_a.currentText()
        if current_driver:
            self._driver_selector_helper(current_driver)

        if self.header_bar.is_compare_mode:
            driver_b = self.dropdown_b.currentText()
            if driver_b:
                self._driver_b_selector_helper(driver_b)