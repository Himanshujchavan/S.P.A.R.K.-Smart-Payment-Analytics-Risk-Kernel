# ml/training/_model_io.py
# Model artifact I/O — load/save the trained classifier, label encoders,
# and threshold config in a single directory that can be picked up by
# api/services/scoring_service.py at serving time.
#
# Artifact layout:
#   models/<MODEL_VERSION>/
#       xgboost.json            # XGBoost booster (or lightgbm.txt)
#       encoders.json           # categorical label encoders
#       thresholds.json         # {allow: x, challenge: y} risk-score cutoffs
#       metadata.json           # {trained_at, n_train, n_test, metrics, ...}

from __future__ import annotations

import json
import logging
import os
import shutil
import sys
import numpy as np
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

logger = logging.getLogger(__name__)


# Default model directory lives inside backend so the API can load it
# without a network mount. In production this would be S3 / MLflow artifact
# store, with a local cache directory.
DEFAULT_MODEL_DIR = os.path.join(_BACKEND_DIR, "ml", "models")
DEFAULT_MODEL_VERSION = "spark-xgb-v3.0.0"


def model_dir(version: str = DEFAULT_MODEL_VERSION) -> str:
    return os.path.join(DEFAULT_MODEL_DIR, version)


def save_artifact(
    version: str,
    booster: Any,
    encoders: dict[str, list[str]],
    thresholds: dict[str, float],
    metadata: dict[str, Any],
    baseline_scores: Optional[np.ndarray] = None,
) -> str:
    """Save the full model bundle. Returns the directory path."""
    import xgboost as xgb

    out_dir = model_dir(version)
    os.makedirs(out_dir, exist_ok=True)

    # XGBoost booster
    booster.save_model(os.path.join(out_dir, "xgboost.json"))

    # Encoders (list of allowed category strings per categorical feature)
    with open(os.path.join(out_dir, "encoders.json"), "w", encoding="utf-8") as f:
        json.dump(encoders, f, indent=2)

    # Thresholds
    with open(os.path.join(out_dir, "thresholds.json"), "w", encoding="utf-8") as f:
        json.dump(thresholds, f, indent=2)

    # Metadata
    metadata = {**metadata, "version": version, "saved_at": datetime.now(timezone.utc).isoformat()}
    with open(os.path.join(out_dir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, default=str)

    # Baseline scores for PSI drift monitoring
    if baseline_scores is not None:
        np.save(os.path.join(out_dir, "baseline_scores.npy"), baseline_scores)

    logger.info(f"Saved model artifact to {out_dir}")
    return out_dir


def load_artifact(version: str = DEFAULT_MODEL_VERSION) -> dict[str, Any]:
    """Load a saved model bundle. Raises FileNotFoundError if missing."""
    import xgboost as xgb

    out_dir = model_dir(version)
    if not os.path.isdir(out_dir):
        raise FileNotFoundError(f"No model artifact at {out_dir}. Run train_model.py first.")

    booster = xgb.Booster()
    booster.load_model(os.path.join(out_dir, "xgboost.json"))

    with open(os.path.join(out_dir, "encoders.json"), "r", encoding="utf-8") as f:
        encoders = json.load(f)
    with open(os.path.join(out_dir, "thresholds.json"), "r", encoding="utf-8") as f:
        thresholds = json.load(f)
    with open(os.path.join(out_dir, "metadata.json"), "r", encoding="utf-8") as f:
        metadata = json.load(f)

    return {
        "booster": booster,
        "encoders": encoders,
        "thresholds": thresholds,
        "metadata": metadata,
        "version": version,
    }


def latest_model_version() -> str | None:
    """Return the most recently saved model version (by directory mtime)."""
    base = DEFAULT_MODEL_DIR
    if not os.path.isdir(base):
        return None
    versions = [
        (os.path.getmtime(os.path.join(base, v)), v)
        for v in os.listdir(base)
        if os.path.isdir(os.path.join(base, v))
    ]
    if not versions:
        return None
    versions.sort(reverse=True)
    return versions[0][1]
