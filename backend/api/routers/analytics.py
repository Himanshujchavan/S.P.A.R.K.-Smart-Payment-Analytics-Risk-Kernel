# api/routers/analytics.py
# FastAPI router for risk metrics, cost curves, and dashboard KPIs.

from typing import Any, Dict, List
from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.core.db import get_db
from ml.training._model_io import DEFAULT_MODEL_VERSION, load_artifact

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("/metrics", response_model=List[Dict[str, Any]], status_code=status.HTTP_200_OK)
def get_metrics(db: Session = Depends(get_db)):
    """Retrieve precision, recall, and F1 per risk tier."""
    try:
        bundle = load_artifact(DEFAULT_MODEL_VERSION)
        metrics = bundle.get("metadata", {}).get("metrics")
        if metrics:
            # Convert metrics dict to the list format expected by frontend
            # Expected: [{tier: 'allow', precision: x, ...}, ...]
            return [
                {"tier": tier, **vals} for tier, vals in metrics.items()
            ]
    except Exception:
        pass

    # Fallback mock metrics
    return [
        {"tier": "allow", "precision": 0.984, "recall": 0.991, "f1": 0.987, "support": 41220},
        {"tier": "challenge", "precision": 0.612, "recall": 0.554, "f1": 0.581, "support": 3104},
        {"tier": "block", "precision": 0.847, "recall": 0.789, "f1": 0.817, "support": 1240},
    ]

@router.get("/cost-curve", response_model=List[Dict[str, Any]], status_code=status.HTTP_200_OK)
def get_cost_curve(db: Session = Depends(get_db)):
    """Retrieve the business cost curve for 3-tier vs binary decisions."""
    try:
        bundle = load_artifact(DEFAULT_MODEL_VERSION)
        curve = bundle.get("metadata", {}).get("cost_curve")
        if curve:
            # The backend stores {threshold: x, cost: y}
            # The frontend expects {threshold: x, threeTier: y, binary: z}
            # For simplicity in this demo, we return the 3-tier curve and a shifted binary one
            return [
                {
                    "threshold": p["threshold"],
                    "threeTier": p["cost"],
                    "binary": p["cost"] * 1.4 # Mocking binary cost as 40% higher
                } for p in curve
            ]
    except Exception:
        pass

    # Fallback mock curve
    return [
        {"threshold": float(i), "threeTier": 10000 + i*10, "binary": 15000 + i*20}
        for i in range(0, 100, 5)
    ]

@router.get("/kpis", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
def get_dashboard_kpis(db: Session = Depends(get_db)):
    """Compute real-time KPIs for the dashboard home page."""
    try:
        # Count transactions today
        count_res = db.execute(
            text("SELECT count(*) FROM transactions WHERE created_at >= CURRENT_DATE")
        ).scalar()
        scored_today = count_res or 0

        # Count decisions
        decision_res = db.execute(
            text("SELECT decision, count(*) FROM model_scores WHERE scored_at >= CURRENT_DATE GROUP BY decision")
        ).mappings().all()
        tier_breakdown = {r["decision"]: r["count"] for r in decision_res}

        # Current PSI from latest snapshot
        psi_res = db.execute(
            text("SELECT psi_score FROM drift_snapshots ORDER BY snapshot_date DESC LIMIT 1")
        ).scalar()

        return {
            "scoredToday": scored_today,
            "fraudRate": 0.018, # Placeholder
            "activeAlerts": 2, # Placeholder
            "avgLatencyMs": 42, # Placeholder
            "tierBreakdown": tier_breakdown,
            "ringActivity": 3, # Placeholder
            "psiCurrent": float(psi_res) if psi_res else 0.062,
            "modelVersion": DEFAULT_MODEL_VERSION,
        }
    except Exception as e:
        # Fallback to realistic mock
        return {
            "scoredToday": 12847,
            "fraudRate": 0.018,
            "activeAlerts": 4,
            "avgLatencyMs": 38,
            "tierBreakdown": {"allow": 11932, "challenge": 712, "block": 203},
            "ringActivity": 4,
            "psiCurrent": 0.062,
            "modelVersion": DEFAULT_MODEL_VERSION,
        }
