import os
import sqlite3

import fastf1
import pandas as pd
from fastf1.events import Session
import traceback

from graphs.graph_metrics import MetricSpec

"""
dbhandler.py — the ONE place the app talks to the database.

Everything that used to live in Services/database.py (creating the schema,
loading a FastF1 session into the tables, previewing them) is now a method on
DBhandler. Services/database.py still exists as a thin wrapper so older code
that imports from it keeps working.

TODO: 
    - loadsessionintodb only loads session5 into the db of a specified event
    - need to update table functions to reflect changes in sessionSelector
"""

os.makedirs("f1_cache", exist_ok=True)
fastf1.Cache.enable_cache("f1_cache")

# TODO: Find a permanent location to store the database on the local machine
DB_PATH = "f1_data.db"


# %% Helpers used when inserting FastF1 data ----------------------------------
def _to_int(value):
    """NaN / None -> None, otherwise a plain int (sqlite can't store numpy ints)"""
    return None if pd.isna(value) else int(value)


def _to_float(value):
    return None if pd.isna(value) else float(value)


def _to_text(value):
    """NaN / None / "" -> None, otherwise a string"""
    return None if pd.isna(value) or str(value).strip() == "" else str(value)


def _to_seconds(value):
    return None if pd.isna(value) else value.total_seconds()


def calculateTotalSessionTime(session: Session) -> float:
    """_helper function to calculate the total session time based off of session flags_

    Args:
        session (fastf1.events.Session): _fastf1 session being loaded_

    Returns:
        float: _total time in seconds_
    """
    # can I just pass the memory location so I don't have to load it again
    # this makes a new DF
    newSessionStatus = session.session_status
    print(newSessionStatus)
    # this is when the start flag is raised so when drivers start racing
    # NOTE: will need to handle an error that comes up when status doesn't have a 'Ends' signal
    dataStreamStart = (
        (newSessionStatus.loc[newSessionStatus["Status"] == "Inactive", "Time"])
        .iloc[0]
        .total_seconds()
    )
    dataStreamEnd = (
        (newSessionStatus.loc[newSessionStatus["Status"] == "Ends", "Time"])
        .iloc[0]
        .total_seconds()
    )
    sessionStartTime = (
        (newSessionStatus.loc[newSessionStatus["Status"] == "Started", "Time"])
        .iloc[0]
        .total_seconds()
    )
    # this is when the positions are finalized I believe this is the last person to come in
    # NOTE: this will need to be sent to playcontrols VM
    sessionEndTime = (
        (newSessionStatus.loc[newSessionStatus["Status"] == "Finalised", "Time"])
        .iloc[0]
        .total_seconds()
    )
    totalSessionTime = sessionEndTime - sessionStartTime
    totalDataStreamTime = dataStreamEnd - dataStreamStart
    totalTimePerDriver = session.laps.groupby("Driver")["LapTime"].sum()
    maxTime = totalTimePerDriver.max()
    raceDurationByLapTimes = maxTime.total_seconds()

    print(f"{session.name} total data stream time = {totalDataStreamTime}")
    print(
        f"{session.name} total race time according to session time = {totalSessionTime}"
    )
    print(
        f"{session.name} total race time according to lap times = {raceDurationByLapTimes}"
    )
    return totalDataStreamTime


"""
    SCHEMA:
    _________________________________________________________________
    |                            track status table        |        |
    _________________________________________________________________
    |entry_id| session_id |time | track_safety_status      | message|
    _________________________________________________________________
    |   0    |     1      | 000 |              0           | normal |example data
    _________________________________________________________________

    NOTE: This table tracks each time the status has been changed not on a time basis.
          It doesn't update every {number} seconds like other tables. 

    track status codes as defined by Fastf1 api:
        '1': Track clear (beginning of session or to indicate the end
           of another status)
        - '2': Yellow flag (sectors are unknown)
        - '3': ??? Never seen so far, does not exist?
        - '4': Safety Car
        - '5': Red Flag
        - '6': Virtual Safety Car deployed
        - '7': Virtual Safety Car ending (As indicated on the drivers steering wheel, on tv and so on; status '1'
          will mark the actual end)
"""
# Tables/columns the handler is allowed to query. Table and column names
# can't be passed as "?" parameters in SQLite, so they get built into the
# query string -- this whitelist makes sure only known names ever get there.
ALLOWED_COLUMNS: dict = {
    "sessions": {
        "session_id",
        "year",
        "event_name",
        "session_type",
        "total_laps",
        "total_time",
    },
    "laps": {
        "lap_id",
        "session_id",
        "driver",
        "team",
        "lap_number",
        "lap_completion_timestamp",
        "lap_time_seconds",
        "compound",
        "tyre_life",
        "track_status",
        "is_pit_lap",
        "position",
        "lap_start_time",
        "lap_end_time",
    },
    "drivers": {
        "session_id",
        "driver_code",
        "full_name",
        "team",
        "number",
        "color",
    },
    "weather": {
        "weather_id",
        "session_id",
        "air_temp",
        "track_temp",
        "humidity",
        "rainfall",
        "sample_time",
    },
    "trackStatus": {
        "entry_id",
        "session_id",
        "time",
        "track_safety_status",
        "message",
    },
    "results": {
        "session_id",
        "driver_code",
        "grid_position",
        "finish_position",
        "classified_position",
        "points",
        "status",
    },
    "raceControlMessages": {
        "message_id",
        "session_id",
        "time",
        "category",
        "message",
        "status",
        "flag",
        "scope",
        "sector",
        "racing_number",
        "lap",
    },
    "live_driver_telemetry": {
        "session_id",
        "driver_code",
        "session_time",
        "source_of_data",
        "status",
        "x_pos",
        "y_pos",
        "distance_to_driver_ahead",
        "gear",
        "throttle",
        "brake",
        "drs",
        "speed",
        "rpm",
    },
}

# Tables that have a numeric elapsed-time column (seconds) we can search by.
TIME_COLUMN: dict = {
    "trackStatus": "time",
}

# What the app should show before the first recorded status change.
DEFAULT_TRACK_STATUS: dict = {
    "entry_id": -1,
    "time": 0.0,
    "statusCode": 1,
    "message": "AllClear",
}


class DBhandler:
    def __init__(self, dbPath: str = DB_PATH):
        print("loading...")
        self.dbPath = dbPath
        self.conn = sqlite3.connect(dbPath)
        self.createSchema()

    # ------------------------------------------------------------------
    # Writing to the database (moved here from Services/database.py)
    # ------------------------------------------------------------------
    def createSchema(self) -> None:
        """Creates any missing tables/columns. Safe to run on every start —
        existing tables and data are left alone."""
        self._createTables(self.conn)
        self._addMissingColumns()
        print(f"Schema created at {self.dbPath}")

    def _addMissingColumns(self) -> None:
        """Upgrade an older f1_data.db in place.

        CREATE TABLE IF NOT EXISTS never changes a table that already exists,
        so a column added to the schema later (e.g. sessions.total_time,
        laps.lap_completion_timestamp, laps.position) would be missing from
        anyone's existing database and every insert would fail. This builds the
        current schema in memory, compares it with the real database, and adds
        any column that's missing. Existing rows are kept.
        """
        reference = sqlite3.connect(":memory:")
        self._createTables(reference)
        cur = self.conn.cursor()
        tables = [
            r[0]
            for r in reference.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence'"
            )
        ]
        for table in tables:
            existing = {r[1] for r in cur.execute(f"PRAGMA table_info({table})")}
            for _, name, colType, notNull, default, _ in reference.execute(
                f"PRAGMA table_info({table})"
            ):
                if name in existing:
                    continue
                definition = f"{name} {colType}".strip()
                if default is not None:
                    definition += f" DEFAULT {default}"
                elif notNull:
                    # SQLite needs a default to add a NOT NULL column to a table with rows
                    definition += " NOT NULL DEFAULT 0"
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")
                print(f"dbhandler.py: added missing column {table}.{name}")
        reference.close()
        self.conn.commit()

    def _createTables(self, conn: sqlite3.Connection) -> None:
        """Runs every CREATE TABLE IF NOT EXISTS on the given connection."""
        cur = conn.cursor()

        """
            SCHEMA:
            _____________________________________________________________________________________
            |                                   sessions                                        |
            _____________________________________________________________________________________
            |session_id| year |    event_name    |    session_type   | total_laps|  total_time  |
            _____________________________________________________________________________________
            |   1      | 2026 | japan grand prix |        R           |     57    |  10000.52    | example data
            _____________________________________________________________________________________
    
            NOTE: 
                - need to determine how to store total_time (is text better in this instance then convert in the playcontrols vm)
                - total_time won't be loaded on db creation it will be loaded on playControls.__init__() so make it 0.00 on load
        """
        # Sessions table — one row per race/session loaded
        cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            event_name TEXT NOT NULL,
            session_type TEXT NOT NULL,
            total_laps INTEGER,
            total_time FLOAT NOT NULL,
            track_rotation REAL, 
            UNIQUE(year, event_name, session_type)
        )
        """)

        # Laps table — one row per lap, linked to a session
        cur.execute("""
        CREATE TABLE IF NOT EXISTS laps (
            lap_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            driver TEXT,
            team TEXT,
            lap_number INTEGER,
            lap_completion_timestamp,
            lap_time_seconds REAL,
            compound TEXT,
            tyre_life INTEGER,
            track_status TEXT,
            is_pit_lap INTEGER,
            position INTEGER,
            lap_start_time REAL,
            lap_end_time REAL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
        """)

        # Drivers table — one row per driver, per session (a driver's team/
        # number can change across a season, so we key on (session_id,
        # driver_code) rather than one global driver_code).
        # driver_code = FastF1's 3-letter code (e.g. "VER") — this is the
        # SAME value already stored in laps.driver, so it works as a join
        # key without changing the laps table.
        cur.execute("""
        CREATE TABLE IF NOT EXISTS drivers (
            session_id INTEGER NOT NULL,
            driver_code TEXT NOT NULL,
            full_name TEXT,
            team TEXT,
            number INTEGER,
            color TEXT,
            PRIMARY KEY (session_id, driver_code),
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
        """)

        # Weather table — one row per weather sample, linked to a session
        cur.execute("""
        CREATE TABLE IF NOT EXISTS weather (
            weather_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            air_temp REAL,
            track_temp REAL,
            humidity REAL,
            rainfall INTEGER,
            sample_time TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
        """)

        """
        SCHEMA:
        _________________________________________________________________
        |                            track status table        |        |
        _________________________________________________________________
        |entry_id| session_id |time | track_safety_status      | message|
        _________________________________________________________________
        |   0    |     1      | 000 |              0           | normal |example data
        _________________________________________________________________

        NOTE: This table tracks each time the status has been changed not on a time basis.
              It doesn't update every {number} seconds like other tables. 

        track status codes as defined by Fastf1 api:
            '1': Track clear (beginning of session or to indicate the end
               of another status)
            - '2': Yellow flag (sectors are unknown)
            - '3': ??? Never seen so far, does not exist?
            - '4': Safety Car
            - '5': Red Flag
            - '6': Virtual Safety Car deployed
            - '7': Virtual Safety Car ending (As indicated on the drivers steering wheel, on tv and so on; status '1'
              will mark the actual end)
        """
        cur.execute("""
        CREATE TABLE IF NOT EXISTS trackStatus (
            entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL, 
            time REAL NOT NULL,
            track_safety_status INTEGER NOT NULL, 
            message TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
        """)

        # Race control messages — FIA/F1 messages issued during a session.
        # Examples include yellow/green flags, safety-car notices, pit-lane
        # messages, investigations, penalties, and other control messages.
        cur.execute("""
        CREATE TABLE IF NOT EXISTS raceControlMessages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            time TEXT,
            category TEXT,
            message TEXT,
            status TEXT,
            flag TEXT,
            scope TEXT,
            sector INTEGER,
            racing_number TEXT,
            lap INTEGER,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
        """)

        # Results table — the official race result, one row per driver per session.
        # Feeds the "placement over time" graph (#44) and race outcome prediction (#42).
        # grid_position 0 = started from the pit lane.
        # finish_position = where they crossed the line (every driver gets one);
        # classified_position = the official result: a number, or "R" retired,
        # "D" disqualified, etc. status = "Finished", "Lapped", "Retired", ...
        # ? NOTE: Do we want to add a column totalRace Time
        cur.execute("""
        CREATE TABLE IF NOT EXISTS results (
            session_id INTEGER NOT NULL,
            driver_code TEXT NOT NULL,
            grid_position INTEGER,
            finish_position INTEGER,
            classified_position TEXT,
            points REAL,
            status TEXT,
            PRIMARY KEY (session_id, driver_code),
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
        """)

        # live telemetry (merged car_telemetry and driver_telemetry) this will reduce the amount of obeservations within the db.
        # should help the total file size of the db file
        """
            NOTE: what data do we need in the db?
                - Distance _float_ : distance driven in meters (could be used to estimate tire life)
                - DriverAhead _str_ : driver number of the driver ahead of car (might not need this, we already have position data from laps)
                - Distance to Driver ahead _float_ : this could be important to change the rate at which the canvas updates
                - z_pos _float_: could be important if we want to calculate driver speed and torque, or make a 3d model
                - drs _int_ : this could help us detect if the driver is slowing down or if the driver is taking a turn or if the user is speeding up
                - date_timestamp _DATETIME_: this could be used to insure the track canvas is properly is aligned.
        """
        cur.execute("""
        CREATE TABLE IF NOT EXISTS live_driver_telemetry (
            session_id INTEGER NOT NULL,
            driver_code TEXT NOT NULL,
            session_time REAL NOT NULL,
            source_of_data TEXT NOT NULL,
            status TEXT NOT NULL,
            x_pos REAL NOT NULL,
            y_pos REAL NOT NULL,
            distance_to_driver_ahead FLOAT,
            gear INTEGER,
            throttle REAL,
            brake INTEGER,
            drs INTEGER,
            SPEED REAL,
            rpm REAL,
            PRIMARY KEY (session_id, driver_code, session_time)
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )


        """)
        # table schema for circuit_corners_data
        # NOTE: this is for draw the track simulation. need corner data for some of the funcitons
        cur.execute("""
        CREATE TABLE IF NOT EXISTS circuit_corners_data (
            session_id INTEGER NOT NULL,
            corner_number INTEGER NOT NULL, 
            letter TEXT NOT NULL DEFAULT '',
            x_pos REAL NOT NULL, 
            y_pos REAL NOT NULL, 
            angle REAL,
            PRIMARY KEY (session_id, corner_number, letter),
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
        """)

        conn.commit()

    # Limiter for the telemetry step will skip _ rows in the telemetry
    def _insertTelemetry(
        self, session: Session, session_id: int, step: int = 2
    ) -> None:
        """
        _parses data from merged car telemetry and pos telemetry data, then inserts rows into live_driver_telemetry table_

        Args:
            session (Session): _fastf1 session_
            session_id (int): _id of session data being inserted into db_
            step (int): _the step amount for data wanting to be kept_
        """
        # connect to the cursor
        conn = self.conn
        cur = conn.cursor()
        # for each driver collect telemetry session.driver is organized by driver_num but our db stores driver abreviation
        for driver_num in session.drivers:
            # get driver code from driver number
            driver_code = session.get_driver(driver_num)["Abbreviation"]
            print(f"fetching telemetry for {driver_num},{driver_code}")
            # try to merge car data with position data
            try:
                telem = session.car_data[driver_num].merge_channels(
                    session.pos_data[driver_num]
                )
            except Exception:
                # if there is an issue with merging the data print out a traceback for debugging purposes
                traceback.print_exc()
                # don't let the app crash
                continue

            # if x or y is NaN remove that row NOTE: we have to have x and y to plot on the graph
            telem = telem.dropna(subset=["X", "Y"])
            # limit the amount of rows in the db set to every other row
            telem = telem.iloc[::step]

            # create a data frame with the data
            df = pd.DataFrame(
                {
                    "session_id": session_id,
                    "driver_code": driver_code,
                    "session_time": telem["SessionTime"].dt.total_seconds(),
                    "source": telem["Source"].fillna("unkown source")
                    if "Source" in telem
                    else "No Source Logged",
                    "status": telem["Status"].fillna("unkown driver status")
                    if "Status" in telem
                    else "No Source Logged",
                    "x": telem["X"].astype(float),
                    "y": telem["Y"].astype(float),
                    "ahead": None,  # see note below
                    "gear": telem["nGear"],
                    "throttle": telem["Throttle"],
                    "brake": telem["Brake"].astype(int),
                    "drs": telem["DRS"],
                    "speed": telem["Speed"],
                    "rpm": telem["RPM"],
                }
            )
            # turn it into tuples autofill any NaN values into None, don't add an index
            dfRow = (
                df.astype(object)
                .where(df.notna(), None)
                .itertuples(index=False, name=None)
            )
            cur.executemany(
                """INSERT OR IGNORE INTO live_driver_telemetry
                (session_id, driver_code, session_time, source_of_data, status,
                x_pos, y_pos, distance_to_driver_ahead, gear, throttle, brake, drs, speed, rpm)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                dfRow,
            )

    def loadSessionIntoDB(self, session: Session) -> int:
        print("loadingSessionNow")
        """_Provided a session, will insert the session data into the database_

        Args:
            session (Session): A session object from the fastf1 API.

        Reloading a session that's already in the database replaces its rows.
        """
        conn = self.conn
        cur = conn.cursor()

        # this creates a property called by session.track_status also
        session.load(telemetry=True)

        laps = session.laps.copy()
        weather = session.weather_data.copy()
        results = session.results.copy()  # has driver code, name, team, number, color
        total_laps = int(laps["LapNumber"].max())
        year = session.date.year
        event = session.event.EventName
        # copy data from session.track_status
        trackStatusDF = session.track_status.copy()
        raceControlDF = session.race_control_messages.copy()
        # ? Session5 is the race event. Do we care about practices and qualifiers? If so, we need to handle that.
        # TODO: yes because we could add a graph to show starting position diffentials vs where drivers started at the beginning of practices
        session_type = session.event.Session5
        session_time = calculateTotalSessionTime(session)
        # Insert into sessions table (or get existing session_id if already loaded)
        cur.execute(
            """
            INSERT OR IGNORE INTO sessions (year, event_name, session_type, total_laps, total_time)
            VALUES (?, ?, ?, ?, ?)
        """,
            (year, event, session_type, total_laps, session_time),
        )
        # If the session was already in the database (e.g. loaded before the
        # total_time column existed), refresh its info instead of keeping 0.0
        cur.execute(
            """
            UPDATE sessions SET total_laps = ?, total_time = ?
            WHERE year = ? AND event_name = ? AND session_type = ?
        """,
            (total_laps, session_time, year, event, session_type),
        )
        cur.execute(
            """
            SELECT session_id FROM sessions
            WHERE year=? AND event_name=? AND session_type=?
        """,
            (year, event, session_type),
        )
        session_id = cur.fetchone()[0]

        # Reloading a race used to insert its laps/weather/trackStatus rows a
        # second time (those tables have no unique key). Clear this session's old
        # rows first so a reload replaces the data instead of duplicating it.
        for table in (
            "laps",
            "weather",
            "trackStatus",
            "results",
            "live_driver_telemetry",
            "circuit_corners_data",
            "raceControlMessages",
        ):
            cur.execute(f"DELETE FROM {table} WHERE session_id = ?", (session_id,))

        # Insert drivers
        for _, row in results.iterrows():
            cur.execute(
                """
                INSERT OR IGNORE INTO drivers (session_id, driver_code, full_name, team, number, color)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    session_id,
                    row.get("Abbreviation"),
                    row.get("FullName"),
                    row.get("TeamName"),
                    row.get("DriverNumber"),
                    row.get("TeamColor"),
                ),
            )

        # Insert results
        for _, row in results.iterrows():
            cur.execute(
                """
                INSERT OR REPLACE INTO results (session_id, driver_code, grid_position,
                    finish_position, classified_position, points, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    session_id,
                    row.get("Abbreviation"),
                    _to_int(row.get("GridPosition")),
                    _to_int(row.get("Position")),
                    _to_text(row.get("ClassifiedPosition")),
                    _to_float(row.get("Points")),
                    _to_text(row.get("Status")),
                ),
            )

        # Insert laps
        # NOTE: changing laps.iterrows to laps.iterlaps so that I can call lap.get_telemetry
        # NOTE: Future change update lap table to show sessionTime for each lap so I can compare to insure correctness of simulation
        for _, lap in laps.iterlaps():
            lap_time = (
                lap["LapTime"].total_seconds() if pd.notna(lap["LapTime"]) else None
            )
            # NOTE: Keep this until I can gaurantee that the session is aligning correctly for the simulation
            lap_timedelta_str: str = str(lap["LapTime"])
            is_pit = (
                1
                if (pd.notna(lap.get("PitInTime")) or pd.notna(lap.get("PitOutTime")))
                else 0
            )
            cur.execute(
                """
                INSERT INTO laps (session_id, driver, team, lap_number, lap_completion_timestamp, lap_time_seconds,
                                   compound, tyre_life, track_status, is_pit_lap, position, lap_start_time, lap_end_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    session_id,
                    lap.get("Driver"),
                    lap.get("Team"),
                    lap.get("LapNumber"),
                    lap_timedelta_str,
                    lap_time,
                    lap.get("Compound"),
                    lap.get("TyreLife"),
                    str(lap.get("TrackStatus")),
                    is_pit,
                    _to_int(
                        lap.get("Position")
                    ),  # race position at the end of this lap
                    _to_seconds(lap.get("LapStartTime")),
                    _to_seconds(lap.get("Time")),
                ),
            )
        # insert live_driver_telemetry
        self._insertTelemetry(session=session, session_id=session_id)

        # Insert weather
        for _, row in weather.iterrows():
            cur.execute(
                """
                INSERT INTO weather (session_id, air_temp, track_temp, humidity, rainfall, sample_time)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    session_id,
                    row.get("AirTemp"),
                    row.get("TrackTemp"),
                    row.get("Humidity"),
                    int(bool(row.get("Rainfall"))),
                    str(row.get("Time")),
                ),
            )

        # insert track_status
        for _, row in trackStatusDF.iterrows():
            """ 
                Dataframe loaded by session.track_status:
                {Time: datetime.timedelta, Status: str, Message: str}
            """
            timeStampRow = row.get("Time")

            # ! timeStampRow being None needs to be handled elegantly
            assert timeStampRow is not None

            timeStampInSeconds = timeStampRow.total_seconds()

            statusNumRow = row.get("Status")

            # ! statusNumRow being None needs to be handled elegantly
            assert statusNumRow is not None

            statusNumCode = int(statusNumRow)
            message = str(row.get("Message"))

            cur.execute(
                """ 
                INSERT INTO trackStatus (session_id, time, track_safety_status, message)
                VALUES(?, ?, ?, ?)
                """,
                (session_id, timeStampInSeconds, statusNumCode, message),
            )

        # insert circuit_corners_data
        circuitInfo = session.get_circuit_info()
        cur.execute(
            "UPDATE sessions SET track_rotation = ? WHERE session_id = ?",
            (float(circuitInfo.rotation), session_id),
        )

        for _, circuit in circuitInfo.corners.iterrows():
            if pd.isna(circuit["Letter"]):
                letter = ""
            else:
                letter = str(circuit["Letter"])
            cur.executemany(
                """
                INSERT INTO circuit_corners_data
                (session_id, corner_number, letter, x_pos, y_pos, angle)
                VALUES (?,?,?,?,?,?)
                """,
                [
                    (
                        session_id,
                        int(circuit["Number"]),
                        letter,
                        float(circuit["X"]),
                        float(circuit["Y"]),
                        float(circuit["Angle"]),
                    )
                ],
            )

        # Insert race-control messages
        for _, row in raceControlDF.iterrows():
            cur.execute(
                """
                INSERT INTO raceControlMessages (
                    session_id, time, category, message, status, flag,
                    scope, sector, racing_number, lap
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    _to_text(row.get("Time")),
                    _to_text(row.get("Category")),
                    _to_text(row.get("Message")),
                    _to_text(row.get("Status")),
                    _to_text(row.get("Flag")),
                    _to_text(row.get("Scope")),
                    _to_int(row.get("Sector")),
                    _to_text(row.get("RacingNumber")),
                    _to_int(row.get("Lap")),
                ),
            )

        conn.commit()
        print(
            f"Loaded {len(results)} drivers, {len(laps)} laps, {len(weather)} "
            f"weather samples, and {len(raceControlDF)} race-control messages "
            f"for {year} {event} {session_type}"
        )
        return session_id

    def previewDB(self) -> None:
        """Helper function to print out the database"""
        conn = self.conn
        print("\n--- Sessions ---")
        print(pd.read_sql("SELECT * FROM sessions", conn))
        print("\n--- Drivers ---")
        print(pd.read_sql("SELECT * FROM drivers", conn))
        print("\n--- Sample laps ---")
        print(pd.read_sql("SELECT * FROM laps LIMIT 5", conn))
        print("\n--- Sample weather ---")
        print(pd.read_sql("SELECT * FROM weather LIMIT 5", conn))
        print("\n--- Results ---")
        print(
            pd.read_sql(
                "SELECT * FROM results ORDER BY session_id, finish_position", conn
            )
        )
        print("\n --- Sample trackStatus ---")
        print(pd.read_sql("SELECT * FROM trackStatus", conn))
        print("\n--- Sample raceControlMessages ---")
        print(pd.read_sql("SELECT * FROM raceControlMessages LIMIT 10", conn))

        print("--- Sample live_driver_telemetry ---")
        print(pd.read_sql("SELECT * FROM live_driver_telemetry LIMIT 5", conn))

    # ------------------------------------------------------------------
    # Reading from the database
    # ------------------------------------------------------------------

    def close(self) -> None:
        """closes the database connection"""
        self.conn.close()

    def getLapPositions(self, sessionID: int) -> dict[str, dict]:
        """Every driver's race position on every lap of one session.
        Feeds the Placement over Time graph (#44).

        Args:
            sessionID (int): which race (sessions.session_id)

        Returns:
            dict[str, dict]: keyed by driver code, each value contains
                laps, positions, team, color, full_name, grid, finish,
                classified, and status.
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT d.driver_code, d.full_name, d.team, d.color,
                   r.grid_position, r.finish_position,
                   r.classified_position, r.status
            FROM drivers d
            LEFT JOIN results r
                   ON r.session_id = d.session_id
                  AND r.driver_code = d.driver_code
            WHERE d.session_id = ?
            """,
            (sessionID,),
        )

        drivers: dict[str, dict] = {}

        for (
            code,
            name,
            team,
            color,
            grid,
            finish,
            classified,
            status,
        ) in cursor.fetchall():
            drivers[code] = {
                "full_name": name,
                "team": team,
                "color": (
                    f"#{color}" if color and not str(color).startswith("#") else color
                ),
                "grid": grid,
                "finish": finish,
                "classified": classified,
                "status": status,
                "laps": [],
                "positions": [],
            }

        cursor.execute(
            """
            SELECT driver, lap_number, position
            FROM laps
            WHERE session_id = ?
              AND position IS NOT NULL
            ORDER BY driver, lap_number
            """,
            (sessionID,),
        )

        for code, lap, position in cursor.fetchall():
            if code not in drivers:
                continue

            drivers[code]["laps"].append(int(lap))
            drivers[code]["positions"].append(int(position))

        fieldSize = len(drivers)

        for info in drivers.values():
            if info["laps"] and info["grid"] is not None:
                grid = info["grid"] if info["grid"] > 0 else fieldSize
                info["laps"].insert(0, 0)
                info["positions"].insert(0, grid)

        return {code: info for code, info in drivers.items() if info["laps"]}

    def getKnownDrivers(self) -> dict[str, str]:
        """Returns a list of every driver that has been recorded in the database

        Returns:
            dict[str, str]: A dictionary containing the driver code (e.g. VER) as the key and the driver's full name (e.g. Max Verstappen) as the value.
        """
        cursor = self.conn.cursor()

        cursor.execute(
            "SELECT DISTINCT driver_code, full_name FROM drivers WHERE driver_code IS NOT NULL"
        )

        rows = cursor.fetchall()

        return {code: name for code, name in rows}

    # might be able to estimate this based off of rainfall and driver comms
    def getTrackSurfaceData(self, approxTime: float) -> dict:
        # search track table
        trackSurfaceData: dict = {"surfaceTemp": 0, "surfaceStatus": "dry"}
        return trackSurfaceData

    def _checkNames(self, tableName: str, columns: tuple) -> None:
        """
        _summary_: makes sure the table and every column are in ALLOWED_COLUMNS
                   before they get put into a query string (stops SQL injection
                   through table/column names)

        Raises:
            ValueError: if the table or any column isn't allowed
        """
        if tableName not in ALLOWED_COLUMNS:
            raise ValueError(f"unknown table: {tableName}")
        for column in columns:
            if column not in ALLOWED_COLUMNS[tableName]:
                raise ValueError(f"unknown column '{column}' for table {tableName}")
        print("dbhandler.py/_checkNames: Valid access to tables within database")

    # NOTE: Flagged for Depreciation
    def getSessionID(
        self, tableName: str, year: int, eventName: str, sessionType: str
    ) -> int:
        """
        _summary_: get the session_id of one row, looked up by entry_id

        Returns:
            _type_ int: the session_id, or -1 if the row doesn't exist
        """
        # self._checkNames(tableName, ("entry_id", "session_id"))
        cursor = self.conn.cursor()
        cursor.execute(
            f"SELECT session_id FROM {tableName} WHERE year = ? AND event_name = ? AND session_type = ? LIMIT 1",
            (year, eventName, sessionType),
        )
        sessionID = cursor.fetchone()
        if sessionID is None:
            print("session_id could not be found\n")
            return -1
        # fetchone() returns a tuple like (1,) -- return the number inside it
        return sessionID[0]

    def _calculateTotalSessionTime(self, session: Session) -> float:
        """
        Args:
            session_id (int): _session id of race to calculate total time_

        Returns:
            float: _returns the total race duration_
        """

        """Time | pd.Timedelta | The drivers total race time 
        (values only given if session is ‘Race’, ‘Sprint’, ‘Sprint Shootout’ or 
        ‘Sprint Qualifying’ >and the driver was not more than one lap behind 
        the leader"""
        # can I just pass the memory location so I don't have to load it again
        # this makes a new DF
        newSessionStatus = session.session_status
        startFlag = newSessionStatus.loc[
            newSessionStatus["Status"] == "Started", "Time"
        ].iloc[0]
        endFlag = newSessionStatus.loc[
            newSessionStatus["Status"] == "Finished", "Time"
        ].iloc[-1]
        raceDuration = (endFlag - startFlag).total_seconds()
        print(f"{session.name} total session time = {raceDuration}")
        return raceDuration

    def _setSessionTotalTime(self):
        """
        _This function needs to be able to set if not set each session time in the session table with the proper session time_
        """
        print("setting total time of sessions")

    def getSessionTime(self, session_id: int) -> float | None:
        """_summary_ sends the race duration of specified session to the playControlsVM

        Args:
            session_id (int): _this is the race session that you are trying to search for_

        Returns:
            _float_: _returns a float value that is the race duration in seconds_
        """
        sessionTime: float
        # testing print statement
        print(
            f"dbhandler.py/getSessionTime: attempting to find session time at session{session_id}"
        )
        sessionDF = self.getDataFromTable(
            tableName="sessions",
            searchBy="first_entry",
            searchData=session_id,
            attributeNameTuple=("total_time",),
            sessionID=session_id,
        )

        # ! sessionDF being None is causing a CTD. This should be handled elegantly in the future.
        if sessionDF is None:
            return None

        # convert DF to float | just take the first value from the tuple
        sessionTime: float = sessionDF[0]
        return sessionTime

    def getDataFromTable(
        self,
        tableName: str,
        searchBy: str,
        searchData: int | float,
        attributeNameTuple: tuple,
        sessionID: int | None = None,
    ) -> tuple | None:
        """
        _summary_: function to get data from database tables

        NOTE:
            - added 2 ways to search because if we skipback the playcontrols then the endflag will no longer be correct
            - searching by time returns the NEAREST ENTRY AT OR BEFORE approxTime
              (the last known state at that moment), never a future entry.
              Because it only depends on approxTime, skipping back/forward on
              the play controls just works -- no stored index to go stale.
        Args:
            tableName (str): the name of the table being accessed
            searchBy (str): the manner of which you are searching entry_id | time | first_entry
            searchData (int): the index of row needed | the approxtime of data
            attributeNameTuple (tuple): attributes needed to be returned
            sessionID (int): required when searchBy == "time" -- times restart
                             at 0 for every session, so we must know which race

        Returns:
            _type_ tuple: returns a tuple of data if found
            _type_ None: returns datatype None if no data was found from query

        Raises:
            ValueError: unknown table/column, or time search without a sessionID
        """
        self._checkNames(tableName, attributeNameTuple)
        # join the tuple to one string
        attributes = ", ".join(attributeNameTuple)
        print(f"dbhandler.py/_getDataFromTable: from {tableName} grab {attributes}")
        cursor = self.conn.cursor()

        if searchBy == "time":
            timeColumn = TIME_COLUMN.get(tableName)
            if timeColumn is None:
                raise ValueError(f"table {tableName} can't be searched by time")
            if sessionID is None:
                raise ValueError("sessionID is required when searching by time")
            dbQuery = (
                f"SELECT {attributes} FROM {tableName} "
                f"WHERE session_id = ? AND {timeColumn} <= ? "
                f"ORDER BY {timeColumn} DESC, entry_id DESC LIMIT 1"
            )
            cursor.execute(dbQuery, (sessionID, float(searchData)))
        elif searchBy == "entry_id":
            dbQuery = (
                f"SELECT {attributes} FROM {tableName} WHERE {searchBy} = ? LIMIT 1"
            )
            cursor.execute(dbQuery, (searchData,))
        elif searchBy == "first_entry":
            # search by first row that returns for specified session_id NOTE find another attribute to order by
            dbQuery = f"SELECT {attributes} FROM {tableName} WHERE session_id = ? ORDER BY session_id LIMIT 1"
            cursor.execute(dbQuery, (searchData,))

        results = cursor.fetchone()
        if results is None:
            print(
                f"dbhandler.py/getDataFromTable: No data found for {attributes} at {searchBy}: {searchData} within {tableName}"
            )
            return None
        # return data from dbQuery to the function that needs it
        # NOTE: might be nice to return a dictionary so that it is easier to read from
        return results

    def getSessionsFromDB(self) -> list[dict]:
        cursor = self.conn.cursor()
        attributes = ("year", "event_name", "session_type")
        columns = ", ".join(attributes)

        cursor.row_factory = sqlite3.Row
        cursor.execute(
            f"""
                SELECT {columns} FROM sessions
            """
        )
        sessionTableDict: list[dict] = []
        # for each row within the list append each to the dict based on their columnNames for keys
        for row in cursor.fetchall():
            rowDict = dict(row)
            rowDict["downloaded"] = True
            sessionTableDict.append(rowDict)

        # procecs the sessionTable and make it a list[dicts]
        return sessionTableDict

    # NOTE: rewrite this to be more standard compared to other getters
    def getDriverPosData(self, session_id: int) -> pd.DataFrame:
        """_return a dataframe with all of the position data from a session then order by driver and time_

        Args:
            session_id (int): _description_

        Returns:
            pd.DataFrame: _description_
        """
        return pd.read_sql_query(
            """
        SELECT driver_code, session_time, x_pos, y_pos
        FROM live_driver_telemetry
        WHERE session_id = ?
        ORDER BY driver_code, session_time
        """,
            self.conn,
            params=(session_id,),
        )

    def getFastestLapPositions(self, session_id: int) -> pd.DataFrame:
        row = self.conn.execute(
            """
            SELECT driver, lap_start_time, lap_end_time 
            FROM laps 
            WHERE session_id = ? AND lap_time_seconds IS NOT NULL AND lap_start_time IS NOT NULL AND lap_end_time IS NOT NULL
            ORDER BY lap_time_seconds ASC LIMIT 1
            """,
            (session_id,),
        ).fetchone()
        if row is None:
            return pd.DataFrame(columns=["X", "Y"])
        driver, startTime, endTime = row
        return pd.read_sql_query(
            """ 
            SELECT x_pos, y_pos
            FROM live_driver_telemetry
            WHERE session_id = ? AND driver_code = ? AND session_time BETWEEN ? AND ?
            ORDER BY session_time
            """,
            self.conn,
            params=(session_id, driver, startTime, endTime),
        )

    def getCircuitRotation(self, session_id: int) -> float:
        row = self.conn.execute(
            "SELECT track_rotation FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        return float(row[0]) if row and row[0] is not None else 0.0

    def getCorners(self, session_id: int) -> pd.DataFrame:
        return pd.read_sql_query(
            """
            SELECT corner_number, letter, x_pos, y_pos, angle
            FROM circuit_corners_data
            WHERE session_id = ?
            ORDER BY corner_number
            """,
            self.conn,
            params=(session_id,),
        )

    def __deleteSessionData(self, session_id: int) -> None:
        """
        _delete session data from the database to keep the total size of application down_
        """

    # NOTE: Flagged for depreciation once moved to trackStatusVM
    def _getNextStatusChange(
        self, sessionID: int, entryID: int, time: float
    ) -> float | None:
        """
        _summary_: finds when the NEXT track status change happens in this session

        Returns:
            _type_ float: time (seconds) of the next change
            _type_ None: there are no more changes -> this is the last one (endFlag)
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT time FROM trackStatus
            WHERE session_id = ?
              AND (time > ? OR (time = ? AND entry_id > ?))
            ORDER BY time ASC, entry_id ASC
            LIMIT 1
            """,
            (sessionID, time, time, entryID),
        )
        nextRow = cursor.fetchone()
        print(f"data found: {nextRow}")
        return None if nextRow is None else nextRow[0]

    # NOTE: flagged for depreciation once validation checks are moved to trackStatusVM
    def getTrackSafetyStatus(
        self,
        approxTime: float = 0.00,
        currentSessionID: int = 1,
        currentIndex: int = -1,
        endFlag: bool = False,
    ) -> dict:
        """
        _summary_: get track data from db and return it to the track status view model

        Args:
            approxTime (float): the approximate time (seconds into the session) of the data for which you are looking
            currentSessionID (int): which session you are grabbing data for
            currentIndex (int): entry_id to grab directly; leave as -1 to search by approxTime
            endFlag (bool): kept for compatibility -- it is now worked out here, not passed in

        Returns:
            _type_ dict: {"entry_id", "time", "statusCode", "message",
                          "endFlag", "nextChangeTime"}
                endFlag is True when there are no more status changes after this one.
                nextChangeTime is when the VM needs to ask again (None at the end).
        """
        columns = ("entry_id", "session_id", "time", "track_safety_status", "message")
        trackTableData: tuple | None
        if currentIndex == -1:
            # pull data via approxTime (nearest entry at or before it)
            trackTableData = self.getDataFromTable(
                tableName="trackStatus",
                searchBy="time",
                searchData=approxTime,
                attributeNameTuple=columns,
                sessionID=currentSessionID,
            )
        else:
            # pull data via entry_id
            trackTableData = self.getDataFromTable(
                tableName="trackStatus",
                searchBy="entry_id",
                searchData=currentIndex,
                attributeNameTuple=columns,
            )
            if trackTableData is not None and trackTableData[1] != currentSessionID:
                print(
                    f"entry {currentIndex} belongs to session {trackTableData[1]}, not {currentSessionID}"
                )
                trackTableData = None

        if trackTableData is None:
            # before the first recorded change (or bad index): report a clear track
            trackStatusData = dict(DEFAULT_TRACK_STATUS)
            firstChange = self._getNextStatusChange(currentSessionID, -1, float("-inf"))
            trackStatusData["endFlag"] = firstChange is None
            trackStatusData["nextChangeTime"] = firstChange
            return trackStatusData

        entryID, _, time, statusCode, message = trackTableData
        nextChangeTime: float | None = self._getNextStatusChange(
            currentSessionID, entryID, time
        )
        # set trackStatusData to send to trackStatusVM
        trackStatusData: dict = {
            "entry_id": entryID,
            "time": time,
            "statusCode": statusCode,
            "message": message,
            "endFlag": nextChangeTime is None,
            "nextChangeTime": nextChangeTime,
        }
        print(
            f"dbhandler.py/DBhandler/getTrackSafetyStatus: nextChangeTime in trackStatusData: {trackStatusData['nextChangeTime']}"
        )
        return trackStatusData

    """
                                driver table
    ______________________________________________________________________
    time | driver name | lap number |  |  
    ______________________________________________________________________
    0.00 |         0         |       97.2       |         "dry"          | 
    ______________________________________________________________________

    """

    def getDriverSpeed(self, approxTime: float, driverCode: str = "") -> float:
        # stub -- needs a telemetry (speed) table first; takes a driverCode
        # because speed is different for every driver
        return 0.00

    def getFirstIndexOfTrackStatus(self, session_id: int) -> int:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT entry_id 
            FROM trackStatus 
            WHERE session_id = ? 
            ORDER BY time ASC, entry_id ASC 
            LIMIT 1
            """,
            (session_id,),
        )
        row = cursor.fetchone()
        return row[0] if row is not None else -1

    def getMetricSeries(
        self, spec: MetricSpec, session_id: int, driver: str | None = None
    ) -> pd.DataFrame:
        """Generic series for a given spec. The x-axis is always in time (seconds).

        Args:
            spec (MetricSpec): The MetricSpec object to use
            session_id (int): What session to generate graphs for
            driver (str | None, optional): The driver to grab objects for. Defaults to None.

        Returns:
            pd.DataFrame: A dataframe object to graph over
        """
        cols = (spec.time_column, spec.column)
        if spec.per_driver:
            cols += (spec.driver_column,)
        self._checkNames(spec.table, cols)

        query = (
            f"SELECT {spec.time_column} AS t, {spec.column} AS y "
            f"FROM {spec.table} "
            f"WHERE session_id = ? AND {spec.column} IS NOT NULL AND {spec.time_column} IS NOT NULL"
        )
        params: list = [session_id]
        if spec.per_driver and driver is not None:
            query += f" AND {spec.driver_column} = ?"
            params.append(driver)
        query += f" ORDER BY {spec.time_column}"

        df = pd.read_sql_query(query, self.conn, params=params)
        if spec.time_is_text and not df.empty:
            df["t"] = pd.to_timedelta(df["t"]).dt.total_seconds()
        return df

    def getSessionDrivers(self, session_id: int) -> list[tuple[str, str | None]]:
        """Gets a list of drivers and colors for those drivers.

        Args:
            session_id (int): What session to generate graphs for

        Returns:
            list[tuple[str, str | None]]: A list of form [(Driver Code, Color), ...] where Color **CAN** be None.
        """

        rows = self.conn.execute(
            """
            SELECT d.driver_code, d.color
            FROM drivers d
            LEFT JOIN results r
                ON r.session_id = d.session_id AND r.driver_code = d.driver_code
            WHERE d.session_id = ?
            ORDER BY r.finish_position IS NULL, r.finish_position
            """,
            (session_id,),
        ).fetchall()

        return [
            (code, f"#{c}" if c and not str(c).startswith("#") else c)
            for code, c in rows
        ]


def main():
    dbHandler = DBhandler()
    dbHandler.loadSessionIntoDB(fastf1.get_session(2026, "Japanese Grand Prix", "R"))
    dbHandler.getSessionsFromDB()
    return 0


if __name__ == "__main__":
    main()
