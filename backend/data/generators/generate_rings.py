# data/generators/generate_rings.py
# Inject coordinated abuse-ring patterns into the dataset.
#
# Real fraud rings don't look like ordinary buyer→device graphs. They share
# fingerprints (one device, many accounts), IP ranges (same ISP/VPN exit),
# and card BINs (stolen card pool). Per-transaction scoring misses this —
# a graph layer catches it. This script makes sure the synthetic data has
# *visible* ring structure for the graph detector to find.
#
# What this script does:
#   1. Picks `num_rings` random device_fingerprints (a NEW shared device
#      per ring, with a realistic fingerprint string).
#   2. Links 4-8 buyers to each shared device in `buyer_device_link`.
#   3. Re-stamps some of those buyers' existing transactions to also use
#      the shared device (so the graph edges become transaction-anchored,
#      not just link-table rows).
#   4. Optionally re-stamps a fraction of ring members' IP addresses to
#      a shared IP — adds a second shared-attribute signal.
#   5. Writes a row to `detected_rings` with the ring metadata so the
#      dashboard has rings to display.
#
# Run AFTER `generate_transactions.py`. Idempotent on (ring_id).

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
from data.generators.generate_transactions import (  # noqa: E402
    SEED_BUYER_COUNT,
    SEED_DEVICE_COUNT,
    SEED_TXN_COUNT,
    device_id,
)


SHARED_ATTR_CHOICES = ["device_fingerprint", "ip_address", "card_bin"]
SHARED_ATTR_WEIGHTS = [0.65, 0.20, 0.15]


def make_ring_id(index: int) -> uuid.UUID:
    """Ring IDs use the `r` prefix: r0000000-0000-4000-8000-NNNN..."""
    return uuid.UUID(f"r{index:012d}".rjust(32, "0"))


def pick_ring_members(
    db, num_buyers: int, ring_size: int, rng: random.Random,
) -> list[uuid.UUID]:
    """Pick `ring_size` distinct buyer UUIDs (offset above the seed range)."""
    rows = db.execute(
        text("""
            SELECT buyer_id FROM buyers
            WHERE buyer_id >= :lo
            ORDER BY random()
            LIMIT :n
        """),
        {"lo": uuid.UUID(int=SEED_BUYER_COUNT + 1), "n": ring_size},
    ).fetchall()
    if len(rows) < ring_size:
        # Fall back to *any* buyers if the offset range is empty.
        rows = db.execute(
            text("SELECT buyer_id FROM buyers ORDER BY random() LIMIT :n"),
            {"n": ring_size},
        ).fetchall()
    return [r[0] for r in rows]


def assign_shared_attribute(
    rng: random.Random, attr: str, device_index: int,
) -> tuple[str, str, str]:
    """Return (attribute_name, attribute_value, fingerprint/ip/bin) suitable
    for inserting into the `devices` table (for device attr) or stamping
    transactions (for ip/bin attr).
    """
    if attr == "device_fingerprint":
        fp = f"fp_ring_dev_{device_index:06d}_{rng.randint(1000, 9999)}"
        os_name, browser = rng.choices(
            [("Android", "Chrome Mobile"), ("iOS", "Mobile Safari"),
             ("Windows", "Chrome")],
            weights=[0.5, 0.3, 0.2],
            k=1,
        )[0]
        return (attr, fp, os_name + "|" + browser)
    if attr == "ip_address":
        # 10.x is the dominant private range in our transactions.
        return (attr, f"10.{rng.randint(200, 250)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}", "")
    if attr == "card_bin":
        return (attr, f"{rng.randint(400_000, 499_999):06d}", "")
    raise ValueError(f"Unknown shared attr: {attr}")


def create_shared_device(
    db, ring_idx: int, rng: random.Random, os_browser: str,
) -> tuple[uuid.UUID, str]:
    """Create a brand-new device row for this ring. Returns (device_id, fingerprint)."""
    os_name, browser = os_browser.split("|", 1)
    new_device_idx = SEED_DEVICE_COUNT + 1 + ring_idx  # offsets well past the seed range
    fingerprint = f"fp_ring_dev_{new_device_idx:06d}_{rng.randint(1000, 9999)}"
    did = device_id(new_device_idx)
    db.execute(
        text("""
            INSERT INTO devices (device_id, fingerprint, os, browser)
            VALUES (:did, :fp, :os, :br)
            ON CONFLICT (device_id) DO NOTHING
        """),
        {"did": did, "fp": fingerprint, "os": os_name, "br": browser},
    )
    return did, fingerprint


def link_ring_members(
    db, members: list[uuid.UUID], shared_device_id: uuid.UUID | None,
) -> int:
    """Insert buyer_device_link rows for each ring member → shared device."""
    if shared_device_id is None:
        return 0
    now = datetime.now(timezone.utc).isoformat()
    params = [
        {"bid": bid, "did": shared_device_id, "ts": now}
        for bid in members
    ]
    if not params:
        return 0
    db.execute(
        text("""
            INSERT INTO buyer_device_link (buyer_id, device_id, first_seen_at, last_seen_at)
            VALUES (:bid, :did, :ts, :ts)
            ON CONFLICT (buyer_id, device_id) DO NOTHING
        """),
        params,
    )
    return len(params)


def restamp_transactions(
    db, members: list[uuid.UUID], shared_device_id: uuid.UUID | None,
    shared_ip: str | None, ring_size_fraction: float, rng: random.Random,
) -> int:
    """For a fraction of each ring member's existing transactions, force
    `device_id = shared_device_id` and/or `ip_address = shared_ip`. This
    is what makes the ring *visible* to the graph layer (transaction-level
    co-occurrence, not just link-table rows).
    """
    if not members:
        return 0
    n_per_buyer = max(2, int(20 * ring_size_fraction))  # how many txns to retag per buyer
    restamped = 0
    for bid in members:
        # Pick the most recent N transactions for this buyer.
        rows = db.execute(
            text("""
                SELECT txn_id FROM transactions
                WHERE buyer_id = :bid
                ORDER BY created_at DESC
                LIMIT :n
            """),
            {"bid": bid, "n": n_per_buyer},
        ).fetchall()
        if not rows:
            continue
        # Drop ~10% to add a bit of imperfection.
        chosen = [r[0] for r in rows if rng.random() > 0.10]
        if not chosen:
            continue
        # Use ANY() so we update all chosen rows in one statement.
        if shared_device_id is not None and shared_ip is not None:
            db.execute(
                text("""
                    UPDATE transactions
                    SET device_id = :did, ip_address = :ip
                    WHERE txn_id = ANY(:tids)
                """),
                {"did": shared_device_id, "ip": shared_ip, "tids": chosen},
            )
        elif shared_device_id is not None:
            db.execute(
                text("""
                    UPDATE transactions
                    SET device_id = :did
                    WHERE txn_id = ANY(:tids)
                """),
                {"did": shared_device_id, "tids": chosen},
            )
        elif shared_ip is not None:
            db.execute(
                text("""
                    UPDATE transactions
                    SET ip_address = :ip
                    WHERE txn_id = ANY(:tids)
                """),
                {"ip": shared_ip, "tids": chosen},
            )
        restamped += len(chosen)
    return restamped


def write_ring_row(
    db, ring_idx: int, members: list[uuid.UUID], attr_name: str,
    attr_value: str, flagged_amount: float, density: float,
) -> uuid.UUID:
    """Write the detected_rings row. Returns the ring_id."""
    rid = make_ring_id(ring_idx)
    db.execute(
        text("""
            INSERT INTO detected_rings
                (ring_id, member_count, density_score, shared_attribute,
                 shared_value, status, flagged_amount, account_ids, detected_at)
            VALUES
                (:rid, :n, :d, :a, :v, 'active', :amt, :ids::jsonb, NOW())
            ON CONFLICT (ring_id) DO UPDATE
                SET member_count = EXCLUDED.member_count,
                    density_score = EXCLUDED.density_score,
                    shared_value = EXCLUDED.shared_value,
                    flagged_amount = EXCLUDED.flagged_amount,
                    account_ids = EXCLUDED.account_ids,
                    detected_at = NOW()
        """),
        {
            "rid": rid,
            "n": len(members),
            "d": density,
            "a": attr_name,
            "v": attr_value,
            "amt": flagged_amount,
            "ids": "[" + ",".join(f'"{str(b)}"' for b in members) + "]",
        },
    )
    return rid


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Inject S.P.A.R.K. abuse-ring patterns.")
    p.add_argument("--rings", type=int, default=15, help="Number of rings to inject (default: 15)")
    p.add_argument("--min-size", type=int, default=4, help="Min buyers per ring (default: 4)")
    p.add_argument("--max-size", type=int, default=8, help="Max buyers per ring (default: 8)")
    p.add_argument("--restamp-fraction", type=float, default=0.6,
                   help="Fraction of each ring member's recent txns to restamp (default: 0.6)")
    p.add_argument("--seed", type=int, default=DEFAULT_SEED + 1)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    rng = make_rng(args.seed)

    if args.rings <= 0 or args.max_size < args.min_size:
        print("[generate_rings] Invalid ring config.")
        sys.exit(1)

    print(f"[generate_rings] rings={args.rings} size=[{args.min_size},{args.max_size}] "
          f"restamp={args.restamp_fraction} seed={args.seed}")

    with session_scope() as db:
        # Ensure we have enough buyers.
        buyer_count = db.execute(text("SELECT count(*) FROM buyers")).scalar()
        if buyer_count < args.max_size * args.rings:
            needed = args.max_size * args.rings - buyer_count
            print(f"[generate_rings] Not enough buyers ({buyer_count}). "
                  f"Run generate_transactions first (need at least {args.max_size * args.rings}).")
            sys.exit(1)

        for i in range(1, args.rings + 1):
            ring_size = rng.randint(args.min_size, args.max_size)
            members = pick_ring_members(db, buyer_count, ring_size, rng)

            attr = rng.choices(SHARED_ATTR_CHOICES, weights=SHARED_ATTR_WEIGHTS, k=1)[0]

            shared_device_id = None
            shared_ip = None
            attr_value = ""
            if attr == "device_fingerprint":
                os_browser = rng.choices(
                    [("Android", "Chrome Mobile"), ("iOS", "Mobile Safari"),
                     ("Windows", "Chrome")],
                    weights=[0.5, 0.3, 0.2],
                    k=1,
                )[0]
                shared_device_id, fp = create_shared_device(db, i, rng, os_browser)
                attr_value = fp
            elif attr == "ip_address":
                shared_ip = f"10.{rng.randint(200, 250)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}"
                attr_value = shared_ip
                # Also link them to a NEW shared device (50% chance) so the
                # graph layer has *two* shared attributes — easier to detect.
                if rng.random() < 0.5:
                    os_browser = ("Android", "Chrome Mobile")
                    shared_device_id, _ = create_shared_device(db, i + 10_000, rng, os_browser)
                    attr_value = f"{shared_ip}|device"
            elif attr == "card_bin":
                shared_bin = f"{rng.randint(400_000, 499_999):06d}"
                attr_value = shared_bin
                # Stamp transactions for these buyers with the shared BIN.
                for bid in members:
                    rows = db.execute(
                        text("""
                            UPDATE transactions
                            SET card_bin = :b
                            WHERE txn_id IN (
                                SELECT txn_id FROM transactions
                                WHERE buyer_id = :bid
                                ORDER BY created_at DESC LIMIT 8
                            )
                        """),
                        {"b": shared_bin, "bid": bid},
                    )

            # Link buyers to the shared device (if we made one).
            link_ring_members(db, members, shared_device_id)

            # Re-stamp recent transactions so the ring is visible at txn level.
            restamp_transactions(
                db, members, shared_device_id, shared_ip,
                args.restamp_fraction, rng,
            )

            # Density: 1.0 means a fully connected clique of N members.
            # In practice we have partial connectivity → ~0.5-0.95.
            density = round(rng.uniform(0.50, 0.95), 3)

            # Flagged amount = sum of recent ring-member transactions.
            flagged = db.execute(
                text("""
                    SELECT COALESCE(SUM(amount), 0)
                    FROM transactions
                    WHERE buyer_id = ANY(:bids)
                """),
                {"bids": members},
            ).scalar() or 0.0

            write_ring_row(db, i, members, attr, attr_value, float(flagged), density)
            log_progress("  rings    ", i, args.rings)
        print()

    # Report
    with session_scope() as db:
        ring_count = db.execute(text("SELECT count(*) FROM detected_rings")).scalar()
        max_density = db.execute(text("SELECT MAX(density_score) FROM detected_rings")).scalar()
        print(f"\n[generate_rings] Done. {ring_count} rings in detected_rings (max density: {max_density}).")


if __name__ == "__main__":
    main()
