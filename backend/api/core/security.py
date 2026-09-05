# api/core/security.py
# Password hashing, JWT token generation, verification, and invite token creation

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from api.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

PINNED_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def hash_token(token: str) -> str:
    """Compute SHA-256 hash of a refresh token for session DB storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(
    data: Dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """Create a signed JWT access token with a unique JTI claim."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    jti = str(uuid.uuid4())
    to_encode.update({"exp": expire, "iat": now, "jti": jti, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=PINNED_ALGORITHM)
    return encoded_jwt


def create_refresh_token(
    data: Dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """Create a signed JWT refresh token."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    jti = str(uuid.uuid4())
    to_encode.update({"exp": expire, "iat": now, "jti": jti, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=PINNED_ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT token using hardcoded pinned algorithm (HS256)."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[PINNED_ALGORITHM])
        return payload
    except JWTError as e:
        raise ValueError(f"Invalid or expired token: {str(e)}")


def create_invite_token(merchant_id: str, role: str, expires_hours: int = 48) -> str:
    """Create a signed invite token for adding new users to an existing merchant."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(hours=expires_hours)
    payload = {
        "merchant_id": str(merchant_id),
        "role": role,
        "type": "invite",
        "exp": expire,
        "iat": now,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=PINNED_ALGORITHM)


def decode_invite_token(token: str) -> Dict[str, Any]:
    """Decode and validate an invite token."""
    payload = decode_token(token)
    if payload.get("type") != "invite":
        raise ValueError("Provided token is not a valid invite token.")
    return payload
