"""Database engine setup and FastAPI session dependency."""

from collections.abc import Generator
from pathlib import Path

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
