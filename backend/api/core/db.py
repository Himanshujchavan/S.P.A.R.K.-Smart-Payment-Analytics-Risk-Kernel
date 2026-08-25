# api/core/db.py
# SQLAlchemy database engine and session factory.
#
# We deliberately avoid `declarative_base()` for now — the codebase uses
# `sqlalchemy.text()` raw SQL for queries so all schema lives in migrations,
# not in Python ORM models. Add ORM models later if/when they earn their
# keep (e.g. complex relationships on the graph side).

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from api.core.config import settings

# Configure SQLAlchemy engine with connection pooling and pre-ping to handle stale connections
engine = create_engine(
    settings.DATABASE_URL, pool_size=20, max_overflow=10, pool_pre_ping=True, echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency yielding a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
