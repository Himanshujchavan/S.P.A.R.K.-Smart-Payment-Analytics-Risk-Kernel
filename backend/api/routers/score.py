# api/routers/score.py
# FastAPI router for real-time transaction scoring and risk decisioning.

from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from api.core.db import get_db
from api.core.redis_client import limiter
from api.schemas.score import RiskDecisionResponse, ScoreRequest
from api.services.score_service import score_transaction

router = APIRouter(prefix="/score", tags=["Scoring"])


@router.post("", response_model=RiskDecisionResponse, status_code=status.HTTP_200_OK)
@limiter.limit("120/minute")
def score(request: Request, body: ScoreRequest, db: Session = Depends(get_db)):
    """Accept a transaction payload, assemble real-time velocity and graph features,

    execute XGBoost model inference, apply three-tier cost-calibrated thresholds,
    generate SHAP and counterfactual explainability, log immutable audit trails,
    and return the final risk decision.
    """
    try:
        payload = body.model_dump()
        decision = score_transaction(db, payload)
        return decision
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scoring error: {str(e)}",
        )
