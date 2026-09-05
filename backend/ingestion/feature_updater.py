# ingestion/feature_updater.py
# Maintains live velocity aggregates in Redis.
#
# Called by:
#   - ingestion/kafka_consumer.py after writing each new transaction to
#     TimescaleDB.
#   - Optionally: on a periodic replay to recover after Redis restart.
#
# Read by:
#   - api/services/feature_assembly.py at inference time, via
#     get_velocity_features(buyer_id, device_id, ip, bin_).
#
# Keys (all use TTL so stale keys expire automatically):
#   buyer:1h:<buyer_id>          sorted-set of txn timestamps → ZCARD
#   buyer:24h:<buyer_id>         sorted-set → ZCARD
#   buyer:7d:<buyer_id>          sorted-set → ZCARD
#   buyer:amt24h:<buyer_id>      sorted-set, score=amount, member=txn_id → sum
#   buyer:last:<buyer_id>        string, last-seen ISO timestamp
#   device:1h:<device_id>        sorted-set
#   device:24h:<device_id>       sorted-set
#   device:7d:<device_id>        sorted-set
#   device:buyers7d:<device_id>  set of distinct buyer_ids seen in 7d
#   device:first:<device_id>     string, ISO of first seen
#   ip:1h:<ip>                   sorted-set
#   ip:24h:<ip>                  sorted-set
#   ip:buyers24h:<ip>            set of distinct buyers
#   bin:1h:<bin>                 sorted-set
#   bin:24h:<bin>                sorted-set
#   bin:buyers24h:<bin>          set of distinct buyers
#   known:dev:<buyer>:<dev>      string "1" if buyer has used this device before
#
# All windows are sliding; the consumer prunes by removing entries
# older than the window from each sorted-set. For very high traffic you
# can swap the in-script pruning for a periodic cron.

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from typing import Optional

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from api.core.redis_client import get_redis  # noqa: E402

logger = logging.getLogger(__name__)


# Window lengths in seconds. Must match what feature_engineering expects.
WINDOW_1H = 3600
WINDOW_24H = 24 * 3600
WINDOW_7D = 7 * 24 * 3600


def _now_ts() -> float:
    return datetime.now(timezone.utc).timestamp()


def _prune_zset(client, key: str, min_score: float) -> None:
    """Remove members with score < min_score from a sorted-set."""
    try:
        client.zremrangebyscore(key, "-inf", min_score)
    except Exception as e:
        logger.warning(f"feature_updater: prune {key} failed: {e}")


def update_for_transaction(txn: dict) -> None:
    """Called immediately after a transaction is written to TimescaleDB.

    `txn` is the validated POST /score body (or Kafka message). Expected
    keys: txn_id, buyer_id, device_id, ip_address, card_bin, amount,
    created_at.
    """
    client = get_redis()
    if client is None:
        # Without Redis we cannot maintain aggregates. The /score endpoint
        # will fall back to the training-time-computed values via SQL.
        logger.debug("feature_updater: no Redis client; skipping update")
        return

    now = _now_ts()
    ts = now
    if txn.get("created_at"):
        try:
            dt = txn["created_at"]
            if isinstance(dt, str):
                # ISO 8601 with timezone
                dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
            ts = dt.timestamp()
        except Exception:
            ts = now

    amount = float(txn.get("amount", 0.0))
    buyer = txn.get("buyer_id")
    device = txn.get("device_id")
    ip = txn.get("ip_address")
    bin_ = txn.get("card_bin")
    txn_id = str(txn.get("txn_id", ""))

    if buyer:
        _update_buyer(client, buyer, txn_id, ts, amount, now)
    if device:
        _update_device(client, device, buyer, txn_id, ts, now)
    if ip:
        _update_ip(client, ip, buyer, txn_id, ts, now)
    if bin_:
        _update_bin(client, bin_, buyer, txn_id, ts, now)
    if buyer and device:
        client.set(f"known:dev:{buyer}:{device}", "1", ex=30 * 24 * 3600)


def _update_buyer(client, buyer: str, txn_id: str, ts: float, amount: float, now: float) -> None:
    # Sliding windows: append a member with score=ts.
    client.zadd(f"buyer:1h:{buyer}", {txn_id: ts})
    client.zadd(f"buyer:24h:{buyer}", {txn_id: ts})
    client.zadd(f"buyer:7d:{buyer}", {txn_id: ts})
    client.zadd(f"buyer:amt24h:{buyer}", {txn_id: amount}, gt=True)  # score = amount
    # Prune entries older than each window.
    _prune_zset(client, f"buyer:1h:{buyer}", now - WINDOW_1H)
    _prune_zset(client, f"buyer:24h:{buyer}", now - WINDOW_24H)
    _prune_zset(client, f"buyer:7d:{buyer}", now - WINDOW_7D)
    _prune_zset(client, f"buyer:amt24h:{buyer}", now - WINDOW_24H)
    # Set TTLs slightly above the window so unused buyers auto-expire.
    client.expire(f"buyer:1h:{buyer}", WINDOW_1H + 60)
    client.expire(f"buyer:24h:{buyer}", WINDOW_24H + 60)
    client.expire(f"buyer:7d:{buyer}", WINDOW_7D + 60)
    client.expire(f"buyer:amt24h:{buyer}", WINDOW_24H + 60)
    # Track last-seen for "seconds since last" feature.
    client.set(f"buyer:last:{buyer}", str(ts), ex=30 * 24 * 3600)


def _update_device(client, device: str, buyer: Optional[str], txn_id: str, ts: float, now: float) -> None:
    client.zadd(f"device:1h:{device}", {txn_id: ts})
    client.zadd(f"device:24h:{device}", {txn_id: ts})
    client.zadd(f"device:7d:{device}", {txn_id: ts})
    if buyer:
        client.sadd(f"device:buyers7d:{device}", str(buyer))
        client.expire(f"device:buyers7d:{device}", WINDOW_7D + 60)
    _prune_zset(client, f"device:1h:{device}", now - WINDOW_1H)
    _prune_zset(client, f"device:24h:{device}", now - WINDOW_24H)
    _prune_zset(client, f"device:7d:{device}", now - WINDOW_7D)
    client.expire(f"device:1h:{device}", WINDOW_1H + 60)
    client.expire(f"device:24h:{device}", WINDOW_24H + 60)
    client.expire(f"device:7d:{device}", WINDOW_7D + 60)
    # Track first-seen for device_age_days.
    if not client.exists(f"device:first:{device}"):
        client.set(f"device:first:{device}", str(ts), ex=30 * 24 * 3600)


def _update_ip(client, ip: str, buyer: Optional[str], txn_id: str, ts: float, now: float) -> None:
    client.zadd(f"ip:1h:{ip}", {txn_id: ts})
    client.zadd(f"ip:24h:{ip}", {txn_id: ts})
    if buyer:
        client.sadd(f"ip:buyers24h:{ip}", str(buyer))
        client.expire(f"ip:buyers24h:{ip}", WINDOW_24H + 60)
    _prune_zset(client, f"ip:1h:{ip}", now - WINDOW_1H)
    _prune_zset(client, f"ip:24h:{ip}", now - WINDOW_24H)
    client.expire(f"ip:1h:{ip}", WINDOW_1H + 60)
    client.expire(f"ip:24h:{ip}", WINDOW_24H + 60)


def _update_bin(client, bin_: str, buyer: Optional[str], txn_id: str, ts: float, now: float) -> None:
    client.zadd(f"bin:1h:{bin_}", {txn_id: ts})
    client.zadd(f"bin:24h:{bin_}", {txn_id: ts})
    if buyer:
        client.sadd(f"bin:buyers24h:{bin_}", str(buyer))
        client.expire(f"bin:buyers24h:{bin_}", WINDOW_24H + 60)
    _prune_zset(client, f"bin:1h:{bin_}", now - WINDOW_1H)
    _prune_zset(client, f"bin:24h:{bin_}", now - WINDOW_24H)
    client.expire(f"bin:1h:{bin_}", WINDOW_1H + 60)
    client.expire(f"bin:24h:{bin_}", WINDOW_24H + 60)


# ---------------------------------------------------------------------------
# Read path
# ---------------------------------------------------------------------------
def get_velocity_features(
    buyer_id: Optional[str],
    device_id: Optional[str],
    ip_address: Optional[str],
    card_bin: Optional[str],
) -> dict:
    """Read all velocity aggregates for an inference call. Returns a dict
    with the keys consumed by build_inference_features():
        buyer_1h, buyer_24h, buyer_7d, buyer_amount_24h,
        buyer_seconds_since_last,
        device_1h, device_24h, device_7d,
        device_distinct_buyers_7d, device_age_days,
        ip_1h, ip_24h, ip_distinct_buyers_24h,
        bin_1h, bin_24h, bin_distinct_buyers_24h,
        is_known_device_for_buyer, is_new_ip_for_buyer, is_new_card_bin_for_buyer,
    """
    out: dict = {
        "buyer_1h": 0, "buyer_24h": 0, "buyer_7d": 0,
        "buyer_amount_24h": 0.0, "buyer_seconds_since_last": 1e10,
        "device_1h": 0, "device_24h": 0, "device_7d": 0,
        "device_distinct_buyers_7d": 1, "device_age_days": 0.0,
        "ip_1h": 0, "ip_24h": 0, "ip_distinct_buyers_24h": 1,
        "bin_1h": 0, "bin_24h": 0, "bin_distinct_buyers_24h": 1,
        "is_known_device_for_buyer": 1,
        "is_new_ip_for_buyer": 0,
        "is_new_card_bin_for_buyer": 0,
    }
    client = get_redis()
    if client is None:
        return out

    now = _now_ts()

    if buyer_id:
        out["buyer_1h"] = _safe_zcard(client, f"buyer:1h:{buyer_id}", now, WINDOW_1H)
        out["buyer_24h"] = _safe_zcard(client, f"buyer:24h:{buyer_id}", now, WINDOW_24H)
        out["buyer_7d"] = _safe_zcard(client, f"buyer:7d:{buyer_id}", now, WINDOW_7D)
        # amount 24h sum
        try:
            client.zremrangebyscore(f"buyer:amt24h:{buyer_id}", "-inf", now - WINDOW_24H)
            members = client.zrange(f"buyer:amt24h:{buyer_id}", 0, -1, withscores=True)
            out["buyer_amount_24h"] = float(sum(s for _, s in members))
        except Exception:
            out["buyer_amount_24h"] = 0.0
        # seconds since last
        last_ts = client.get(f"buyer:last:{buyer_id}")
        if last_ts:
            try:
                out["buyer_seconds_since_last"] = max(0.0, now - float(last_ts))
            except ValueError:
                pass

    if device_id:
        out["device_1h"] = _safe_zcard(client, f"device:1h:{device_id}", now, WINDOW_1H)
        out["device_24h"] = _safe_zcard(client, f"device:24h:{device_id}", now, WINDOW_24H)
        out["device_7d"] = _safe_zcard(client, f"device:7d:{device_id}", now, WINDOW_7D)
        try:
            out["device_distinct_buyers_7d"] = max(1, client.scard(f"device:buyers7d:{device_id}") or 1)
        except Exception:
            pass
        first = client.get(f"device:first:{device_id}")
        if first:
            try:
                out["device_age_days"] = max(0.0, (now - float(first)) / 86400.0)
            except ValueError:
                pass
        if buyer_id:
            try:
                out["is_known_device_for_buyer"] = 1 if client.exists(
                    f"known:dev:{buyer_id}:{device_id}"
                ) else 0
            except Exception:
                pass

    if ip_address:
        out["ip_1h"] = _safe_zcard(client, f"ip:1h:{ip_address}", now, WINDOW_1H)
        out["ip_24h"] = _safe_zcard(client, f"ip:24h:{ip_address}", now, WINDOW_24H)
        try:
            out["ip_distinct_buyers_24h"] = max(1, client.scard(f"ip:buyers24h:{ip_address}") or 1)
        except Exception:
            pass
        # New IP for buyer? Use the device-known signal as a proxy:
        # we don't track every IP a buyer has used. A simpler proxy: if the
        # buyer has ANY prior txn (we have buyer:1h/24h/7d), and this IP
        # is appearing for the first time in the ip:24h set, it's "new".
        # We approximate this by checking the count of buyer txns vs ip txns.
        if buyer_id and out["buyer_24h"] > 0 and out["ip_24h"] <= 1:
            out["is_new_ip_for_buyer"] = 1

    if card_bin:
        out["bin_1h"] = _safe_zcard(client, f"bin:1h:{card_bin}", now, WINDOW_1H)
        out["bin_24h"] = _safe_zcard(client, f"bin:24h:{card_bin}", now, WINDOW_24H)
        try:
            out["bin_distinct_buyers_24h"] = max(1, client.scard(f"bin:buyers24h:{card_bin}") or 1)
        except Exception:
            pass
        if buyer_id and out["buyer_24h"] > 0 and out["bin_24h"] <= 1:
            out["is_new_card_bin_for_buyer"] = 1

    return out


def _safe_zcard(client, key: str, now: float, window: int) -> int:
    try:
        _prune_zset(client, key, now - window)
        return int(client.zcard(key) or 0)
    except Exception:
        return 0
