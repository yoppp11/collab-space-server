"""
Base test classes and utilities for all tests.
"""
import pytest
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APITestCase
from channels.testing import ChannelsLiveServerTestCase


class BaseTestCase(TestCase):
    """
    Base test case with common setup and utilities.
    """
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data once for the entire test class."""
        super().setUpTestData()
    
    def setUp(self):
        """Set up test environment before each test method."""
        super().setUp()
    
    def tearDown(self):
        """Clean up after each test method."""
        super().tearDown()


class BaseTransactionTestCase(TransactionTestCase):
    """
    Base transaction test case for tests requiring database transactions.
    """
    
    def setUp(self):
        """Set up test environment before each test method."""
        super().setUp()
    
    def tearDown(self):
        """Clean up after each test method."""
        super().tearDown()


class BaseAPITestCase(APITestCase):
    """
    Base API test case for testing REST API endpoints.
    """
    
    def setUp(self):
        """Set up test environment before each test method."""
        super().setUp()
    
    def tearDown(self):
        """Clean up after each test method."""
        super().tearDown()
    
    def assert_response_success(self, response, status_code=200):
        """Assert response is successful."""
        self.assertEqual(response.status_code, status_code)
        if hasattr(response, 'json'):
            data = response.json()
            if 'success' in data:
                self.assertTrue(data['success'])
    
    def assert_response_error(self, response, status_code=400):
        """Assert response is an error."""
        self.assertEqual(response.status_code, status_code)


class BaseWebSocketTestCase(ChannelsLiveServerTestCase):
    """
    Base test case for WebSocket consumers.
    """
    
    def setUp(self):
        """Set up test environment before each test method."""
        super().setUp()
    
    def tearDown(self):
        """Clean up after each test method."""
        super().tearDown()
