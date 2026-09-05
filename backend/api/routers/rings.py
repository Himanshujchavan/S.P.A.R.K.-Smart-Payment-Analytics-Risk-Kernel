# api/routers/rings.py
# FastAPI router for abuse rings and ring graph visualization

from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.core.db import get_db
from api.services.ring_service import get_ring, get_ring_graph, list_rings

router = APIRouter(prefix="/rings", tags=["Rings"])


@router.get("", response_model=List[Dict[str, Any]], status_code=status.HTTP_200_OK)
@router.get("/", response_model=List[Dict[str, Any]], status_code=status.HTTP_200_OK)
def list_rings_endpoint(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List detected abuse rings with status, member counts, and density."""
    return list_rings(db, skip=skip, limit=limit)


@router.get("/{ring_id}", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
def get_ring_endpoint(ring_id: str, db: Session = Depends(get_db)):
    """Retrieve details for a specific abuse ring."""
    res = get_ring(db, ring_id)
    if not res:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ring not found")
    return res


@router.get("/{ring_id}/graph", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
def get_ring_graph_endpoint(ring_id: str, db: Session = Depends(get_db)):
    """Retrieve node-edge topology for SVG graph visualization."""
    return get_ring_graph(db, ring_id)
