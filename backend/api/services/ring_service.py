from typing import List, Dict

def list_rings(db, skip: int = 0, limit: int = 100) -> List[Dict]:
    return []

def get_ring(db, ring_id: str) -> Dict:
    return {"ring_id": ring_id, "status": "active"}
