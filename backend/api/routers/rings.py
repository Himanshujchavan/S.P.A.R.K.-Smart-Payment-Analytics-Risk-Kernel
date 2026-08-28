from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from api.core.db import get_db
from api.services.ring_service import list_rings, get_ring
from typing import List, Dict

router = APIRouter(prefix="/rings", tags=["Rings"])

@router.get("/", response_model=List[Dict], status_code=status.HTTP_200_OK)
def list_rings_endpoint(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Placeholder endpoint to list abuse rings."""
    return list_rings(db, skip=skip, limit=limit)

@router.get("/{ring_id}", response_model=Dict, status_code=status.HTTP_200_OK)
def get_ring_endpoint(ring_id: str, db: Session = Depends(get_db)):
    """Placeholder endpoint to get a specific ring."""
    return get_ring(db, ring_id)
