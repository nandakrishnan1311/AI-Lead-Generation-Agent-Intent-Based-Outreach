"""
database/db.py — SQLite engine, session factory, and helpers.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.database.models import Base
from app.config import DATABASE_PATH
from app.utils.logger import get_logger

logger = get_logger(__name__)

# SQLite engine — check_same_thread=False required for FastAPI async usage
_engine = create_engine(
    f"sqlite:///{DATABASE_PATH}",
    connect_args={"check_same_thread": False},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def init_db() -> None:
    """Create all tables if they don't exist yet."""
    Base.metadata.create_all(bind=_engine)
    logger.info("Database initialised at %s", DATABASE_PATH)


def get_db() -> Session:
    """FastAPI dependency — yields a DB session and ensures it's closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
