"""
Local Development Settings
"""
from .base import *

DEBUG = True

# Development-specific apps
INSTALLED_APPS += [
    'debug_toolbar',
]

# Add debug toolbar to middleware (prepend to existing MIDDLEWARE from base.py)
MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')

INTERNAL_IPS = ['127.0.0.1', 'localhost']

CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000'
]

ALLOWED_HOSTS = [
    ".up.railway.app",
    "localhost",
    "127.0.0.1",
]

# Use console email backend for development
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Disable caching in development
CACHES['default']['OPTIONS']['IGNORE_EXCEPTIONS'] = True
