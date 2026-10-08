from __future__ import annotations
from PySide6.QtCore import QObject, Signal, QByteArray, Qt, QRunnable, QThreadPool
from Services.stat_scraper import DriverStatScraper
from Services.dbhandler import DBhandler
from PySide6.QtGui import QPixmap, QPainter, QPainterPath
from bs4 import BeautifulSoup

class ImageWorkerSignals(QObject):
    # ? Private access variable, the double underscore should prevent use outside of the class unless through the property.
    __finished = Signal(QPixmap)

    @property
    def finished_signal(self):
        return self.__finished

class ImageWorker(QRunnable):
    def __init__(self, scraper: DriverStatScraper, soup: BeautifulSoup, size: int = 100):
        super().__init__()
        self.scraper = scraper
        self.soup = soup
        self.size = size
        self.signals = ImageWorkerSignals()

    def run(self):
        image_bytes = self.scraper.fetch_driver_image(self.soup)

        pixmap = QPixmap()
        if not (image_bytes and pixmap.loadFromData(QByteArray(image_bytes))):
            pixmap = QPixmap("images/Driver_Not_found.jpg")

        scaled = pixmap.scaled(
            self.size, self.size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )

        canvas = QPixmap(self.size, self.size)
        canvas.fill(Qt.GlobalColor.transparent)

        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        path.addEllipse(0, 0, self.size, self.size)

        painter.setClipPath(path)
        painter.drawPixmap(0, 0, scaled)
        painter.end()

        self.signals.finished_signal.emit(canvas)

class DriverProfilesViewModel(QObject):
    """_summary_

    Args:
        QObject (_type_): _description_

    Methods:
        - fetchDriverInfo(season, session, race)


    Variables:
        - driver1 from class
        - driver2 from class

    """

    # ? Private signals and properties to read those signals externally
    __stats_loaded = Signal(dict)
    __bio_loaded = Signal(str)
    __name_loaded = Signal(str)
    __img_loaded = Signal(QPixmap)
    __stats_b_loaded = Signal(dict)
    __name_b_loaded = Signal(str)
    __img_b_loaded = Signal(QPixmap)

    @property
    def stats_changed(self):
        return self.__stats_loaded

    @property
    def bio_changed(self):
        return self.__bio_loaded

    @property
    def name_changed(self):
        return self.__name_loaded

    @property
    def img_changed(self):
        return self.__img_loaded

    @property
    def stats_b_changed(self):
        return self.__stats_b_loaded

    @property
    def name_b_changed(self):
        return self.__name_b_loaded

    @property
    def img_b_changed(self):
        return self.__img_b_loaded

    def __init__(self):
        """Generic initialization of the `DriverProfilesViewModel` class

        Args:
            dbhandler (DBhandler): A `DBhandler` object that will be used to communicate with the database. Should be passed from `main.py`
        """
        super().__init__()

        self.dbhandler = DBhandler()

        self.scraper = DriverStatScraper()
        self.thread_pool = QThreadPool.globalInstance()

    # Methods to be used externally
    def get_driver_names(self) -> list[str]:
        """Gets a list of all known driver names

        Returns:
            list[str]: A list containing all names as strings.
        """
        dict = self._get_known_drivers()

        return list(dict.values())

    def get_driver_codes(self) -> list[str]:
        """Gets a list of all known driver codes

        Returns:
            list[str]: A list containing all codes as strings
        """
        dict = self._get_known_drivers()

        return list(dict.keys())

    def get_driver_bio(self, soup: BeautifulSoup) -> str:
        """Gets the driver bio as a string

        Args:
            soup (BeautifulSoup): A BeautifulSoup object that contains the text of the webpage. Can be obtained by calling get_soup() on a DriverStatScraper object.

        Returns:
            str: The biography of the driver
        """
        return self.scraper.fetch_driver_bio(soup)
    
    def get_formatted_placements(
        self, placement_history: list[int], location_history: list[str]
    ) -> list[tuple[str, str]]:
        """When supplied with a list of placement history and the corresponding locations of those placements, will format the placement and place them in a tuple

        Args:
            placement_history (list[int]): The list of placements of the drivers as integers
            location_history (list[str]): The list of

        Returns:
            list[tuple[str, str]]: _description_
        """
        formatted_cards = []
        for place, location in zip(placement_history, location_history):
            formatted_place = self._format_placement(place)
            formatted_cards.append((formatted_place, location))

        return formatted_cards

    def get_season_stats(self, soup: BeautifulSoup) -> dict[str, str]:
        """Returns the given driver's season stats

        Args:
            soup (BeautifulSoup): A BeautifulSoup object that contains the text of the webpage. Can be obtained by calling get_soup() on a DriverStatScraper object.

        Returns:
            dict[str, str]: A dictionary containing the key of the title of the stat and the value of the value of said stat.
        """
        return self._load_driver_stats(soup, "season")

    def get_career_stats(self, soup: BeautifulSoup):
        """Returns the given driver's career stats

        Args:
           soup (BeautifulSoup): A BeautifulSoup object that contains the text of the webpage. Can be obtained by calling get_soup() on a DriverStatScraper object.

        Returns:
            dict[str, str]: A dictionary containing the key of the title of the stat and the value of the value of said stat.
        """
        return self._load_driver_stats(soup, "career")

    def select_driver(self, driver_code: str):
        """Binds to the signal objects from the driverProfiles to update the display

        Args:
            driver_code (str): The code of the driver (e.g. Max Verstappen would be `VER`)
        """
        driver_dict = self._get_known_drivers()

        driver_name = driver_dict[driver_code]
        # ? We store a copy of the driver name to display before replacing it for URL purposes
        _driver_display_name = driver_name
        driver_name = driver_name.lower().replace(" ", "-")

        soup = self.scraper.get_soup(driver_name)

        if soup is None:
            self.stats_changed.emit({"Status": "No Stats Available"})
            self.bio_changed.emit("Biography Not Available")
            # ? I'm displaying this as is because it could be useful for debugging why a page didn't return (since it's equivalent to what we pass to get_soup())
            self.name_changed.emit(_driver_display_name)
            raise ValueError(f"Driver not found: {driver_name}. Showing default values")

        career_stats = self.get_career_stats(soup)
        bio_text = self.get_driver_bio(soup)

        if not career_stats:
            career_stats = {"Status": "No Stats Available"}
        if not bio_text:
            bio_text = "Biography Not Available."

        self.stats_changed.emit(career_stats)
        self.bio_changed.emit(bio_text)
        self.name_changed.emit(_driver_display_name)
        
        worker = ImageWorker(self.scraper, soup)
        worker.signals.finished_signal.connect(self.img_changed.emit)

        self.thread_pool.start(worker)

    def select_driver_b(self, driver_code: str):
        driver_dict = self._get_known_drivers()

        _driver_display_name = driver_dict[driver_code]
        driver_name = _driver_display_name.lower().replace(" ", "-")

        soup = self.scraper.get_soup(driver_name)

        if soup is None:
            self.stats_b_changed.emit({"Status": "No Stats Available"})
            self.name_b_changed.emit(_driver_display_name)
            raise ValueError(f"Driver not found: {driver_name}. Showing default values")

        career_stats = self.get_career_stats(soup)
        if not career_stats:
            career_stats = {"Status": "No Stats Available"}

        self.stats_b_changed.emit(career_stats)
        self.name_b_changed.emit(_driver_display_name)

        worker = ImageWorker(self.scraper, soup, size=60)
        worker.signals.finished_signal.connect(self.img_b_changed.emit)
        self.thread_pool.start(worker)
    
    # Helper Methods
    def _get_known_drivers(self) -> dict[str, str]:
        """Helper function for `get_driver_names()` and `get_driver_codes()`

        Returns:
            dict[str, str]: A dictionary with the driver codes as keys and the driver names as values (e.g. {'VER': 'Max Verstappen'})
        """
        return self.dbhandler.getKnownDrivers()

    def _format_placement(self, place: int) -> str:
        """Helper function: called by `get_formatted_placements()`"""
        match place:
            case 1:
                placement_string = "1st"
            case 2:
                placement_string = "2nd"
            case 3:
                placement_string = "3rd"
            case _:
                placement_string = f"{place}th"
        return placement_string

    def _load_driver_stats(self, soup: BeautifulSoup, scope: str) -> dict[str, str]:
        """Loads the driver stats from the F1 website

        Args:
            soup (BeautifulSoup): A BeautifulSoup object that contains the text of the webpage. Can be obtained by calling get_soup() on a DriverStatScraper object.
            scope (str): Whether to use the scope of "season" or "career" for stats.

        Returns:
            dict[str, str]: The stats returned in a pairing of "Title": "Value"
        """
        data = self.scraper.fetch_driver_stats(soup)

        if not data:
            return {"ERROR": "Data Unavailable"}

        return data[scope]

def _main():
    vm_test = DriverProfilesViewModel()
    data = vm_test.get_driver_codes()
    print(data)
    data = vm_test.get_driver_names()
    print(data)

    return 0

if __name__ == "__main__":
    _main()
