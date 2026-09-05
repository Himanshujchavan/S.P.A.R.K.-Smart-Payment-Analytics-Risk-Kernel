from typing import Any, Dict, List
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from api.core.db import get_db
from ml.training._model_io import DEFAULT_MODEL_VERSION, load_artifact
router = APIRouter(prefix="/analytics", tags=["Analytics"])

def _bundle():
    try: return load_artifact(DEFAULT_MODEL_VERSION)
    except Exception: return {}

@router.get("/metrics", response_model=List[Dict[str, Any]])
def get_metrics(db: Session = Depends(get_db)):
    bundle=_bundle(); metrics=bundle.get("metadata",{}).get("metrics")
    if metrics: return [{"tier": tier, **vals} for tier, vals in metrics.items()]
    rows=db.execute(text("SELECT decision, count(*) AS support FROM model_scores GROUP BY decision")).mappings().all()
    return [{"tier": r["decision"], "support": int(r["support"])} for r in rows]

@router.get("/cost-curve", response_model=List[Dict[str, Any]])
def get_cost_curve(db: Session = Depends(get_db)):
    curve=_bundle().get("metadata",{}).get("cost_curve")
    if not curve: return []
    return [{"threshold": p["threshold"], "threeTier": p["cost"]} for p in curve]

@router.get("/kpis", response_model=Dict[str, Any])
def get_dashboard_kpis(db: Session = Depends(get_db)):
    scored_today=int(db.execute(text("SELECT count(*) FROM model_scores WHERE scored_at >= CURRENT_DATE")).scalar() or 0)
    counts=db.execute(text("SELECT decision, count(*) AS count FROM model_scores WHERE scored_at >= CURRENT_DATE GROUP BY decision")).mappings().all()
    tier={"allow":0,"challenge":0,"block":0}; tier.update({r["decision"]:int(r["count"]) for r in counts})
    fraud_rate=float(db.execute(text("SELECT COALESCE(AVG(CASE WHEN fl.is_fraud THEN 1.0 ELSE 0.0 END),0) FROM model_scores ms JOIN fraud_labels fl ON fl.txn_id=ms.txn_id WHERE ms.scored_at >= CURRENT_DATE")).scalar() or 0)
    active_alerts=int(db.execute(text("SELECT count(*) FROM drift_snapshots WHERE alert_triggered=true AND snapshot_date >= CURRENT_DATE - 7")).scalar() or 0)
    psi=db.execute(text("SELECT psi_score FROM drift_snapshots ORDER BY snapshot_date DESC LIMIT 1")).scalar()
    return {"scoredToday":scored_today,"fraudRate":fraud_rate,"activeAlerts":active_alerts,"avgLatencyMs":None,"tierBreakdown":tier,"ringActivity":int(db.execute(text("SELECT count(*) FROM detected_rings WHERE status='active'")).scalar() or 0),"psiCurrent":float(psi) if psi is not None else None,"modelVersion":DEFAULT_MODEL_VERSION}
