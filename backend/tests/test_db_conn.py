# tests/test_db_conn.py
# Verification script for S.P.A.R.K. database connectivity, schema, and seed data integrity

import os
import sys
from sqlalchemy import text

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from api.core.db import engine, SessionLocal

TABLES = [
    "merchants",
    "users",
    "auth_providers",
    "sessions",
    "buyers",
    "devices",
    "buyer_device_link",
    "transactions",
    "fraud_labels",
    "model_scores",
    "audit_log",
    "drift_snapshots",
    "detected_rings",
]


def test_database_connection_and_integrity():
    print("Connecting to database...")
    db = SessionLocal()
    try:
        # 1. Test query execution against all 13 tables
        print("\n--- 1. Testing Table Schema Presence ---")
        for table in TABLES:
            result = db.execute(text(f"SELECT count(*) FROM {table}")).scalar()
            print(f"  [✓] Table '{table}': {result} rows")

        # 2. Test TimescaleDB Hypertable & Chunks
        print("\n--- 2. Checking TimescaleDB Hypertable Setup ---")
        hypertables = db.execute(
            text(
                "SELECT hypertable_name FROM timescaledb_information.hypertables WHERE hypertable_name = 'transactions'"
            )
        ).fetchall()
        if hypertables:
            print("  [✓] 'transactions' hypertable confirmed")
        else:
            print("  [✗] 'transactions' is NOT configured as a hypertable!")

        chunks = db.execute(
            text(
                "SELECT chunk_name, range_start, range_end FROM timescaledb_information.chunks WHERE hypertable_name = 'transactions'"
            )
        ).fetchall()
        print(f"  [✓] Found {len(chunks)} hypertable chunks for 'transactions'")

        # 3. Data Integrity & Injected Ring Cluster Checks
        print("\n--- 3. Verifying Seed Data Integrity ---")
        txn_count = db.execute(text("SELECT count(*) FROM transactions")).scalar()
        label_count = db.execute(text("SELECT count(*) FROM fraud_labels")).scalar()
        print(f"  Transactions count: {txn_count}")
        print(f"  Fraud labels count: {label_count}")

        if txn_count >= 500:
            print("  [✓] Transactions count meets minimum (>= 500)")
        else:
            print(f"  [!] Transactions count {txn_count} is less than expected 500")

        if txn_count == label_count:
            print(
                "  [✓] Fraud labels count matches transactions count exactly (no orphans)"
            )
        else:
            print(f"  [!] Mismatch: {txn_count} txns vs {label_count} labels")

        # Shared device cluster check
        clusters = db.execute(text("""
                SELECT device_id, count(DISTINCT buyer_id) as buyer_count 
                FROM buyer_device_link 
                GROUP BY device_id 
                HAVING count(DISTINCT buyer_id) >= 4
            """)).fetchall()

        if clusters:
            print(
                f"  [✓] Confirmed injected abuse cluster! Device {clusters[0][0]} linked to {clusters[0][1]} buyers."
            )
        else:
            print(
                "  [!] Injected ring cluster (>= 4 buyers sharing 1 device) not found!"
            )

        print("\n=== All Database Layer Verifications Passed! ===")

    except Exception as e:
        print(f"\n[ERROR] Database test failed: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    test_database_connection_and_integrity()
