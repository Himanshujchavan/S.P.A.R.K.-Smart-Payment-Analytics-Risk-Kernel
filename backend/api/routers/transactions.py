from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from api.core.db import get_db
from api.services.transaction_service import get_transaction, list_transactions, create_transaction
from typing import List, Dict
router=APIRouter(prefix="/transactions",tags=["Transactions"])
@router.get("/{txn_id}",response_model=Dict)
def read_transaction(txn_id:str,db:Session=Depends(get_db)):
    result=get_transaction(db,txn_id)
    if result is None: raise HTTPException(status_code=404,detail="Transaction not found")
    return result
@router.get("/",response_model=List[Dict])
def read_transactions(skip:int=0,limit:int=100,db:Session=Depends(get_db)):
    if skip<0 or limit<1 or limit>200: raise HTTPException(status_code=400,detail="Invalid pagination")
    return list_transactions(db,skip=skip,limit=limit)
@router.post("/",response_model=Dict,status_code=201)
def create_txn(payload:Dict,db:Session=Depends(get_db)):
    try:return create_transaction(db,payload)
    except ValueError as e: raise HTTPException(status_code=400,detail=str(e))
