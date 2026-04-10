"""
backend/core/database.py (Hardened)
Fix #16: Now uses settings object instead of raw os.getenv() for DB config.
"""
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from backend.core.config import settings

logger = logging.getLogger(__name__)

_SQLITE_URL = "sqlite:///./dreamagent.db"
_PG_URL = (
    f"postgresql://{settings.PG_USER}:{settings.PG_PASSWORD}"
    f"@{settings.PG_HOST}:{settings.PG_PORT}/{settings.PG_DB}"
)


def _build_engine():
    # Fast bypass for local development without Postgres running
    if not settings.PG_PASSWORD or settings.PG_PASSWORD in ("yourpassword", ""):
        import os
        os.environ["ACTIVE_DB_DIALECT"] = "sqlite"
        return create_engine(_SQLITE_URL, connect_args={"check_same_thread": False})

    try:
        eng = create_engine(_PG_URL, pool_pre_ping=True, connect_args={"connect_timeout": 3})
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("✅ Connected to PostgreSQL")
        import os
        os.environ["ACTIVE_DB_DIALECT"] = "postgresql"
        return eng
    except Exception as e:
        logger.warning("PostgreSQL unavailable. Falling back to SQLite.")
        import os
        os.environ["ACTIVE_DB_DIALECT"] = "sqlite"
        return create_engine(_SQLITE_URL, connect_args={"check_same_thread": False})


DATABASE_URL = _PG_URL  # informational only
engine = _build_engine()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
