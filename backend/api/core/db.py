import logging
from fastapi import HTTPException, status
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from api.core.config import settings

logger = logging.getLogger(__name__)
engine = create_engine(settings.DATABASE_URL, pool_size=20, max_overflow=10, pool_pre_ping=True, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
    except Exception as exc:
        logger.exception("Database unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from exc
    try:
        yield db
    finally:
        db.close()
