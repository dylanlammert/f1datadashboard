"""
Services/database.py — kept for backwards compatibility.

All database code now lives in Services/dbhandler.py (DBhandler). These
functions just forward to it, so existing imports such as
    from Services.database import DB_PATH, create_schema, load_session_into_db
keep working. New code should use DBhandler directly.
"""

from fastf1.events import Session

from Services.dbhandler import (  # noqa: F401  (re-exported for old imports)
    DB_PATH,
    DBhandler,
    _to_float,
    _to_int,
    _to_text,
    calculateTotalSessionTime,
)


def create_schema(db_path: str = DB_PATH) -> None:
    """Create any missing tables/columns. Same as DBhandler(db_path)."""
    DBhandler(db_path).close()


def load_session_into_db(session: Session, db_path: str = DB_PATH) -> None:
    """Insert a FastF1 session into the database. Same as DBhandler.loadSessionIntoDB."""
    handler = DBhandler(db_path)
    try:
        handler.loadSessionIntoDB(session)
    finally:
        handler.close()


def _preview_db(db_path: str = DB_PATH) -> None:
    handler = DBhandler(db_path)
    try:
        handler.previewDB()
    finally:
        handler.close()


def _main():
    import fastf1

    handler = DBhandler()
    handler.loadSessionIntoDB(fastf1.get_session(2023, "Bahrain", "R"))
    handler.previewDB()
    handler.close()
    return 0


if __name__ == "__main__":
    _main()
