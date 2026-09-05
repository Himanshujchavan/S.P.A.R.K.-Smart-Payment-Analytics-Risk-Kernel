# ml/explainability/counterfactual.py
# Counterfactual explanation module for S.P.A.R.K.
# Generates plain-language counterfactuals explaining what changes would have
# lowered the risk decision to "Allow".

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import xgboost as xgb

from ml.features.feature_schema import FEATURE_DESCRIPTIONS, all_feature_names

logger = logging.getLogger(__name__)


def generate_counterfactual(
    booster: xgb.Booster,
    feature_row: pd.Series | pd.DataFrame,
    allow_threshold: float = 0.30,
    feature_names: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Generate a counterfactual explanation for a high-risk transaction decision.

    Searches for key feature adjustments (e.g. amount reduction, velocity decrease)
    that bring the transaction's risk score below `allow_threshold`.
    """
    names = feature_names or all_feature_names()
    if isinstance(feature_row, pd.Series):
        df_row = pd.DataFrame([feature_row])
    else:
        df_row = feature_row.copy()

    df_row = df_row[names]
    dmatrix = xgb.DMatrix(df_row)
    orig_score = float(booster.predict(dmatrix)[0])

    if orig_score < allow_threshold:
        return {
            "current_score": orig_score,
            "target_threshold": allow_threshold,
            "counterfactual_found": False,
            "explanation": "Transaction is already in the Allowed risk tier.",
            "suggested_changes": [],
        }

    suggested_changes = []

    # 1. Test reduction in transaction amount
    if "amount" in df_row.columns or "txn_amount" in df_row.columns:
        amt_col = "amount" if "amount" in df_row.columns else "txn_amount"
        orig_amt = float(df_row[amt_col].iloc[0])
        for pct in [0.25, 0.50, 0.75]:
            test_df = df_row.copy()
            new_amt = orig_amt * (1.0 - pct)
            test_df[amt_col] = new_amt
            if "log_amount" in test_df.columns:
                test_df["log_amount"] = np.log1p(new_amt)

            test_score = float(booster.predict(xgb.DMatrix(test_df))[0])
            if test_score < allow_threshold:
                suggested_changes.append({
                    "feature": amt_col,
                    "original_value": orig_amt,
                    "suggested_value": round(new_amt, 2),
                    "new_score": round(test_score, 4),
                    "text": f"Would have been Allowed if the transaction amount was ₹{round(orig_amt - new_amt, 2):,.0f} lower.",
                })
                break

    # 2. Test reduction in 1h buyer velocity
    if "buyer_1h" in df_row.columns or "txn_count_buyer_1h" in df_row.columns:
        vel_col = "buyer_1h" if "buyer_1h" in df_row.columns else "txn_count_buyer_1h"
        orig_vel = float(df_row[vel_col].iloc[0])
        if orig_vel > 1:
            test_df = df_row.copy()
            test_df[vel_col] = 1.0
            test_score = float(booster.predict(xgb.DMatrix(test_df))[0])
            if test_score < allow_threshold:
                suggested_changes.append({
                    "feature": vel_col,
                    "original_value": orig_vel,
                    "suggested_value": 1.0,
                    "new_score": round(test_score, 4),
                    "text": "Would have been Allowed if buyer velocity in the last hour was 1 transaction.",
                })

    # Generic fallback description if specific counterfactual sweep didn't reach allow_threshold
    if not suggested_changes:
        explanation = f"Score of {orig_score:.3f} exceeds allow threshold {allow_threshold:.2f} due to combined risk signals across amount and velocity."
    else:
        explanation = suggested_changes[0]["text"]

    return {
        "current_score": round(orig_score, 4),
        "target_threshold": allow_threshold,
        "counterfactual_found": len(suggested_changes) > 0,
        "explanation": explanation,
        "suggested_changes": suggested_changes,
    }
