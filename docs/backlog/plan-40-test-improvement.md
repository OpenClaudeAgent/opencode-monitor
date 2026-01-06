# Plan 40: Test Suite Improvement

**Date**: 2026-01-06  
**Status**: Analysis Complete  
**Priority**: High  

## Executive Summary

The test suite has reached **1,199 tests** with **69% coverage** across **28,886 LOC** of test code for **31,061 LOC** of source code (ratio: 0.93 test LOC per source LOC).

**Key Finding**: While test quantity is good, the test/value ratio needs optimization. Several areas are over-tested with verbose tests while critical business logic has coverage gaps.

---

## 1. Current State Summary

### 1.1 Quantitative Metrics

| Metric | Value |
|--------|-------|
| Total tests | 1,199 |
| Test LOC | 28,886 |
| Source LOC | 31,061 |
| Test/Source Ratio | 0.93 |
| Overall Coverage | 69% |
| Test Functions | 715 |
| Assertions | 2,513 |
| Assertions/Test | 3.5 avg |
| Parametrized Tests | 129 |
| Test Classes | 257 |
| Unit Tests | 1,123 (94%) |
| Integration Tests | 76 (6%) |

### 1.2 Coverage Distribution

#### High Coverage (>80%) - Well tested
- `core/models.py` - 100%
- `core/usage.py` - 100%
- `core/monitor/helpers.py` - 100%
- `analytics/loaders/` - 79-100%
- `security/analyzer/` - 96-100%
- `dashboard/widgets/` - 88-100%
- `utils/` - 100%

#### Medium Coverage (50-80%) - Adequate but gaps exist
- `core/monitor/fetcher.py` - 98%
- `core/monitor/ask_user.py` - 96%
- `analytics/indexer/tracker.py` - 77%
- `analytics/indexer/watcher.py` - 82%
- `analytics/tracing/` - 50-81%
- `app/core.py` - 96%
- `app/handlers.py` - 58%

#### Low Coverage (<50%) - Critical gaps
| Module | Coverage | Missing Lines |
|--------|----------|---------------|
| `analytics/indexer/unified.py` | **0%** | 1,087 lines |
| `api/routes/tracing/builders.py` | **8%** | 119 lines |
| `api/routes/tracing/utils.py` | **10%** | 110 lines |
| `api/routes/sessions.py` | **24%** | 77 lines |
| `api/routes/stats.py` | **34%** | 19 lines |
| `api/routes/delegations.py` | **38%** | 13 lines |
| `api/tree_builder.py` | **17%** | 95 lines |
| `analytics/report/charts.py` | **11%** | 77 lines |
| `analytics/report/sections.py` | **14%** | 121 lines |
| `analytics/queries/trace_queries.py` | **46%** | 79 lines |
| `dashboard/sections/tracing/tree_items.py` | **8%** | 98 lines |
| `dashboard/sections/tracing/widgets.py` | **16%** | 68 lines |
| `dashboard/sections/tracing/tabs/timeline.py` | **33%** | 31 lines |

### 1.3 Largest Test Files (LOC Analysis)

| File | LOC | Tests | LOC/Test | Assessment |
|------|-----|-------|----------|------------|
| `test_monitor.py` | 1,452 | 46 | 31.6 | Good - complex mocking |
| `test_loader.py` | 1,363 | 42 | 32.5 | Good - data factories |
| `test_dashboard_window_coverage.py` | 1,290 | 35 | 36.9 | **Review** - verbose |
| `test_analytics_queries.py` | 1,254 | 68 | 18.4 | Good - parametrized |
| `test_app.py` | 1,128 | 38 | 29.7 | **Review** - UI heavy |
| `test_menu.py` | 1,105 | 52 | 21.3 | Good |
| `test_bulk_loader.py` | 983 | 34 | 28.9 | Good |

---

## 2. Problem Areas

### 2.1 Mock Strategy Issues

#### A) Mock Duplication
The same mocks are recreated in multiple places:

```python
# In conftest.py
def create_default_auditor_stats() -> dict:
    return {"total_scanned": 0, "critical": 0, ...}

# In integration/conftest.py - SIMILAR
mock_auditor.get_stats.return_value = {"total_scanned": 0, ...}

# In test_auditor.py - SIMILAR
@pytest.fixture
def mock_db():
    db.get_stats.return_value = {...}
```

**Impact**: 431 mock usages scattered across test files with inconsistent patterns.

#### B) Over-Mocking in Integration Tests
Integration tests mock too much, reducing their value:

```python
# tests/integration/conftest.py
@pytest.fixture
def dashboard_window(qtbot, patched_api_client, patched_monitoring, patched_security):
    # 3 layers of mocking for "integration" tests
```

**Issue**: Integration tests should test component interaction, not isolated units.

#### C) Factory Function Duplication

| Factory Function | Files Using |
|------------------|-------------|
| `create_session_file()` | test_loader.py, test_bulk_loader.py |
| `make_mock_state()` | test_dashboard_window_coverage.py, test_menu.py |
| `make_mock_agent()` | test_dashboard_window_coverage.py, test_app.py |
| `insert_session()` | test_analytics_queries.py, test_trace_queries.py |

### 2.2 Assertion Quality

#### Good Examples (Behavior Testing)
```python
# test_analytics_queries.py - Tests WHAT, not HOW
assert len(result) == 2
assert result[0]["tool_name"] == "bash"
assert result[0]["total_calls"] == 5
```

#### Weak Examples (Implementation Testing)
```python
# test_app.py - Tests internal method calls
mock_refresh.assert_called_once()
mock_timer.start.assert_called()
```

**Analysis**: ~30% of assertions test implementation details rather than behavior.

### 2.3 Test Architecture Anti-Patterns

#### A) Verbose Test Setup
Many tests have 50+ lines of setup for simple assertions:

```python
# test_dashboard_window_coverage.py
def test_fetch_monitoring_data_success(...):
    # 30 lines of mock setup
    # 10 lines of execution
    # 5 lines of assertions
```

#### B) Sleep Calls (18 instances)
```python
# Potential flakiness
time.sleep(0.1)  # 18 occurrences
qtbot.wait(50)   # Additional waits in Qt tests
```

#### C) Missing Error Path Tests
Many modules have happy-path coverage but missing error scenarios:
- `api/routes/` - No error response testing
- `analytics/indexer/` - No recovery testing
- `dashboard/` - No widget error state testing

### 2.4 Coverage Gaps - Critical Business Logic

| Component | What's Missing | Risk Level |
|-----------|----------------|------------|
| `unified.py` (0%) | Entire indexer pipeline | **CRITICAL** |
| `api/routes/tracing/` (8-18%) | Tree building, session views | **HIGH** |
| `analytics/report/` (11-14%) | Report generation | MEDIUM |
| `dashboard/tracing/tree_items.py` (8%) | UI node rendering | MEDIUM |

---

## 3. Recommendations

### 3.1 Mock Consolidation Strategy

#### A) Create Centralized Mock Factory Module
```
tests/
  mocks/
    __init__.py
    api_client.py      # MockAPIClient variations
    models.py          # Model factories (Agent, Session, etc.)
    database.py        # DB fixtures
    security.py        # Security auditor mocks
```

**Benefit**: Single source of truth for mocks, easier maintenance.

#### B) Use `pytest-factoryboy` Pattern
```python
# tests/mocks/models.py
class AgentFactory:
    @staticmethod
    def idle(id="agent-1", **kwargs):
        return Agent(id=id, status=SessionStatus.IDLE, **kwargs)
    
    @staticmethod
    def busy(id="agent-1", **kwargs):
        return Agent(id=id, status=SessionStatus.BUSY, **kwargs)
```

### 3.2 Coverage Priorities

#### Priority 1: Critical Gaps (0-20% coverage)
1. `analytics/indexer/unified.py` - Core indexing pipeline
2. `api/routes/tracing/builders.py` - Session tree building
3. `api/routes/tracing/utils.py` - Data transformation

#### Priority 2: Important Business Logic (20-50% coverage)
4. `api/routes/sessions.py` - Session API endpoints
5. `analytics/queries/trace_queries.py` - Trace data queries
6. `api/tree_builder.py` - Tree construction logic

#### Priority 3: Presentation Layer (can stay lower)
7. `analytics/report/` - Report generation (11-14%)
8. `dashboard/sections/tracing/` - UI components

### 3.3 Test Refactoring Opportunities

#### A) Parametrize Repetitive Tests
```python
# BEFORE: 5 similar tests
def test_truncate_short_text(): ...
def test_truncate_long_text(): ...
def test_truncate_emoji(): ...

# AFTER: 1 parametrized test
@pytest.mark.parametrize("input,expected", [
    ("short", "short"),
    ("x" * 100, "x" * 40 + "..."),
    ("emoji text", "emoji text"),
])
def test_truncate(input, expected): ...
```

**Estimated reduction**: 200-300 LOC

#### B) Extract Test Data Builders
```python
# Create tests/builders.py
class SessionBuilder:
    def __init__(self):
        self.data = {"id": "sess-001", "title": "Default"}
    
    def with_tokens(self, input=100, output=50):
        self.data["tokens_in"] = input
        self.data["tokens_out"] = output
        return self
    
    def build(self):
        return self.data
```

#### C) Use Table-Driven Tests for Queries
```python
@pytest.mark.parametrize("query_method,expected_fields", [
    ("get_sessions", ["id", "title", "created_at"]),
    ("get_messages", ["id", "session_id", "content"]),
    ("get_tools", ["id", "tool_name", "status"]),
])
def test_query_returns_expected_fields(query_method, expected_fields, db): ...
```

### 3.4 Tests to Remove/Simplify

| File | Current LOC | Target LOC | Action |
|------|-------------|------------|--------|
| `test_dashboard_window_coverage.py` | 1,290 | 800 | Simplify setup |
| `test_app.py` | 1,128 | 700 | Remove mock verification |
| `test_models.py` | 691 | 400 | Parametrize edge cases |

---

## 4. Proposed Sprint: Test Suite Optimization

### Epic: TST-40 - Test Suite Quality Improvement

**Goal**: Increase meaningful coverage to 80% while reducing test LOC by 15%

---

### Story 1: Mock Centralization
**Points**: 5  
**Priority**: HIGH

**Description**: Consolidate all mock factories into `tests/mocks/` module.

**Acceptance Criteria**:
- [ ] Create `tests/mocks/__init__.py` with exports
- [ ] Create `tests/mocks/api_client.py` with MockAPIClient variants
- [ ] Create `tests/mocks/models.py` with Agent, Session, State factories
- [ ] Create `tests/mocks/database.py` with DB fixtures
- [ ] Update `tests/conftest.py` to import from `mocks/`
- [ ] Update `tests/integration/conftest.py` to import from `mocks/`
- [ ] Remove duplicate mock definitions from individual test files

**Test Impact**:
- Remove ~500 LOC of duplicated mock code
- Single source of truth for test data

---

### Story 2: Critical Coverage - UnifiedIndexer
**Points**: 8  
**Priority**: CRITICAL

**Description**: Add tests for `analytics/indexer/unified.py` (currently 0% coverage).

**Acceptance Criteria**:
- [ ] Test `UnifiedIndexer.__init__()` initialization
- [ ] Test `start()` / `stop()` lifecycle
- [ ] Test `_process_session()` with valid/invalid data
- [ ] Test `_process_message()` with valid/invalid data
- [ ] Test `_process_part()` with tool/text/delegation types
- [ ] Test `_batch_process_*()` methods
- [ ] Test `get_stats()` returns correct metrics
- [ ] Test `force_backfill()` triggers reprocessing
- [ ] Coverage target: >70%

**Technical Notes**:
- Use `tmp_path` for file system operations
- Mock `AnalyticsDB` for database operations
- Test error recovery scenarios

---

### Story 3: Critical Coverage - API Tracing Routes
**Points**: 5  
**Priority**: HIGH

**Description**: Add tests for `api/routes/tracing/` (currently 8-18% coverage).

**Acceptance Criteria**:
- [ ] Test `builders.py` - `build_session_node()` with various inputs
- [ ] Test `builders.py` - `build_exchanges_from_messages()`
- [ ] Test `utils.py` - data transformation functions
- [ ] Test `fetchers.py` - session data fetching
- [ ] Test error cases (missing data, invalid IDs)
- [ ] Coverage target: >60%

---

### Story 4: Parametrize Repetitive Tests
**Points**: 3  
**Priority**: MEDIUM

**Description**: Consolidate similar tests using `@pytest.mark.parametrize`.

**Acceptance Criteria**:
- [ ] Identify tests with similar structure (grep for patterns)
- [ ] Refactor `test_models.py` edge cases
- [ ] Refactor `test_settings.py` validation tests
- [ ] Refactor `test_risk_analyzer.py` classification tests
- [ ] Maintain 100% test coverage
- [ ] Reduce test LOC by 300+

---

### Story 5: Test Data Builders
**Points**: 3  
**Priority**: MEDIUM

**Description**: Create builder pattern for complex test data.

**Acceptance Criteria**:
- [ ] Create `tests/builders/__init__.py`
- [ ] Create `SessionBuilder` for session test data
- [ ] Create `MessageBuilder` for message test data
- [ ] Create `TracingTreeBuilder` for tree structure data
- [ ] Update 3+ test files to use builders
- [ ] Document builder usage in tests README

---

### Story 6: Remove Weak Tests
**Points**: 2  
**Priority**: LOW

**Description**: Remove tests that only verify mock calls without behavior.

**Acceptance Criteria**:
- [ ] Audit tests with only `assert_called_*` assertions
- [ ] Remove or improve tests that don't verify behavior
- [ ] Replace mock verification with behavior verification where possible
- [ ] Document why remaining mock verifications are necessary

---

### Story 7: Error Path Coverage
**Points**: 5  
**Priority**: MEDIUM

**Description**: Add error scenario tests for critical modules.

**Acceptance Criteria**:
- [ ] Test API routes with invalid inputs
- [ ] Test indexer recovery from corrupted files
- [ ] Test dashboard graceful degradation
- [ ] Test database connection failures
- [ ] Add boundary value tests

---

## 5. Sprint Metrics & Goals

### Before Sprint
| Metric | Current |
|--------|---------|
| Coverage | 69% |
| Test LOC | 28,886 |
| Tests | 1,199 |
| LOC/Test ratio | 24.1 |

### After Sprint (Target)
| Metric | Target | Change |
|--------|--------|--------|
| Coverage | 78%+ | +9% |
| Test LOC | 24,500 | -15% |
| Tests | 1,100 | -8% (consolidation) |
| LOC/Test ratio | 22.3 | -7% |

### Quality Gates
- No test file >1,000 LOC
- No module with <40% coverage (critical paths)
- Max 10 `time.sleep()` calls in tests
- All mocks defined in `tests/mocks/`

---

## 6. Future Considerations

### Not in Scope for This Sprint
1. **Property-based testing** - Consider `hypothesis` for model validation
2. **Mutation testing** - Consider `mutmut` to verify assertion quality
3. **Visual regression** - Screenshot testing for dashboard
4. **Performance benchmarks** - Query performance testing

### Technical Debt to Address Later
1. Deprecate `analytics/indexer/unified.py` (monolithic) in favor of modular `unified/` package
2. Consider E2E tests with real DuckDB (vs mocked)
3. Add contract tests for API responses

---

## 7. Appendix: Module Coverage Details

<details>
<summary>Full coverage report by module</summary>

```
analytics/indexer/unified.py                 0%   (1087 uncovered lines)
api/routes/tracing/builders.py               8%   (119 uncovered lines)
dashboard/sections/tracing/tree_items.py     8%   (98 uncovered lines)
api/routes/tracing/utils.py                 10%   (110 uncovered lines)
analytics/report/charts.py                  11%   (77 uncovered lines)
analytics/report/sections.py                14%   (121 uncovered lines)
dashboard/sections/tracing/widgets.py       16%   (68 uncovered lines)
api/tree_builder.py                         17%   (95 uncovered lines)
api/routes/tracing/__init__.py              18%   (49 uncovered lines)
analytics/indexer/trace_builder/segments.py 20%   (68 uncovered lines)
api/routes/sessions.py                      24%   (77 uncovered lines)
analytics/indexer/unified/processing.py     31%   (85 uncovered lines)
dashboard/sections/tracing/tabs/timeline.py 33%   (31 uncovered lines)
api/routes/stats.py                         34%   (19 uncovered lines)
api/routes/health.py                        36%   (16 uncovered lines)
analytics/indexer/unified/batch.py          38%   (59 uncovered lines)
api/routes/delegations.py                   38%   (13 uncovered lines)
dashboard/sections/tracing/tabs/agents.py   43%   (16 uncovered lines)
analytics/queries/trace_queries.py          46%   (79 uncovered lines)
analytics/tracing/session_queries.py        50%   (65 uncovered lines)
api/client.py                               51%   (39 uncovered lines)
dashboard/sections/tracing/detail_panel/panel.py 53%  (132 uncovered lines)
dashboard/sections/tracing/tabs/tokens.py   54%   (26 uncovered lines)
dashboard/sections/tracing/tabs/tools.py    54%   (26 uncovered lines)
app/handlers.py                             58%   (63 uncovered lines)
analytics/indexer/unified/core.py           61%   (62 uncovered lines)
dashboard/sections/tracing/tree_builder.py  61%   (72 uncovered lines)
```

</details>

---

*Document generated by TEA (Test Architect Agent)*
