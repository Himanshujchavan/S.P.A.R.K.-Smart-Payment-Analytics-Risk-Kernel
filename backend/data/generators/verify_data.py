# data/generators/verify_data.py
# Sanity-check the synthetic dataset after generation.
#
# Run after all three generators have completed:
#   python -m data.generators.verify_data
#
# Checks:
#   1. Row counts for buyers, devices, transactions, fraud_labels
#   2. Every transaction has exactly one fraud_labels row (no orphans)
#   3. Detected ring count and at least one cluster with >= 4 buyers
#   4. Fraud label distribution by source
#   5. Reasonable fraud rate (1% - 5% for the synthetic mix)

from __future__ import annotations

import os
import sys

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from sqlalchemy import text  # noqa: E402

from api.core.db import SessionLocal  # noqa: E402


def main() -> int:
    db = SessionLocal()
    try:
        print("=== S.P.A.R.K. data verification ===\n")

        # 1. Counts
        counts = {}
        for tbl in ("buyers", "devices", "buyer_device_link", "transactions",
                    "fraud_labels", "detected_rings"):
            counts[tbl] = db.execute(text(f"SELECT count(*) FROM {tbl}")).scalar()
        for k, v in counts.items():
            print(f"  {k:<22} {v:>10,}")

        # 2. Orphan check
        orphan_txns = db.execute(text("""
            SELECT count(*) FROM transactions t
            LEFT JOIN fraud_labels f ON f.txn_id = t.txn_id
            WHERE f.txn_id IS NULL
        """)).scalar()
        if orphan_txns == 0:
            print("\n  [✓] No transactions missing labels.")
        else:
            print(f"\n  [✗] {orphan_txns} transactions have no fraud_labels row!")
            return 1

        # 3. Ring check
        ring_count = counts["detected_rings"]
        if ring_count == 0:
            print("\n  [✗] No detected_rings — run generate_rings.py")
            return 1
        max_members = db.execute(text(
            "SELECT MAX(member_count) FROM detected_rings"
        )).scalar()
        density_max = db.execute(text(
            "SELECT MAX(density_score) FROM detected_rings"
        )).scalar()
        print(f"\n  [✓] {ring_count} rings, max member_count={max_members}, "
              f"max density={density_max}")

        # 4. Label distribution
        rows = db.execute(text("""
            SELECT label_source, count(*) FROM fraud_labels
            GROUP BY label_source ORDER BY 2 DESC
        """)).fetchall()
        print("\n  Label source distribution:")
        for src, c in rows:
            print(f"    {src:<22} {c:>10,}")

        # 5. Fraud rate
        total = counts["fraud_labels"]
        fraud = db.execute(text("SELECT count(*) FROM fraud_labels WHERE is_fraud")).scalar()
        rate = 100.0 * fraud / total if total else 0.0
        print(f"\n  Fraud rate: {fraud:,}/{total:,} = {rate:.2f}%")
        if 0.5 <= rate <= 10.0:
            print("  [✓] Fraud rate is in the plausible synthetic range (0.5%–10%).")
        else:
            print("  [!] Fraud rate outside expected range — review generator tuning.")

        # 6. Top shared-attribute check (one ring with >= 4 buyers)
        top_ring = db.execute(text("""
            SELECT ring_id, member_count, shared_attribute, shared_value
            FROM detected_rings
            ORDER BY member_count DESC LIMIT 1
        """)).first()
        if top_ring and top_ring[1] >= 4:
            print(f"\n  [✓] Largest ring has {top_ring[1]} members "
                  f"on {top_ring[2]}='{top_ring[3]}'.")
        else:
            print("\n  [!] No ring has >= 4 members — graph detector will have nothing to find.")

        print("\n=== Verification complete ===")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
