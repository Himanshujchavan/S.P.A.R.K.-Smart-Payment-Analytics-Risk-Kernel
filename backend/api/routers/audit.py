# api/routers/audit.py
# FastAPI router for compliance audit logs

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.core.db import get_db

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("", response_model=List[Dict[str, Any]], status_code=status.HTTP_200_OK)
@router.get("/", response_model=List[Dict[str, Any]], status_code=status.HTTP_200_OK)
def list_audit(
    action: Optional[str] = Query(None, description="Filter by decision action: allow, challenge, block"),
    user_id: Optional[str] = Query(None, description="Filter by actor user"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    start: Optional[str] = Query(None, description="Start ISO timestamp"),
    end: Optional[str] = Query(None, description="End ISO timestamp"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Retrieve immutable audit trail entries with filtering for compliance review."""
    if db is None:
        return []

    try:
        filters = []
        params = {"skip": skip, "limit": limit}

        if action:
            filters.append("action = :action")
            params["action"] = action
        if user_id:
            filters.append("actor_user_id = :user_id")
            params["user_id"] = user_id
        if event_type:
            filters.append("event_type = :event_type")
            params["event_type"] = event_type
        if start:
            filters.append("created_at >= :start")
            params["start"] = start
        if end:
            filters.append("created_at <= :end")
            params["end"] = end

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        query_sql = f"""
            SELECT audit_id, txn_id, actor_user_id, event_type, action, triggered_by, reasoning, created_at
            FROM audit_log
            {where_clause}
            ORDER BY created_at DESC
            OFFSET :skip LIMIT :limit
        """
        rows = db.execute(text(query_sql), params).mappings().fetchall()
        result = []
        for r in rows:
            result.append({
                "id": str(r["audit_id"]),
                "audit_id": str(r["audit_id"]),
                "transactionId": str(r["txn_id"]) if r["txn_id"] else None,
                "txn_id": str(r["txn_id"]) if r["txn_id"] else None,
                "actorUserId": str(r["actor_user_id"]) if r["actor_user_id"] else None,
                "eventType": r["event_type"],
                "action": r["action"],
                "triggeredBy": r["triggered_by"],
                "triggered_by": r["triggered_by"],
                "reasoning": r["reasoning"],
                "timestamp": r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else str(r["created_at"]),
                "created_at": r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else str(r["created_at"]),
            })
        return result
    except Exception as e:
        return []


@router.get("/{audit_id}", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
def get_audit(audit_id: str, db: Session = Depends(get_db)):
    """Retrieve a single audit log entry by audit ID."""
    if db is None:
        return {"audit_id": audit_id}

    try:
        query = text("""
            SELECT audit_id, txn_id, actor_user_id, event_type, action, triggered_by, reasoning, created_at
            FROM audit_log
            WHERE audit_id = :aid
            LIMIT 1
        """)
        r = db.execute(query, {"aid": audit_id}).mappings().first()
        if not r:
            return {"audit_id": audit_id}
        return {
            "id": str(r["audit_id"]),
            "audit_id": str(r["audit_id"]),
            "transactionId": str(r["txn_id"]) if r["txn_id"] else None,
            "action": r["action"],
            "triggeredBy": r["triggered_by"],
            "reasoning": r["reasoning"],
            "timestamp": r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else str(r["created_at"]),
        }
    except Exception:
        return {"audit_id": audit_id}
