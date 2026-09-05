# ml/training/train_model.py
# Train the S.P.A.R.K. XGBoost fraud classifier end-to-end.
#
# Pipeline:
#   1. build_training_matrix(db)  -> full DataFrame with all features
#   2. Encode categoricals to ints (XGBoost wants numeric input)
#   3. Time-based train/test split (last 20% of time = test, NO random split)
#   4. Fit XGBoost with class-imbalance aware hyperparams
#   5. Log params + metrics to MLflow (if available)
#   6. Hand the booster + encoders + (placeholder) thresholds to
#      _model_io.save_artifact(). The actual threshold pair is filled in
#      by threshold_calibration.py after this script writes the booster.
#
# Usage:
#   python -m ml.training.train_model
#   python -m ml.training.train_model --model-version spark-xgb-v3.1.0
#   python -m ml.training.train_model --no-mlflow

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

# Allow `from api...` / `from ml...` from anywhere.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from api.core.db import SessionLocal
from ml.features.feature_engineering import build_training_matrix
from ml.features.feature_schema import (
    CATEGORICAL_FEATURES,
    LABEL_COLUMN,
    TIMESTAMP_COLUMN,
    TXN_ID_COLUMN,
    all_feature_names,
    categorical_feature_names,
    numeric_feature_names,
)
from ml.training._model_io import (
    DEFAULT_MODEL_VERSION,
    save_artifact,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [train] %(levelname)s %(message)s")


# ---------------------------------------------------------------------------
# Categorical encoding
# ---------------------------------------------------------------------------
def encode_categoricals(
    df: pd.DataFrame,
) -> Tuple[pd.DataFrame, Dict[str, List[str]]]:
    """Map each categorical value to an int index based on its position in
    `feature_schema.CATEGORICAL_FEATURES[i].allowed`. Unknown values get
    the "OTHER" bucket, encoded as the last index (matches the schema's
    default_label for inference parity).

    Returns the encoded DataFrame and an encoders dict
    `{feature_name: [allowed_value_1, allowed_value_2, ...]}` for storing
    alongside the model.
    """
    out = df.copy()
    encoders: Dict[str, List[str]] = {}

    for c in CATEGORICAL_FEATURES:
        # Build the canonical allowed list and pin a stable int mapping.
        # Order: allowed values first, then "OTHER" (which feature_engineering
        # already normalizes to) so the model can rely on consistent indices.
        allowed_list: List[str] = list(c.allowed) + ["OTHER"]
        encoders[c.name] = allowed_list
        value_to_idx = {v: i for i, v in enumerate(allowed_list)}

        # Coerce to string, normalize to "OTHER" if unknown.
        col = out[c.name].astype(str)
        col = col.where(col.isin(value_to_idx), other="OTHER")
        out[c.name] = col.map(value_to_idx).astype(np.int32)

    return out, encoders


# ---------------------------------------------------------------------------
# Time-based split
# ---------------------------------------------------------------------------
def time_based_split(
    df: pd.DataFrame, test_fraction: float = 0.20
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Split by *time*, not row index. The last `test_fraction` of
    `created_at` values go to test. This matches real fraud drift: we train
    on the past, evaluate on the future.
    """
    if not 0.0 < test_fraction < 0.9:
        raise ValueError("test_fraction must be in (0, 0.9)")
    df = df.sort_values(TIMESTAMP_COLUMN).reset_index(drop=True)
    cut = int(len(df) * (1.0 - test_fraction))
    return df.iloc[:cut].copy(), df.iloc[cut:].copy()


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------
def _class_scale(y: np.ndarray) -> float:
    """scale_pos_weight = negatives / positives. Helps XGBoost on imbalanced
    fraud data without paying for the runtime cost of SMOTE."""
    pos = int(y.sum())
    neg = int(len(y) - pos)
    if pos == 0:
        return 1.0
    return neg / pos


def fit_xgb(
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    X_val: pd.DataFrame | None,
    y_val: np.ndarray | None,
    params: Dict[str, Any],
    num_boost_round: int,
    early_stopping_rounds: int | None,
) -> Any:
    """Fit an xgboost.Booster. We use the DMatrix + Booster API rather than
    sklearn's XGBClassifier so the artifact is a raw Booster (smaller,
    identical format to what training scripts anywhere would save).
    """
    import xgboost as xgb

    dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=list(X_train.columns))
    evals = []
    if X_val is not None and len(X_val) > 0:
        dval = xgb.DMatrix(X_val, label=y_val, feature_names=list(X_val.columns))
        evals = [(dval, "val")]

    booster = xgb.train(
        params,
        dtrain,
        num_boost_round=num_boost_round,
        evals=evals,
        early_stopping_rounds=early_stopping_rounds if evals else None,
        verbose_eval=False,
    )
    return booster


# ---------------------------------------------------------------------------
# MLflow (optional)
# ---------------------------------------------------------------------------
def maybe_log_mlflow(
    enabled: bool,
    version: str,
    params: Dict[str, Any],
    metrics: Dict[str, float],
    feature_importance: Dict[str, float],
    artifact_dir: str,
) -> None:
    if not enabled:
        logger.info("MLflow logging disabled (--no-mlflow).")
        return
    try:
        import mlflow
    except Exception as e:
        logger.warning(f"MLflow not available ({e}); skipping logging.")
        return
    try:
        mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "file:./mlruns"))
        mlflow.set_experiment("spark-fraud")
        with mlflow.start_run(run_name=version):
            mlflow.set_tag("model_version", version)
            for k, v in params.items():
                mlflow.log_param(k, v)
            for k, v in metrics.items():
                mlflow.log_metric(k, v)
            # Top-10 features as a metric group
            top = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:10]
            for name, imp in top:
                mlflow.log_metric(f"feat_importance.{name}", float(imp))
            # Log the artifact dir
            try:
                mlflow.log_artifacts(artifact_dir, artifact_path="model")
            except Exception as e:
                logger.warning(f"MLflow artifact log skipped: {e}")
        logger.info(f"MLflow run logged for {version}.")
    except Exception as e:
        logger.warning(f"MLflow logging failed: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train S.P.A.R.K. fraud classifier.")
    p.add_argument("--model-version", default=DEFAULT_MODEL_VERSION,
                   help=f"Model version directory name (default: {DEFAULT_MODEL_VERSION})")
    p.add_argument("--test-fraction", type=float, default=0.20,
                   help="Fraction of most-recent data to hold out (default: 0.20)")
    p.add_argument("--num-boost-round", type=int, default=400)
    p.add_argument("--early-stopping", type=int, default=25,
                   help="Early-stopping rounds on val AUC; set to 0 to disable")
    p.add_argument("--no-mlflow", action="store_true", help="Skip MLflow logging")
    p.add_argument("--max-train-rows", type=int, default=0,
                   help="Subsample training rows (0 = use all)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    logger.info(f"Training model version: {args.model_version}")
    logger.info(f"Test fraction: {args.test_fraction}")

    # ---- 1) Build the feature matrix ----
    db: Session = SessionLocal()
    try:
        logger.info("Building training matrix (this can take ~30-60s)...")
        df = build_training_matrix(db)
    finally:
        db.close()

    if df.empty:
        logger.error("No training data available. Run the data generators first.")
        sys.exit(1)

    n_total = len(df)
    n_pos = int(df[LABEL_COLUMN].sum())
    logger.info(f"  rows: {n_total}  fraud: {n_pos}  rate: {n_pos / max(1, n_total) * 100:.2f}%")

    # ---- 2) Encode categoricals ----
    df, encoders = encode_categoricals(df)

    # ---- 3) Time-based split ----
    train_df, test_df = time_based_split(df, test_fraction=args.test_fraction)
    logger.info(f"  train rows: {len(train_df)}  test rows: {len(test_df)}")

    feature_cols = all_feature_names()
    missing = [c for c in feature_cols if c not in train_df.columns]
    if missing:
        logger.error(f"Feature matrix is missing columns: {missing}")
        sys.exit(2)

    X_train = train_df[feature_cols].astype(np.float32)
    y_train = train_df[LABEL_COLUMN].astype(np.int8).to_numpy()
    X_test = test_df[feature_cols].astype(np.float32)
    y_test = test_df[LABEL_COLUMN].astype(np.int8).to_numpy()

    if args.max_train_rows and args.max_train_rows < len(X_train):
        X_train = X_train.iloc[: args.max_train_rows]
        y_train = y_train[: args.max_train_rows]
        logger.info(f"  subsampled train to {len(X_train)} rows")

    # ---- 4) Fit XGBoost ----
    scale_pos_weight = _class_scale(y_train)
    params = {
        "objective": "binary:logistic",
        "eval_metric": "auc",
        "eta": 0.05,
        "max_depth": 6,
        "min_child_weight": 5,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "gamma": 0.1,
        "lambda": 1.0,
        "alpha": 0.0,
        "scale_pos_weight": float(scale_pos_weight),
        "tree_method": "hist",
        "verbosity": 0,
        "nthread": max(1, os.cpu_count() or 1),
        "seed": 42,
    }
    early_stopping = args.early_stopping if args.early_stopping > 0 else None
    logger.info("Fitting XGBoost...")
    booster = fit_xgb(
        X_train, y_train,
        X_test if early_stopping else None, y_test if early_stopping else None,
        params,
        num_boost_round=args.num_boost_round,
        early_stopping_rounds=early_stopping,
    )

    # ---- 5) Quick self-check AUC on test ----
    import xgboost as xgb
    dtest = xgb.DMatrix(X_test, feature_names=list(X_test.columns))
    y_pred_test = booster.predict(dtest)
    try:
        from sklearn.metrics import roc_auc_score
        test_auc = float(roc_auc_score(y_test, y_pred_test))
    except Exception:
        test_auc = float("nan")
    logger.info(f"  test AUC: {test_auc:.4f}")

    # ---- 6) Feature importance (gain) ----
    try:
        gain = booster.get_score(importance_type="gain")
    except Exception:
        gain = {}
    # Normalize: divide by total so the values sum to 1
    total_gain = sum(gain.values()) or 1.0
    feature_importance = {k: v / total_gain for k, v in gain.items()}

    # ---- 7) Save artifact (placeholder thresholds; calibration overwrites) ----
    placeholder_thresholds = {"allow": 0.5, "challenge": 0.85, "calibrated": False}
    metadata = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "n_features": len(feature_cols),
        "feature_names": feature_cols,
        "numeric_features": numeric_feature_names(),
        "categorical_features": [c.name for c in CATEGORICAL_FEATURES],
        "scale_pos_weight": float(scale_pos_weight),
        "test_auc": test_auc,
        "best_iteration": int(getattr(booster, "best_iteration", 0) or 0) or None,
        "label_distribution": {
            "train_pos": int(y_train.sum()),
            "train_neg": int(len(y_train) - y_train.sum()),
            "test_pos": int(y_test.sum()),
            "test_neg": int(len(y_test) - y_test.sum()),
        },
        "top_features_by_gain": sorted(
            feature_importance.items(), key=lambda x: x[1], reverse=True
        )[:15],
    }
    artifact_dir = save_artifact(
        version=args.model_version,
        booster=booster,
        encoders=encoders,
        thresholds=placeholder_thresholds,
        metadata=metadata,
        baseline_scores=y_pred_test,
    )
    logger.info(f"Saved artifact to {artifact_dir}")

    # ---- 8) MLflow ----
    metrics = {
        "test_auc": test_auc,
        "train_rows": float(len(X_train)),
        "test_rows": float(len(X_test)),
        "fraud_rate_train": float(y_train.mean()),
        "fraud_rate_test": float(y_test.mean()),
    }
    maybe_log_mlflow(
        enabled=not args.no_mlflow,
        version=args.model_version,
        params=params,
        metrics=metrics,
        feature_importance=feature_importance,
        artifact_dir=artifact_dir,
    )

    # ---- 9) Hint to the user ----
    print()
    print("=" * 64)
    print(f"  Model trained. AUC (test, raw score): {test_auc:.4f}")
    print(f"  Artifact dir:  {artifact_dir}")
    print()
    print("  Next step:")
    print(f"    python -m ml.training.threshold_calibration \"")
    print(f"        --model-version {args.model_version}")
    print("=" * 64)


if __name__ == "__main__":
    main()
