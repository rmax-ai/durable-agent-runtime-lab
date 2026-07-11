"""SQLite database setup using SQLModel.

Provides engine creation and session management for state projections.
"""

from pathlib import Path

from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine


def get_engine(data_dir: Path) -> Engine:
    """Create a SQLite engine for the project database."""
    db_path = data_dir / "dar_state.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    return engine


def init_db(engine: Engine) -> None:
    """Create all tables."""
    SQLModel.metadata.create_all(engine)


def get_session(engine: Engine) -> Session:
    """Get a new session."""
    return Session(engine)
