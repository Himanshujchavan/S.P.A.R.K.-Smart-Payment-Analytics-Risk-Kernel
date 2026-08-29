from typing import Dict
from api.schemas.auth import TokenResponse
from api.core.config import settings

def score_transaction(db, payload: Dict) -> TokenResponse:
    """Score a transaction payload and return risk decision response stub."""
    return TokenResponse(
        access_token="dummy_access_token",
        refresh_token="dummy_refresh_token",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
