# Plan 41: Security Database Migration (SQLite → DuckDB)

## Objective

Unify the database layer by migrating the security audit data from SQLite to DuckDB, eliminating the dual-database architecture.

## Current State

### Architecture
```
┌─────────────────────────────────────┐
│           analytics.duckdb          │  ← Analytics (15 tables)
│  - sessions, messages, parts, ...   │
│  - security_scanned (scan tracking) │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│            security.db              │  ← Security audit (SQLite)
│  - commands                         │
│  - file_reads                       │
│  - file_writes                      │
│  - webfetches                       │
│  - scan_stats                       │
└─────────────────────────────────────┘
```

### Target State
```
┌─────────────────────────────────────┐
│           analytics.duckdb          │
│                                     │
│  Analytics:                         │
│  - sessions, messages, parts, ...   │
│                                     │
│  Security:                          │
│  - security_commands                │
│  - security_file_reads              │
│  - security_file_writes             │
│  - security_webfetches              │
│  - security_scanned                 │
│  - security_stats                   │
└─────────────────────────────────────┘
```

## Benefits

1. **Single database** - Simplified architecture
2. **Better performance** - DuckDB faster for analytics queries
3. **Cross-domain JOINs** - Link security events to sessions/parts
4. **Less maintenance** - One DB to backup/manage
5. **Consistency** - Same SQL dialect everywhere

## Implementation

### Phase 1: Create DuckDB Schema (1h)

Add security tables to `analytics/db.py`:

```python
# Security audit tables
CREATE TABLE IF NOT EXISTS security_commands (
    id VARCHAR PRIMARY KEY,
    file_id VARCHAR NOT NULL,
    content_hash VARCHAR NOT NULL,
    session_id VARCHAR,
    tool VARCHAR NOT NULL,
    command VARCHAR NOT NULL,
    risk_score INTEGER NOT NULL,
    risk_level VARCHAR NOT NULL,
    risk_reason VARCHAR,
    command_timestamp BIGINT,
    scanned_at TIMESTAMP NOT NULL,
    mitre_techniques VARCHAR DEFAULT '[]',
    edr_sequence_bonus INTEGER DEFAULT 0,
    edr_correlation_bonus INTEGER DEFAULT 0,
    UNIQUE(file_id)
);

-- Similar for security_file_reads, security_file_writes, security_webfetches
-- Add security_stats table
```

### Phase 2: Rewrite SecurityDatabase (3-4h)

**File:** `security/db/repository.py`

1. Replace `sqlite3` imports with DuckDB connection
2. Inject `AnalyticsDB` dependency (like `SecurityScannerDuckDB`)
3. Adapt SQL syntax (minimal changes - DuckDB compatible)
4. Use `INSERT OR REPLACE` → DuckDB equivalent
5. Remove `SecurityScannerDuckDB` class (merge into `SecurityDatabase`)

```python
class SecurityDatabase:
    """DuckDB repository for security audit data"""
    
    def __init__(self, db: Optional["AnalyticsDB"] = None):
        self._db = db
        self._owns_db = db is None
    
    def _get_db(self) -> "AnalyticsDB":
        if self._db is None:
            from ...analytics.db import AnalyticsDB
            self._db = AnalyticsDB()
        return self._db
    
    # ... rest of methods using DuckDB
```

### Phase 3: Update Auditor (30min)

**File:** `security/auditor/core.py`

- Update initialization to use new `SecurityDatabase`
- Remove `SecurityScannerDuckDB` usage (now integrated)

### Phase 4: Update Tests (2h)

**Files:**
- `tests/test_database.py`
- `tests/test_auditor.py`
- `tests/test_security_scanner_duckdb.py` → merge/delete
- `tests/mocks/security.py`
- `tests/conftest.py`

Changes:
- Use in-memory DuckDB for tests
- Update mock classes
- Merge scanner tests into database tests

### Phase 5: Cleanup (30min)

1. Delete `security.db` reference in docs
2. Update documentation
3. Remove SQLite dependency from security module
4. Delete old `SecurityScannerDuckDB` class

## Files to Modify

| File | Action |
|------|--------|
| `analytics/db.py` | Add security tables schema |
| `security/db/repository.py` | Rewrite for DuckDB |
| `security/db/__init__.py` | Update exports |
| `security/auditor/core.py` | Update DB usage |
| `security/auditor/__init__.py` | Update exports |
| `api/routes/security.py` | No change (uses auditor) |
| `tests/test_database.py` | Update for DuckDB |
| `tests/test_auditor.py` | Update mocks |
| `tests/mocks/security.py` | Update mock |
| `tests/conftest.py` | Update fixtures |
| `docs/structure.md` | Update architecture |
| `DEVELOPMENT.md` | Update architecture |

## SQL Syntax Changes

| SQLite | DuckDB |
|--------|--------|
| `INTEGER PRIMARY KEY AUTOINCREMENT` | `VARCHAR PRIMARY KEY` (use UUID) |
| `INSERT OR IGNORE` | `INSERT OR IGNORE` (same) |
| `INSERT OR REPLACE` | `INSERT OR REPLACE` (same) |
| `PRAGMA table_info()` | `DESCRIBE table` |

## Migration Strategy

**No data migration needed!**

- Clear `security_scanned` table
- Auditor will re-scan all part files
- Fresh start with DuckDB

## Acceptance Criteria

- [ ] All security data stored in `analytics.duckdb`
- [ ] `security.db` file no longer created/used
- [ ] All existing tests pass
- [ ] Security dashboard works correctly
- [ ] Auditor scans and stores data correctly
- [ ] Cross-domain queries possible (security ↔ sessions)

## Estimated Effort

| Task | Time |
|------|------|
| Phase 1: Schema | 1h |
| Phase 2: Repository | 3-4h |
| Phase 3: Auditor | 30min |
| Phase 4: Tests | 2h |
| Phase 5: Cleanup | 30min |
| **Total** | **~8h (1 day)** |

## Risks

| Risk | Mitigation |
|------|------------|
| Query syntax differences | DuckDB is SQLite-compatible for most queries |
| Performance regression | DuckDB is generally faster |
| Test complexity | Use in-memory DuckDB |

## Future Opportunities

Once migrated, we can:
1. JOIN security events with session data
2. Correlate commands with specific messages/parts
3. Build unified timeline (analytics + security)
4. Single backup/restore process
