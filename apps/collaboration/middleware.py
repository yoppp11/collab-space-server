"""
JWT Authentication Middleware for WebSocket Connections

Authenticates WebSocket connections using JWT tokens.
"""
import logging
from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken, TokenError
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


@database_sync_to_async
def get_user_from_token(token_string):
    """
    Validate JWT token and return user.
    """
    try:
        token = AccessToken(token_string)
        user_id = token.payload.get('user_id')
        
        if not user_id:
            return AnonymousUser()
        
        user = User.objects.get(id=user_id, is_active=True)
        return user
    except (TokenError, User.DoesNotExist) as e:
        logger.warning(f"Token validation failed: {e}")
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """
    Custom middleware to authenticate WebSocket connections using JWT.
    
    Tokens can be passed via:
    1. Query parameter: ?token=<jwt>
    2. Subprotocol header (for some clients)
    """
    
    async def __call__(self, scope, receive, send):
        # Extract token from query string
        query_string = scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        token = query_params.get('token', [None])[0]
        
        # Fallback to subprotocol if no query param
        if not token and 'subprotocols' in scope:
            subprotocols = scope['subprotocols']
            for subprotocol in subprotocols:
                if subprotocol.startswith('token-'):
                    token = subprotocol[6:]  # Remove 'token-' prefix
                    break
        
        # Authenticate user
        if token:
            scope['user'] = await get_user_from_token(token)
        else:
            scope['user'] = AnonymousUser()
        
        return await super().__call__(scope, receive, send)


class RateLimitMiddleware(BaseMiddleware):
    """
    Rate limiting for WebSocket connections.
    """
    
    async def __call__(self, scope, receive, send):
        # TODO: Implement rate limiting logic
        # Can use Redis to track message rates per user/connection
        return await super().__call__(scope, receive, send)
