"""
URL Configuration for Real-time Collaboration Platform
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API v1 endpoints
    path('api/', include([
        path('auth/', include('apps.users.urls')),
        path('workspaces/', include('apps.workspaces.urls')),
        path('documents/', include('apps.documents.urls')),
        path('notifications/', include('apps.notifications.urls')),
    ])),
]

# Debug toolbar URLs (development only)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    
    try:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass
