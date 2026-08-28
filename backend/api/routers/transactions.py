from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from api.core.db import get_db
from api.services.transaction_service import get_transaction, list_transactions, create_transaction
from typing import List, Dict

router = APIRouter(prefix="/transactions", tags=["Transactions"])

@router.get("/{txn_id}", response_model=Dict, status_code=status.HTTP_200_OK)
def read_transaction(txn_id: str, db: Session = Depends(get_db)):
    """Retrieve a single transaction by ID (placeholder)."""
    return get_transaction(db, txn_id)

@router.get("/", response_model=List[Dict], status_code=status.HTTP_200_OK)
def read_transactions(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List transactions with pagination (placeholder)."""
    return list_transactions(db, skip=skip, limit=limit)

@router.post("/", response_model=Dict, status_code=status.HTTP_201_CREATED)
def create_txn(payload: Dict, db: Session = Depends(get_db)):
    """Create a new transaction (placeholder)."""
    return create_transaction(db, payload)
