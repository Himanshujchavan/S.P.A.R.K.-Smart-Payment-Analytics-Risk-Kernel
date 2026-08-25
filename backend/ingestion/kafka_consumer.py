# ingestion/kafka_consumer.py
# Kafka consumer that writes incoming transactions to TimescaleDB and
# updates Redis velocity aggregates.
#
# Topic: spark.transactions
# Message format: JSON (matches the producer's serialization)
#
# Behavior:
#   - Consume one message at a time (group_id=spark-ingestion)
#   - Insert into the `transactions` table (ON CONFLICT DO NOTHING for
#     replay safety)
#   - Hand the message to feature_updater.update_for_transaction() so
#     subsequent /score calls have fresh velocity aggregates
#   - On DB error: log + commit offset (so we don't block on poison
#     messages). Move poison messages to a dead-letter table later.
#
# Usage:
#   python -m ingestion.kafka_consumer
#
# Graceful shutdown: SIGTERM/SIGINT flushes the consumer group cleanly.

from __future__ import annotations

import json
import logging
import os
import signal
import sys
import time
import uuid
from typing import Optional

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from sqlalchemy import text  # noqa: E402

from api.core.config import settings  # noqa: E402
from api.core.db import SessionLocal  # noqa: E402
from ingestion.feature_updater import update_for_transaction  # noqa: E402

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [consumer] %(levelname)s %(message)s")


TOPIC = "spark.transactions"
GROUP_ID = "spark-ingestion"


# ---------------------------------------------------------------------------
# DB write
# ---------------------------------------------------------------------------
def _insert_transaction(txn: dict) -> bool:
    """Insert one transaction row. Returns True on success, False on
    duplicate (ON CONFLICT). Raises on real DB errors.
    """
    db = SessionLocal()
    try:
        db.execute(
            text("""
                INSERT INTO transactions
                    (txn_id, created_at, merchant_id, buyer_id, device_id,
                     amount, currency, method, card_bin, ip_address, city)
                VALUES
                    (:tid, :ts, :mid, :bid, :did,
                     :amt, :cur, :method, :bin, :ip, :city)
                ON CONFLICT (txn_id, created_at) DO NOTHING
            """),
            {
                "tid": txn.get("txn_id") or uuid.uuid4(),
                "ts": _to_dt(txn.get("created_at")),
                "mid": txn.get("merchant_id"),
                "bid": txn.get("buyer_id"),
                "did": txn.get("device_id"),
                "amt": float(txn.get("amount", 0.0)),
                "cur": txn.get("currency", "INR"),
                "method": txn.get("method", "upi"),
                "bin": txn.get("card_bin"),
                "ip": txn.get("ip_address"),
                "city": txn.get("city"),
            },
        )
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"DB insert failed for txn {txn.get('txn_id')}: {e}")
        raise
    finally:
        db.close()


def _to_dt(value) -> Optional[object]:
    """Parse various incoming timestamp formats into a Python datetime."""
    if value is None:
        return None
    if hasattr(value, "isoformat"):  # already a datetime
        return value
    from datetime import datetime
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# Consumer loop
# ---------------------------------------------------------------------------
_stop_requested = False


def _handle_signal(signum, frame):
    global _stop_requested
    logger.info(f"Signal {signum} received — graceful shutdown starting")
    _stop_requested = True


def _build_consumer():
    try:
        from kafka import KafkaConsumer
        return KafkaConsumer(
            TOPIC,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS.split(","),
            group_id=GROUP_ID,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            enable_auto_commit=False,
            auto_offset_reset="earliest",
            consumer_timeout_ms=1000,
        )
    except Exception as e:
        logger.error(f"Kafka consumer init failed: {e}")
        return None


def run() -> int:
    """Consume until SIGTERM/SIGINT. Returns the number of messages processed."""
    consumer = _build_consumer()
    if consumer is None:
        logger.error("Cannot start without a Kafka broker. Aborting.")
        return 0

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    processed = 0
    failed = 0
    logger.info(f"Consuming from {TOPIC} (group={GROUP_ID})")
    try:
        while not _stop_requested:
            # Poll in batches with a small timeout to allow signal handling
            for msg in consumer:
                if _stop_requested:
                    break
                try:
                    txn = msg.value
                    if not isinstance(txn, dict):
                        logger.warning(f"Skipping non-dict message: {type(txn)}")
                        continue
                    _insert_transaction(txn)
                    update_for_transaction(txn)
                    processed += 1
                    if processed % 500 == 0:
                        logger.info(f"  processed {processed} (failed: {failed})")
                except Exception as e:
                    failed += 1
                    logger.error(f"  message failed: {e} (offset={msg.offset})")
                finally:
                    # Commit per-message: at-least-once. Idempotency comes
                    # from ON CONFLICT DO NOTHING in insert.
                    consumer.commit()
            # consumer_timeout_ms elapsed, loop again to allow signal handling
    finally:
        try:
            consumer.close()
        except Exception:
            pass
        logger.info(f"Shutdown complete. processed={processed} failed={failed}")
    return processed


def main() -> None:
    run()


if __name__ == "__main__":
    main()
