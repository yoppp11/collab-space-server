"""
Core Utility Functions
"""
import hashlib
import json
from typing import Any, Dict, Optional
from django.core.cache import cache
from django.conf import settings
import redis


def generate_cache_key(*args, prefix: str = '') -> str:
    """
    Generate a consistent cache key from arguments.
    """
    key_data = ':'.join(str(arg) for arg in args)
    if prefix:
        return f"{prefix}:{hashlib.md5(key_data.encode()).hexdigest()}"
    return hashlib.md5(key_data.encode()).hexdigest()


def get_redis_client():
    """Get a Redis client for direct operations."""
    return redis.Redis(
        host=settings.CHANNEL_LAYERS['default']['CONFIG']['hosts'][0][0],
        port=settings.CHANNEL_LAYERS['default']['CONFIG']['hosts'][0][1],
        decode_responses=True
    )


class CacheService:
    """
    Service for managing cached data with consistent patterns.
    """
    
    @staticmethod
    def get_or_set(
        key: str,
        fetch_func,
        timeout: int = 300,
        version: Optional[int] = None
    ) -> Any:
        """
        Get value from cache or fetch and cache it.
        """
        value = cache.get(key, version=version)
        if value is None:
            value = fetch_func()
            cache.set(key, value, timeout, version=version)
        return value

    @staticmethod
    def invalidate_pattern(pattern: str):
        """
        Invalidate all keys matching a pattern.
        Uses Redis SCAN for efficiency.
        """
        redis_client = get_redis_client()
        cursor = 0
        while True:
            cursor, keys = redis_client.scan(
                cursor=cursor,
                match=f"*{pattern}*",
                count=100
            )
            if keys:
                redis_client.delete(*keys)
            if cursor == 0:
                break

    @staticmethod
    def get_document_cache_key(document_id: str) -> str:
        """Generate cache key for document data."""
        return f"doc:{document_id}"

    @staticmethod
    def get_presence_cache_key(document_id: str) -> str:
        """Generate cache key for presence data."""
        return f"presence:{document_id}"

    @staticmethod
    def get_user_session_key(user_id: str) -> str:
        """Generate cache key for user session data."""
        return f"user_session:{user_id}"


class IdempotencyService:
    """
    Service for ensuring idempotent operations.
    Prevents duplicate processing of WebSocket messages.
    """
    
    IDEMPOTENCY_TTL = 60 * 5  # 5 minutes
    
    @classmethod
    def is_duplicate(cls, message_id: str) -> bool:
        """
        Check if a message has already been processed.
        """
        key = f"idempotency:{message_id}"
        return cache.get(key) is not None

    @classmethod
    def mark_processed(cls, message_id: str):
        """
        Mark a message as processed.
        """
        key = f"idempotency:{message_id}"
        cache.set(key, True, cls.IDEMPOTENCY_TTL)

    @classmethod
    def process_once(cls, message_id: str, process_func, *args, **kwargs):
        """
        Process a message only if it hasn't been processed before.
        Returns (result, was_processed) tuple.
        """
        if cls.is_duplicate(message_id):
            return None, False
        
        result = process_func(*args, **kwargs)
        cls.mark_processed(message_id)
        return result, True


def deep_merge(base: Dict, updates: Dict) -> Dict:
    """
    Deep merge two dictionaries.
    """
    result = base.copy()
    for key, value in updates.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def calculate_content_hash(content: Any) -> str:
    """
    Calculate a hash of content for comparison purposes.
    """
    if isinstance(content, dict):
        content = json.dumps(content, sort_keys=True)
    return hashlib.sha256(str(content).encode()).hexdigest()[:16]
