"""
Unit tests for Core utilities.
"""
import pytest
from unittest.mock import patch, MagicMock
from apps.core.utils import (
    generate_cache_key,
    CacheService,
    IdempotencyService,
    deep_merge,
    calculate_content_hash
)

pytestmark = pytest.mark.django_db


class TestGenerateCacheKey:
    """Tests for generate_cache_key function."""
    
    def test_generate_cache_key_simple(self):
        """Test generating a cache key with simple arguments."""
        key = generate_cache_key('arg1', 'arg2')
        
        assert key is not None
        assert len(key) == 32  # MD5 hex length
    
    def test_generate_cache_key_with_prefix(self):
        """Test generating a cache key with prefix."""
        key = generate_cache_key('arg1', 'arg2', prefix='test')
        
        assert key.startswith('test:')
    
    def test_generate_cache_key_consistency(self):
        """Test that same arguments produce same key."""
        key1 = generate_cache_key('arg1', 'arg2')
        key2 = generate_cache_key('arg1', 'arg2')
        
        assert key1 == key2
    
    def test_generate_cache_key_different_args(self):
        """Test that different arguments produce different keys."""
        key1 = generate_cache_key('arg1', 'arg2')
        key2 = generate_cache_key('arg1', 'arg3')
        
        assert key1 != key2


class TestCacheService:
    """Tests for CacheService class."""
    
    def test_get_or_set_cache_miss(self):
        """Test get_or_set when value is not in cache."""
        fetch_calls = []
        
        def fetch_func():
            fetch_calls.append(1)
            return 'test_value'
        
        result = CacheService.get_or_set('test_key', fetch_func, timeout=60)
        
        assert result == 'test_value'
        assert len(fetch_calls) == 1
    
    def test_get_or_set_cache_hit(self):
        """Test get_or_set when value is in cache."""
        from django.core.cache import cache
        
        cache.set('cached_key', 'cached_value', 60)
        
        fetch_calls = []
        def fetch_func():
            fetch_calls.append(1)
            return 'new_value'
        
        result = CacheService.get_or_set('cached_key', fetch_func, timeout=60)
        
        assert result == 'cached_value'
        assert len(fetch_calls) == 0  # fetch_func should not be called
    
    @patch('apps.core.utils.get_redis_client')
    def test_invalidate_pattern(self, mock_get_redis):
        """Test invalidating cache keys by pattern."""
        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis
        
        # Simulate scan returning some keys then finishing
        mock_redis.scan.side_effect = [
            (100, ['key1', 'key2']),
            (0, [])
        ]
        
        CacheService.invalidate_pattern('test_pattern')
        
        mock_redis.scan.assert_called()
        mock_redis.delete.assert_called_with('key1', 'key2')
    
    def test_get_document_cache_key(self):
        """Test generating document cache key."""
        key = CacheService.get_document_cache_key('doc-123')
        
        assert key == 'doc:doc-123'
    
    def test_get_presence_cache_key(self):
        """Test generating presence cache key."""
        key = CacheService.get_presence_cache_key('doc-123')
        
        assert key == 'presence:doc-123'
    
    def test_get_user_session_key(self):
        """Test generating user session cache key."""
        key = CacheService.get_user_session_key('user-123')
        
        assert key == 'user_session:user-123'


class TestIdempotencyService:
    """Tests for IdempotencyService class."""
    
    def test_is_duplicate_false(self):
        """Test is_duplicate returns False for new message."""
        from django.core.cache import cache
        cache.delete('idempotency:new-message-id')
        
        result = IdempotencyService.is_duplicate('new-message-id')
        
        assert result is False
    
    def test_is_duplicate_true(self):
        """Test is_duplicate returns True for processed message."""
        from django.core.cache import cache
        cache.set('idempotency:processed-message-id', True, 300)
        
        result = IdempotencyService.is_duplicate('processed-message-id')
        
        assert result is True
    
    def test_mark_processed(self):
        """Test marking a message as processed."""
        from django.core.cache import cache
        
        IdempotencyService.mark_processed('test-message-id')
        
        assert cache.get('idempotency:test-message-id') is True
    
    def test_process_once_first_time(self):
        """Test process_once executes function first time."""
        from django.core.cache import cache
        cache.delete('idempotency:first-time-msg')
        
        def my_func(x, y):
            return x + y
        
        result, was_processed = IdempotencyService.process_once(
            'first-time-msg',
            my_func,
            2, 3
        )
        
        assert result == 5
        assert was_processed is True
    
    def test_process_once_duplicate(self):
        """Test process_once skips duplicate."""
        from django.core.cache import cache
        cache.set('idempotency:duplicate-msg', True, 300)
        
        call_count = []
        def my_func():
            call_count.append(1)
            return 'result'
        
        result, was_processed = IdempotencyService.process_once(
            'duplicate-msg',
            my_func
        )
        
        assert result is None
        assert was_processed is False
        assert len(call_count) == 0


class TestDeepMerge:
    """Tests for deep_merge function."""
    
    def test_deep_merge_simple(self):
        """Test deep merge with simple dictionaries."""
        base = {'a': 1, 'b': 2}
        updates = {'b': 3, 'c': 4}
        
        result = deep_merge(base, updates)
        
        assert result == {'a': 1, 'b': 3, 'c': 4}
    
    def test_deep_merge_nested(self):
        """Test deep merge with nested dictionaries."""
        base = {
            'a': 1,
            'nested': {'x': 1, 'y': 2}
        }
        updates = {
            'nested': {'y': 3, 'z': 4}
        }
        
        result = deep_merge(base, updates)
        
        assert result == {
            'a': 1,
            'nested': {'x': 1, 'y': 3, 'z': 4}
        }
    
    def test_deep_merge_overwrites_non_dict(self):
        """Test deep merge overwrites non-dict with dict."""
        base = {'a': 'string'}
        updates = {'a': {'nested': 'value'}}
        
        result = deep_merge(base, updates)
        
        assert result == {'a': {'nested': 'value'}}
    
    def test_deep_merge_does_not_modify_base(self):
        """Test deep merge does not modify the base dictionary."""
        base = {'a': 1}
        updates = {'b': 2}
        
        deep_merge(base, updates)
        
        assert base == {'a': 1}


class TestCalculateContentHash:
    """Tests for calculate_content_hash function."""
    
    def test_hash_string(self):
        """Test hashing a string."""
        hash1 = calculate_content_hash('test content')
        hash2 = calculate_content_hash('test content')
        
        assert hash1 == hash2
        assert len(hash1) == 16  # Truncated SHA256
    
    def test_hash_dict(self):
        """Test hashing a dictionary."""
        hash1 = calculate_content_hash({'a': 1, 'b': 2})
        hash2 = calculate_content_hash({'b': 2, 'a': 1})
        
        # Should be same regardless of key order due to sort_keys
        assert hash1 == hash2
    
    def test_hash_different_content(self):
        """Test that different content produces different hashes."""
        hash1 = calculate_content_hash('content1')
        hash2 = calculate_content_hash('content2')
        
        assert hash1 != hash2
