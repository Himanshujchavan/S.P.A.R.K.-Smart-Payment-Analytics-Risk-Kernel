from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session
from api.core.db import get_db
from ml.training._model_io import DEFAULT_MODEL_VERSION, load_artifact

from api.services.score_service import reload_model

router = APIRouter(prefix="/model/health", tags=["Model Health"])

def _model_bundle():
    try:
        return load_artifact(DEFAULT_MODEL_VERSION)
    except Exception:
        return {"version": DEFAULT_MODEL_VERSION, "metadata": {}, "thresholds": {"allow": 0.45, "challenge": 0.75}}

@router.get("", response_model=Dict[str, Any])
@router.get("/", response_model=Dict[str, Any])
def get_model_health(db: Session = Depends(get_db)):
    bundle = _model_bundle()
    metadata = bundle.get("metadata", {})
    thresholds = bundle.get("thresholds", {})
    row = db.execute(text("SELECT allow_threshold, challenge_threshold FROM decision_thresholds WHERE config_id = TRUE")).mappings().first()
    if row:
        thresholds = {"allow": float(row["allow_threshold"]), "challenge": float(row["challenge_threshold"])}
    rows = db.execute(text("SELECT snapshot_date, psi_score, feature_drift, alert_triggered FROM drift_snapshots ORDER BY snapshot_date DESC LIMIT 30")).mappings().all()
    psi_history = [{"date": str(r["snapshot_date"]), "psi": float(r["psi_score"]), "alert": bool(r["alert_triggered"])} for r in reversed(rows)]
    current_psi = psi_history[-1]["psi"] if psi_history else None
    current_status = "UNKNOWN" if current_psi is None else ("ALERT" if current_psi >= 0.25 else "WARNING" if current_psi >= 0.10 else "STABLE")
    feature_drift = []
    if rows and rows[0].get("feature_drift"):
        fd = rows[0]["feature_drift"]
        feature_drift = fd if isinstance(fd, list) else [{"feature": k, "score": v} for k, v in fd.items()]
    return {"model": {"version": bundle.get("version", DEFAULT_MODEL_VERSION), "trained_on": metadata.get("trained_at"), "last_retrained": metadata.get("calibrated_at"), "accuracy": metadata.get("accuracy"), "macro_f1": metadata.get("macro_f1"), "thresholds": thresholds, "metrics": metadata.get("metrics", {}), "current_drift_status": current_status}, "psi": psi_history, "feature_drift": feature_drift}

@router.put("/thresholds", response_model=Dict[str, float])
def update_thresholds(payload: Dict[str, float], db: Session = Depends(get_db)):
    allow = float(payload.get("allow"))
    challenge = float(payload.get("challenge"))
    if not 0 <= allow < challenge <= 1:
        raise HTTPException(status_code=400, detail="Thresholds must satisfy 0 <= allow < challenge <= 1")
    db.execute(text("UPDATE decision_thresholds SET allow_threshold=:allow, challenge_threshold=:challenge, updated_at=NOW() WHERE config_id=TRUE"), {"allow": allow, "challenge": challenge})
    db.commit()
    return {"allow": allow, "challenge": challenge}

@router.post("/reload")
def trigger_model_reload():
    try:
        reload_model()
        return {"status": "success", "message": "Model artifact and cached explainers reloaded successfully."}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
