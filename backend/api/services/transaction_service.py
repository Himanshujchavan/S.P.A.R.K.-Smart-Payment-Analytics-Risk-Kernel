from typing import List, Dict

def get_transaction(db, txn_id: str) -> Dict:
    return {"txn_id": txn_id, "status": "processed"}

def list_transactions(db, skip: int = 0, limit: int = 100) -> List[Dict]:
    return []

def create_transaction(db, payload: Dict) -> Dict:
    return {"txn_id": "new_txn_id", "status": "created"}
