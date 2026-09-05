# ml/training/evaluate.py
# Evaluate a trained S.P.A.R.K. model artifact on the held-out test split.
#
# Produces:
#   * Per-tier precision / recall / F1
#   * 3-tier (Allow / Challenge / Block) confusion matrix
#   * Cost curve: total ₹ cost at each (allow, challenge) threshold pair
#   * Binary baseline cost curve: every txn above `t` -> Block
#   * Honest exception list: top false negatives and false positives, written
#     to ml/models/<version>/exceptions.csv
#   * Writes a JSON metrics report to ml/models/<version>/eval_report.json
#
# Usage:
#   python -m ml.training.evaluate
#   python -m ml.training.evaluate --model-version spark-xgb-v3.1.0
#   python -m ml.training.evaluate --cost-step 0.025

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
from ml.training._model_io import DEFAULT_MODEL_VERSION, load_artifact

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [evaluate] %(levelname)s %(message)s")


# Windows consoles default to cp1252, which can't encode U+20B9 (₹).
# Reconfigure stdout to UTF-8 if we can; otherwise _rs() falls back to
# "Rs." so print() never blows up on legacy Windows consoles.
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
# Same categorical encoder as train / calibrate
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
# Metrics
# ---------------------------------------------------------------------------
def safe_div(a: float, b: float) -> float:
    return float(a) / float(b) if b else float("nan")


def per_tier_metrics(
    y_true: np.ndarray, y_pred_tier: np.ndarray
) -> Dict[str, Dict[str, float]]:
    """Compute precision/recall/F1 for each tier.

    For Allow: precision = TN / predicted Allow, recall = TN / all actual legit
    For Challenge & Block: precision = TP / predicted, recall = TP / all fraud.
    """
    out: Dict[str, Dict[str, float]] = {}
    y_true = y_true.astype(np.int8)
    n_fraud = int((y_true == 1).sum())
    n_legit = int((y_true == 0).sum())

    # Allow
    pred_allow = (y_pred_tier == 0)
    tp_a = int(((pred_allow) & (y_true == 0)).sum())   # legit allowed = TN
    fp_a = int(((pred_allow) & (y_true == 1)).sum())   # fraud allowed = FN
    out["allow"] = {
        "n": int(pred_allow.sum()),
        "precision": safe_div(tp_a, tp_a + fp_a),       # "TN rate among allowed"
        "recall_legit": safe_div(tp_a, n_legit),
        "f1": float("nan"),  # F1 isn't really meaningful for "Allow"
        "fraud_leaked": fp_a,
    }

    # Challenge
    pred_c = (y_pred_tier == 1)
    tp_c = int(((pred_c) & (y_true == 1)).sum())
    fp_c = int(((pred_c) & (y_true == 0)).sum())
    prec_c = safe_div(tp_c, tp_c + fp_c)
    rec_c = safe_div(tp_c, n_fraud)
    f1_c = (
        2 * prec_c * rec_c / (prec_c + rec_c)
        if (prec_c == prec_c and rec_c == rec_c and (prec_c + rec_c) > 0)
        else float("nan")
    )
    out["challenge"] = {
        "n": int(pred_c.sum()),
        "precision": prec_c,
        "recall_fraud": rec_c,
        "f1": f1_c,
    }

    # Block
    pred_b = (y_pred_tier == 2)
    tp_b = int(((pred_b) & (y_true == 1)).sum())
    fp_b = int(((pred_b) & (y_true == 0)).sum())
    prec_b = safe_div(tp_b, tp_b + fp_b)
    rec_b = safe_div(tp_b, n_fraud)
    f1_b = (
        2 * prec_b * rec_b / (prec_b + rec_b)
        if (prec_b == prec_b and rec_b == rec_b and (prec_b + rec_b) > 0)
        else float("nan")
    )
    out["block"] = {
        "n": int(pred_b.sum()),
        "precision": prec_b,
        "recall_fraud": rec_b,
        "f1": f1_b,
    }

    out["_summary"] = {
        "n_test": int(len(y_true)),
        "n_fraud": n_fraud,
        "n_legit": n_legit,
        "fraud_rate": safe_div(n_fraud, len(y_true)),
    }
    return out


def confusion_3x3(y_true: np.ndarray, y_pred_tier: np.ndarray) -> List[List[int]]:
    """Rows = actual tier, Cols = predicted tier. Tier ids: 0=Allow, 1=Challenge, 2=Block.
    We project actual fraud -> "Block" and actual legit -> "Allow" for the matrix,
    because the test set ground truth is binary; the rows below show:
       [[TN, fp_into_ch, fp_into_block],
        [fn_from_allow, correctly_challenged, fn_into_block]]
    """
    y_true = y_true.astype(np.int8)
    m = np.zeros((2, 3), dtype=np.int64)
    # Legit
    for col, tier in enumerate((0, 1, 2)):
        m[0, col] = int(((y_true == 0) & (y_pred_tier == tier)).sum())
    # Fraud
    for col, tier in enumerate((0, 1, 2)):
        m[1, col] = int(((y_true == 1) & (y_pred_tier == tier)).sum())
    return m.tolist()


# ---------------------------------------------------------------------------
# Cost curves
# ---------------------------------------------------------------------------
def three_tier_cost_curve(
    scores: np.ndarray, y_true: np.ndarray, amounts: np.ndarray,
    c_fp_block: float, c_fp_challenge: float,
    c_fn_allow: float, c_fn_challenge: float,
    step: float,
) -> Dict[str, Any]:
    """For each candidate (allow_t, challenge_t), compute total INR cost."""
    grid = np.round(np.arange(0.05, 0.96, step), 4)
    points: List[Dict[str, float]] = []
    best_cost = float("inf")
    best_pair = (0.5, 0.85)
    for challenge_t in grid:
        for allow_t in grid:
            if allow_t + 0.10 > challenge_t:
                continue
            pred = np.zeros_like(scores, dtype=np.int8)
            pred[scores >= allow_t] = 1
            pred[scores >= challenge_t] = 2
            cost = float(
                c_fp_block * float(np.sum(amounts[(pred == 2) & (y_true == 0)]))
                + c_fp_challenge * float(np.sum(amounts[(pred == 1) & (y_true == 0)]))
                + c_fn_allow * float(np.sum(amounts[(pred == 0) & (y_true == 1)]))
                + c_fn_challenge * float(np.sum(amounts[(pred == 1) & (y_true == 1)]))
            )
            points.append({
                "allow": float(allow_t),
                "challenge": float(challenge_t),
                "cost": cost,
            })
            if cost < best_cost:
                best_cost = cost
                best_pair = (float(allow_t), float(challenge_t))
    return {
        "points": points,
        "best_allow": best_pair[0],
        "best_challenge": best_pair[1],
        "best_cost": best_cost,
    }


def binary_cost_curve(
    scores: np.ndarray, y_true: np.ndarray, amounts: np.ndarray,
    c_fp_block: float, c_fn_allow: float, step: float,
) -> List[Dict[str, float]]:
    """Naive baseline: every txn above t -> Block, otherwise Allow.
    Same cost model, no Challenge tier."""
    grid = np.round(np.arange(0.05, 0.96, step), 4)
    points: List[Dict[str, float]] = []
    for t in grid:
        pred_block = scores >= t
        # False-positive blocks: legit predicted block
        fp_cost = c_fp_block * float(np.sum(amounts[pred_block & (y_true == 0)]))
        # False-negative allows: fraud predicted allow
        fn_cost = c_fn_allow * float(np.sum(amounts[(~pred_block) & (y_true == 1)]))
        points.append({"threshold": float(t), "cost": fp_cost + fn_cost})
    return points


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Evaluate S.P.A.R.K. fraud model.")
    p.add_argument("--model-version", default=DEFAULT_MODEL_VERSION)
    p.add_argument("--test-fraction", type=float, default=0.20)
    p.add_argument("--cost-step", type=float, default=0.025)
    p.add_argument("--c-fp-block", type=float, default=1.0)
    p.add_argument("--c-fp-challenge", type=float, default=0.30)
    p.add_argument("--c-fn-allow", type=float, default=1.0)
    p.add_argument("--c-fn-challenge", type=float, default=0.30)
    p.add_argument("--top-exceptions", type=int, default=20,
                   help="How many FP / FN examples to dump to exceptions.csv")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    logger.info(f"Evaluating model version: {args.model_version}")

    # ---- Load artifact ----
    try:
        bundle = load_artifact(args.model_version)
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
    booster = bundle["booster"]
    feature_names = bundle["metadata"].get("feature_names") or all_feature_names()
    thresholds = bundle.get("thresholds") or {"allow": 0.5, "challenge": 0.85}
    logger.info(f"  loaded; using thresholds {thresholds.get('allow')} / {thresholds.get('challenge')}")

    # ---- Rebuild test split ----
    db: Session = SessionLocal()
    try:
        df = build_training_matrix(db)
    finally:
        db.close()
    if df.empty:
        logger.error("No data. Run generators + train_model.py first.")
        sys.exit(2)

    df, _ = encode_categoricals(df)
    df = df.sort_values(TIMESTAMP_COLUMN).reset_index(drop=True)
    cut = int(len(df) * (1.0 - args.test_fraction))
    test_df = df.iloc[cut:].copy()
    logger.info(f"  test rows: {len(test_df)}")

    X_test = test_df[feature_names].astype(np.float32)
    y_test = test_df[LABEL_COLUMN].astype(np.int8).to_numpy()
    amounts = test_df["amount"].astype(np.float64).to_numpy()

    dtest = xgb.DMatrix(X_test, feature_names=list(X_test.columns))
    scores = booster.predict(dtest)
    try:
        from sklearn.metrics import roc_auc_score
        test_auc = float(roc_auc_score(y_test, scores))
    except Exception:
        test_auc = float("nan")
    logger.info(f"  test AUC: {test_auc:.4f}")

    # ---- Per-tier metrics at the calibrated thresholds ----
    allow_t = float(thresholds.get("allow", 0.5))
    challenge_t = float(thresholds.get("challenge", 0.85))
    pred = np.zeros_like(scores, dtype=np.int8)
    pred[scores >= allow_t] = 1
    pred[scores >= challenge_t] = 2
    tier_metrics = per_tier_metrics(y_test, pred)
    cm = confusion_3x3(y_test, pred)

    logger.info("Per-tier metrics at calibrated thresholds:")
    for tier in ("allow", "challenge", "block"):
        m = tier_metrics[tier]
        logger.info(
            f"  {tier:10s}  n={m['n']:>6}  precision={m['precision']:.3f}  "
            f"recall={m.get('recall_legit', m.get('recall_fraud', float('nan'))):.3f}  "
            f"f1={m.get('f1', float('nan')) if m.get('f1') == m.get('f1') else float('nan'):.3f}"
        )

    # ---- Cost curves ----
    logger.info("Computing 3-tier cost curve...")
    tier_curve = three_tier_cost_curve(
        scores, y_test, amounts,
        args.c_fp_block, args.c_fp_challenge,
        args.c_fn_allow, args.c_fn_challenge,
        step=args.cost_step,
    )
    logger.info(f"  best 3-tier: allow={tier_curve['best_allow']:.3f} "
                f"challenge={tier_curve['best_challenge']:.3f} "
                f"cost={_rs(tier_curve['best_cost'])}")

    logger.info("Computing binary baseline cost curve...")
    binary_curve = binary_cost_curve(
        scores, y_test, amounts,
        args.c_fp_block, args.c_fn_allow, step=args.cost_step,
    )
    binary_best = min(binary_curve, key=lambda p: p["cost"])
    logger.info(f"  best binary: threshold={binary_best['threshold']:.3f} "
                f"cost={_rs(binary_best['cost'])}")

    savings_inr = binary_best["cost"] - tier_curve["best_cost"]
    savings_pct = (
        100.0 * savings_inr / binary_best["cost"] if binary_best["cost"] > 0 else 0.0
    )
    logger.info(f"  3-tier saves {_rs(savings_inr)} ({savings_pct:.1f}%) vs binary baseline")

    # ---- Exception list ----
    # False negatives (fraud that we allowed): most damaging misses
    fn_mask = (y_test == 1) & (pred == 0)
    fn_idx = np.where(fn_mask)[0]
    fn_sorted = fn_idx[np.argsort(-scores[fn_idx])]  # closest-to-threshold first
    # False positives (legit that we blocked): revenue we lost
    fp_mask = (y_test == 0) & (pred == 2)
    fp_idx = np.where(fp_mask)[0]
    fp_sorted = fp_idx[np.argsort(-scores[fp_idx])]   # most confident blocks first

    def _row(tid: int) -> Dict[str, Any]:
        return {
            "txn_id": str(test_df.iloc[tid]["txn_id"]),
            "score": float(scores[tid]),
            "amount": float(amounts[tid]),
            "is_fraud": int(y_test[tid]),
            "predicted_tier": int(pred[tid]),
        }

    exceptions = (
        [_row(i) for i in fn_sorted[: args.top_exceptions]]
        + [_row(i) for i in fp_sorted[: args.top_exceptions]]
    )

    # ---- Persist report ----
    artifact_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "ml", "models", args.model_version,
    )
    os.makedirs(artifact_dir, exist_ok=True)

    report = {
        "model_version": args.model_version,
        "thresholds": thresholds,
        "test_auc": test_auc,
        "per_tier_metrics": tier_metrics,
        "confusion_matrix_2x3": {
            "rows": ["actual_legit", "actual_fraud"],
            "cols": ["pred_allow", "pred_challenge", "pred_block"],
            "matrix": cm,
        },
        "cost_curve_3tier": {
            "best_allow": tier_curve["best_allow"],
            "best_challenge": tier_curve["best_challenge"],
            "best_cost_inr": tier_curve["best_cost"],
            "n_points": len(tier_curve["points"]),
        },
        "cost_curve_binary_baseline": {
            "best_threshold": binary_best["threshold"],
            "best_cost_inr": binary_best["cost"],
            "n_points": len(binary_curve),
        },
        "savings_inr": float(savings_inr),
        "savings_pct_vs_binary": float(savings_pct),
        "exceptions_n": len(exceptions),
    }
    report_path = os.path.join(artifact_dir, "eval_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    logger.info(f"Wrote {report_path}")

    # Cost curve CSV (one row per grid point) — both curves
    curve_rows: List[Dict[str, Any]] = []
    for p in tier_curve["points"]:
        curve_rows.append({
            "curve": "3tier",
            "threshold_a": p["allow"],
            "threshold_b": p["challenge"],
            "cost_inr": p["cost"],
        })
    for p in binary_curve:
        curve_rows.append({
            "curve": "binary",
            "threshold_a": p["threshold"],
            "threshold_b": None,
            "cost_inr": p["cost"],
        })
    curve_df = pd.DataFrame(curve_rows)
    curve_path = os.path.join(artifact_dir, "cost_curve.csv")
    curve_df.to_csv(curve_path, index=False)
    logger.info(f"Wrote {curve_path}")

    # Exceptions CSV
    exc_path = os.path.join(artifact_dir, "exceptions.csv")
    pd.DataFrame(exceptions).to_csv(exc_path, index=False)
    logger.info(f"Wrote {exc_path} ({len(exceptions)} rows)")

    # ---- Stdout summary ----
    print()
    print("=" * 64)
    print(f"  Model:        {args.model_version}")
    print(f"  Test AUC:     {test_auc:.4f}")
    print(f"  Thresholds:   allow={allow_t:.3f}  challenge={challenge_t:.3f}")
    s = tier_metrics["_summary"]
    print(f"  Test set:     {s['n_test']} rows ({s['n_fraud']} fraud, "
          f"{s['fraud_rate'] * 100:.2f}% rate)")
    print("-" * 64)
    for tier in ("allow", "challenge", "block"):
        m = tier_metrics[tier]
        print(f"  {tier:10s}  n={m['n']:>6}  precision={m['precision']:.3f}  "
              f"f1={m.get('f1', float('nan')):.3f}")
    print("-" * 64)
    print(f"  3-tier best cost:  {_rs(tier_curve['best_cost']):>16s}")
    print(f"  Binary best cost:  {_rs(binary_best['cost']):>16s}")
    print(f"  Savings:           {_rs(savings_inr):>16s}  ({savings_pct:5.1f}%)")
    print("=" * 64)


if __name__ == "__main__":
    main()
