# ml/features/feature_schema.py
# Single source of truth for S.P.A.R.K. feature names, types, and groupings.
#
# This is consumed by:
#   - feature_engineering.py: builds the feature matrix at training time
#   - ingestion/feature_updater.py: maintains Redis aggregates for online
#     scoring
#   - api/services/feature_assembly.py: assembles features at inference time
#   - training/train_model.py: declares the column order the model expects
#
# IMPORTANT: feature names are part of the model contract. Renaming or
# reordering an entry in NUMERIC_FEATURES / CATEGORICAL_FEATURES will
# break stored model artifacts. Always bump MODEL_VERSION in
# threshold_calibration.py when changing the schema.

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


# ---------------------------------------------------------------------------
# Feature groups — used for per-group PSI drift tracking in Phase 7
# ---------------------------------------------------------------------------
GROUP_BEHAVIORAL: Final[str] = "behavioral"
GROUP_DEVICE: Final[str] = "device"
GROUP_GEO: Final[str] = "geo"
GROUP_CARD: Final[str] = "card"
GROUP_RING: Final[str] = "ring"


# ---------------------------------------------------------------------------
# Numeric features (float / int, fed directly to XGBoost)
# ---------------------------------------------------------------------------
# Each entry: (name, default value if missing, group, description)
NUMERIC_FEATURES: Final[list[tuple[str, float, str, str]]] = [
    # --- Behavioral / velocity ---
    ("amount",                         0.0,    GROUP_BEHAVIORAL, "Transaction amount in INR"),
    ("amount_log",                     0.0,    GROUP_BEHAVIORAL, "log1p(amount)"),
    ("hour_of_day",                    12,     GROUP_BEHAVIORAL, "UTC hour of the transaction (0-23)"),
    ("day_of_week",                    3,      GROUP_BEHAVIORAL, "Day of week (0=Mon..6=Sun)"),
    ("is_weekend",                     0,      GROUP_BEHAVIORAL, "1 if Saturday/Sunday"),
    ("is_late_night",                  0,      GROUP_BEHAVIORAL, "1 if hour between 1 and 5 UTC"),
    ("txn_count_buyer_1h",             0,      GROUP_BEHAVIORAL, "Txns by this buyer in last 1h"),
    ("txn_count_buyer_24h",            0,      GROUP_BEHAVIORAL, "Txns by this buyer in last 24h"),
    ("txn_count_buyer_7d",             0,      GROUP_BEHAVIORAL, "Txns by this buyer in last 7d"),
    ("amount_sum_buyer_24h",           0.0,    GROUP_BEHAVIORAL, "Sum of amounts for this buyer in last 24h (INR)"),
    ("seconds_since_last_buyer_txn",   9.99e9, GROUP_BEHAVIORAL, "Seconds since buyer's previous txn; 1e10 if none"),

    # --- Device ---
    ("txn_count_device_1h",            0,      GROUP_DEVICE, "Txns on this device in last 1h"),
    ("txn_count_device_24h",           0,      GROUP_DEVICE, "Txns on this device in last 24h"),
    ("txn_count_device_7d",            0,      GROUP_DEVICE, "Txns on this device in last 7d"),
    ("distinct_buyers_device_7d",      1,      GROUP_DEVICE, "Distinct buyers on this device in last 7d"),
    ("device_age_days",                0,      GROUP_DEVICE, "Days since this device first appeared in our data"),
    ("is_known_device_for_buyer",      1,      GROUP_DEVICE, "1 if this device is in buyer_device_link for this buyer"),

    # --- Geo / network ---
    ("txn_count_ip_1h",                0,      GROUP_GEO, "Txns from this IP in last 1h"),
    ("txn_count_ip_24h",               0,      GROUP_GEO, "Txns from this IP in last 24h"),
    ("distinct_buyers_ip_24h",         1,      GROUP_GEO, "Distinct buyers on this IP in last 24h"),
    ("is_new_ip_for_buyer",            0,      GROUP_GEO, "1 if buyer hasn't transacted from this IP before"),
    ("ip_first_octet",                 10,     GROUP_GEO, "First octet of IP (ISP signal)"),

    # --- Card ---
    ("txn_count_card_bin_1h",          0,      GROUP_CARD, "Txns on this card BIN in last 1h"),
    ("txn_count_card_bin_24h",         0,      GROUP_CARD, "Txns on this card BIN in last 24h"),
    ("distinct_buyers_card_bin_24h",   1,      GROUP_CARD, "Distinct buyers on this card BIN in last 24h"),
    ("is_new_card_bin_for_buyer",      0,      GROUP_CARD, "1 if buyer has never used this BIN before"),

    # --- Ring (graph-derived) ---
    ("ring_member_count",              0,      GROUP_RING, "Members of the ring this buyer belongs to (0 if none)"),
    ("ring_density",                   0.0,    GROUP_RING, "Density score of buyer's ring (0 if none)"),
    ("ring_flagged_amount",            0.0,    GROUP_RING, "Total flagged amount in buyer's ring (INR)"),
    ("on_ring_shared_device",          0,      GROUP_RING, "1 if txn device matches a ring's shared device"),
    ("on_ring_shared_ip",              0,      GROUP_RING, "1 if txn IP matches a ring's shared IP"),
    ("on_ring_shared_bin",             0,      GROUP_RING, "1 if txn card BIN matches a ring's shared BIN"),
]


# ---------------------------------------------------------------------------
# Categorical features (label-encoded ints for XGBoost)
# ---------------------------------------------------------------------------
# Each entry: (name, default label, group, allowed values, description)
@dataclass(frozen=True)
class CategoricalFeature:
    name: str
    default_label: str
    group: str
    allowed: tuple[str, ...]
    description: str


CATEGORICAL_FEATURES: Final[tuple[CategoricalFeature, ...]] = (
    CategoricalFeature(
        "method", "upi", GROUP_BEHAVIORAL,
        ("upi", "card", "netbanking", "wallet", "emandate"),
        "Razorpay payment method",
    ),
    CategoricalFeature(
        "city", "Bengaluru", GROUP_GEO,
        ("Bengaluru", "Mumbai", "Delhi", "Pune", "Hyderabad",
         "Chennai", "Kolkata", "Ahmedabad", "OTHER"),
        "Buyer city at txn time",
    ),
    CategoricalFeature(
        "os", "Android", GROUP_DEVICE,
        ("Android", "iOS", "Windows", "macOS", "OTHER"),
        "Device OS",
    ),
    CategoricalFeature(
        "browser", "Chrome", GROUP_DEVICE,
        ("Chrome", "Chrome Mobile", "Mobile Safari", "Safari", "Firefox", "OTHER"),
        "Device browser",
    ),
    CategoricalFeature(
        "currency", "INR", GROUP_BEHAVIORAL,
        ("INR",),
        "Currency code (single-currency for now)",
    ),
)


# ---------------------------------------------------------------------------
# Label column (not a feature)
# ---------------------------------------------------------------------------
LABEL_COLUMN: Final[str] = "is_fraud"
TXN_ID_COLUMN: Final[str] = "txn_id"
TIMESTAMP_COLUMN: Final[str] = "created_at"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def all_feature_names() -> list[str]:
    """Return the full ordered feature list. Order matters for inference
    parity with the trained model — never reorder.
    """
    return [name for name, *_ in NUMERIC_FEATURES] + [c.name for c in CATEGORICAL_FEATURES]


def numeric_feature_names() -> list[str]:
    return [name for name, *_ in NUMERIC_FEATURES]


def categorical_feature_names() -> list[str]:
    return [c.name for c in CATEGORICAL_FEATURES]


def feature_groups() -> dict[str, list[str]]:
    """Group all features by their drift-monitor group, for per-group PSI."""
    out: dict[str, list[str]] = {}
    for name, _default, group, _desc in NUMERIC_FEATURES:
        out.setdefault(group, []).append(name)
    for c in CATEGORICAL_FEATURES:
        out.setdefault(c.group, []).append(c.name)
    return out


FEATURE_DESCRIPTIONS: Final[dict[str, str]] = {
    **{name: desc for name, _default, _group, desc in NUMERIC_FEATURES},
    **{c.name: c.description for c in CATEGORICAL_FEATURES},
}
