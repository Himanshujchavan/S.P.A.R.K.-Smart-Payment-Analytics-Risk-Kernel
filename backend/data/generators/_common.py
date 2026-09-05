# data/generators/_common.py
# Shared utilities for S.P.A.R.K. synthetic data generators.
#
# All three generators (transactions, rings, labels) need the same:
#   - Deterministic seeding (so a re-run reproduces the same dataset)
#   - DB session + connection handling
#   - Idempotent inserts (ON CONFLICT DO NOTHING where possible)
#   - Realistic Indian payment context (Razorpay test-mode shapes)
#
# Keep this file small and dependency-light — generators run as standalone
# scripts invoked by the training pipeline, not as part of the API.

from __future__ import annotations

import os
import random
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

# Make `api.*` importable when the script is run from anywhere.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(os.path.dirname(_THIS_DIR))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from api.core.db import SessionLocal  # noqa: E402


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------
DEFAULT_SEED = 20240825


def make_rng(seed: int = DEFAULT_SEED) -> random.Random:
    """Return a seeded Python `random.Random` for reproducible runs."""
    return random.Random(seed)


# ---------------------------------------------------------------------------
# Razorpay test-mode constants
# ---------------------------------------------------------------------------
PAYMENT_METHODS = ["upi", "card", "netbanking", "wallet", "emandate"]
PAYMENT_METHOD_WEIGHTS = [0.55, 0.30, 0.10, 0.04, 0.01]

INDIAN_CITIES = [
    ("Bengaluru", 12.9716, 77.5946),
    ("Mumbai", 19.0760, 72.8777),
    ("Delhi", 28.6139, 77.2090),
    ("Pune", 18.5204, 73.8567),
    ("Hyderabad", 17.3850, 78.4867),
    ("Chennai", 13.0827, 80.2707),
    ("Kolkata", 22.5726, 88.3639),
    ("Ahmedabad", 23.0225, 72.5714),
]
CITY_WEIGHTS = [0.22, 0.20, 0.16, 0.12, 0.10, 0.08, 0.07, 0.05]

OS_CHOICES = [("Android", "Chrome Mobile"), ("iOS", "Mobile Safari"),
              ("Windows", "Chrome"), ("macOS", "Safari"), ("Android", "Firefox")]
OS_WEIGHTS = [0.45, 0.30, 0.15, 0.07, 0.03]

DEVICE_OS_BROWSER = OS_CHOICES
DEVICE_OS_WEIGHTS = OS_WEIGHTS

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan",
    "Krishna", "Ishaan", "Ananya", "Aadhya", "Saanvi", "Aanya", "Pari", "Diya",
    "Aaradhya", "Anika", "Myra", "Ira", "Riya", "Priya", "Neha", "Pooja",
]
LAST_NAMES = [
    "Sharma", "Verma", "Patel", "Gupta", "Iyer", "Reddy", "Nair", "Khan",
    "Singh", "Kumar", "Das", "Roy", "Mehta", "Joshi", "Kapoor", "Bose",
    "Rao", "Pillai", "Menon", "Chatterjee",
]


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------
@contextmanager
def session_scope() -> Iterator[Session]:
    """Context manager that yields a SessionLocal and commits/rolls back."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def fetch_merchants(db: Session) -> list[dict]:
    """Return all active merchants as a list of dicts."""
    rows = db.execute(
        text("SELECT merchant_id, name FROM merchants WHERE status = 'active'")
    ).mappings().fetchall()
    return [dict(r) for r in rows]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def chunked(iterable, size: int):
    """Yield successive `size`-element chunks from `iterable`."""
    chunk = []
    for item in iterable:
        chunk.append(item)
        if len(chunk) >= size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def log_progress(prefix: str, done: int, total: int) -> None:
    if total <= 0:
        return
    pct = 100.0 * done / total
    bar_len = 30
    filled = int(bar_len * done / total)
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f"\r{prefix} |{bar}| {done}/{total} ({pct:5.1f}%)", end="", flush=True)
    if done >= total:
        print()
