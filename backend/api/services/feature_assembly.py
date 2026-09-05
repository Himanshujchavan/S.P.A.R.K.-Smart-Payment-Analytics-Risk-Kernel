# api/services/feature_assembly.py
# Assembles real-time inference features from Redis velocity caches and PostgreSQL.

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple
import pandas as pd
from sqlalchemy.orm import Session

from ingestion.feature_updater import get_velocity_features
from ml.features.feature_engineering import build_inference_features
from ml.features.feature_schema import all_feature_names

logger = logging.getLogger(__name__)


def assemble_features_for_inference(
    db: Session,
    txn_payload: Dict[str, Any],
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Assemble feature matrix (1 row DataFrame) matching the model's expected schema.

    Pulls live sliding-window velocity aggregations from Redis and static/ring
    context from PostgreSQL.

    Args:
        db: SQLAlchemy session
        txn_payload: Transaction details from incoming POST /score request

    Returns:
        (feature_df, redis_velocity_dict)
    """
    buyer_id = txn_payload.get("buyer_id")
    device_id = txn_payload.get("device_id")
    ip_address = txn_payload.get("ip_address")
    card_bin = txn_payload.get("card_bin")

    # 1. Pull real-time velocity features from Redis
    try:
        redis_features = get_velocity_features(
            buyer_id=buyer_id,
            device_id=device_id,
            ip_address=ip_address,
            card_bin=card_bin,
        )
    except Exception as e:
        logger.warning(f"Error fetching velocity aggregates from Redis: {e}. Using empty fallback.")
        redis_features = {}

    # 2. Build complete feature vector using feature_engineering pipeline
    feature_df = build_inference_features(
        db=db,
        txn=txn_payload,
        redis_features=redis_features,
    )

    return feature_df, redis_features
