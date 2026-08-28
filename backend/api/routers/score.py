from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from api.core.db import get_db
from api.services.score_service import score_transaction
from api.schemas.auth import TokenResponse

router = APIRouter(prefix="/score", tags=["Scoring"])

@router.post("", response_model=TokenResponse)
def score(request_body: dict, db: Session = Depends(get_db)):
    """Accept a transaction payload, compute a risk score, and return a decision.
    Placeholder implementation – returns a dummy Allow decision.
    """
    decision = score_transaction(db, request_body)
    return decision
