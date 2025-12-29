"""
WebSocket Routing Configuration
"""
from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('ws/documents/<uuid:document_id>/', consumers.DocumentConsumer.as_asgi()),
    path('ws/notifications/', consumers.NotificationConsumer.as_asgi()),
]
