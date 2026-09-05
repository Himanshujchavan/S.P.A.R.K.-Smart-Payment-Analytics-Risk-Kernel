# api/services/drift_service.py
# Automated drift monitoring service for S.P.A.R.K.
#
# This service computes the Population Stability Index (PSI) between the
# baseline scores (from training) and recent live scores from production.

from __future__ import annotations

import logging
import numpy as np
from typing import Any, Dict, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.core.db import SessionLocal
from ml.drift.psi_monitor import calculate_psi, evaluate_drift, save_drift_snapshot
from ml.training._model_io import load_artifact, DEFAULT_MODEL_VERSION, model_dir

logger = logging.getLogger(__name__)

class DriftService:
    def __init__(self, model_version: str = DEFAULT_MODEL_VERSION):
        self.model_version = model_version

    def _get_baseline_scores(self) -> np.ndarray:
        """Load the baseline scores from the model artifact directory."""
        import numpy as np
        import os

        artifact_path = os.path.join(model_dir(self.model_version), "baseline_scores.npy")
        if not os.path.exists(artifact_path):
            raise FileNotFoundError(f"Baseline scores not found at {artifact_path}. Please retrain the model.")

        return np.load(artifact_path)

    def _get_live_scores(self, db: Session, window_size: int = 5000) -> np.ndarray:
        """Fetch recent live scores from the model_scores table."""
        query = text("""
            SELECT risk_score
            FROM model_scores
            ORDER BY scored_at DESC
            LIMIT :limit
        """)
        rows = db.execute(query, {"limit": window_size}).mappings().all()
        if not rows:
            return np.array([])

        # Convert scores back to 0.0-1.0 scale (they are stored as * 100)
        return np.array([float(r["risk_score"]) / 100.0 for r in rows])

    def run_check(self) -> Dict[str, Any]:
        """Execute the drift check pipeline and persist results."""
        db = SessionLocal()
        try:
            logger.info(f"Running drift check for model version: {self.model_version}")

            # 1. Get scores
            baseline = self._get_baseline_scores()
            live = self._get_live_scores(db)

            if len(live) < 100:
                logger.warning(f"Insufficient live data for drift check (n={len(live)}). Skipping.")
                return {"status": "INSUFFICIENT_DATA", "psi": None}

            # 2. Evaluate drift
            result = evaluate_drift(baseline, live)

            # 3. Save snapshot
            snapshot_id = save_drift_snapshot(
                db=db,
                model_version=self.model_version,
                psi_value=result["psi"],
                status=result["status"]
            )

            logger.info(f"Drift check complete. PSI: {result['psi']} Status: {result['status']}")
            return {
                "snapshot_id": snapshot_id,
                "psi": result["psi"],
                "status": result["status"],
                "message": result["message"]
            }
        except Exception as e:
            logger.exception(f"Drift check failed: {e}")
            raise
        finally:
            db.close()

# Global shared instance
drift_service = DriftService()
