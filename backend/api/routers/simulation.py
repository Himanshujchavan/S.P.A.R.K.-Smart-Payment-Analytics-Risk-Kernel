# api/routers/simulation.py
# FastAPI router for triggering and monitoring load simulations.

from typing import Any, Dict
from fastapi import APIRouter, status
from datetime import datetime

router = APIRouter(prefix="/simulation", tags=["Simulation"])

@router.post("/start", status_code=status.HTTP_200_OK)
def start_simulation(payload: Dict):
    """Trigger a synthetic traffic load test.

    Expects: { "rate": int, "duration": int, "scenario": str }
    """
    # In a real system, this would spawn a Celery task or a subprocess running load_test.py
    return {
        "runId": f"sim_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "rate": payload.get("rate", 100),
        "duration": payload.get("duration", 60),
        "scenario": payload.get("scenario", "default"),
        "startedAt": datetime.now().isoformat(),
        "status": "running"
    }
