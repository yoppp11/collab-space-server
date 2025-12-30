# Testing Guide

## Overview

This project uses **pytest** as the testing framework with comprehensive test coverage across all apps. The test suite includes unit tests, integration tests, and WebSocket tests.

## Test Structure

```
├── conftest.py                    # Root pytest configuration and fixtures
├── pytest.ini                     # Pytest settings and markers
├── apps/
│   ├── core/tests/
│   │   ├── base.py               # Base test classes
│   │   ├── factories.py          # Factory Boy factories for test data
│   │   └── conftest.py
│   ├── users/tests/
│   │   ├── test_models.py        # User model tests
│   │   ├── test_serializers.py   # Serializer tests
│   │   ├── test_views.py         # API view tests
│   │   ├── test_services.py      # Service layer tests
│   │   └── conftest.py           # User-specific fixtures
│   ├── workspaces/tests/         # Workspace tests
│   ├── documents/tests/          # Document tests
│   ├── collaboration/tests/      # WebSocket and collaboration tests
│   └── notifications/tests/      # Notification tests
└── tests/
    ├── test_integration.py       # End-to-end integration tests
    └── test_api_integration.py   # API workflow tests
```

## Running Tests

### Run All Tests
```bash
pytest
```

### Run Tests with Coverage
```bash
pytest --cov=apps --cov-report=html
```

### Run Specific Test Categories
```bash
# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# WebSocket tests only
pytest -m websocket

# Tests for a specific app
pytest apps/users/tests/

# Run a specific test file
pytest apps/users/tests/test_models.py

# Run a specific test class
pytest apps/users/tests/test_models.py::TestUserModel

# Run a specific test
pytest apps/users/tests/test_models.py::TestUserModel::test_create_user
```

### Run Tests in Parallel
```bash
pytest -n auto  # Uses all CPU cores
pytest -n 4     # Uses 4 workers
```

### Run Tests with Verbose Output
```bash
pytest -v       # Verbose
pytest -vv      # Extra verbose
pytest -s       # Show print statements
```

## Test Markers

Custom pytest markers are defined in `pytest.ini`:

- `@pytest.mark.unit` - Unit tests (fast, isolated)
- `@pytest.mark.integration` - Integration tests (slower, cross-app)
- `@pytest.mark.slow` - Slow-running tests
- `@pytest.mark.websocket` - WebSocket consumer tests
- `@pytest.mark.celery` - Celery task tests
- `@pytest.mark.models` - Model tests
- `@pytest.mark.views` - View tests
- `@pytest.mark.serializers` - Serializer tests
- `@pytest.mark.services` - Service tests
- `@pytest.mark.permissions` - Permission tests

Example usage:
```python
@pytest.mark.unit
@pytest.mark.models
def test_user_creation():
    """Test creating a user."""
    pass
```

## Fixtures

### Common Fixtures (conftest.py)

- `api_client` - DRF API test client
- `authenticated_client` - Pre-authenticated API client
- `admin_client` - Admin authenticated client
- `user` - Regular user instance
- `admin_user` - Superuser instance
- `channel_layer` - Channel layer for WebSocket tests
- `clear_cache` - Auto-clears cache before/after tests
- `celery_eager_mode` - Runs Celery tasks synchronously

### App-Specific Fixtures

See each app's `conftest.py` for app-specific fixtures like:
- `workspace` - Workspace instance
- `document` - Document instance
- `notification` - Notification instance

## Factory Boy

Test data is generated using Factory Boy. Factories are defined in `apps/core/tests/factories.py`:

```python
from apps.core.tests.factories import UserFactory, WorkspaceFactory, DocumentFactory

# Create a user
user = UserFactory()

# Create a user with specific attributes
user = UserFactory(email='test@example.com', first_name='John')

# Create multiple users
users = UserFactory.create_batch(5)

# Create a workspace
workspace = WorkspaceFactory(owner=user)
```

## Writing Tests

### Unit Test Example

```python
import pytest
from apps.core.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

class TestUserModel:
    """Tests for User model."""
    
    def test_create_user(self):
        """Test creating a user."""
        user = UserFactory(email='test@example.com')
        assert user.email == 'test@example.com'
        assert user.is_active is True
```

### API View Test Example

```python
import pytest
from django.urls import reverse
from rest_framework import status

pytestmark = pytest.mark.django_db

class TestUserAPI:
    """Tests for User API endpoints."""
    
    def test_get_profile(self, authenticated_client, user):
        """Test retrieving user profile."""
        url = reverse('users:profile')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['email'] == user.email
```

### Integration Test Example

```python
import pytest
from django.urls import reverse

pytestmark = [pytest.mark.django_db, pytest.mark.integration]

class TestWorkspaceFlow:
    """Integration tests for workspace workflows."""
    
    def test_create_workspace_and_document(self, authenticated_client, user):
        """Test creating workspace then document."""
        # Create workspace
        workspace_response = authenticated_client.post(
            reverse('workspaces:workspace-list'),
            {'name': 'Test Workspace'},
            format='json'
        )
        workspace_id = workspace_response.data['data']['id']
        
        # Create document in workspace
        document_response = authenticated_client.post(
            reverse('documents:document-list'),
            {'workspace': workspace_id, 'title': 'Test Doc'},
            format='json'
        )
        assert document_response.status_code == 201
```

### WebSocket Test Example

```python
import pytest
from channels.testing import WebsocketCommunicator

pytestmark = [pytest.mark.django_db, pytest.mark.asyncio, pytest.mark.websocket]

class TestDocumentConsumer:
    """Tests for WebSocket consumer."""
    
    async def test_websocket_connection(self, user, document):
        """Test WebSocket connection."""
        from apps.collaboration.consumers import DocumentConsumer
        
        communicator = WebsocketCommunicator(
            DocumentConsumer.as_asgi(),
            f"/ws/documents/{document.id}/"
        )
        communicator.scope['user'] = user
        
        connected, _ = await communicator.connect()
        assert connected
        await communicator.disconnect()
```

## Best Practices

### 1. Test Naming
- Use descriptive test names: `test_user_can_create_workspace`
- Follow pattern: `test_<what>_<condition>_<expected_result>`

### 2. Test Organization
- One test class per model/view/serializer
- Group related tests in classes
- Use clear docstrings

### 3. Test Independence
- Each test should be independent
- Use fixtures instead of setUp/tearDown when possible
- Don't rely on test execution order

### 4. Use Factories
- Always use Factory Boy instead of creating instances manually
- Keeps tests DRY and maintainable
- Easier to update when models change

### 5. Test Coverage
- Aim for >80% code coverage
- Focus on business logic and edge cases
- Don't test Django/DRF internals

### 6. Assertions
- Use specific assertions: `assert user.is_active is True` not `assert user.is_active`
- Include failure messages when helpful
- Test one thing per test

### 7. Mocking
- Mock external services (email, Redis, etc.)
- Use `pytest-mock` for mocking
- Don't mock what you're testing

Example:
```python
def test_send_notification(self, mocker, user):
    """Test sending notification."""
    mock_send = mocker.patch('apps.notifications.services.send_email')
    
    # Test code here
    
    mock_send.assert_called_once()
```

## Continuous Integration

Tests are automatically run in CI/CD pipeline. Ensure:
- All tests pass before merging
- Code coverage remains >80%
- No new warnings or errors

## Debugging Tests

```bash
# Run with pdb debugger
pytest --pdb

# Drop to debugger on failure
pytest --pdb --maxfail=1

# Run last failed tests
pytest --lf

# See print statements
pytest -s

# More verbose output
pytest -vv
```

## Performance

```bash
# Show slowest tests
pytest --durations=10

# Run tests in parallel
pytest -n auto

# Reuse database between runs
pytest --reuse-db
```

## Database

Tests use SQLite in-memory database by default for speed. This is configured in `conftest.py`:

```python
@pytest.fixture(scope='session')
def django_db_setup():
    settings.DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
```

For tests requiring PostgreSQL-specific features, override this fixture.

## Additional Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Django Testing](https://docs.djangoproject.com/en/stable/topics/testing/)
- [DRF Testing](https://www.django-rest-framework.org/api-guide/testing/)
- [Factory Boy](https://factoryboy.readthedocs.io/)
- [pytest-django](https://pytest-django.readthedocs.io/)
