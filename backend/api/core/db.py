# api/core/db.py
# SQLAlchemy database engine, session factory, and connection pool configuration

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from api.core.config import settings

# Configure SQLAlchemy engine with connection pooling and pre-ping to handle stale connections
engine = create_engine(
    settings.DATABASE_URL, pool_size=20, max_overflow=10, pool_pre_ping=True, echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency yielding a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
