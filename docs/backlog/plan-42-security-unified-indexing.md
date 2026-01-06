# Plan 42: Security Unified Indexing

## Objective

Unify security data loading with the existing bulk loader and file watcher, eliminating the separate security scanner process. The auditor would query DuckDB directly instead of maintaining its own scan loop.

## Current Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      CURRENT (Dual Path)                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  OpenCode Storage (prt_*.json files)                           │
│           │                                                     │
│           ├──────────────────┬──────────────────────────────────┤
│           │                  │                                  │
│           ▼                  ▼                                  │
│  ┌─────────────────┐  ┌─────────────────┐                      │
│  │  Bulk Loader /  │  │ Security Auditor │                      │
│  │  File Watcher   │  │ (separate loop)  │                      │
│  │                 │  │                  │                      │
│  │ - read_json()   │  │ - json.loads()   │                      │
│  │ - batch INSERT  │  │ - analyze risk   │                      │
│  │ - fast          │  │ - INSERT one by  │                      │
│  │                 │  │   one (slow)     │                      │
│  └────────┬────────┘  └────────┬─────────┘                      │
│           │                    │                                │
│           ▼                    ▼                                │
│  ┌─────────────────┐  ┌─────────────────┐                      │
│  │ parts, messages │  │ security_*      │                      │
│  │ sessions, etc.  │  │ tables          │                      │
│  └─────────────────┘  └─────────────────┘                      │
│                                                                 │
│  Problems:                                                      │
│  - Dual file reading (wasteful I/O)                            │
│  - Security scanner is slow (Python loop, 1 file at a time)    │
│  - Data duplication (command stored in parts AND security_*)   │
│  - Scan state tracking complexity                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Proposed Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    PROPOSED (Unified Path)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  OpenCode Storage (prt_*.json files)                           │
│           │                                                     │
│           ▼                                                     │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │              Unified Indexer (existing)                     ││
│  │                                                             ││
│  │  Bulk Loader:  DuckDB read_json() + batch INSERT            ││
│  │  File Watcher: Real-time single file INSERT                 ││
│  │                                                             ││
│  │  NEW: Extract security-relevant fields during indexing      ││
│  │       (command, file_path, url already in arguments JSON)   ││
│  └─────────────────────────────────────────────────────────────┘│
│           │                                                     │
│           ▼                                                     │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    DuckDB (unified)                         ││
│  │                                                             ││
│  │  parts table (enhanced):                                    ││
│  │  - id, message_id, tool_name, arguments (existing)          ││
│  │  - command (extracted from arguments)      ◄── NEW          ││
│  │  - file_path (extracted from arguments)    ◄── NEW          ││
│  │  - url (extracted from arguments)          ◄── NEW          ││
│  │                                                             ││
│  └─────────────────────────────────────────────────────────────┘│
│           │                                                     │
│           ▼                                                     │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │              Security Auditor (query-only)                  ││
│  │                                                             ││
│  │  Option A: Compute scores at query time (views/functions)   ││
│  │  Option B: Pre-compute scores during indexing               ││
│  │  Option C: Async enrichment worker                          ││
│  │                                                             ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Design Options

### Option A: Query-Time Computation (Views)

Compute risk scores dynamically using SQL views with regex patterns.

```sql
-- View that computes risk scores on-the-fly
CREATE VIEW security_commands_view AS
SELECT 
    p.id,
    p.session_id,
    p.tool_name,
    p.command,
    p.created_at,
    -- Risk scoring via CASE + regexp_matches
    CASE 
        WHEN regexp_matches(p.command, 'rm\s+-rf\s+/') THEN 90
        WHEN regexp_matches(p.command, 'curl.*\|.*sh') THEN 95
        WHEN regexp_matches(p.command, '(chmod|chown).*777') THEN 70
        WHEN regexp_matches(p.command, 'sudo\s+') THEN 50
        ELSE 0
    END AS risk_score,
    CASE 
        WHEN risk_score >= 80 THEN 'critical'
        WHEN risk_score >= 60 THEN 'high'
        WHEN risk_score >= 30 THEN 'medium'
        ELSE 'low'
    END AS risk_level
FROM parts p
WHERE p.tool_name = 'bash';
```

**Pros:**
- No data duplication
- Always up-to-date with latest data
- Pattern changes take effect immediately
- Simpler architecture

**Cons:**
- Complex patterns harder to express in SQL
- Performance concern for large datasets (need benchmarking)
- EDR correlation/sequences difficult (multi-row analysis)
- MITRE mapping complex in pure SQL

**Performance Estimate:**
- DuckDB regex is fast (vectorized)
- ~160k parts, filtered to ~20k bash commands
- Likely <100ms for simple queries
- Need to benchmark complex patterns

### Option B: Pre-Compute During Indexing

Add risk scoring to the indexing pipeline.

```python
# In bulk_loader.py / file_processor.py
def process_part(part_data):
    # Existing processing...
    
    # NEW: Compute security score
    if part_data.tool_name == 'bash':
        risk = analyzer.analyze_command(part_data.command)
        part_data.risk_score = risk.score
        part_data.risk_level = risk.level
        part_data.risk_reason = risk.reason
```

**Schema change:**
```sql
ALTER TABLE parts ADD COLUMN risk_score INTEGER DEFAULT 0;
ALTER TABLE parts ADD COLUMN risk_level VARCHAR DEFAULT 'low';
ALTER TABLE parts ADD COLUMN risk_reason VARCHAR;
ALTER TABLE parts ADD COLUMN mitre_techniques VARCHAR DEFAULT '[]';
```

**Pros:**
- Best query performance (pre-computed)
- Can use full Python analyzer (complex patterns, MITRE)
- EDR analysis possible during indexing

**Cons:**
- Couples indexer with security logic
- Need to re-index if patterns change
- Slight slowdown of indexing (adds analysis step)

### Option C: Async Enrichment Worker (Hybrid) ✓ RECOMMENDED

Index raw data fast, enrich asynchronously in background.

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  ┌──────────────┐                                              │
│  │ Bulk Loader  │──────┐                                       │
│  │ (~5000/sec)  │      │                                       │
│  └──────────────┘      │      ┌─────────────────────────────┐  │
│                        ├─────▶│      parts table            │  │
│  ┌──────────────┐      │      │                             │  │
│  │ File Watcher │──────┘      │  - id, tool_name, arguments │  │
│  │ (real-time)  │             │  - risk_score (NULL → val)  │  │
│  └──────────────┘             │  - risk_level (NULL → val)  │  │
│                               │  - security_enriched_at     │  │
│                               └──────────────┬──────────────┘  │
│                                              │                 │
│                                              │ Query unenriched│
│                                              ▼                 │
│                               ┌──────────────────────────────┐ │
│                               │   Enrichment Worker          │ │
│                               │                              │ │
│                               │   SELECT ... WHERE           │ │
│                               │     security_enriched_at     │ │
│                               │     IS NULL                  │ │
│                               │           │                  │ │
│                               │           ▼                  │ │
│                               │   Python analyzer            │ │
│                               │   (risk scoring, MITRE)      │ │
│                               │           │                  │ │
│                               │           ▼                  │ │
│                               │   UPDATE parts SET           │ │
│                               │     risk_score = ...         │ │
│                               └──────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Pros:**
- Fast initial indexing (unchanged)
- Decoupled concerns (indexer vs security)
- Can re-enrich without re-indexing
- Uses existing Python analyzer (proven, MITRE support)
- Similar to current architecture but unified storage

**Cons:**
- Small delay before scores available (~seconds for new parts)
- Need to track enrichment state (simple NULL check)

## Recommendation

**Option C (Async Enrichment Worker)** because:

1. **Preserves indexing speed** - bulk loader stays at ~5000 parts/sec
2. **Decoupled concerns** - indexer focuses on data, worker focuses on security
3. **Reuses existing analyzer** - proven Python code, MITRE mapping, complex patterns
4. **Similar to current architecture** - just better integrated with DuckDB
5. **Flexible** - can re-enrich without re-indexing if patterns change

**Key insight**: The current security auditor IS essentially an async enrichment worker, but it:
- Reads files again (wasteful I/O)
- Stores in separate tables (duplication)
- Tracks its own scan state (complexity)

The new worker would:
- Query `parts` table directly (no file I/O)
- Update `parts` table in place (no duplication)
- Use simple "is enriched?" column (simpler state)

## Implementation Plan (Option C: Async Enrichment)

### Phase 1: Schema Enhancement (1h)

Add security columns to `parts` table:

```sql
ALTER TABLE parts ADD COLUMN risk_score INTEGER;
ALTER TABLE parts ADD COLUMN risk_level VARCHAR;
ALTER TABLE parts ADD COLUMN risk_reason VARCHAR;
ALTER TABLE parts ADD COLUMN mitre_techniques VARCHAR;
ALTER TABLE parts ADD COLUMN security_enriched_at TIMESTAMP;

-- Index for fast filtering and finding unenriched parts
CREATE INDEX idx_parts_risk ON parts(risk_level, risk_score DESC);
CREATE INDEX idx_parts_unenriched ON parts(security_enriched_at) 
    WHERE security_enriched_at IS NULL;
```

### Phase 2: Create Security Enrichment Worker (3h)

New module `security/enrichment/worker.py`:

```python
class SecurityEnrichmentWorker:
    """Async worker that enriches parts with security scores.
    
    Queries unenriched parts from DuckDB, computes risk scores,
    and updates the parts table in batches.
    """
    
    def __init__(self, db: AnalyticsDB):
        self._db = db
        self._analyzer = get_risk_analyzer()
        self._running = False
        self._thread = None
    
    def start(self):
        """Start background enrichment thread."""
        self._running = True
        self._thread = Thread(target=self._enrichment_loop, daemon=True)
        self._thread.start()
    
    def _enrichment_loop(self):
        """Main loop: find unenriched parts, score them, update DB."""
        while self._running:
            enriched = self._enrich_batch(limit=500)
            if enriched == 0:
                time.sleep(5)  # Nothing to do, wait
            else:
                time.sleep(0.1)  # More work, continue quickly
    
    def _enrich_batch(self, limit: int = 500) -> int:
        """Enrich a batch of unenriched parts."""
        conn = self._db.connect()
        
        # Get unenriched parts (commands, reads, writes, webfetches)
        parts = conn.execute("""
            SELECT id, tool_name, 
                   arguments->>'command' as command,
                   arguments->>'filePath' as file_path,
                   arguments->>'url' as url
            FROM parts 
            WHERE security_enriched_at IS NULL
              AND tool_name IN ('bash', 'read', 'write', 'edit', 'webfetch')
            LIMIT ?
        """, [limit]).fetchall()
        
        if not parts:
            return 0
        
        # Compute scores
        updates = []
        for part_id, tool, command, file_path, url in parts:
            if tool == 'bash' and command:
                result = self._analyzer.analyze_command(command)
            elif tool in ('read',) and file_path:
                result = self._analyzer.analyze_file_path(file_path)
            elif tool in ('write', 'edit') and file_path:
                result = self._analyzer.analyze_file_path(file_path)
            elif tool == 'webfetch' and url:
                result = self._analyzer.analyze_url(url)
            else:
                result = RiskResult(0, 'low', '')
            
            updates.append((
                result.score, result.level, result.reason,
                json.dumps(result.mitre_techniques),
                datetime.now(), part_id
            ))
        
        # Batch update
        conn.executemany("""
            UPDATE parts SET 
                risk_score = ?, risk_level = ?, risk_reason = ?,
                mitre_techniques = ?, security_enriched_at = ?
            WHERE id = ?
        """, updates)
        
        return len(updates)
```

### Phase 3: Integrate Worker with App (1h)

Start enrichment worker alongside indexer in `app/core.py`:

```python
def __init__(self):
    # Existing...
    self._indexer = UnifiedIndexer()
    self._enrichment_worker = SecurityEnrichmentWorker(self._db)

def _start_services(self):
    self._indexer.start()
    self._enrichment_worker.start()  # NEW
```

### Phase 4: Simplify Security Auditor (2h)

Convert auditor to query-only (no more scanning):

```python
class SecurityAuditor:
    """Query-only security auditor - enrichment done by worker."""
    
    def __init__(self, db: AnalyticsDB):
        self._db = db
    
    def get_stats(self) -> dict:
        """Get security stats from parts table."""
        conn = self._db.connect()
        result = conn.execute("""
            SELECT 
                COUNT(*) FILTER (WHERE risk_level = 'critical') as critical,
                COUNT(*) FILTER (WHERE risk_level = 'high') as high,
                COUNT(*) FILTER (WHERE risk_level = 'medium') as medium,
                COUNT(*) FILTER (WHERE risk_level = 'low') as low,
                COUNT(*) FILTER (WHERE tool_name = 'bash') as total_commands,
                COUNT(*) FILTER (WHERE tool_name = 'read') as total_reads,
                COUNT(*) FILTER (WHERE tool_name IN ('write', 'edit')) as total_writes,
                COUNT(*) FILTER (WHERE tool_name = 'webfetch') as total_webfetches,
                COUNT(*) as total_scanned
            FROM parts 
            WHERE security_enriched_at IS NOT NULL
        """).fetchone()
        return dict(zip([...], result))
    
    def get_critical_commands(self, limit=50):
        """Query pre-computed risk scores from parts table."""
        return self._db.execute("""
            SELECT id, session_id, tool_name as tool, 
                   arguments->>'command' as command,
                   risk_score, risk_level, risk_reason, created_at
            FROM parts 
            WHERE tool_name = 'bash' 
              AND risk_level IN ('critical', 'high')
              AND security_enriched_at IS NOT NULL
            ORDER BY risk_score DESC, created_at DESC
            LIMIT ?
        """, [limit]).fetchall()
```

### Phase 5: Cleanup (1h)

1. Remove `security_scanned` table
2. Remove `security_commands/reads/writes/webfetches/stats` tables
3. Update API routes to use new auditor
4. Update tests
5. Optionally delete old `security.db` file

### Phase 6: EDR Correlation (Optional, 2h)

Keep existing correlation logic but query from `parts` table instead.

## Files to Modify

| File | Change |
|------|--------|
| `analytics/db.py` | Add risk columns to parts schema |
| `security/enrichment/worker.py` | NEW - Async enrichment worker |
| `security/enrichment/__init__.py` | NEW - Module exports |
| `security/auditor/core.py` | Convert to query-only |
| `security/db/repository.py` | Remove (no longer needed) |
| `app/core.py` | Start enrichment worker |
| `api/routes/security.py` | Query parts table |
| `dashboard/sections/security.py` | Update if needed |

## Migration Strategy

1. **Add columns** to parts table (non-breaking)
2. **Deploy new indexer** that enriches data
3. **Backfill** existing parts with risk scores (one-time job)
4. **Switch auditor** to query-only mode
5. **Remove** old security tables

## Performance Considerations

### Indexing Impact

**None!** Bulk loader stays at ~5000 parts/sec - enrichment is decoupled.

### Enrichment Worker Performance

Estimated: ~500-1000 parts/sec for enrichment
- Python analyzer with regex patterns
- Batch updates (500 at a time)
- Background thread, non-blocking

For 160k parts: ~3-5 minutes for full enrichment (one-time backfill)
New parts: Enriched within seconds of indexing

### Query Performance

```sql
-- Fast with idx_parts_risk index
SELECT * FROM parts 
WHERE risk_level IN ('critical', 'high')
ORDER BY risk_score DESC
LIMIT 100;

-- Fast with idx_parts_unenriched index
SELECT * FROM parts
WHERE security_enriched_at IS NULL
LIMIT 500;
```

## Acceptance Criteria

- [ ] Parts table has risk_score, risk_level columns
- [ ] Bulk loader enriches security data during indexing
- [ ] File watcher enriches security data in real-time
- [ ] Security auditor queries parts table (no scan loop)
- [ ] Old security_* tables removed
- [ ] Performance acceptable (<500ms for security dashboard)
- [ ] All existing tests pass
- [ ] Security dashboard shows same data quality

## Estimated Effort

| Phase | Time |
|-------|------|
| Phase 1: Schema Enhancement | 1h |
| Phase 2: Enrichment Worker | 3h |
| Phase 3: App Integration | 1h |
| Phase 4: Query-Only Auditor | 2h |
| Phase 5: Cleanup | 1h |
| Phase 6: EDR (optional) | 2h |
| **Total** | **8-10h** |

## Open Questions

1. **Pattern updates**: If risk patterns change, do we need to re-score all parts?
   - Option: Store pattern version, re-score on mismatch
   - Option: Accept stale scores, only new data uses new patterns
   - Option: Add "re-enrich" command that clears `security_enriched_at`

2. **File operations**: Currently we have `security_file_reads/writes`. 
   - Parts already has `file_path` in arguments JSON
   - Just need to extract with `arguments->>'filePath'`

3. **EDR sequences**: Complex multi-event analysis
   - Keep existing correlator logic
   - Query from parts table instead of security_* tables
   - May need session-level aggregation table

4. **Dashboard compatibility**: Ensure API response format unchanged
   - Auditor API should return same structure
   - May need adapter layer during migration

5. **Backfill strategy**: How to enrich existing 160k parts?
   - Option: Let worker process them naturally (3-5 min)
   - Option: One-time batch script for faster backfill
