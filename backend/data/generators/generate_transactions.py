# data/generators/generate_transactions.py
# Synthetic Razorpay-style transaction generator.
#
# Writes to: buyers, devices, buyer_device_link, transactions.
# Idempotent: every row uses a deterministic UUID derived from a sequence
# index, so re-running won't duplicate rows.
#
# Usage:
#   python -m data.generators.generate_transactions \
#       --buyers 2000 --devices 2400 --transactions 25000 --days 60
#
# Defaults produce ~25k transactions, ~2k buyers, ~2.4k devices, spread
# over the last 60 days — enough for time-based train/test split.

from __future__ import annotations

import argparse
import os
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone

# Allow running as a script from anywhere in the repo.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from sqlalchemy import text  # noqa: E402

from data.generators._common import (  # noqa: E402
    DEFAULT_SEED,
    CITY_WEIGHTS,
    DEVICE_OS_BROWSER,
    DEVICE_OS_WEIGHTS,
    FIRST_NAMES,
    INDIAN_CITIES,
    LAST_NAMES,
    PAYMENT_METHODS,
    PAYMENT_METHOD_WEIGHTS,
    chunked,
    fetch_merchants,
    log_progress,
    make_rng,
    session_scope,
)


# ---------------------------------------------------------------------------
# Deterministic ID derivation
# ---------------------------------------------------------------------------
# Buyer/device IDs retain the original readable deterministic format.
# Transaction IDs use a separate UUID5 namespace so they never collide with
# legacy e000... transaction IDs already present in development databases.
SEED_BUYER_COUNT = 60
SEED_DEVICE_COUNT = 75
SEED_TXN_COUNT = 520
_TXN_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://spark.local/generated-transactions/v2")


def _id(prefix: str, index: int) -> uuid.UUID:
    """Build a deterministic UUID like `b0000000-0000-4000-8000-NNNN...`."""
    # Strip the dashes of the canonical pattern and embed `index`.
    # The prefix hex chars keep IDs grouped when sorted in psql output.
    tail = f"{index:012d}"
    s = f"{prefix}0000000-0000-4000-8000-{tail}"
    return uuid.UUID(s)


def buyer_id(index: int) -> uuid.UUID:
    return _id("b", index)


def device_id(index: int) -> uuid.UUID:
    return _id("d", index)


def txn_id(index: int) -> uuid.UUID:
    """Stable v2 transaction UUID that is safe across repeated generator runs."""
    return uuid.uuid5(_TXN_NAMESPACE, f"txn-{index}")


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------
def gen_buyer_name(rng: random.Random) -> tuple[str, str, str, str]:
    first = rng.choice(FIRST_NAMES)
    last = rng.choice(LAST_NAMES)
    name = f"{first} {last}"
    email = f"{first.lower()}.{last.lower()}{rng.randint(1, 9999)}@example.in"
    phone = f"+91{rng.randint(70_0000_0000, 99_9999_9999)}"
    return name, email, phone


def seed_buyers(db, count: int, rng: random.Random) -> int:
    """Insert `count` buyers. Returns number of rows inserted."""
    inserted = 0
    BATCH = 500
    for batch in chunked(range(SEED_BUYER_COUNT + 1, SEED_BUYER_COUNT + 1 + count), BATCH):
        params = []
        for i in batch:
            name, email, phone = gen_buyer_name(rng)
            params.append({"bid": buyer_id(i), "name": name, "email": email, "phone": phone})
        db.execute(
            text("""
                INSERT INTO buyers (buyer_id, name, email, phone)
                VALUES (:bid, :name, :email, :phone)
                ON CONFLICT (buyer_id) DO NOTHING
            """),
            params,
        )
        inserted += len(params)
        log_progress("  buyers   ", min(inserted, count), count)
    return inserted


def seed_devices(db, count: int, rng: random.Random) -> int:
    inserted = 0
    BATCH = 500
    for batch in chunked(range(SEED_DEVICE_COUNT + 1, SEED_DEVICE_COUNT + 1 + count), BATCH):
        params = []
        for i in batch:
            os_browser = rng.choices(DEVICE_OS_BROWSER, weights=DEVICE_OS_WEIGHTS, k=1)[0]
            os_name, browser = os_browser
            params.append({
                "did": device_id(i),
                "fp": f"fp_gen_{i:09d}_{rng.randint(1000, 9999)}",
                "os": os_name,
                "br": browser,
            })
        db.execute(
            text("""
                INSERT INTO devices (device_id, fingerprint, os, browser)
                VALUES (:did, :fp, :os, :br)
                ON CONFLICT (device_id) DO NOTHING
            """),
            params,
        )
        inserted += len(params)
        log_progress("  devices  ", min(inserted, count), count)
    return inserted


def link_buyers_to_devices(db, buyer_count: int, device_count: int, rng: random.Random) -> int:
    """Each buyer has 1 primary device + 0..2 secondary devices.

    Primary device is unique per buyer. Secondaries can overlap (this is the
    natural substrate for ring detection — but the actual *injection* of
    suspicious overlap is done by `generate_rings.py`, not here).
    """
    inserted = 0
    BATCH = 1000

    # Pre-compute primary device index for each buyer.
    primary = {i: rng.randint(SEED_DEVICE_COUNT + 1, SEED_DEVICE_COUNT + device_count)
               for i in range(SEED_BUYER_COUNT + 1, SEED_BUYER_COUNT + 1 + buyer_count)}

    for batch in chunked(list(primary.items()), BATCH):
        params = []
        for buyer_idx, dev_idx in batch:
            params.append({
                "bid": buyer_id(buyer_idx),
                "did": device_id(dev_idx),
                "first": (datetime.now(timezone.utc) - timedelta(days=rng.randint(0, 60))).isoformat(),
                "last": datetime.now(timezone.utc).isoformat(),
            })
        db.execute(
            text("""
                INSERT INTO buyer_device_link (buyer_id, device_id, first_seen_at, last_seen_at)
                VALUES (:bid, :did, :first, :last)
                ON CONFLICT (buyer_id, device_id) DO NOTHING
            """),
            params,
        )
        inserted += len(params)

    # Add secondary devices (probability ~ 25% per buyer, max 2).
    secondary = []
    for buyer_idx in primary:
        if rng.random() < 0.25:
            n = rng.randint(1, 2)
            extras = rng.sample(
                range(SEED_DEVICE_COUNT + 1, SEED_DEVICE_COUNT + 1 + device_count),
                k=min(n, device_count),
            )
            for dev_idx in extras:
                if dev_idx == primary[buyer_idx]:
                    continue
                secondary.append({
                    "bid": buyer_id(buyer_idx),
                    "did": device_id(dev_idx),
                    "first": (datetime.now(timezone.utc) - timedelta(days=rng.randint(0, 30))).isoformat(),
                    "last": datetime.now(timezone.utc).isoformat(),
                })

    for batch in chunked(secondary, BATCH):
        if not batch:
            continue
        db.execute(
            text("""
                INSERT INTO buyer_device_link (buyer_id, device_id, first_seen_at, last_seen_at)
                VALUES (:bid, :did, :first, :last)
                ON CONFLICT (buyer_id, device_id) DO NOTHING
            """),
            batch,
        )
        inserted += len(batch)

    log_progress("  links    ", min(inserted, buyer_count), buyer_count)
    return inserted


def gen_card_bin(rng: random.Random) -> str:
    # 400000-499999 is the standard card-BIN space (Visa/MC). We pick a real
    # sub-range and emit 6 digits.
    return f"{rng.randint(400_000, 499_999):06d}"


def gen_ipv4(rng: random.Random) -> str:
    # Skew toward plausible Indian ISP ranges: 49.x, 117.x, 122.x, 203.x
    first = rng.choices(
        [10, 49, 117, 122, 152, 182, 202, 203],
        weights=[0.20, 0.18, 0.15, 0.12, 0.10, 0.10, 0.08, 0.07],
        k=1,
    )[0]
    return f"{first}.{rng.randint(0, 255)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}"


def gen_amount(rng: random.Random) -> float:
    # Long-tail distribution: most txns small, a few large. Clamp to sane
    # Razorpay limits (<= 15 lakh INR per txn).
    r = rng.random()
    if r < 0.60:
        return round(rng.uniform(50, 1500), 2)
    if r < 0.90:
        return round(rng.uniform(1500, 15000), 2)
    if r < 0.99:
        return round(rng.uniform(15000, 100000), 2)
    return round(rng.uniform(100000, 1_500_000), 2)


def gen_timestamp(rng: random.Random, days: int) -> datetime:
    """Random moment within the last `days` days."""
    now = datetime.now(timezone.utc)
    secs_ago = rng.randint(0, days * 24 * 3600)
    return now - timedelta(seconds=secs_ago)


def gen_transactions(
    db, count: int, buyer_count: int, device_count: int, days: int,
    merchants: list[dict], rng: random.Random,
) -> int:
    if not merchants:
        raise RuntimeError("No active merchants found. Run seed_data.sql first.")

    inserted = 0
    BATCH = 1000
    buyer_indices = list(range(SEED_BUYER_COUNT + 1, SEED_BUYER_COUNT + 1 + buyer_count))
    device_indices = list(range(SEED_DEVICE_COUNT + 1, SEED_DEVICE_COUNT + 1 + device_count))
    merchant_ids = [m["merchant_id"] for m in merchants]

    # Make generation idempotent even though the legacy schema has no UNIQUE(txn_id).
    # This also prevents a rerun from creating another physical row with the same ID.
    requested_ids = [txn_id(i) for i in range(SEED_TXN_COUNT + 1, SEED_TXN_COUNT + 1 + count)]
    existing = db.execute(
        text("SELECT txn_id FROM transactions WHERE txn_id = ANY(:tids)"),
        {"tids": requested_ids},
    ).scalars().all()
    existing_ids = set(existing)

    indices = [i for i in range(SEED_TXN_COUNT + 1, SEED_TXN_COUNT + 1 + count)
               if txn_id(i) not in existing_ids]
    skipped = count - len(indices)
    if skipped:
        print(f"[generate_transactions] Skipping {skipped} existing transaction IDs.")

    for batch in chunked(indices, BATCH):
        params = []
        for i in batch:
            b_idx = rng.choice(buyer_indices)
            d_idx = rng.choice(device_indices)
            m_id = rng.choice(merchant_ids)
            city_tuple = rng.choices(INDIAN_CITIES, weights=CITY_WEIGHTS, k=1)[0]
            city, _, _ = city_tuple
            method = rng.choices(PAYMENT_METHODS, weights=PAYMENT_METHOD_WEIGHTS, k=1)[0]
            params.append({
                "tid": txn_id(i),
                "ts": gen_timestamp(rng, days).isoformat(),
                "mid": m_id,
                "bid": buyer_id(b_idx),
                "did": device_id(d_idx),
                "amt": gen_amount(rng),
                "method": method,
                "bin": gen_card_bin(rng) if method == "card" else None,
                "ip": gen_ipv4(rng),
                "city": city,
            })
        db.execute(
            text("""
                INSERT INTO transactions
                    (txn_id, created_at, merchant_id, buyer_id, device_id,
                     amount, currency, method, card_bin, ip_address, city)
                VALUES
                    (:tid, :ts, :mid, :bid, :did,
                     :amt, 'INR', :method, :bin, :ip, :city)
                ON CONFLICT (txn_id, created_at) DO NOTHING
            """),
            params,
        )
        inserted += len(params)
        log_progress("  txns     ", min(inserted, count), count)
    return inserted


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate S.P.A.R.K. synthetic transactions.")
    p.add_argument("--buyers", type=int, default=2000, help="Number of buyers to seed (default: 2000)")
    p.add_argument("--devices", type=int, default=2400, help="Number of devices to seed (default: 2400)")
    p.add_argument("--transactions", type=int, default=25_000, help="Number of transactions (default: 25000)")
    p.add_argument("--days", type=int, default=60, help="Spread transactions over the last N days (default: 60)")
    p.add_argument("--seed", type=int, default=DEFAULT_SEED, help="RNG seed for reproducibility")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    rng = make_rng(args.seed)

    print(f"[generate_transactions] seed={args.seed} "
          f"buyers={args.buyers} devices={args.devices} txns={args.transactions} days={args.days}")

    with session_scope() as db:
        merchants = fetch_merchants(db)
        if not merchants:
            print("[generate_transactions] ERROR: no active merchants. Run `psql -f db/seed/seed_data.sql` first.")
            sys.exit(1)
        print(f"[generate_transactions] Found {len(merchants)} active merchant(s)")

        print("[generate_transactions] Seeding buyers...")
        seed_buyers(db, args.buyers, rng)
        print("\n[generate_transactions] Seeding devices...")
        seed_devices(db, args.devices, rng)
        print("\n[generate_transactions] Linking buyers to devices...")
        link_buyers_to_devices(db, args.buyers, args.devices, rng)
        print("\n[generate_transactions] Generating transactions...")
        n = gen_transactions(db, args.transactions, args.buyers, args.devices, args.days, merchants, rng)
        print(f"\n[generate_transactions] Done. {n} transaction rows queued.")

    # After commit, report table counts.
    with session_scope() as db:
        for tbl in ("buyers", "devices", "buyer_device_link", "transactions"):
            c = db.execute(text(f"SELECT count(*) FROM {tbl}")).scalar()
            print(f"  {tbl:<22} {c:>8}")


if __name__ == "__main__":
    main()
