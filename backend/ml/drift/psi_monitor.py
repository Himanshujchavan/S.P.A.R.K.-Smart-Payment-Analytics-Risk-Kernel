# ml/drift/psi_monitor.py
# Population Stability Index (PSI) drift monitoring for S.P.A.R.K.

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def calculate_psi(
    baseline: np.ndarray | pd.Series,
    target: np.ndarray | pd.Series,
    num_bins: int = 10,
    eps: float = 1e-4,
) -> Tuple[float, List[Dict[str, Any]]]:
    """Calculate Population Stability Index (PSI) between baseline and target distributions.

    PSI interpretation:
        PSI < 0.10: No significant distribution shift (Stable)
        0.10 <= PSI < 0.25: Moderate distribution shift (Warning)
        PSI >= 0.25: Significant distribution shift (Alert - recalibration required)
    """
    baseline_arr = np.asarray(baseline, dtype=np.float64)
    target_arr = np.asarray(target, dtype=np.float64)

    if len(baseline_arr) == 0 or len(target_arr) == 0:
        return 0.0, []

    # Determine bin edges based on baseline quantiles
    quantiles = np.linspace(0, 100, num_bins + 1)
    bin_edges = np.percentile(baseline_arr, quantiles)
    # Deduplicate edges to avoid zero-width bins
    bin_edges = np.unique(bin_edges)
    if len(bin_edges) < 2:
        bin_edges = np.array([min(baseline_arr.min(), target_arr.min()), max(baseline_arr.max(), target_arr.max()) + eps])

    baseline_counts, _ = np.histogram(baseline_arr, bins=bin_edges)
    target_counts, _ = np.histogram(target_arr, bins=bin_edges)

    baseline_pct = baseline_counts / len(baseline_arr)
    target_pct = target_counts / len(target_arr)

    # Avoid zero division
    baseline_pct = np.clip(baseline_pct, eps, 1.0)
    target_pct = np.clip(target_pct, eps, 1.0)

    psi_per_bin = (target_pct - baseline_pct) * np.log(target_pct / baseline_pct)
    total_psi = float(np.sum(psi_per_bin))

    bin_details = []
    for i in range(len(baseline_counts)):
        bin_details.append({
            "bin": i + 1,
            "lower": float(bin_edges[i]),
            "upper": float(bin_edges[i + 1]),
            "baseline_pct": float(baseline_pct[i]),
            "target_pct": float(target_pct[i]),
            "psi": float(psi_per_bin[i]),
        })

    return total_psi, bin_details


def evaluate_drift(
    baseline_scores: np.ndarray | pd.Series,
    live_scores: np.ndarray | pd.Series,
) -> Dict[str, Any]:
    """Compute score drift metrics and determine drift alert status."""
    psi_val, bin_details = calculate_psi(baseline_scores, live_scores)

    if psi_val < 0.10:
        status = "STABLE"
        message = "Model score distribution is stable."
    elif psi_val < 0.25:
        status = "WARNING"
        message = "Moderate score distribution drift detected."
    else:
        status = "ALERT"
        message = "Significant drift detected! Threshold re-calibration or model re-training recommended."

    return {
        "psi": round(psi_val, 4),
        "status": status,
        "message": message,
        "bin_details": bin_details,
        "n_baseline": len(baseline_scores),
        "n_live": len(live_scores),
    }


def save_drift_snapshot(
    db: Session,
    model_version: str,
    psi_value: float,
    status: str,
    feature_drift: Optional[Dict[str, Any]] = None,
) -> str:
    """Save a PSI drift snapshot record into the `drift_snapshots` DB table."""
    snapshot_id = str(uuid.uuid4())
    try:
        db.execute(
            text("""
                INSERT INTO drift_snapshots
                    (snapshot_id, snapshot_time, model_version, psi_score, drift_status, feature_psi_json)
                VALUES
                    (:sid, NOW(), :version, :psi, :status, :f_json)
            """),
            {
                "sid": snapshot_id,
                "version": model_version,
                "psi": psi_value,
                "status": status,
                "f_json": str(feature_drift or {}),
            },
        )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save drift snapshot to DB: {e}")

    return snapshot_id
