# ingestion/kafka_producer.py
# Simulates Razorpay checkout traffic on a Kafka topic.
#
# In production this would be replaced by a real Razorpay webhook consumer
# that publishes each verified payment event to `spark.transactions`. For
# demo / load testing we replay rows from the `transactions` table at a
# configurable rate.
#
# Usage:
#   python -m ingestion.kafka_producer --rate 100
#   python -m ingestion.kafka_producer --rate 1000 --once
#
# Topic: spark.transactions
# Value format: JSON

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
import time
import uuid
from datetime import datetime, timezone

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from sqlalchemy import text  # noqa: E402

from api.core.config import settings  # noqa: E402
from api.core.db import SessionLocal  # noqa: E402

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [producer] %(levelname)s %(message)s")


TOPIC = "spark.transactions"


def _serialize(txn: dict) -> str:
    out = {}
    for k, v in txn.items():
        if isinstance(v, (datetime,)):
            out[k] = v.isoformat()
        elif isinstance(v, uuid.UUID):
            out[k] = str(v)
        else:
            out[k] = v
    return json.dumps(out, default=str)


def _build_producer():
    """Return a KafkaProducer or None if Kafka is unreachable.

    Falling back to None lets the rest of the system run without Kafka
    (the consumer will just see zero events). Real deployments should
    treat a missing broker as fatal.
    """
    try:
        from kafka import KafkaProducer
        producer = KafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS.split(","),
            value_serializer=lambda v: v.encode("utf-8") if isinstance(v, str) else v,
            linger_ms=20,
            acks="all",
            retries=3,
        )
        return producer
    except Exception as e:
        logger.error(f"Kafka producer init failed: {e}")
        return None


def stream_transactions(rate_per_sec: int, max_txns: int | None, rng: random.Random) -> int:
    """Read transactions from the DB and emit them to Kafka at `rate_per_sec`.

    If max_txns is set, stop after that many (useful for tests).
    Returns the number of messages sent.
    """
    producer = _build_producer()
    if producer is None:
        logger.error("Cannot produce without a Kafka broker. Aborting.")
        return 0

    sent = 0
    db = SessionLocal()
    try:
        q = text("""
            SELECT
                txn_id, created_at, merchant_id, buyer_id, device_id,
                amount, currency, method, card_bin, ip_address, city
            FROM transactions
            ORDER BY created_at
        """)
        rows = db.execute(q).mappings().fetchall()
    finally:
        db.close()

    if not rows:
        logger.warning("No transactions in DB to stream. Run generate_transactions first.")
        return 0

    if max_txns is not None and max_txns < len(rows):
        rows = rng.sample(rows, max_txns)

    interval = 1.0 / max(1, rate_per_sec)
    logger.info(f"Streaming {len(rows)} txns at {rate_per_sec} msg/s (interval={interval*1000:.1f}ms)")

    futures = []
    try:
        for txn in rows:
            payload = _serialize(dict(txn))
            futures.append(producer.send(TOPIC, value=payload))
            sent += 1
            if sent % 1000 == 0:
                logger.info(f"  queued {sent}/{len(rows)}")
                producer.flush()
            if max_txns is None and rate_per_sec > 0:
                time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("Interrupted; flushing and exiting.")
    finally:
        producer.flush()
        producer.close()

    logger.info(f"Done. Sent {sent} messages.")
    return sent


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stream transactions to Kafka")
    p.add_argument("--rate", type=int, default=100, help="Messages per second (default: 100)")
    p.add_argument("--max", type=int, default=None, help="Max txns to send (default: all)")
    p.add_argument("--once", action="store_true", help="Send all txns as fast as possible, then exit")
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    rate = 10**9 if args.once else args.rate
    rng = random.Random(args.seed)
    stream_transactions(rate, args.max, rng)


if __name__ == "__main__":
    main()
