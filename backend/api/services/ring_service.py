# api/services/ring_service.py
# Abuse ring retrieval and graph topology service

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def list_rings(db: Optional[Session], skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    """Query detected abuse rings with pagination and density metrics."""
    if db is None:
        return []

    try:
        query = text("""
            SELECT ring_id, member_count, density_score, shared_attribute,
                   shared_value, status, flagged_amount, account_ids, detected_at
            FROM detected_rings
            ORDER BY detected_at DESC
            OFFSET :skip LIMIT :limit
        """)
        rows = db.execute(query, {"skip": skip, "limit": limit}).mappings().fetchall()
        result = []
        for r in rows:
            acc_ids = r["account_ids"]
            if isinstance(acc_ids, str):
                try:
                    acc_ids = json.loads(acc_ids)
                except Exception:
                    acc_ids = []
            result.append({
                "ring_id": str(r["ring_id"]),
                "id": str(r["ring_id"]),
                "member_count": r["member_count"],
                "memberCount": r["member_count"],
                "density": float(r["density_score"]),
                "density_score": float(r["density_score"]),
                "shared_attribute": r["shared_attribute"],
                "sharedAttribute": r["shared_attribute"],
                "shared_value": r["shared_value"],
                "sharedValue": r["shared_value"],
                "status": r["status"],
                "flagged_amount": float(r["flagged_amount"]),
                "flaggedAmount": float(r["flagged_amount"]),
                "account_ids": acc_ids,
                "accountIds": acc_ids,
                "detected_at": r["detected_at"].isoformat() if hasattr(r["detected_at"], "isoformat") else str(r["detected_at"]),
                "detectedAt": r["detected_at"].isoformat() if hasattr(r["detected_at"], "isoformat") else str(r["detected_at"]),
            })
        return result
    except Exception as e:
        logger.warning(f"Error listing rings from DB: {e}")
        return []


def get_ring(db: Optional[Session], ring_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve details for a single detected ring."""
    if db is None:
        return {"ring_id": ring_id, "status": "active", "account_ids": []}

    try:
        query = text("""
            SELECT ring_id, member_count, density_score, shared_attribute,
                   shared_value, status, flagged_amount, account_ids, detected_at
            FROM detected_rings
            WHERE ring_id = :rid
            LIMIT 1
        """)
        r = db.execute(query, {"rid": ring_id}).mappings().first()
        if not r:
            return None
        acc_ids = r["account_ids"]
        if isinstance(acc_ids, str):
            try:
                acc_ids = json.loads(acc_ids)
            except Exception:
                acc_ids = []
        return {
            "ring_id": str(r["ring_id"]),
            "id": str(r["ring_id"]),
            "member_count": r["member_count"],
            "density": float(r["density_score"]),
            "shared_attribute": r["shared_attribute"],
            "shared_value": r["shared_value"],
            "status": r["status"],
            "flagged_amount": float(r["flagged_amount"]),
            "account_ids": acc_ids,
            "detected_at": r["detected_at"].isoformat() if hasattr(r["detected_at"], "isoformat") else str(r["detected_at"]),
        }
    except Exception as e:
        logger.warning(f"Error getting ring {ring_id}: {e}")
        return {"ring_id": ring_id, "status": "active", "account_ids": []}


def get_ring_graph(db: Optional[Session], ring_id: str) -> Dict[str, Any]:
    """Build the node-link graph payload for SVG visualization in the frontend.

    Nodes: central shared attribute entity + member buyer nodes.
    Edges: shared link connecting buyer accounts to shared attribute entity.
    """
    ring = get_ring(db, ring_id)
    if not ring:
        return {"nodes": [], "edges": []}

    shared_attr = ring.get("shared_attribute", "device_fingerprint")
    shared_val = ring.get("shared_value", "shared_entity")
    account_ids = ring.get("account_ids", [])

    nodes = [
        {
            "id": "hub",
            "label": f"{shared_attr}: {shared_val}",
            "type": "shared",
            "group": 1,
        }
    ]
    edges = []

    for idx, acc in enumerate(account_ids):
        node_id = f"buyer_{acc}"
        nodes.append({
            "id": node_id,
            "label": f"Buyer {acc}",
            "type": "buyer",
            "group": 2,
        })
        edges.append({
            "source": node_id,
            "target": "hub",
            "relation": shared_attr,
        })

    return {
        "ring_id": ring_id,
        "nodes": nodes,
        "edges": edges,
        "density": ring.get("density", 0.5),
        "member_count": len(account_ids),
    }
