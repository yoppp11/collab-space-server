"""
Pytest fixtures for users app tests.

Note: Common fixtures (user, admin_user, etc.) are defined in the root conftest.py
and are available to all tests.
"""
import pytest
from django.contrib.auth import get_user_model

User = get_user_model()

# App-specific fixtures can be added here if needed
