# api/core/deps.py
# Security dependencies for FastAPI routes (token validation, current user lookup, role checks)

from typing import Callable, Sequence
from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import text
from sqlalchemy.orm import Session
from api.core.db import get_db
from api.core.redis_client import is_token_blacklisted
from api.core.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
):
    """FastAPI security dependency validating JWT access token and returning current user DB model."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(token)
        user_id_str: str = payload.get("sub")
        token_type: str = payload.get("type")
        jti: str = payload.get("jti")

        if not user_id_str or token_type != "access":
            raise credentials_exception

        if jti and is_token_blacklisted(jti):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_id = UUID(user_id_str)
    except Exception:
        raise credentials_exception

    # Query DB for user
    query = text(
        "SELECT user_id, merchant_id, email, phone, full_name, role, failed_login_attempts, locked_until FROM users WHERE user_id = :user_id"
    )
    user = db.execute(query, {"user_id": user_id}).mappings().first()

    if user is None:
        raise credentials_exception

    return user


def get_current_merchant_user(current_user=Depends(get_current_user)):
    """Ensure current user belongs to a merchant organization."""
    if not current_user["merchant_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted: user is not assigned to a merchant organization.",
        )
    return current_user


def require_role(*allowed_roles: str) -> Callable:
    """Dependency factory checking user role against allowed roles."""

    def role_checker(current_user=Depends(get_current_user)):
        user_role = current_user["role"]
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Action forbidden. Requires one of roles: {list(allowed_roles)}",
            )
        return current_user

    return role_checker
