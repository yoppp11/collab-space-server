"""
Core App URL Configuration
"""
from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Cache management endpoints
    path('cache/stats/', views.cache_stats, name='cache-stats'),
    path('cache/clear/', views.clear_cache, name='cache-clear'),
    path('cache/invalidate-mine/', views.invalidate_my_cache, name='cache-invalidate-mine'),
]
