# api/core/redis_client.py
# Redis client connection, token blacklisting, and SlowAPI rate limiter setup

import logging
from typing import Optional
import redis
from slowapi import Limiter
from slowapi.util import get_remote_address
from api.core.config import settings

logger = logging.getLogger(__name__)

# Initialize SlowAPI limiter keyed on remote IP address
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

_redis_instance: Optional[redis.Redis] = None


def get_redis() -> Optional[redis.Redis]:
    """Retrieve shared Redis client instance. Handles connection fallbacks gracefully."""
    global _redis_instance
    if _redis_instance is None:
        try:
            _redis_instance = redis.Redis.from_url(
                settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2
            )
            _redis_instance.ping()
        except Exception as e:
            logger.warning(
                f"Redis connection failed ({e}). Proceeding in-memory/fallback mode."
            )
            return None
    return _redis_instance


# Fallback in-memory blacklist set for unit tests or environments without Redis active
_in_memory_blacklist = set()


def blacklist_token(jti: str, ttl_seconds: int) -> None:
    """Blacklist a JWT token JTI until its expiration time."""
    client = get_redis()
    if client:
        try:
            client.setex(f"blacklist:{jti}", max(1, ttl_seconds), "true")
            return
        except Exception as e:
            logger.error(f"Failed to set token blacklist in Redis: {e}")
    _in_memory_blacklist.add(jti)


def is_token_blacklisted(jti: str) -> bool:
    """Check if a JWT token JTI has been revoked/blacklisted."""
    if jti in _in_memory_blacklist:
        return True
    client = get_redis()
    if client:
        try:
            return bool(client.exists(f"blacklist:{jti}"))
        except Exception as e:
            logger.error(f"Failed to check token blacklist in Redis: {e}")
    return False
