# api/services/transaction_service.py
# Service for retrieving and managing transaction data for the risk dashboard.

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

def list_transactions(db: Session, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Retrieve a list of transactions joined with buyer, device, and scoring data.
    Matches the expected frontend Transaction schema.
    """
    try:
        query = text("""
            SELECT
                t.txn_id as id,
                t.amount,
                t.currency,
                t.method,
                t.card_bin as "cardBin",
                t.ip_address as "ipAddress",
                t.city,
                t.created_at as "scoredAt",
                b.name as "userName",
                b.buyer_id as "userId",
                d.fingerprint as "deviceFingerprint",
                ms.risk_score as "riskScore",
                ms.decision,
                ms.ring_id as "ringId",
                ms.counterfactual,
                ms.top_features as top_features
            FROM transactions t
            JOIN buyers b ON t.buyer_id = b.buyer_id
            LEFT JOIN devices d ON t.device_id = d.device_id
            LEFT JOIN LATERAL (SELECT * FROM model_scores ms0 WHERE ms0.txn_id = t.txn_id ORDER BY ms0.scored_at DESC LIMIT 1) ms ON TRUE
            ORDER BY t.created_at DESC
            OFFSET :skip LIMIT :limit
        """)
        rows = db.execute(query, {"skip": skip, "limit": limit}).mappings().all()

        result = []
        for r in rows:
            top_f = r["top_features"]
            if isinstance(top_f, str):
                try: top_f = json.loads(top_f)
                except: top_f = []

            result.append({
                "id": str(r["id"]),
                "amount": float(r["amount"]),
                "currency": r["currency"],
                "method": r["method"],
                "cardBin": r["cardBin"],
                "ipAddress": r["ipAddress"],
                "city": r["city"],
                "scoredAt": r["scoredAt"].isoformat() if hasattr(r["scoredAt"], "isoformat") else str(r["scoredAt"]),
                "userName": r["userName"],
                "userId": str(r["userId"]),
                "deviceFingerprint": r["deviceFingerprint"],
                "riskScore": float(r["riskScore"]) if r["riskScore"] is not None else 0.0,
                # model_scores is LEFT JOINed, so decision can be NULL for
                # transactions that haven't been scored yet (or whose score
                # row is missing) - normalize that to an explicit 'pending'
                # value instead of letting `null` leak to the frontend.
                "decision": r["decision"] or "pending",
                "ringId": str(r["ringId"]) if r["ringId"] else None,
                "counterfactual": r["counterfactual"],
                "topFeatures": top_f,
            })
        return result
    except Exception as e:
        logger.error(f"Error listing transactions: {e}")
        return []

def get_transaction(db: Session, txn_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve detailed data for a single transaction."""
    try:
        query = text("""
            SELECT
                t.txn_id as id,
                t.amount,
                t.currency,
                t.method,
                t.card_bin as "cardBin",
                t.ip_address as "ipAddress",
                t.city,
                t.created_at as "scoredAt",
                b.name as "userName",
                b.buyer_id as "userId",
                d.fingerprint as "deviceFingerprint",
                ms.risk_score as "riskScore",
                ms.decision,
                ms.ring_id as "ringId",
                ms.counterfactual,
                ms.top_features as top_features
            FROM transactions t
            JOIN buyers b ON t.buyer_id = b.buyer_id
            LEFT JOIN devices d ON t.device_id = d.device_id
            LEFT JOIN LATERAL (SELECT * FROM model_scores ms0 WHERE ms0.txn_id = t.txn_id ORDER BY ms0.scored_at DESC LIMIT 1) ms ON TRUE
            WHERE t.txn_id = :tid
        """)
        row = db.execute(query, {"tid": txn_id}).mappings().first()
        if not row:
            return None

        top_f = row["top_features"]
        if isinstance(top_f, str):
            try: top_f = json.loads(top_f)
            except: top_f = []

        return {
            "id": str(row["id"]),
            "amount": float(row["amount"]),
            "currency": row["currency"],
            "method": row["method"],
            "cardBin": row["cardBin"],
            "ipAddress": row["ipAddress"],
            "city": row["city"],
            "scoredAt": row["scoredAt"].isoformat() if hasattr(row["scoredAt"], "isoformat") else str(row["scoredAt"]),
            "userName": row["userName"],
            "userId": str(row["userId"]),
            "deviceFingerprint": row["deviceFingerprint"],
            "riskScore": float(row["riskScore"]) if row["riskScore"] is not None else 0.0,
            # Same LEFT JOIN caveat as list_transactions above.
            "decision": row["decision"] or "pending",
            "ringId": str(row["ringId"]) if row["ringId"] else None,
            "counterfactual": row["counterfactual"],
            "topFeatures": top_f,
        }
    except Exception as e:
        logger.error(f"Error getting transaction {txn_id}: {e}")
        return None

def create_transaction(db: Session, payload: Dict) -> Dict:
    """Persist a transaction record and return its identifier."""
    import uuid
    txn_id = str(payload.get("txn_id") or uuid.uuid4())
    buyer_id = payload.get("buyer_id")
    merchant_id = payload.get("merchant_id")
    if not buyer_id or not merchant_id:
        raise ValueError("buyer_id and merchant_id are required")
    db.execute(text("""INSERT INTO transactions (txn_id, merchant_id, buyer_id, device_id, amount, currency, method, card_bin, ip_address, city) VALUES (:txn_id,:merchant_id,:buyer_id,:device_id,:amount,:currency,:method,:card_bin,:ip_address,:city)"""), {"txn_id":txn_id,"merchant_id":merchant_id,"buyer_id":buyer_id,"device_id":payload.get("device_id"),"amount":payload.get("amount"),"currency":payload.get("currency","INR"),"method":payload.get("method"),"card_bin":payload.get("card_bin"),"ip_address":payload.get("ip_address"),"city":payload.get("city")})
    db.commit()
    return {"status":"created", "txn_id":txn_id}
