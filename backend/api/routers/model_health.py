// backend/api/routers/model_health.py
// FastAPI router providing model health and metrics information.

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from api.core.db import get_db
from api.schemas.auth import TokenResponse  # Reusing TokenResponse schema for simplicity

router = APIRouter(prefix="/model/health", tags=["Model Health"])

# Dummy data structure – replace with real model metadata retrieval as needed.
MODEL_HEALTH = {
    "version": "xgboost-v2.4.1",
    "trained_on": "2025-08-01",
    "last_retrained": "2026-08-08",
    "accuracy": 0.978,
    "precision": {"allow": 0.99, "challenge": 0.62, "block": 0.85},
    "recall": {"allow": 0.99, "challenge": 0.55, "block": 0.79},
    "psi": [
        {"date": "2026-07-30", "psi": 0.04},
        {"date": "2026-07-31", "psi": 0.045},
        {"date": "2026-08-01", "psi": 0.06},
        {"date": "2026-08-02", "psi": 0.07},
    ],
    "feature_drift": [
        {"feature": "velocity_1h", "score": 0.18, "trend": "up"},
        {"feature": "device_reuse", "score": 0.12, "trend": "up"},
        {"feature": "geo_mismatch", "score": 0.09, "trend": "flat"},
    ],
}

@router.get("", response_model=TokenResponse, status_code=status.HTTP_200_OK)
def get_model_health(db: Session = Depends(get_db)):
    """Return model health information.
    In a real implementation this would query a database or MLflow tracking server.
    Here we return a static payload wrapped in the existing TokenResponse schema for
    compatibility with the front‑end's current expectations.
    """
    # Re‑use TokenResponse fields (access_token, refresh_token, expires_in) to pass data.
    # The front‑end will need to adapt to this shape; for now we embed JSON in the
    # access_token field as a quick shim.
    import json
    payload = json.dumps(MODEL_HEALTH)
    return TokenResponse(
        access_token=payload,
        refresh_token="",
        expires_in=0,
    )
