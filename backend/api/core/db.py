# api/core/db.py
# SQLAlchemy database engine and session factory.
#
# We deliberately avoid `declarative_base()` for now — the codebase uses
# `sqlalchemy.text()` raw SQL for queries so all schema lives in migrations,
# not in Python ORM models. Add ORM models later if/when they earn their
# keep (e.g. complex relationships on the graph side).

import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from api.core.config import settings

logger = logging.getLogger(__name__)

# Configure SQLAlchemy engine with connection pooling and pre-ping
engine = create_engine(
    settings.DATABASE_URL, pool_size=20, max_overflow=10, pool_pre_ping=True, echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency yielding a database session per request.
    Yields None gracefully if PostgreSQL host/container is unavailable.
    """
    db = None
    try:
        db = SessionLocal()
        # Ping connection to verify availability
        db.execute(text("SELECT 1"))
        yield db
    except Exception as e:
        logger.warning(f"Database connection unavailable ({e}). Running in fallback mode.")
        yield None
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                pass

