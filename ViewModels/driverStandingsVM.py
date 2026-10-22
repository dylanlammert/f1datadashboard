from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from Services.dbhandler import DBhandler


class DriverStandingsViewModel(QObject):
    """Provides race-based driver standings to the UI."""

    __standings_loaded = Signal(list)
    __focused_driver_loaded = Signal(dict)

    @property
    def standings_changed(self):
        return self.__standings_loaded

    @property
    def focused_driver_changed(self):
        return self.__focused_driver_loaded

    def __init__(self, dbhandler: DBhandler | None = None):
        super().__init__()
        self.dbhandler = dbhandler if dbhandler is not None else DBhandler()
        self.__driver_data = []
        self.__focused_driver = None

    def get_driver_data(self) -> list[dict]:
        return [row.copy() for row in self.__driver_data]

    def set_driver_data(self, data: list[dict]) -> None:
        self.__driver_data = [row.copy() for row in data]
        self.__standings_loaded.emit(self.get_driver_data())

        if self.__focused_driver is not None:
            self.fetch_focused_driver_data()

    def fetch_driver_data(self, year: int) -> list[dict]:
        """Load driver standings for a season from race results."""
        query = """
            SELECT
                r.driver_code,
                COALESCE(MAX(d.full_name), r.driver_code) AS full_name,
                COALESCE(SUM(r.points), 0) AS total_points
            FROM results r
            JOIN sessions s ON s.session_id = r.session_id
            LEFT JOIN drivers d
                ON d.session_id = r.session_id
                AND d.driver_code = r.driver_code
            WHERE s.year = ? AND s.session_type = 'Race'
            GROUP BY r.driver_code
            ORDER BY total_points DESC, r.driver_code ASC
        """

        rows = self.dbhandler.conn.execute(query, (int(year),)).fetchall()

        standings = [
            {
                "position": index,
                "driver_code": row[0],
                "full_name": row[1],
                "points": float(row[2]),
            }
            for index, row in enumerate(rows, start=1)
        ]

        self.set_driver_data(standings)
        return self.get_driver_data()

    def set_focused_driver(self, driver_code: str) -> dict:
        self.__focused_driver = driver_code.strip().upper()
        return self.fetch_focused_driver_data()

    def get_focused_driver_data(self) -> dict:
        for row in self.__driver_data:
            if row["driver_code"] == self.__focused_driver:
                return row.copy()
        return {}

    def fetch_focused_driver_data(self) -> dict:
        focused = self.get_focused_driver_data()
        self.__focused_driver_loaded.emit(focused)
        return focused
