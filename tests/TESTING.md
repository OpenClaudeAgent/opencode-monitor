# Testing Strategy

## Philosophy

**Integration > Unit**: Prefer real dependencies over mocks when safe and fast
**Fixtures for DI**: Use pytest fixtures for dependency injection
**Real databases**: DuckDB in-memory for fast, realistic tests
**No over-mocking**: Mock only external boundaries (HTTP, filesystem boundaries)

## Test Hierarchy

```
tests/
├── unit/          # 30% - Pure functions, validators, models
├── integration/   # 60% - Real DB, real Flask, real async
├── e2e/           # 10% - Full stack workflows
├── fixtures/      # Test data builders
└── legacy/        # Old tests (being migrated)
```

## When to Use What

### Unit Tests (`tests/unit/`)

For pure functions without I/O:
- Data validation logic
- Model methods
- Utility functions
- Simple calculations

**Example:**
```python
def test_session_status_validation(sample_session_id):
    session = Session(session_id=sample_session_id, status="active")
    assert session.is_active
```

### Integration Tests (`tests/integration/`)

For components with real dependencies:
- Database operations (real DuckDB)
- API routes (Flask test_client)
- Analytics queries
- Security analysis
- Async operations (mocked HTTP)

**Example:**
```python
def test_store_session_real_db(analytics_db_real):
    session = SessionDataFactory.build()
    analytics_db_real.store_session(session)
    
    result = analytics_db_real.query(
        "SELECT * FROM sessions WHERE session_id = ?",
        [session["session_id"]]
    )
    assert len(result) == 1
```

### E2E Tests (`tests/e2e/`)

For full system workflows:
- Menu bar + dashboard + API
- End-to-end user scenarios
- Cross-component integration

**Example:**
```python
def test_full_stack_workflow(full_stack, qtbot):
    db = full_stack["db"]
    session = SessionDataFactory.build()
    db.store_session(session)
    
    response = requests.get(f"{full_stack['api_url']}/api/sessions")
    assert len(response.json()) == 1
    
    window = DashboardWindow(api_url=full_stack["api_url"])
    qtbot.addWidget(window)
    qtbot.waitUntil(lambda: window.session_count == 1, timeout=5000)
    assert window.session_count == 1
```

## Fixtures Guide

### Database Fixtures

```python
@pytest.fixture
def analytics_db_real(tmp_path):
    db_path = Path(tmp_path) / "test_analytics.duckdb"
    db = AnalyticsDB(db_path=db_path, read_only=False)
    
    with db:
        db._create_schema()
    
    yield db
    
    db.close()
```

### Flask Fixtures

```python
@pytest.fixture
def flask_app_real(analytics_db_real):
    app = Flask(__name__)
    app.config.update({"TESTING": True})
    
    # Register blueprints...
    
    with app.app_context():
        yield app

@pytest.fixture
def api_client_real(flask_app_real):
    return flask_app_real.test_client()
```

### Async Fixtures

```python
@pytest.fixture
def mock_aioresponse():
    with aioresponses() as m:
        yield m

def test_fetch_instance(mock_aioresponse):
    mock_aioresponse.get(
        "http://127.0.0.1:8080/session/status",
        payload={"status": "active"}
    )
    
    result = await fetch_instance(8080)
    assert result.status == "active"
```

### Time Fixtures

```python
@pytest.fixture
def freezer():
    with freeze_time("2026-01-11 12:00:00") as frozen:
        yield frozen

def test_timing(freezer):
    now = datetime.now()
    freezer.move_to("2026-01-11 13:00:00")
    later = datetime.now()
    assert (later - now).seconds == 3600
```

## Test Data Factories

Use Factory Boy for realistic test data:

```python
from tests.fixtures.builders import AgentFactory, SessionDataFactory

def test_with_factories():
    agent = AgentFactory.build()
    session = SessionDataFactory.build()
    
    assert agent.title
    assert session["session_id"]
```

## Running Tests

```bash
# All tests
make test-all

# Unit only (fast)
pytest tests/unit/ -v

# Integration (slower)
pytest tests/integration/ -v

# Parallel execution
pytest -n auto

# Specific marker
pytest -m "not slow" -v

# Random order (detect dependencies)
pytest --randomly-seed=auto

# Legacy tests only
pytest -m legacy -v

# New tests only
pytest -m "not legacy" -v
```

## Migration Status

Current progress (3/8 phases completed):

**✅ Completed:**
- Phase 1: Infrastructure (fixtures, factories, dependencies)
- Phase 2: Database tests (13 tests with real DuckDB)
- Phase 3: API tests (5 tests with Flask test_client)

**📝 In Progress:**
- Phase 4: Flaky tests (examples created, existing tests not migrated)
- Phase 8: Documentation (TESTING.md, Makefile, migration script)

**⏳ Pending:**
- Phase 5: Async tests (aioresponses)
- Phase 6: UI tests (PyQt6 DI)
- Phase 7: E2E tests (full stack)

Check migration progress:
```bash
make test-migration-status
python scripts/migration-report.py
```

**Total migrated:** 51 tests
- Unit: 28 tests
- Integration DB: 13 tests
- Integration API: 5 tests
- Examples: 5 tests

## Best Practices

### DO

- ✅ Use real DuckDB for database tests
- ✅ Use Flask test_client for API tests
- ✅ Use aioresponses for async HTTP tests
- ✅ Use freezegun for time-based tests
- ✅ Use Factory Boy for test data
- ✅ Close connections in teardown (yield)
- ✅ Isolate tests with tmp_path

### DON'T

- ❌ Mock DuckDB (use real in-memory)
- ❌ Mock Flask app (use test_client)
- ❌ Patch time.sleep (use freezegun)
- ❌ Mock threading (use real with barriers)
- ❌ Share mutable state between tests
- ❌ Leave connections open

## Common Patterns

### Database Test Pattern

```python
def test_database_operation(analytics_db_real):
    data = SessionDataFactory.build()
    analytics_db_real.store_session(data)
    
    result = analytics_db_real.get_session(data["session_id"])
    assert result["session_id"] == data["session_id"]
```

### API Test Pattern

```python
def test_api_endpoint(api_client_real, analytics_db_real):
    session = SessionDataFactory.build()
    analytics_db_real.store_session(session)
    
    response = api_client_real.get("/api/sessions")
    assert response.status_code == 200
    assert len(response.json) == 1
```

### Async Test Pattern

```python
@pytest.mark.asyncio
async def test_async_operation(mock_aioresponse):
    mock_aioresponse.get(
        "http://example.com/api",
        payload={"result": "success"}
    )
    
    result = await fetch_data("http://example.com/api")
    assert result["result"] == "success"
```

## Troubleshooting

### Tests are slow

- Check if using real network calls (should use mocks)
- Verify database scope (function vs session)
- Run with pytest-xdist: `pytest -n auto`

### Tests are flaky

- Use freezegun instead of time.sleep
- Use thread barriers for synchronization
- Check for shared mutable state
- Run with random order: `pytest --randomly-seed=auto`

### LSP errors on factory-boy

Factory-boy uses advanced Python features that confuse type checkers. If code runs correctly, ignore LSP errors on factory imports.

## Resources

- [Pytest Fixtures](https://docs.pytest.org/en/stable/how-to/fixtures.html)
- [Flask Testing](https://flask.palletsprojects.com/en/stable/testing/)
- [Factory Boy](https://factoryboy.readthedocs.io/en/stable/)
- [Freezegun](https://github.com/spulec/freezegun)
- [Aioresponses](https://github.com/pnuckowski/aioresponses)
