# Testing Quick Reference Card

## 🚀 Quick Commands

### Basic Test Execution
```bash
pytest                          # Run all tests
pytest -v                       # Verbose output
pytest -s                       # Show print statements
pytest -x                       # Stop on first failure
pytest --lf                     # Run last failed tests only
```

### By Category
```bash
pytest -m unit                  # Unit tests only
pytest -m integration           # Integration tests only
pytest -m websocket            # WebSocket tests only
pytest -m "not slow"           # Exclude slow tests
```

### By App
```bash
pytest apps/users/tests/                    # All user tests
pytest apps/workspaces/tests/test_models.py # Specific file
pytest apps/users/tests/test_models.py::TestUserModel  # Specific class
pytest apps/users/tests/test_models.py::TestUserModel::test_create_user  # Specific test
```

### Coverage
```bash
pytest --cov=apps                           # Coverage summary
pytest --cov=apps --cov-report=html         # HTML report
pytest --cov=apps --cov-report=term-missing # Show missing lines
pytest --cov=apps --cov-fail-under=80       # Fail if <80%
```

### Performance
```bash
pytest -n auto                  # Parallel execution (all cores)
pytest -n 4                     # Parallel execution (4 workers)
pytest --durations=10           # Show 10 slowest tests
```

### Using Scripts
```bash
# Python
python run_tests.py --unit
python run_tests.py --coverage
python run_tests.py --app users

# Shell (Linux/Mac)
./run_tests.sh unit
./run_tests.sh coverage

# Batch (Windows)
run_tests.bat unit
run_tests.bat coverage
```

## 📝 Writing Tests

### Basic Test Structure
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
```

### Using Fixtures
```python
def test_authenticated_request(authenticated_client, user):
    """Test with authenticated client."""
    url = reverse('users:profile')
    response = authenticated_client.get(url)
    assert response.status_code == 200
```

### Testing APIs
```python
from django.urls import reverse
from rest_framework import status

def test_create_workspace(authenticated_client):
    """Test creating a workspace."""
    url = reverse('workspaces:workspace-list')
    data = {'name': 'Test Workspace'}
    response = authenticated_client.post(url, data, format='json')
    
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data['data']['name'] == 'Test Workspace'
```

### Async Tests
```python
import pytest

@pytest.mark.asyncio
async def test_websocket_connection(websocket_communicator):
    """Test WebSocket connection."""
    connected, _ = await websocket_communicator.connect()
    assert connected
    await websocket_communicator.disconnect()
```

## 🏭 Factories

### Common Factories
```python
from apps.core.tests.factories import (
    UserFactory, WorkspaceFactory, DocumentFactory,
    BlockFactory, CommentFactory, NotificationFactory
)

# Create single instance
user = UserFactory()

# Create with specific attributes
user = UserFactory(email='specific@example.com', first_name='John')

# Create batch
users = UserFactory.create_batch(10)

# Create with relationships
workspace = WorkspaceFactory(owner=user)
document = DocumentFactory(workspace=workspace, created_by=user)
```

## 🎯 Common Fixtures

### Available Fixtures
```python
# API Clients
api_client              # Unauthenticated DRF client
authenticated_client    # Authenticated DRF client
admin_client           # Admin authenticated client

# Users
user                   # Regular user
admin_user            # Superuser
user_with_password    # User with password='testpass123'
multiple_users        # List of 5 users

# Workspaces
workspace             # Basic workspace
workspace_with_members # Workspace with members
board                 # Board in workspace

# Documents
document              # Basic document
document_with_blocks  # Document with blocks
comment              # Comment on document

# Other
channel_layer         # WebSocket channel layer
clear_cache          # Auto-clears cache
celery_eager_mode    # Runs tasks synchronously
mock_redis           # Mocked Redis client
```

## 🏷️ Test Markers

### Available Markers
```python
@pytest.mark.unit          # Fast, isolated tests
@pytest.mark.integration   # E2E workflow tests
@pytest.mark.slow          # Slow running tests
@pytest.mark.websocket     # WebSocket tests
@pytest.mark.celery        # Celery task tests
@pytest.mark.models        # Model tests
@pytest.mark.views         # View tests
@pytest.mark.serializers   # Serializer tests
@pytest.mark.services      # Service tests
@pytest.mark.permissions   # Permission tests

# Use multiple markers
@pytest.mark.unit
@pytest.mark.models
def test_user_model():
    pass
```

## 🐛 Debugging

### Debug Options
```bash
pytest --pdb                    # Drop to debugger on failure
pytest --pdb --maxfail=1        # Debug first failure
pytest --lf --pdb              # Debug last failed test
pytest -vv                     # Extra verbose output
pytest -s                      # Show print() output
pytest --tb=short              # Short traceback
pytest --tb=long               # Long traceback
```

### Using breakpoint()
```python
def test_something():
    user = UserFactory()
    breakpoint()  # Debugger will stop here
    assert user.is_active
```

## 📊 Coverage Reports

### Generate Reports
```bash
# Terminal report
pytest --cov=apps --cov-report=term

# HTML report (recommended)
pytest --cov=apps --cov-report=html
# Open htmlcov/index.html

# XML report (for CI/CD)
pytest --cov=apps --cov-report=xml

# Multiple formats
pytest --cov=apps --cov-report=html --cov-report=term-missing
```

### Check Coverage
```bash
# View coverage percentage
pytest --cov=apps

# Fail if coverage below threshold
pytest --cov=apps --cov-fail-under=80
```

## 🔧 Common Patterns

### Test Database Setup
```python
@pytest.fixture
def setup_test_data():
    """Create test data."""
    user = UserFactory()
    workspace = WorkspaceFactory(owner=user)
    return {'user': user, 'workspace': workspace}

def test_something(setup_test_data):
    user = setup_test_data['user']
    workspace = setup_test_data['workspace']
    # Test code
```

### Mocking
```python
def test_with_mock(mocker):
    """Test with mocked function."""
    mock_send = mocker.patch('apps.notifications.services.send_email')
    
    # Test code that calls send_email
    
    mock_send.assert_called_once()
    mock_send.assert_called_with(expected_args)
```

### Parameterized Tests
```python
@pytest.mark.parametrize('role,can_edit', [
    ('owner', True),
    ('admin', True),
    ('member', False),
    ('guest', False),
])
def test_permissions(role, can_edit):
    """Test permissions for different roles."""
    assert check_permission(role, 'edit') == can_edit
```

## 🔗 Useful URLs

### Reverse URL
```python
from django.urls import reverse

url = reverse('users:profile')
url = reverse('workspaces:workspace-detail', args=[workspace.id])
url = reverse('documents:document-list')
```

### Making Requests
```python
# GET
response = authenticated_client.get(url)

# POST
response = authenticated_client.post(url, data, format='json')

# PATCH
response = authenticated_client.patch(url, data, format='json')

# DELETE
response = authenticated_client.delete(url)
```

## 📚 Resources

- [Full Testing Guide](TESTING.md)
- [Coverage Summary](TEST_COVERAGE.md)
- [Implementation Summary](TEST_IMPLEMENTATION_SUMMARY.md)
- [pytest Documentation](https://docs.pytest.org/)
- [Factory Boy](https://factoryboy.readthedocs.io/)

---

**Keep this card handy for quick reference while writing tests!**
