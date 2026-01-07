"""
Redis Cache Utilities for Performance Optimization

Provides decorators and helper functions for caching frequently accessed data.
"""
from functools import wraps
from typing import Optional, Callable, Any, Union
import hashlib
import json
import logging

from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)

# Cache timeout constants (in seconds)
CACHE_TIMEOUT_SHORT = 60  # 1 minute
CACHE_TIMEOUT_MEDIUM = 300  # 5 minutes
CACHE_TIMEOUT_LONG = 3600  # 1 hour
CACHE_TIMEOUT_DAY = 86400  # 24 hours

# Cache key prefixes
CACHE_PREFIX_USER = "user"
CACHE_PREFIX_WORKSPACE = "workspace"
CACHE_PREFIX_DOCUMENT = "document"
CACHE_PREFIX_BOARD = "board"
CACHE_PREFIX_PERMISSIONS = "perms"


def make_cache_key(*args, prefix: str = "") -> str:
    """
    Generate a cache key from arguments.
    
    Args:
        *args: Values to include in the key
        prefix: Optional prefix for the key
        
    Returns:
        A unique cache key string
    """
    key_parts = [str(arg) for arg in args if arg is not None]
    key_data = ":".join(key_parts)
    
    # If key is too long, hash it
    if len(key_data) > 200:
        key_hash = hashlib.md5(key_data.encode()).hexdigest()
        key_data = key_hash
    
    if prefix:
        return f"{prefix}:{key_data}"
    return key_data


def cached(
    timeout: int = CACHE_TIMEOUT_MEDIUM,
    key_prefix: str = "",
    key_func: Optional[Callable] = None,
    cache_none: bool = False
):
    """
    Decorator to cache function results in Redis.
    
    Args:
        timeout: Cache timeout in seconds
        key_prefix: Prefix for cache key
        key_func: Optional function to generate cache key from args
        cache_none: Whether to cache None results
        
    Usage:
        @cached(timeout=300, key_prefix="user_profile")
        def get_user_profile(user_id):
            return User.objects.get(id=user_id)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default key generation
                func_name = func.__name__
                all_args = list(args) + [f"{k}={v}" for k, v in sorted(kwargs.items())]
                cache_key = make_cache_key(func_name, *all_args, prefix=key_prefix)
            
            # Try to get from cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_value
            
            # Check for cached None (special marker)
            if cache_none:
                none_marker = cache.get(f"{cache_key}:none")
                if none_marker:
                    logger.debug(f"Cache hit (None): {cache_key}")
                    return None
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Cache result
            if result is not None:
                cache.set(cache_key, result, timeout)
                logger.debug(f"Cache set: {cache_key}")
            elif cache_none:
                cache.set(f"{cache_key}:none", True, timeout)
            
            return result
        
        # Add cache invalidation method
        wrapper.invalidate = lambda *args, **kwargs: invalidate_cached(
            func, key_prefix, key_func, *args, **kwargs
        )
        wrapper.cache_key_prefix = key_prefix
        
        return wrapper
    return decorator


def invalidate_cached(func, key_prefix, key_func, *args, **kwargs):
    """
    Invalidate cached result for specific arguments.
    """
    if key_func:
        cache_key = key_func(*args, **kwargs)
    else:
        func_name = func.__name__
        all_args = list(args) + [f"{k}={v}" for k, v in sorted(kwargs.items())]
        cache_key = make_cache_key(func_name, *all_args, prefix=key_prefix)
    
    cache.delete(cache_key)
    cache.delete(f"{cache_key}:none")
    logger.debug(f"Cache invalidated: {cache_key}")


class CacheManager:
    """
    Centralized cache management for the application.
    """
    
    @staticmethod
    def get_user_cache_key(user_id: str, suffix: str = "") -> str:
        """Generate cache key for user-related data."""
        key = f"{CACHE_PREFIX_USER}:{user_id}"
        if suffix:
            key = f"{key}:{suffix}"
        return key
    
    @staticmethod
    def get_workspace_cache_key(workspace_id: str, suffix: str = "") -> str:
        """Generate cache key for workspace-related data."""
        key = f"{CACHE_PREFIX_WORKSPACE}:{workspace_id}"
        if suffix:
            key = f"{key}:{suffix}"
        return key
    
    @staticmethod
    def get_document_cache_key(document_id: str, suffix: str = "") -> str:
        """Generate cache key for document-related data."""
        key = f"{CACHE_PREFIX_DOCUMENT}:{document_id}"
        if suffix:
            key = f"{key}:{suffix}"
        return key
    
    @staticmethod
    def get_board_cache_key(board_id: str, suffix: str = "") -> str:
        """Generate cache key for board-related data."""
        key = f"{CACHE_PREFIX_BOARD}:{board_id}"
        if suffix:
            key = f"{key}:{suffix}"
        return key
    
    # =========================================================================
    # User caching methods
    # =========================================================================
    
    @classmethod
    def cache_user_workspaces(cls, user_id: str, workspaces_data: Any, timeout: int = CACHE_TIMEOUT_MEDIUM):
        """Cache user's workspaces list."""
        key = cls.get_user_cache_key(user_id, "workspaces")
        cache.set(key, workspaces_data, timeout)
    
    @classmethod
    def get_user_workspaces(cls, user_id: str) -> Optional[Any]:
        """Get cached user's workspaces list."""
        key = cls.get_user_cache_key(user_id, "workspaces")
        return cache.get(key)
    
    @classmethod
    def invalidate_user_workspaces(cls, user_id: str):
        """Invalidate user's workspaces cache."""
        key = cls.get_user_cache_key(user_id, "workspaces")
        cache.delete(key)
    
    @classmethod
    def cache_user_profile(cls, user_id: str, profile_data: Any, timeout: int = CACHE_TIMEOUT_LONG):
        """Cache user profile data."""
        key = cls.get_user_cache_key(user_id, "profile")
        cache.set(key, profile_data, timeout)
    
    @classmethod
    def get_user_profile(cls, user_id: str) -> Optional[Any]:
        """Get cached user profile."""
        key = cls.get_user_cache_key(user_id, "profile")
        return cache.get(key)
    
    @classmethod
    def invalidate_user_profile(cls, user_id: str):
        """Invalidate user profile cache."""
        key = cls.get_user_cache_key(user_id, "profile")
        cache.delete(key)
    
    # =========================================================================
    # Workspace caching methods
    # =========================================================================
    
    @classmethod
    def cache_workspace_members(cls, workspace_id: str, members_data: Any, timeout: int = CACHE_TIMEOUT_MEDIUM):
        """Cache workspace members list."""
        key = cls.get_workspace_cache_key(workspace_id, "members")
        cache.set(key, members_data, timeout)
    
    @classmethod
    def get_workspace_members(cls, workspace_id: str) -> Optional[Any]:
        """Get cached workspace members."""
        key = cls.get_workspace_cache_key(workspace_id, "members")
        return cache.get(key)
    
    @classmethod
    def invalidate_workspace_members(cls, workspace_id: str):
        """Invalidate workspace members cache."""
        key = cls.get_workspace_cache_key(workspace_id, "members")
        cache.delete(key)
    
    @classmethod
    def cache_workspace_boards(cls, workspace_id: str, boards_data: Any, timeout: int = CACHE_TIMEOUT_MEDIUM):
        """Cache workspace boards list."""
        key = cls.get_workspace_cache_key(workspace_id, "boards")
        cache.set(key, boards_data, timeout)
    
    @classmethod
    def get_workspace_boards(cls, workspace_id: str) -> Optional[Any]:
        """Get cached workspace boards."""
        key = cls.get_workspace_cache_key(workspace_id, "boards")
        return cache.get(key)
    
    @classmethod
    def invalidate_workspace_boards(cls, workspace_id: str):
        """Invalidate workspace boards cache."""
        key = cls.get_workspace_cache_key(workspace_id, "boards")
        cache.delete(key)
    
    @classmethod
    def cache_workspace_detail(cls, workspace_id: str, data: Any, timeout: int = CACHE_TIMEOUT_MEDIUM):
        """Cache workspace detail."""
        key = cls.get_workspace_cache_key(workspace_id, "detail")
        cache.set(key, data, timeout)
    
    @classmethod
    def get_workspace_detail(cls, workspace_id: str) -> Optional[Any]:
        """Get cached workspace detail."""
        key = cls.get_workspace_cache_key(workspace_id, "detail")
        return cache.get(key)
    
    @classmethod
    def invalidate_workspace_detail(cls, workspace_id: str):
        """Invalidate workspace detail cache."""
        key = cls.get_workspace_cache_key(workspace_id, "detail")
        cache.delete(key)
    
    # =========================================================================
    # Document caching methods
    # =========================================================================
    
    @classmethod
    def cache_document_detail(cls, document_id: str, data: Any, timeout: int = CACHE_TIMEOUT_MEDIUM):
        """Cache document detail."""
        key = cls.get_document_cache_key(document_id, "detail")
        cache.set(key, data, timeout)
    
    @classmethod
    def get_document_detail(cls, document_id: str) -> Optional[Any]:
        """Get cached document detail."""
        key = cls.get_document_cache_key(document_id, "detail")
        return cache.get(key)
    
    @classmethod
    def invalidate_document_detail(cls, document_id: str):
        """Invalidate document detail cache."""
        key = cls.get_document_cache_key(document_id, "detail")
        cache.delete(key)
    
    @classmethod
    def cache_document_blocks(cls, document_id: str, blocks_data: Any, timeout: int = CACHE_TIMEOUT_SHORT):
        """Cache document blocks."""
        key = cls.get_document_cache_key(document_id, "blocks")
        cache.set(key, blocks_data, timeout)
    
    @classmethod
    def get_document_blocks(cls, document_id: str) -> Optional[Any]:
        """Get cached document blocks."""
        key = cls.get_document_cache_key(document_id, "blocks")
        return cache.get(key)
    
    @classmethod
    def invalidate_document_blocks(cls, document_id: str):
        """Invalidate document blocks cache."""
        key = cls.get_document_cache_key(document_id, "blocks")
        cache.delete(key)
    
    # =========================================================================
    # Board caching methods
    # =========================================================================
    
    @classmethod
    def cache_board_detail(cls, board_id: str, data: Any, timeout: int = CACHE_TIMEOUT_MEDIUM):
        """Cache board detail with lists and cards."""
        key = cls.get_board_cache_key(board_id, "detail")
        cache.set(key, data, timeout)
    
    @classmethod
    def get_board_detail(cls, board_id: str) -> Optional[Any]:
        """Get cached board detail."""
        key = cls.get_board_cache_key(board_id, "detail")
        return cache.get(key)
    
    @classmethod
    def invalidate_board_detail(cls, board_id: str):
        """Invalidate board detail cache."""
        key = cls.get_board_cache_key(board_id, "detail")
        cache.delete(key)
    
    @classmethod
    def cache_board_cards(cls, board_id: str, list_id: str, cards_data: Any, timeout: int = CACHE_TIMEOUT_SHORT):
        """Cache board list cards."""
        key = cls.get_board_cache_key(board_id, f"list:{list_id}:cards")
        cache.set(key, cards_data, timeout)
    
    @classmethod
    def get_board_cards(cls, board_id: str, list_id: str) -> Optional[Any]:
        """Get cached board list cards."""
        key = cls.get_board_cache_key(board_id, f"list:{list_id}:cards")
        return cache.get(key)
    
    @classmethod
    def invalidate_board_cards(cls, board_id: str, list_id: str = None):
        """Invalidate board cards cache."""
        if list_id:
            key = cls.get_board_cache_key(board_id, f"list:{list_id}:cards")
            cache.delete(key)
        else:
            # Invalidate all lists - use pattern delete
            pattern = cls.get_board_cache_key(board_id, "list:*:cards")
            cache.delete_pattern(pattern)
    
    # =========================================================================
    # Permission caching methods
    # =========================================================================
    
    @classmethod
    def cache_user_workspace_role(
        cls, user_id: str, workspace_id: str, role: str, timeout: int = CACHE_TIMEOUT_MEDIUM
    ):
        """Cache user's role in a workspace."""
        key = f"{CACHE_PREFIX_PERMISSIONS}:user:{user_id}:workspace:{workspace_id}:role"
        cache.set(key, role, timeout)
    
    @classmethod
    def get_user_workspace_role(cls, user_id: str, workspace_id: str) -> Optional[str]:
        """Get cached user's workspace role."""
        key = f"{CACHE_PREFIX_PERMISSIONS}:user:{user_id}:workspace:{workspace_id}:role"
        return cache.get(key)
    
    @classmethod
    def invalidate_user_workspace_role(cls, user_id: str, workspace_id: str):
        """Invalidate user's workspace role cache."""
        key = f"{CACHE_PREFIX_PERMISSIONS}:user:{user_id}:workspace:{workspace_id}:role"
        cache.delete(key)
    
    # =========================================================================
    # Bulk invalidation methods
    # =========================================================================
    
    @classmethod
    def invalidate_workspace_all(cls, workspace_id: str):
        """Invalidate all cache related to a workspace."""
        cls.invalidate_workspace_detail(workspace_id)
        cls.invalidate_workspace_members(workspace_id)
        cls.invalidate_workspace_boards(workspace_id)
    
    @classmethod
    def invalidate_user_all(cls, user_id: str):
        """Invalidate all cache related to a user."""
        cls.invalidate_user_profile(user_id)
        cls.invalidate_user_workspaces(user_id)
    
    @classmethod
    def invalidate_board_all(cls, board_id: str):
        """Invalidate all cache related to a board."""
        cls.invalidate_board_detail(board_id)
    
    @classmethod
    def invalidate_document_all(cls, document_id: str):
        """Invalidate all cache related to a document."""
        cls.invalidate_document_detail(document_id)
        cls.invalidate_document_blocks(document_id)


# Convenience function for cache statistics
def get_cache_stats() -> dict:
    """
    Get cache statistics (if using Redis backend).
    """
    try:
        from django_redis import get_redis_connection
        redis_conn = get_redis_connection("default")
        info = redis_conn.info()
        return {
            "used_memory": info.get("used_memory_human"),
            "connected_clients": info.get("connected_clients"),
            "total_connections_received": info.get("total_connections_received"),
            "keyspace_hits": info.get("keyspace_hits"),
            "keyspace_misses": info.get("keyspace_misses"),
            "hit_rate": (
                info.get("keyspace_hits", 0) / 
                max(info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0), 1) * 100
            ),
        }
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        return {}


def clear_all_cache():
    """
    Clear all cache (use with caution).
    """
    try:
        cache.clear()
        logger.info("All cache cleared")
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
