"""
VisionTrace AI – Database Connection and Session Management
Configured for SQLAlchemy 2.0 with connection pooling and health checking.
"""
import logging
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


import logging
import socket
from pathlib import Path
from typing import Generator
from urllib.parse import urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


def _is_postgres_available(db_url: str, timeout: float = 0.25) -> bool:
    """Quick socket probe to check if PostgreSQL server is listening."""
    try:
        parsed = urlparse(db_url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 5432
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, TimeoutError):
        return False


def create_configured_engine():
    """
    Creates the SQLAlchemy engine.
    In development mode, if PostgreSQL is configured but unreachable
    (e.g., Docker or local PostgreSQL service is not running),
    it automatically falls back to a local SQLite database in the storage directory
    so that local testing, UI exploration, and video uploads work seamlessly.
    """
    db_url = settings.database_url
    engine_kwargs = {"pool_pre_ping": True}

    if db_url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
        eng = create_engine(db_url, **engine_kwargs)
        import app.models  # noqa: F401
        Base.metadata.create_all(bind=eng)
        return eng

    # For PostgreSQL:
    engine_kwargs.update({
        "pool_size": 10,
        "max_overflow": 20,
        "pool_timeout": 5,
        "pool_recycle": 1800,
    })

    if settings.app_env == "development":
        # Fast socket check before waiting for psycopg connection timeout
        if not _is_postgres_available(db_url):
            dev_db = settings.storage_base / "visiontrace_dev.db"
            dev_url = f"sqlite:///{dev_db.as_posix()}"
            logger.info("PostgreSQL offline on port 5432. Active dev DB: %s", dev_url)
            dev_engine = create_engine(
                dev_url,
                connect_args={"check_same_thread": False},
                pool_pre_ping=True,
            )
            import app.models  # noqa: F401
            Base.metadata.create_all(bind=dev_engine)
            return dev_engine

    # Test connection to PostgreSQL before committing to it in development
    test_engine = create_engine(db_url, **engine_kwargs)
    try:
        with test_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Connected to PostgreSQL at %s", db_url.split("@")[-1])
        return test_engine
    except Exception as exc:
        test_engine.dispose()
        if settings.app_env == "development":
            dev_db = settings.storage_base / "visiontrace_dev.db"
            dev_url = f"sqlite:///{dev_db.as_posix()}"
            logger.warning(
                "⚠️ PostgreSQL is unreachable at %s. Falling back to SQLite development database: %s",
                db_url,
                dev_url,
            )
            dev_engine = create_engine(
                dev_url,
                connect_args={"check_same_thread": False},
                pool_pre_ping=True,
            )
            import app.models  # noqa: F401
            Base.metadata.create_all(bind=dev_engine)
            return dev_engine
        # In non-development mode, return the configured PostgreSQL engine
        return create_engine(db_url, **engine_kwargs)


engine = create_configured_engine()

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def init_db():
    """Ensure database schema is created when running on SQLite development mode."""
    if engine.url.drivername.startswith("sqlite"):
        import app.models  # noqa: F401
        Base.metadata.create_all(bind=engine)
        logger.info("Initialized local development schema on SQLite (%s)", engine.url)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a transactional database session per request.
    Automatically closes the session when the request finishes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> tuple[bool, str]:
    """
    Checks whether the database server is reachable and accepting queries.
    Returns (True, "connected") or (False, error_message).
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "connected"
    except Exception as exc:
        return False, str(exc)
