"""
Cache Middleware for API Response Optimization
"""
import hashlib
import logging
from django.core.cache import cache
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class CacheHeaderMiddleware(MiddlewareMixin):
    """
    Middleware to add cache control headers to API responses.
    """
    
    # Paths that should have caching headers
    CACHEABLE_PATHS = [
        '/api/workspaces/',
        '/api/documents/',
    ]
    
    # Paths that should never be cached
    NO_CACHE_PATHS = [
        '/api/auth/',
        '/api/notifications/',
        '/admin/',
    ]
    
    def process_response(self, request, response):
        """Add appropriate cache headers to responses."""
        path = request.path
        
        # Skip non-GET requests
        if request.method != 'GET':
            response['Cache-Control'] = 'no-store'
            return response
        
        # Check if path should not be cached
        for no_cache_path in self.NO_CACHE_PATHS:
            if path.startswith(no_cache_path):
                response['Cache-Control'] = 'no-store'
                return response
        
        # Add cache headers for cacheable paths
        for cacheable_path in self.CACHEABLE_PATHS:
            if path.startswith(cacheable_path):
                # Private cache (browser only, not CDN)
                # max-age for browser, must-revalidate after
                response['Cache-Control'] = 'private, max-age=60, must-revalidate'
                
                # Add ETag based on response content
                if response.content:
                    etag = hashlib.md5(response.content).hexdigest()
                    response['ETag'] = f'"{etag}"'
                
                return response
        
        return response


class APIResponseCacheMiddleware(MiddlewareMixin):
    """
    Middleware to cache entire API responses for read-heavy endpoints.
    Use with caution - only for endpoints that can tolerate stale data.
    """
    
    # Cache duration in seconds
    CACHE_DURATION = 30
    
    # Endpoints to cache responses for
    CACHED_ENDPOINTS = {
        # Pattern: cache_key_prefix
        '/api/workspaces/$': 'api:workspaces:list',  # List view
    }
    
    def _get_cache_key(self, request):
        """Generate a unique cache key for the request."""
        user_id = request.user.id if request.user.is_authenticated else 'anon'
        path = request.path
        query = request.GET.urlencode()
        
        key_data = f"{user_id}:{path}:{query}"
        return f"api_response:{hashlib.md5(key_data.encode()).hexdigest()}"
    
    def process_request(self, request):
        """Check for cached response."""
        # Only cache GET requests
        if request.method != 'GET':
            return None
        
        # Check if user is authenticated (for user-specific caching)
        if not request.user.is_authenticated:
            return None
        
        cache_key = self._get_cache_key(request)
        cached_response = cache.get(cache_key)
        
        if cached_response:
            logger.debug(f"API cache hit: {request.path}")
            from django.http import JsonResponse
            return JsonResponse(cached_response, safe=False)
        
        return None
    
    def process_response(self, request, response):
        """Cache successful GET responses."""
        # Only cache successful GET responses
        if request.method != 'GET':
            return response
        
        if response.status_code != 200:
            return response
        
        if not request.user.is_authenticated:
            return response
        
        # Only cache JSON responses
        content_type = response.get('Content-Type', '')
        if 'application/json' not in content_type:
            return response
        
        # Cache the response
        try:
            import json
            cache_key = self._get_cache_key(request)
            response_data = json.loads(response.content.decode('utf-8'))
            cache.set(cache_key, response_data, self.CACHE_DURATION)
            logger.debug(f"API cache set: {request.path}")
        except Exception as e:
            logger.warning(f"Failed to cache API response: {e}")
        
        return response
