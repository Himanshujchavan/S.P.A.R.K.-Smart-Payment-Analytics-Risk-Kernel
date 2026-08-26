# ml/training/threshold_calibration.py
# Pick the (allow_threshold, challenge_threshold) pair that minimizes the
# expected business cost on the held-out time-based test set.
#
# Cost model (in INR per transaction):
#   * False positive (predict Block, actually legit)  = +amount  (lost sale)
#   * False positive (predict Challenge, actually legit) = +0.30 * amount (friction)
#   * False negative (predict Allow, actually fraud)   = +amount  (chargeback)
#   * False negative (predict Challenge, actually fraud) = +0.30 * amount
#     (assumed we let it through after a step-up that fails; you can tune)
#   * True positives / true negatives                 = +0
#
# The decision rule (decision_engine will mirror this):
#   score < allow_threshold             -> Allow
#   allow_threshold <= score < challenge -> Challenge
#   score >= challenge_threshold        -> Block
#
# We do a coarse 2D grid search (challenge in {0.50, ..., 0.95}, allow in
# {0.05, ..., challenge - 0.05}) and pick the cheapest pair. We *enforce*
# allow < challenge by at least 0.10 so the Challenge band has width.
#
# Usage:
#   python -m ml.training.threshold_calibration
#   python -m ml.training.threshold_calibration --model-version spark-xgb-v3.1.0
#   python -m ml.training.threshold_calibration --c-fp-block 1.0 --c-fn-allow 1.0

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Any, Dict, List, Tuple

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import numpy as np
import pandas as pd
import xgboost as xgb
from sqlalchemy.orm import Session

from api.core.db import SessionLocal
from ml.features.feature_engineering import build_training_matrix
from ml.features.feature_schema import (
    CATEGORICAL_FEATURES,
    LABEL_COLUMN,
    TIMESTAMP_COLUMN,
    all_feature_names,
)
from ml.training._model_io import DEFAULT_MODEL_VERSION, load_artifact, save_artifact

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [calibrate] %(levelname)s %(message)s")


# Windows consoles default to cp1252, which can't encode U+20B9 (₹).
# Reconfigure stdout to UTF-8 if we can; otherwise the _rs() helper falls
# back to ASCII "Rs." so print() never blows up.
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass


def _rs(amount: float) -> str:
    """Render an INR amount with the rupee glyph. Fall back to 'Rs.' on
    any console (e.g. legacy Windows cp1252) that can't encode U+20B9."""
    try:
        return f"₹{amount:,.0f}"
    except UnicodeEncodeError:
        return f"Rs.{amount:,.0f}"


# ---------------------------------------------------------------------------
# Reuse the training-time categorical encoding (must match train_model.py).
# ---------------------------------------------------------------------------
def encode_categoricals(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, List[str]]]:
    out = df.copy()
    encoders: Dict[str, List[str]] = {}
    for c in CATEGORICAL_FEATURES:
        allowed_list: List[str] = list(c.allowed) + ["OTHER"]
        encoders[c.name] = allowed_list
        value_to_idx = {v: i for i, v in enumerate(allowed_list)}
        col = out[c.name].astype(str)
        col = col.where(col.isin(value_to_idx), other="OTHER")
        out[c.name] = col.map(value_to_idx).astype(np.int32)
    return out, encoders


# ---------------------------------------------------------------------------
# Cost model
# ---------------------------------------------------------------------------
def txn_cost(
    y_true: np.ndarray,   # 0 = legit, 1 = fraud
    y_pred_tier: np.ndarray,  # 0 = Allow, 1 = Challenge, 2 = Block
    amounts: np.ndarray,
    c_fp_block: float,
    c_fp_challenge: float,
    c_fn_allow: float,
    c_fn_challenge: float,
) -> float:
    """Sum of INR-denominated misclassification costs across the test set."""
    fp_block = (y_pred_tier == 2) & (y_true == 0)
    fp_challenge = (y_pred_tier == 1) & (y_true == 0)
    fn_allow = (y_pred_tier == 0) & (y_true == 1)
    fn_challenge = (y_pred_tier == 1) & (y_true == 1)
    return float(
        c_fp_block * float(np.sum(amounts[fp_block]))
        + c_fp_challenge * float(np.sum(amounts[fp_challenge]))
        + c_fn_allow * float(np.sum(amounts[fn_allow]))
        + c_fn_challenge * float(np.sum(amounts[fn_challenge]))
    )


def tier_predictions(
    scores: np.ndarray, allow_t: float, challenge_t: float
) -> np.ndarray:
    """Vectorized decision: 0 = Allow, 1 = Challenge, 2 = Block."""
    pred = np.zeros_like(scores, dtype=np.int8)
    pred[scores >= allow_t] = 1
    pred[scores >= challenge_t] = 2
    return pred


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Calibrate S.P.A.R.K. decision thresholds.")
    p.add_argument("--model-version", default=DEFAULT_MODEL_VERSION)
    p.add_argument("--test-fraction", type=float, default=0.20,
                   help="Must match train_model.py (default: 0.20)")
    # Cost model (in fraction of transaction amount).
    p.add_argument("--c-fp-block", type=float, default=1.0,
                   help="Cost of a false-positive Block (default: 1.0 = full amount)")
    p.add_argument("--c-fp-challenge", type=float, default=0.30,
                   help="Cost of a false-positive Challenge (default: 0.30)")
    p.add_argument("--c-fn-allow", type=float, default=1.0,
                   help="Cost of a false-negative Allow (default: 1.0)")
    p.add_argument("--c-fn-challenge", type=float, default=0.30,
                   help="Cost of a false-negative Challenge (default: 0.30)")
    # Grid resolution. Defaults are fine for our score distribution.
    p.add_argument("--step", type=float, default=0.025,
                   help="Grid step for both thresholds (default: 0.025)")
    p.add_argument("--min-band", type=float, default=0.10,
                   help="Minimum width of the Challenge band (default: 0.10)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    logger.info(f"Calibrating model version: {args.model_version}")

    # ---- 1) Load artifact ----
    try:
        bundle = load_artifact(args.model_version)
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
    booster = bundle["booster"]
    encoders_saved = bundle["encoders"]
    feature_names = bundle["metadata"].get("feature_names") or all_feature_names()
    logger.info(f"  loaded booster; {len(feature_names)} features")

    # ---- 2) Rebuild the test split (same time-based split as training) ----
    db: Session = SessionLocal()
    try:
        logger.info("Rebuilding feature matrix for the test split...")
        df = build_training_matrix(db)
    finally:
        db.close()

    if df.empty:
        logger.error("No training data. Run the generators + train_model.py first.")
        sys.exit(2)

    df, _ = encode_categoricals(df)
    df = df.sort_values(TIMESTAMP_COLUMN).reset_index(drop=True)
    cut = int(len(df) * (1.0 - args.test_fraction))
    test_df = df.iloc[cut:].copy()
    logger.info(f"  test rows: {len(test_df)}  fraud rate: {test_df[LABEL_COLUMN].mean():.4f}")

    X_test = test_df[feature_names].astype(np.float32)
    y_test = test_df[LABEL_COLUMN].astype(np.int8).to_numpy()
    # The amount column is included as a feature, but for cost we want the
    # raw transaction amount. We kept `amount` in the feature matrix which
    # is the raw amount, so we can use the column directly.
    amounts = test_df["amount"].astype(np.float64).to_numpy()

    dtest = xgb.DMatrix(X_test, feature_names=list(X_test.columns))
    scores = booster.predict(dtest)
    logger.info(f"  score stats: min={scores.min():.4f} "
                f"p50={np.median(scores):.4f} p95={np.percentile(scores, 95):.4f} "
                f"max={scores.max():.4f}")

    # ---- 3) Grid search ----
    step = args.step
    min_band = args.min_band
    grid = np.round(np.arange(0.05, 0.95 + step / 2, step), 4)

    best: Dict[str, Any] = {
        "cost": float("inf"),
        "allow": 0.5,
        "challenge": 0.85,
        "n_block": 0,
        "n_challenge": 0,
        "n_allow": 0,
    }
    n_scored = 0
    for challenge_t in grid:
        for allow_t in grid:
            if allow_t + min_band > challenge_t:
                continue
            pred = tier_predictions(scores, allow_t, challenge_t)
            cost = txn_cost(
                y_test, pred, amounts,
                args.c_fp_block, args.c_fp_challenge,
                args.c_fn_allow, args.c_fn_challenge,
            )
            n_scored += 1
            if cost < best["cost"]:
                pred_best = pred
                best = {
                    "cost": cost,
                    "allow": float(allow_t),
                    "challenge": float(challenge_t),
                    "n_block": int((pred_best == 2).sum()),
                    "n_challenge": int((pred_best == 1).sum()),
                    "n_allow": int((pred_best == 0).sum()),
                }
    logger.info(f"  grid points evaluated: {n_scored}")
    logger.info(f"  best: allow={best['allow']:.3f}  "
                f"challenge={best['challenge']:.3f}  cost={_rs(best['cost'])}")

    # ---- 4) Per-tier metrics at the chosen thresholds ----
    pred = tier_predictions(scores, best["allow"], best["challenge"])
    for tier_name, tier_id in [("allow", 0), ("challenge", 1), ("block", 2)]:
        mask = pred == tier_id
        n = int(mask.sum())
        if n == 0:
            continue
        fraud_in_tier = int(y_test[mask].sum())
        precision = float("nan")
        if tier_id in (1, 2):  # precision only meaningful for non-allow
            tp = int(((pred == tier_id) & (y_test == 1)).sum())
            fp = int(((pred == tier_id) & (y_test == 0)).sum())
            precision = tp / max(1, tp + fp)
        recall = float(fraud_in_tier) / max(1, int(y_test.sum())) if tier_id in (1, 2) else float("nan")
        logger.info(
            f"  {tier_name:10s}  n={n:>6}  fraud_in_tier={fraud_in_tier:>4}  "
            f"precision={precision if not (precision != precision) else float('nan'):.3f}  "
            f"recall_vs_total_fraud={recall:.3f}"
        )

    # ---- 5) Persist thresholds into the existing artifact ----
    new_thresholds = {
        "allow": best["allow"],
        "challenge": best["challenge"],
        "calibrated": True,
        "cost_at_optimum_inr": best["cost"],
        "min_band": float(min_band),
        "test_size": int(len(X_test)),
        "costs": {
            "fp_block_per_unit": args.c_fp_block,
            "fp_challenge_per_unit": args.c_fp_challenge,
            "fn_allow_per_unit": args.c_fn_allow,
            "fn_challenge_per_unit": args.c_fn_challenge,
        },
        "n_block": best["n_block"],
        "n_challenge": best["n_challenge"],
        "n_allow": best["n_allow"],
    }
    metadata = dict(bundle["metadata"])
    metadata["thresholds"] = new_thresholds
    metadata["calibrated_at"] = pd.Timestamp.now(tz="UTC").isoformat()

    out_dir = save_artifact(
        version=args.model_version,
        booster=booster,
        encoders=encoders_saved,
        thresholds=new_thresholds,
        metadata=metadata,
    )
    logger.info(f"Updated artifact at {out_dir} with calibrated thresholds.")

    # Echo to stdout for piping
    print()
    print("=" * 64)
    print("  Calibrated thresholds:")
    print(f"    allow     = {best['allow']:.3f}  -> {best['n_allow']} txns")
    print(f"    challenge = {best['challenge']:.3f}  -> {best['n_challenge']} txns")
    print(f"    block     = (>= challenge)  -> {best['n_block']} txns")
    print(f"  Expected cost (test):  {_rs(best['cost'])}")
    print("=" * 64)


if __name__ == "__main__":
    main()
