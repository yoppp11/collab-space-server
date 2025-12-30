# Test Coverage Summary

This document provides an overview of the test coverage for the Real-time Collaboration Platform.

## Overall Coverage Target

**Minimum Coverage**: 80%
**Recommended Coverage**: 85%+

## Test Categories

### Unit Tests
- **Location**: `apps/*/tests/test_*.py`
- **Markers**: `@pytest.mark.unit`
- **Coverage**: Models, Serializers, Services, Utilities
- **Execution Time**: Fast (< 30 seconds for all unit tests)

### Integration Tests
- **Location**: `tests/test_integration.py`, `tests/test_api_integration.py`
- **Markers**: `@pytest.mark.integration`
- **Coverage**: End-to-end workflows, API interactions
- **Execution Time**: Moderate (1-2 minutes)

### WebSocket Tests
- **Location**: `apps/collaboration/tests/test_consumers.py`
- **Markers**: `@pytest.mark.websocket`, `@pytest.mark.asyncio`
- **Coverage**: Real-time collaboration features
- **Execution Time**: Moderate (30-60 seconds)

### Performance Tests
- **Location**: `tests/test_performance.py`
- **Markers**: `@pytest.mark.slow`
- **Coverage**: Critical operations benchmarks
- **Execution Time**: Slow (2-5 minutes)

## Coverage by App

### apps/users (Target: 90%+)
- ✅ Models: User, UserSession, UserActivity
- ✅ Serializers: UserSerializer, UserCreateSerializer, PasswordChangeSerializer
- ✅ Views: Registration, Login, Profile, Password Change
- ✅ Services: UserService (activity logging, session management)
- ✅ Fixtures: user, admin_user, authenticated_client

**Files Tested**:
- `test_models.py` - 16 tests
- `test_serializers.py` - 13 tests
- `test_views.py` - 14 tests
- `test_services.py` - 8 tests

### apps/workspaces (Target: 85%+)
- ✅ Models: Workspace, WorkspaceMembership, Board, BoardList
- ✅ Permissions: Role-based access control
- ✅ Views: Workspace CRUD, member management
- ✅ Services: WorkspaceService, BoardService

**Files Tested**:
- `test_models.py` - 22 tests
- `test_views.py` - 15 tests
- `test_permissions.py` - 12 tests

### apps/documents (Target: 85%+)
- ✅ Models: Document, Block (MPTT), Comment
- ✅ Views: Document CRUD, Block management, Comments
- ✅ Services: DocumentService, VersionService

**Files Tested**:
- `test_models.py` - 14 tests
- `test_views.py` - 12 tests

### apps/collaboration (Target: 75%+)
- ✅ Consumers: DocumentConsumer (WebSocket)
- ⚠️ Services: CRDT, Presence (basic tests)
- ⚠️ Middleware: WebSocket authentication

**Files Tested**:
- `test_consumers.py` - 4 tests (expandable)

**Note**: WebSocket testing is more complex and requires additional setup. Current coverage focuses on structure validation.

### apps/notifications (Target: 80%+)
- ✅ Models: Notification
- ✅ Services: NotificationService

**Files Tested**:
- `test_models.py` - 4 tests

### apps/core (Target: 90%+)
- ✅ Base Models: BaseModel, SoftDeleteModel
- ✅ Factories: Factory Boy factories for all models
- ✅ Base Test Classes: BaseTestCase, BaseAPITestCase
- ✅ Utilities: Idempotency, caching helpers

## Test Execution Statistics

### Current Status
```
Total Tests: ~130+
Unit Tests: ~100
Integration Tests: ~20
WebSocket Tests: ~4
Performance Tests: ~4

Execution Time:
- Unit: ~15-30 seconds
- Integration: ~30-60 seconds
- WebSocket: ~10-20 seconds
- Performance: ~60-120 seconds
- All: ~2-4 minutes
```

### Parallel Execution
Using `pytest -n auto` reduces execution time by ~50-70%:
- All tests: ~60-90 seconds

## Coverage Reports

### Generating Coverage Reports

**Terminal Report**:
```bash
pytest --cov=apps --cov-report=term-missing
```

**HTML Report** (recommended):
```bash
pytest --cov=apps --cov-report=html
# Open htmlcov/index.html in browser
```

**XML Report** (for CI/CD):
```bash
pytest --cov=apps --cov-report=xml
```

### Interpreting Coverage

- **Green (>80%)**: Good coverage
- **Yellow (60-80%)**: Needs improvement
- **Red (<60%)**: Critical - add tests

## Continuous Integration

Tests run automatically on:
- ✅ Every push to `main` or `develop` branches
- ✅ Every pull request
- ✅ Nightly builds (optional)

### CI Pipeline (.github/workflows/tests.yml)
1. Set up Python 3.11
2. Install dependencies
3. Start PostgreSQL and Redis services
4. Run linting (flake8)
5. Run unit tests with coverage
6. Run integration tests
7. Check for missing migrations
8. Upload coverage to Codecov

## Test Quality Metrics

### Code Quality Checks
- **Linting**: flake8
- **Type Checking**: Not currently implemented (future: mypy)
- **Security**: Not currently implemented (future: bandit)

### Test Best Practices Followed
✅ Descriptive test names
✅ Independent tests (no test dependencies)
✅ Factory Boy for test data
✅ Fixtures for common setup
✅ Markers for test categorization
✅ Clear assertions with helpful messages
✅ Mocking for external services
✅ Integration tests for critical workflows

## Known Gaps & Future Improvements

### Current Gaps
1. **WebSocket Tests**: Only structural tests, need full E2E WebSocket tests
2. **Celery Tasks**: Task execution tests missing
3. **Permissions**: More edge case testing needed
4. **API Throttling**: Rate limiting tests missing
5. **File Upload**: File handling tests missing

### Planned Improvements
1. Add Selenium/Playwright for browser-based E2E tests
2. Load testing with Locust
3. Security testing (SQL injection, XSS, CSRF)
4. API contract testing (Pact/Dredd)
5. Mutation testing (mutmut)

## Running Tests in Different Environments

### Local Development
```bash
pytest                                    # All tests
pytest -m unit                            # Fast unit tests only
pytest apps/users/tests/                  # Specific app
```

### CI/CD
```bash
pytest --cov=apps --cov-report=xml --cov-fail-under=80
```

### Docker
```bash
docker-compose exec web pytest
docker-compose exec web pytest --cov=apps
```

### Pre-commit Hook
```bash
# Add to .git/hooks/pre-commit
pytest -m unit --maxfail=1
```

## Maintenance

### Adding New Tests
1. Create test file in appropriate `tests/` directory
2. Use appropriate markers (`@pytest.mark.unit`, etc.)
3. Follow naming convention: `test_<feature>_<scenario>`
4. Add fixtures to `conftest.py` if reusable
5. Run tests to verify
6. Check coverage increased

### Updating Tests
- When models change, update factories
- When APIs change, update view tests
- When business logic changes, update service tests
- Keep integration tests in sync with workflows

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [Django Testing Best Practices](https://docs.djangoproject.com/en/stable/topics/testing/overview/)
- [Factory Boy Documentation](https://factoryboy.readthedocs.io/)
- [Testing Guide](TESTING.md) - Detailed testing documentation

---

**Last Updated**: December 30, 2025
**Maintained By**: Development Team
