# ml/features/feature_engineering.py
# Build the S.P.A.R.K. feature matrix from raw transactions.
#
# Two entry points:
#   - build_training_matrix(db): produces a full pandas DataFrame by
#     streaming all transactions, computing all features, and joining
#     fraud_labels. Used by ml/training/train_model.py.
#   - build_inference_features(db, txn, redis_features): produces a single
#     feature vector (pandas Series, 1 row) for the /score endpoint.
#     `redis_features` is the live aggregates dict that the Kafka consumer
#     maintains (see ingestion/feature_updater.py).
#
# All features must match feature_schema.NUMERIC_FEATURES /
# CATEGORICAL_FEATURES. Adding a feature? Add it to the schema FIRST,
# then compute it here, then re-train.

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from ml.features.feature_schema import (
    CATEGORICAL_FEATURES,
    CategoricalFeature,
    LABEL_COLUMN,
    NUMERIC_FEATURES,
    TIMESTAMP_COLUMN,
    TXN_ID_COLUMN,
    all_feature_names,
    categorical_feature_names,
    numeric_feature_names,
)


# ---------------------------------------------------------------------------
# Defaults pulled from the schema
# ---------------------------------------------------------------------------
_NUMERIC_DEFAULTS: dict[str, float] = {n: d for n, d, _g, _desc in NUMERIC_FEATURES}
_CAT_DEFAULTS: dict[str, str] = {c.name: c.default_label for c in CATEGORICAL_FEATURES}
_CAT_ALLOWED: dict[str, set[str]] = {c.name: set(c.allowed) for c in CATEGORICAL_FEATURES}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _safe_log1p(x: float) -> float:
    try:
        return math.log1p(max(0.0, float(x)))
    except (TypeError, ValueError):
        return 0.0


def _categorize(value: Optional[str], feature: CategoricalFeature) -> str:
    if value is None:
        return feature.default_label
    return value if value in _CAT_ALLOWED[feature.name] else "OTHER"


def _weekend(dt: datetime) -> int:
    return 1 if dt.weekday() >= 5 else 0


# ---------------------------------------------------------------------------
# Velocity computation (training-time, batch SQL)
# ---------------------------------------------------------------------------
def _velocity_features(
    db: Session, txn_df: pd.DataFrame,
) -> dict[str, np.ndarray]:
    """Compute buyer/device/ip/card_bin velocity columns in one SQL pass.

    Returns a dict of column_name -> np.ndarray aligned with txn_df.index.
    Uses window functions on the (buyer_id, created_at), (device_id, ...),
    etc. partitioned transactions. TimescaleDB handles this fine.
    """
    # We need a strict cutoff (no future leaks). Use min/max created_at
    # from the input df to bound the lookback.
    if len(txn_df) == 0:
        cols = [
            "txn_count_buyer_1h", "txn_count_buyer_24h", "txn_count_buyer_7d",
            "amount_sum_buyer_24h", "seconds_since_last_buyer_txn",
            "txn_count_device_1h", "txn_count_device_24h", "txn_count_device_7d",
            "distinct_buyers_device_7d", "device_age_days",
            "txn_count_ip_1h", "txn_count_ip_24h", "distinct_buyers_ip_24h",
            "txn_count_card_bin_1h", "txn_count_card_bin_24h",
            "distinct_buyers_card_bin_24h",
        ]
        return {c: np.zeros(0, dtype=np.float64) for c in cols}

    # We do the velocity computation with a single query that joins
    # transactions to itself on the relevant key, restricted to a
    # <= 7-day lookback. The query is parameterized by `ref_time` so
    # we can compute *causal* (point-in-time) velocities.
    # We use ROW_NUMBER to assign ranks within each (key, created_at)
    # group; from that we derive the rolling 1h/24h/7d counts.

    # Approach: for each (key_col, time_window) we run a query that
    # returns a per-txn count of *prior* transactions in the window.
    # We union these into a single temp-style result and pivot in pandas.

    # Fetch all relevant transactions in one shot. With ~25k txns over
    # 60 days, this is well under memory pressure.
    rows = db.execute(text("""
        SELECT
            t.txn_id,
            t.buyer_id,
            t.device_id,
            t.ip_address,
            t.card_bin,
            t.amount,
            t.created_at
        FROM transactions t
    """)).mappings().fetchall()

    if not rows:
        cols = [
            "txn_count_buyer_1h", "txn_count_buyer_24h", "txn_count_buyer_7d",
            "amount_sum_buyer_24h", "seconds_since_last_buyer_txn",
            "txn_count_device_1h", "txn_count_device_24h", "txn_count_device_7d",
            "distinct_buyers_device_7d", "device_age_days",
            "txn_count_ip_1h", "txn_count_ip_24h", "distinct_buyers_ip_24h",
            "txn_count_card_bin_1h", "txn_count_card_bin_24h",
            "distinct_buyers_card_bin_24h",
        ]
        return {c: np.zeros(len(txn_df), dtype=np.float64) for c in cols}

    df_all = pd.DataFrame([dict(r) for r in rows])
    df_all["created_at"] = pd.to_datetime(df_all["created_at"], utc=True)
    df_all = df_all.sort_values("created_at").reset_index(drop=True)

    n = len(txn_df)
    out: dict[str, np.ndarray] = {}

    # --- Buyer velocity ---
    buyer_sorted = df_all.sort_values(["buyer_id", "created_at"])
    g = buyer_sorted.groupby("buyer_id", sort=False)
    # rolling window counts based on time deltas
    for col, window in [
        ("txn_count_buyer_1h", "1h"),
        ("txn_count_buyer_24h", "24h"),
        ("txn_count_buyer_7d", "7d"),
    ]:
        # For each (buyer), count *prior* txns within `window`.
        # Use a groupby + rolling on time index.
        cnt = (
            g.rolling(window, on="created_at", closed="left")["txn_id"]
            .count()
            .reset_index(level=0, drop=True)
        )
        buyer_sorted[col] = cnt.fillna(0).astype(np.int64)

    # buyer 24h amount sum
    buyer_sorted["amount_sum_buyer_24h"] = (
        g.rolling("24h", on="created_at", closed="left")["amount"]
        .sum()
        .reset_index(level=0, drop=True)
        .fillna(0.0)
    )
    # seconds since last buyer txn
    buyer_sorted["prev_ts"] = g["created_at"].shift(1)
    buyer_sorted["seconds_since_last_buyer_txn"] = (
        (buyer_sorted["created_at"] - buyer_sorted["prev_ts"])
        .dt.total_seconds()
        .fillna(1e10)
    )

    # Map back to txn_df row order
    buyer_view = buyer_sorted.set_index("txn_id")
    for col in ["txn_count_buyer_1h", "txn_count_buyer_24h", "txn_count_buyer_7d",
                "amount_sum_buyer_24h", "seconds_since_last_buyer_txn"]:
        out[col] = (
            txn_df[TXN_ID_COLUMN].map(buyer_view[col]).fillna(0).to_numpy(dtype=np.float64)
        )

    # --- Device velocity ---
    dev_sorted = df_all.dropna(subset=["device_id"]).sort_values(["device_id", "created_at"])
    g = dev_sorted.groupby("device_id", sort=False)
    for col, window in [
        ("txn_count_device_1h", "1h"),
        ("txn_count_device_24h", "24h"),
        ("txn_count_device_7d", "7d"),
    ]:
        dev_sorted[col] = (
            g.rolling(window, on="created_at", closed="left")["txn_id"]
            .count()
            .reset_index(level=0, drop=True)
            .fillna(0).astype(np.int64)
        )
    # distinct buyers on this device in last 7d
    dev_sorted["distinct_buyers_device_7d"] = (
        g.rolling("7d", on="created_at", closed="left")["buyer_id"]
        .nunique()
        .reset_index(level=0, drop=True)
        .fillna(1).astype(np.int64)
    )
    # device age = days since device's first txn
    first_seen = dev_sorted.groupby("device_id")["created_at"].transform("min")
    dev_sorted["device_age_days"] = (
        (dev_sorted["created_at"] - first_seen).dt.total_seconds() / 86400.0
    ).fillna(0.0)

    dev_view = dev_sorted.set_index("txn_id")
    for col in ["txn_count_device_1h", "txn_count_device_24h", "txn_count_device_7d",
                "distinct_buyers_device_7d", "device_age_days"]:
        out[col] = (
            txn_df[TXN_ID_COLUMN].map(dev_view[col]).fillna(0).to_numpy(dtype=np.float64)
        )

    # --- IP velocity ---
    ip_sorted = df_all.dropna(subset=["ip_address"]).sort_values(["ip_address", "created_at"])
    g = ip_sorted.groupby("ip_address", sort=False)
    for col, window in [("txn_count_ip_1h", "1h"), ("txn_count_ip_24h", "24h")]:
        ip_sorted[col] = (
            g.rolling(window, on="created_at", closed="left")["txn_id"]
            .count()
            .reset_index(level=0, drop=True)
            .fillna(0).astype(np.int64)
        )
    ip_sorted["distinct_buyers_ip_24h"] = (
        g.rolling("24h", on="created_at", closed="left")["buyer_id"]
        .nunique()
        .reset_index(level=0, drop=True)
        .fillna(1).astype(np.int64)
    )
    ip_view = ip_sorted.set_index("txn_id")
    for col in ["txn_count_ip_1h", "txn_count_ip_24h", "distinct_buyers_ip_24h"]:
        out[col] = (
            txn_df[TXN_ID_COLUMN].map(ip_view[col]).fillna(0).to_numpy(dtype=np.float64)
        )

    # --- Card BIN velocity ---
    bin_sorted = df_all.dropna(subset=["card_bin"]).sort_values(["card_bin", "created_at"])
    g = bin_sorted.groupby("card_bin", sort=False)
    for col, window in [("txn_count_card_bin_1h", "1h"), ("txn_count_card_bin_24h", "24h")]:
        bin_sorted[col] = (
            g.rolling(window, on="created_at", closed="left")["txn_id"]
            .count()
            .reset_index(level=0, drop=True)
            .fillna(0).astype(np.int64)
        )
    bin_sorted["distinct_buyers_card_bin_24h"] = (
        g.rolling("24h", on="created_at", closed="left")["buyer_id"]
        .nunique()
        .reset_index(level=0, drop=True)
        .fillna(1).astype(np.int64)
    )
    bin_view = bin_sorted.set_index("txn_id")
    for col in ["txn_count_card_bin_1h", "txn_count_card_bin_24h",
                "distinct_buyers_card_bin_24h"]:
        out[col] = (
            txn_df[TXN_ID_COLUMN].map(bin_view[col]).fillna(0).to_numpy(dtype=np.float64)
        )

    return out


def _novelty_features(
    db: Session, txn_df: pd.DataFrame,
) -> dict[str, np.ndarray]:
    """Compute 'is this buyer seeing this device/IP/BIN for the first time?'
    via a per-buyer set of prior (device, ip, bin) values.
    """
    n = len(txn_df)
    out = {
        "is_known_device_for_buyer": np.ones(n, dtype=np.float64),
        "is_new_ip_for_buyer": np.zeros(n, dtype=np.float64),
        "is_new_card_bin_for_buyer": np.zeros(n, dtype=np.float64),
    }
    if n == 0:
        return out

    # Fetch all buyer → (device, ip, bin) pairs in chronological order.
    rows = db.execute(text("""
        SELECT buyer_id, device_id, ip_address, card_bin, created_at
        FROM transactions ORDER BY created_at
    """)).fetchall()

    seen_device: dict[Any, set] = defaultdict(set)
    seen_ip: dict[Any, set] = defaultdict(set)
    seen_bin: dict[Any, set] = defaultdict(set)

    txn_to_idx = {tid: i for i, tid in enumerate(txn_df[TXN_ID_COLUMN].tolist())}

    for buyer, dev, ip, bin_, _ts in rows:
        idx = txn_to_idx.get(txn_to_idx_key := None)  # placeholder
        # We need to find this row's index. Since `rows` is sorted by created_at
        # and txn_df preserves db order, we instead do this via a separate
        # join. Cheaper: do it via a per-row left-anti-join in SQL.
        pass

    # Easier: do it in SQL with a window function on prior txns.
    # We use count(*) FILTER for each key and check if any prior txn exists.
    q = text("""
        WITH ordered AS (
            SELECT
                txn_id, buyer_id, device_id, ip_address, card_bin,
                ROW_NUMBER() OVER (PARTITION BY buyer_id ORDER BY created_at) AS rn
            FROM transactions
        )
        SELECT
            o.txn_id,
            -- device: any prior txn with same buyer+device?
            CASE WHEN EXISTS (
                SELECT 1 FROM ordered o2
                WHERE o2.buyer_id = o.buyer_id
                  AND o2.device_id IS NOT DISTINCT FROM o.device_id
                  AND o2.rn < o.rn
            ) THEN 1 ELSE 0 END AS known_dev,
            -- ip: any prior txn with same buyer+ip?
            CASE WHEN EXISTS (
                SELECT 1 FROM ordered o2
                WHERE o2.buyer_id = o.buyer_id
                  AND o2.ip_address IS NOT DISTINCT FROM o.ip_address
                  AND o2.rn < o.rn
            ) THEN 0 ELSE 1 END AS new_ip,
            -- bin: any prior txn with same buyer+bin?
            CASE WHEN EXISTS (
                SELECT 1 FROM ordered o2
                WHERE o2.buyer_id = o.buyer_id
                  AND o2.card_bin IS NOT DISTINCT FROM o.card_bin
                  AND o2.rn < o.rn
            ) THEN 0 ELSE 1 END AS new_bin
        FROM ordered o
    """)
    rows = db.execute(q).fetchall()
    for tid, known_dev, new_ip, new_bin in rows:
        idx = txn_to_idx.get(tid)
        if idx is None:
            continue
        out["is_known_device_for_buyer"][idx] = float(known_dev)
        out["is_new_ip_for_buyer"][idx] = float(new_ip)
        out["is_new_card_bin_for_buyer"][idx] = float(new_bin)
    return out


def _ring_features(db: Session, txn_df: pd.DataFrame) -> dict[str, np.ndarray]:
    """For each transaction, look up the buyer's ring (if any) and the
    ring-overlap signals at the device/IP/BIN level.
    """
    n = len(txn_df)
    out = {
        "ring_member_count": np.zeros(n, dtype=np.float64),
        "ring_density": np.zeros(n, dtype=np.float64),
        "ring_flagged_amount": np.zeros(n, dtype=np.float64),
        "on_ring_shared_device": np.zeros(n, dtype=np.float64),
        "on_ring_shared_ip": np.zeros(n, dtype=np.float64),
        "on_ring_shared_bin": np.zeros(n, dtype=np.float64),
    }
    if n == 0:
        return out

    # rings: { ring_id: { 'members': set[buyer], 'shared_devices': set, ... } }
    rows = db.execute(text("""
        SELECT
            dr.ring_id, dr.member_count, dr.density_score, dr.flagged_amount,
            dr.shared_attribute, dr.shared_value, dr.account_ids
        FROM detected_rings
        WHERE status = 'active'
    """)).mappings().fetchall()

    import json as _json
    rings: list[dict] = []
    ring_devices: set = set()
    ring_ips: set = set()
    ring_bins: set = set()
    for r in rows:
        members_raw = r["account_ids"]
        if isinstance(members_raw, str):
            members_raw = _json.loads(members_raw)
        try:
            members = {uuid_str(m) for m in (members_raw or [])}
        except Exception:
            members = set()
        rings.append({
            "members": members,
            "member_count": float(r["member_count"] or 0),
            "density": float(r["density_score"] or 0.0),
            "flagged_amount": float(r["flagged_amount"] or 0.0),
            "shared_attr": r["shared_attribute"],
            "shared_value": r["shared_value"],
        })
        # Build device/ip/bin sets by joining to the underlying tables.
        if r["shared_attribute"] == "device_fingerprint":
            dev = db.execute(
                text("SELECT device_id FROM devices WHERE fingerprint = :v LIMIT 1"),
                {"v": r["shared_value"]},
            ).first()
            if dev:
                ring_devices.add(dev[0])
        elif r["shared_attribute"] == "ip_address":
            ring_ips.add(r["shared_value"])
        elif r["shared_attribute"] == "card_bin":
            ring_bins.add(r["shared_value"])

    # Index each txn row to its position
    txn_to_idx = {tid: i for i, tid in enumerate(txn_df[TXN_ID_COLUMN].tolist())}

    # Pre-fetch the device, ip, bin, buyer for each txn in our matrix
    rows = db.execute(text("""
        SELECT txn_id, buyer_id, device_id, ip_address, card_bin
        FROM transactions
        WHERE txn_id = ANY(:tids)
    """), {"tids": list(txn_to_idx.keys())}).fetchall()

    for tid, buyer, dev, ip, bin_ in rows:
        idx = txn_to_idx.get(tid)
        if idx is None:
            continue
        # find the ring this buyer belongs to (if any)
        for ring in rings:
            if buyer in ring["members"]:
                out["ring_member_count"][idx] = ring["member_count"]
                out["ring_density"][idx] = ring["density"]
                out["ring_flagged_amount"][idx] = ring["flagged_amount"]
                break
        if dev is not None and dev in ring_devices:
            out["on_ring_shared_device"][idx] = 1.0
        if ip is not None and ip in ring_ips:
            out["on_ring_shared_ip"][idx] = 1.0
        if bin_ is not None and bin_ in ring_bins:
            out["on_ring_shared_bin"][idx] = 1.0
    return out


def uuid_str(s: str):
    """Parse a UUID string, returning it unchanged if invalid (used in
    `is_new_*` checks where the column is JSON-encoded list of strings)."""
    import uuid as _uuid
    try:
        return _uuid.UUID(s)
    except (ValueError, TypeError):
        return s


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------
def build_training_matrix(db: Session) -> pd.DataFrame:
    """Build the full feature matrix for training. Returns a DataFrame
    with one row per transaction, columns = all_feature_names() +
    [txn_id, created_at, is_fraud].
    """
    # Pull the base transaction + label set.
    rows = db.execute(text("""
        SELECT
            t.txn_id, t.created_at, t.amount, t.method, t.card_bin,
            t.ip_address, t.city, t.buyer_id, t.device_id, t.currency,
            d.os, d.browser,
            f.is_fraud
        FROM transactions t
        LEFT JOIN fraud_labels f ON f.txn_id = t.txn_id
        LEFT JOIN devices d ON d.device_id = t.device_id
    """)).mappings().fetchall()

    if not rows:
        return pd.DataFrame(columns=all_feature_names() + [LABEL_COLUMN, TXN_ID_COLUMN, TIMESTAMP_COLUMN])

    df = pd.DataFrame([dict(r) for r in rows])
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True)
    df = df.sort_values("created_at").reset_index(drop=True)

    # --- Numeric base features (no joins) ---
    df["amount_log"] = df["amount"].apply(_safe_log1p)
    df["hour_of_day"] = df["created_at"].dt.hour
    df["day_of_week"] = df["created_at"].dt.dayofweek
    df["is_weekend"] = df["created_at"].dt.weekday.apply(lambda d: 1 if d >= 5 else 0)
    df["is_late_night"] = df["hour_of_day"].apply(lambda h: 1 if 1 <= int(h) <= 5 else 0)
    df["ip_first_octet"] = df["ip_address"].fillna("").apply(
        lambda s: int(s.split(".")[0]) if "." in s else 10
    )

    # --- Velocity features (from SQL) ---
    vel = _velocity_features(db, df)
    for k, v in vel.items():
        df[k] = v

    # --- Novelty features (from SQL) ---
    nov = _novelty_features(db, df)
    for k, v in nov.items():
        df[k] = v

    # --- Ring features (from SQL) ---
    ring = _ring_features(db, df)
    for k, v in ring.items():
        df[k] = v

    # --- Categorical: encode to default if missing/unknown ---
    for c in CATEGORICAL_FEATURES:
        col = c.name
        if col not in df.columns:
            df[col] = c.default_label
        df[col] = df[col].fillna(c.default_label).apply(
            lambda v: v if v in _CAT_ALLOWED[c.name] else "OTHER"
        )

    # --- Final column order ---
    out_cols = [TXN_ID_COLUMN, TIMESTAMP_COLUMN] + all_feature_names() + [LABEL_COLUMN]
    return df[out_cols]


def build_inference_features(
    db: Session,
    txn: dict,
    redis_features: dict,
) -> pd.DataFrame:
    """Build the 1-row feature vector for a single transaction at scoring
    time. `txn` is the validated POST /score body (already sanitized).
    `redis_features` is the live aggregates dict from feature_updater.py.

    Returns a DataFrame with exactly one row, columns in
    all_feature_names() order.
    """
    row: dict[str, Any] = {}

    # --- Numeric base ---
    amount = float(txn.get("amount", 0.0))
    row["amount"] = amount
    row["amount_log"] = _safe_log1p(amount)
    ts = txn.get("created_at")
    if isinstance(ts, str):
        ts = pd.to_datetime(ts, utc=True)
    elif not isinstance(ts, pd.Timestamp):
        ts = pd.Timestamp.now(tz="UTC")
    row["hour_of_day"] = int(ts.hour)
    row["day_of_week"] = int(ts.dayofweek)
    row["is_weekend"] = 1 if row["day_of_week"] >= 5 else 0
    row["is_late_night"] = 1 if 1 <= row["hour_of_day"] <= 5 else 0
    ip = txn.get("ip_address", "")
    row["ip_first_octet"] = int(ip.split(".")[0]) if "." in (ip or "") else 10

    # --- Velocity: prefer Redis live aggregates (point-in-time accurate) ---
    rf = redis_features or {}
    row["txn_count_buyer_1h"] = rf.get("buyer_1h", 0)
    row["txn_count_buyer_24h"] = rf.get("buyer_24h", 0)
    row["txn_count_buyer_7d"] = rf.get("buyer_7d", 0)
    row["amount_sum_buyer_24h"] = rf.get("buyer_amount_24h", 0.0)
    row["seconds_since_last_buyer_txn"] = rf.get("buyer_seconds_since_last", 1e10)
    row["txn_count_device_1h"] = rf.get("device_1h", 0)
    row["txn_count_device_24h"] = rf.get("device_24h", 0)
    row["txn_count_device_7d"] = rf.get("device_7d", 0)
    row["distinct_buyers_device_7d"] = rf.get("device_distinct_buyers_7d", 1)
    row["device_age_days"] = rf.get("device_age_days", 0.0)
    row["txn_count_ip_1h"] = rf.get("ip_1h", 0)
    row["txn_count_ip_24h"] = rf.get("ip_24h", 0)
    row["distinct_buyers_ip_24h"] = rf.get("ip_distinct_buyers_24h", 1)
    row["txn_count_card_bin_1h"] = rf.get("bin_1h", 0)
    row["txn_count_card_bin_24h"] = rf.get("bin_24h", 0)
    row["distinct_buyers_card_bin_24h"] = rf.get("bin_distinct_buyers_24h", 1)
    row["is_known_device_for_buyer"] = rf.get("is_known_device_for_buyer", 1)
    row["is_new_ip_for_buyer"] = rf.get("is_new_ip_for_buyer", 0)
    row["is_new_card_bin_for_buyer"] = rf.get("is_new_card_bin_for_buyer", 0)

    # --- Ring features (cheap SQL lookup, no Redis) ---
    ring = _ring_features_for_inference(db, txn)
    row.update(ring)

    # --- Categorical: encode to default if missing/unknown ---
    for c in CATEGORICAL_FEATURES:
        row[c.name] = _categorize(txn.get(c.name), c)

    # Reorder to schema order.
    return pd.DataFrame([row])[all_feature_names()]


def _ring_features_for_inference(db: Optional[Session], txn: dict) -> dict[str, float]:
    """Look up ring signals for one transaction. Cheap: 2 small queries."""
    out = {
        "ring_member_count": 0.0,
        "ring_density": 0.0,
        "ring_flagged_amount": 0.0,
        "on_ring_shared_device": 0.0,
        "on_ring_shared_ip": 0.0,
        "on_ring_shared_bin": 0.0,
    }
    buyer = txn.get("buyer_id")
    if buyer is None or db is None:
        return out
    rows = db.execute(text("""
        SELECT ring_id, member_count, density_score, flagged_amount,
               shared_attribute, shared_value
        FROM detected_rings
        WHERE status = 'active'
          AND account_ids @> :buyer_json
    """), {"buyer_json": f'["{buyer}"]'}).mappings().fetchall()
    if rows:
        # Pick the densest ring this buyer is in.
        r = max(rows, key=lambda x: float(x["density_score"] or 0.0))
        out["ring_member_count"] = float(r["member_count"] or 0)
        out["ring_density"] = float(r["density_score"] or 0.0)
        out["ring_flagged_amount"] = float(r["flagged_amount"] or 0.0)
        # And check the txn's own attributes against that ring's shared attr
        attr, val = r["shared_attribute"], r["shared_value"]
        if attr == "device_fingerprint":
            dev = db.execute(
                text("SELECT device_id FROM devices WHERE fingerprint = :v LIMIT 1"),
                {"v": val},
            ).first()
            if dev and dev[0] == txn.get("device_id"):
                out["on_ring_shared_device"] = 1.0
        elif attr == "ip_address" and txn.get("ip_address") == val:
            out["on_ring_shared_ip"] = 1.0
        elif attr == "card_bin" and txn.get("card_bin") == val:
            out["on_ring_shared_bin"] = 1.0
    return out
