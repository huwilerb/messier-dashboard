"""Database engine setup and FastAPI session dependency."""

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

# SQLite needs this connect_arg when used from multiple threads (FastAPI's
# default threadpool for sync endpoints).
_connect_args = (
    {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
)

engine = create_engine(
    settings.DATABASE_URL, echo=settings.DEBUG, connect_args=_connect_args
)

if settings.DATABASE_URL.startswith("sqlite"):
    # Defaults (journal_mode=DELETE, synchronous=FULL, no busy_timeout) make
    # every writer block all readers and fsync on every commit, and make
    # concurrent access raise "database is locked" instead of waiting --
    # all needlessly costly on the slow disk/IO of a small low-end host.
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def _ensure_sqlite_parent_dir() -> None:
    """Create the parent directory of a sqlite file-based DB if needed."""
    if not settings.DATABASE_URL.startswith("sqlite:///"):
        return
    db_path = settings.DATABASE_URL.removeprefix("sqlite:///")
    if db_path in (":memory:", ""):
        return
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)


def create_db_and_tables() -> None:
    """Create all tables declared via SQLModel metadata (idempotent)."""
    _ensure_sqlite_parent_dir()
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a SQLModel session."""
    with Session(engine) as session:
        yield session
