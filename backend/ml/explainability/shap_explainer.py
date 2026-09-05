# ml/explainability/shap_explainer.py
# SHAP-based feature attribution for S.P.A.R.K. risk decisions.

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import xgboost as xgb

from ml.features.feature_schema import FEATURE_DESCRIPTIONS, all_feature_names

logger = logging.getLogger(__name__)

try:
    import shap
    _HAS_SHAP = True
except Exception as exc:
    # shap pulls in cv2, which crashes if NumPy 2.x is installed against a 1.x-built wheel.
    logger.warning("SHAP unavailable (%s); using XGBoost gain fallback.", exc)
    shap = None
    _HAS_SHAP = False


class SHAPExplainer:
    def __init__(self, booster: xgb.Booster, feature_names: Optional[List[str]] = None):
        self.booster = booster
        self.feature_names = feature_names or all_feature_names()
        if _HAS_SHAP:
            self.explainer = shap.TreeExplainer(self.booster)
        else:
            self.explainer = None

    def explain_instance(
        self, feature_row: pd.Series | pd.DataFrame, top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Compute top-K SHAP feature contributions for a single transaction."""
        if isinstance(feature_row, pd.Series):
            df_row = pd.DataFrame([feature_row])
        else:
            df_row = feature_row.copy()

        df_row = df_row[self.feature_names]

        if _HAS_SHAP and self.explainer is not None:
            dmatrix = xgb.DMatrix(df_row)
            shap_values = self.explainer.shap_values(dmatrix)
            if isinstance(shap_values, list):
                shap_values = shap_values[0]
            row_shap = shap_values[0]
        else:
            # Fallback: estimate importance using XGBoost gain weights
            score_map = self.booster.get_score(importance_type="gain")
            row_shap = [score_map.get(f, 0.0) for f in self.feature_names]

        row_vals = df_row.iloc[0].to_dict()

        contributions = []
        for feat, val, s_val in zip(self.feature_names, row_vals.values(), row_shap):
            contributions.append({
                "feature": feat,
                "value": float(val) if isinstance(val, (int, float, np.number)) else str(val),
                "shap_value": float(s_val),
                "description": FEATURE_DESCRIPTIONS.get(feat, feat),
            })

        # Sort by absolute SHAP value impact descending
        contributions.sort(key=lambda x: abs(x["shap_value"]), reverse=True)
        return contributions[:top_k]
