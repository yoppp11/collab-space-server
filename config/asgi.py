"""
ASGI config for Real-time Collaboration Platform

Handles both HTTP and WebSocket connections.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')
django.setup()

from django.core.asgi import get_asgi_application

# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

# Try to set up channels, fall back to simple HTTP if it fails
try:
    from channels.routing import ProtocolTypeRouter, URLRouter
    from channels.security.websocket import AllowedHostsOriginValidator
    from apps.collaboration.middleware import JWTAuthMiddleware
    from apps.collaboration.routing import websocket_urlpatterns

    application = ProtocolTypeRouter({
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            JWTAuthMiddleware(
                URLRouter(websocket_urlpatterns)
            )
        ),
    })
except Exception as e:
    import logging
    logging.warning(f"Failed to initialize WebSocket support: {e}. Running HTTP only.")
    application = django_asgi_app
