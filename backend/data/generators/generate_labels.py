# data/generators/generate_labels.py
# Generate fraud/chargeback labels for every transaction.
#
# Ground truth is what the ML model trains against and what evaluation
# metrics measure. We need:
#   - Exactly 1 label per transaction (no orphans — checked in
#     test_db_conn.py).
#   - Realistic fraud rate (~1-3% for clean traffic, ~10-25% for ring
#     members, so the model can actually learn to use ring features).
#   - Labels anchored to *plausible* fraud signals, not random — high
#     amount, late night, burst velocity, UPI→card method-switching are
#     well-known chargeback predictors, so we lean on them.
#
# Run AFTER `generate_rings.py` so ring membership is available.

from __future__ import annotations

import argparse
import os
import random
import sys
import uuid
from datetime import datetime, timezone

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from sqlalchemy import text  # noqa: E402

from data.generators._common import (  # noqa: E402
    DEFAULT_SEED,
    chunked,
    log_progress,
    make_rng,
    session_scope,
)


# Baseline per-transaction fraud probability by feature profile.
# These get MULTIPLIED by a ring-membership boost (see _fraud_prob below).
BASE_P_CLEAN = 0.012          # ordinary txn
BASE_P_LARGE_AMOUNT = 0.04    # > 50k INR
BASE_P_LATE_NIGHT = 0.025     # 1-5am local
BASE_P_HIGH_VELOCITY = 0.06   # 5+ txns in last hour for same buyer
BASE_P_RING_MEMBER = 0.18     # ring member (boosted from above)
BASE_P_RING_TX = 0.28         # on the *shared* device/IP/BIN used by a ring


# Label sources — useful for downstream evaluation filtering.
LABEL_SOURCES = ["synthetic_seed", "chargeback_webhook", "manual_review", "model_inference"]


def _fraud_prob(
    amount: float,
    hour_utc: int,
    velocity_1h: int,
    is_ring_member: bool,
    on_ring_signal: bool,
) -> float:
    """Combine base probabilities and take the max. We *don't* want
    independent multiplication here — fraud is driven by a small number
    of strong signals, not by stacking many weak ones.
    """
    p = BASE_P_CLEAN
    if amount > 50_000:
        p = max(p, BASE_P_LARGE_AMOUNT)
    if 1 <= hour_utc <= 5:
        p = max(p, BASE_P_LATE_NIGHT)
    if velocity_1h >= 5:
        p = max(p, BASE_P_HIGH_VELOCITY)
    if on_ring_signal:
        p = max(p, BASE_P_RING_TX)
    if is_ring_member:
        p = max(p, BASE_P_RING_MEMBER)
    return p


def fetch_ring_buyers(db) -> set[uuid.UUID]:
    """Return the set of buyer_ids that are members of any detected_rings row."""
    rows = db.execute(
        text("SELECT account_ids FROM detected_rings WHERE status = 'active'")
    ).fetchall()
    members: set[uuid.UUID] = set()
    for (raw,) in rows:
        if not raw:
            continue
        # `account_ids` is JSONB. SQLAlchemy returns either a Python list
        # (psycopg2 json deserializer) or a JSON string depending on driver.
        if isinstance(raw, str):
            import json
            raw = json.loads(raw)
        for item in raw or []:
            try:
                members.add(uuid.UUID(item))
            except (ValueError, TypeError):
                continue
    return members


def fetch_ring_signals(db) -> dict[str, set]:
    """Return a dict mapping shared attribute values that are part of a ring.
    Keys: 'device_id', 'ip_address', 'card_bin'. Values: sets of attribute
    values that are 'ring signals' (transactions matching these are more
    likely to be fraud).
    """
    rows = db.execute(
        text("SELECT shared_attribute, shared_value FROM detected_rings WHERE status = 'active'")
    ).fetchall()
    out: dict[str, set] = {"device_id": set(), "ip_address": set(), "card_bin": set()}
    for attr, value in rows:
        if not attr or not value:
            continue
        if attr == "device_fingerprint":
            # Look up device_id by fingerprint.
            dev = db.execute(
                text("SELECT device_id FROM devices WHERE fingerprint = :v LIMIT 1"),
                {"v": value},
            ).first()
            if dev:
                out["device_id"].add(dev[0])
        elif attr == "ip_address":
            out["ip_address"].add(value)
        elif attr == "card_bin":
            out["card_bin"].add(value)
    return out


# ---------------------------------------------------------------------------
# Main labeling logic
# ---------------------------------------------------------------------------
def label_all_transactions(db, rng: random.Random, dry_run: bool = False) -> int:
    """Stream all transactions and write fraud_labels rows. Returns count labeled."""
    ring_buyers = fetch_ring_buyers(db)
    ring_signals = fetch_ring_signals(db)
    print(f"[generate_labels] Ring members: {len(ring_buyers)}")
    print(f"[generate_labels] Ring signal "
          f"devices={len(ring_signals['device_id'])} "
          f"ips={len(ring_signals['ip_address'])} "
          f"bins={len(ring_signals['card_bin'])}")

    # Pre-compute 1h velocity per buyer. We do this in one pass over the
    # transactions table ordered by (buyer_id, created_at).
    velocity_rows = db.execute(text("""
        SELECT buyer_id, count(*) AS n
        FROM (
            SELECT buyer_id, created_at,
                   count(*) OVER (
                       PARTITION BY buyer_id
                       ORDER BY created_at
                       RANGE BETWEEN INTERVAL '1 hour' PRECEDING AND CURRENT ROW
                   ) AS window_count
            FROM transactions
        ) t
        WHERE window_count > 0
        GROUP BY buyer_id
    """)).fetchall()
    # Actually a simpler proxy: how many txns each buyer has at all. We use
    # that as a *coarse* velocity signal — buyers with many txns in the
    # dataset are likelier to be burst-shoppers or fraud rings.
    total_per_buyer = dict(db.execute(
        text("SELECT buyer_id, count(*) FROM transactions GROUP BY buyer_id")
    ).fetchall())
    # Use a per-buyer transaction count threshold as a velocity proxy.
    HIGH_VELOCITY_THRESHOLD = 25  # buyers with > 25 txns in 60 days = "bursty"

    # Stream all txns in batches.
    BATCH = 1000
    total_labeled = 0
    fraud_count = 0
    last_id = None  # for keyset pagination

    while True:
        if last_id is None:
            rows = db.execute(text("""
                SELECT txn_id, created_at, buyer_id, device_id, ip_address, card_bin, amount
                FROM transactions
                ORDER BY txn_id
                LIMIT :lim
            """), {"lim": BATCH}).fetchall()
        else:
            rows = db.execute(text("""
                SELECT txn_id, created_at, buyer_id, device_id, ip_address, card_bin, amount
                FROM transactions
                WHERE txn_id > :lo
                ORDER BY txn_id
                LIMIT :lim
            """), {"lo": last_id, "lim": BATCH}).fetchall()

        if not rows:
            break

        label_params = []
        for txn_id, created_at, buyer_id, device_id_v, ip, card_bin, amount in rows:
            last_id = txn_id
            hour_utc = created_at.hour if hasattr(created_at, "hour") else 12
            buyer_total = total_per_buyer.get(buyer_id, 0)
            velocity_1h = buyer_total  # proxy
            is_ring_member = buyer_id in ring_buyers
            on_ring_signal = (
                (device_id_v is not None and device_id_v in ring_signals["device_id"])
                or (ip in ring_signals["ip_address"] if ip else False)
                or (card_bin in ring_signals["card_bin"] if card_bin else False)
            )

            p = _fraud_prob(float(amount), hour_utc, velocity_1h, is_ring_member, on_ring_signal)
            # If buyer is very high velocity, nudge probability up.
            if buyer_total > HIGH_VELOCITY_THRESHOLD:
                p = max(p, 0.05)

            is_fraud = rng.random() < p

            # Pick a label source: synthetic for clean, chargeback_webhook for fraud
            # if it's a ring member, manual_review otherwise.
            if is_fraud:
                if is_ring_member or on_ring_signal:
                    source = "chargeback_webhook" if rng.random() < 0.85 else "manual_review"
                else:
                    source = "chargeback_webhook" if rng.random() < 0.7 else "manual_review"
            else:
                source = "synthetic_seed" if rng.random() < 0.95 else "model_inference"

            label_params.append({
                "tid": txn_id,
                "is_fraud": is_fraud,
                "src": source,
                "ts": (created_at if isinstance(created_at, datetime) else datetime.now(timezone.utc)).isoformat(),
            })
            if is_fraud:
                fraud_count += 1

        if not dry_run:
            # ON CONFLICT (txn_id) DO UPDATE so re-running relabels cleanly.
            for batch in chunked(label_params, 500):
                db.execute(
                    text("""
                        INSERT INTO fraud_labels (txn_id, is_fraud, label_source, updated_at)
                        VALUES (:tid, :is_fraud, :src, :ts)
                        ON CONFLICT (txn_id) DO UPDATE
                            SET is_fraud = EXCLUDED.is_fraud,
                                label_source = EXCLUDED.label_source,
                                updated_at = EXCLUDED.updated_at
                    """),
                    batch,
                )

        total_labeled += len(label_params)
        log_progress("  labels   ", total_labeled, sum(total_per_buyer.values()))

        # Save progress to DB between batches so long runs don't lose work.
        if not dry_run and total_labeled % 5000 == 0:
            db.commit()

    return total_labeled


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate S.P.A.R.K. fraud labels.")
    p.add_argument("--dry-run", action="store_true", help="Compute but don't write")
    p.add_argument("--seed", type=int, default=DEFAULT_SEED + 2)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    rng = make_rng(args.seed)
    print(f"[generate_labels] seed={args.seed} dry_run={args.dry_run}")

    with session_scope() as db:
        txn_count = db.execute(text("SELECT count(*) FROM transactions")).scalar()
        if txn_count == 0:
            print("[generate_labels] No transactions found. Run generate_transactions first.")
            sys.exit(1)
        print(f"[generate_labels] Found {txn_count} transactions to label.")

        n = label_all_transactions(db, rng, dry_run=args.dry_run)
        # Final commit happens via session_scope context manager.
        print(f"\n[generate_labels] Labeled {n} transactions.")

    # Report
    if not args.dry_run:
        with session_scope() as db:
            total = db.execute(text("SELECT count(*) FROM fraud_labels")).scalar()
            fraud = db.execute(text("SELECT count(*) FROM fraud_labels WHERE is_fraud")).scalar()
            rate = (100.0 * fraud / total) if total else 0.0
            print(f"\n=== Label summary ===")
            print(f"  total labels:  {total}")
            print(f"  fraud labels:  {fraud}  ({rate:.2f}%)")
            by_src = db.execute(
                text("SELECT label_source, count(*) FROM fraud_labels GROUP BY label_source ORDER BY 2 DESC")
            ).fetchall()
            for src, c in by_src:
                print(f"  {src:<22} {c:>8}")


if __name__ == "__main__":
    main()
