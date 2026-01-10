# Database Migrations

This directory contains database schema migrations for the analytics database.

## Migration 001: Add error_data JSON column

**Story**: DQ-005 - Migrate error_data from VARCHAR to JSON  
**Date**: 2026-01-10  
**Status**: ✅ Complete

### Overview

Adds `error_data` column to the `parts` table as JSON type to enable structured error analytics.

### Changes

1. **Schema**: Added `parts.error_data` column as JSON type
2. **Parser**: Updated `FileParser.parse_part()` to structure error data as JSON
3. **Indexer**: Updated `handlers.py` and `queries.py` to insert error_data

### Structured Error Format

```json
{
  "error_type": "timeout|auth|network|syntax|not_found|unknown",
  "error_message": "Error message text",
  "tool_name": "tool that errored",
  "tool_status": "error status",
  "timestamp": "ISO 8601 timestamp",
  "error_code": 400,  // Optional HTTP-style code
  "stack_trace": "..." // Optional stack trace
}
```

### Error Type Detection

The parser automatically detects error types from error messages:

- **timeout**: "timeout" in message → 408
- **auth**: "auth" or "permission" in message → 403
- **network**: "network" or "connection" in message → 500
- **syntax**: "syntax" or "parse" in message → 400
- **not_found**: "not found" in message → 404
- **unknown**: Default fallback

### Running the Migration

```bash
# Apply migration
python -m opencode_monitor.analytics.migrations.001_add_error_data_json

# Rollback (if needed)
python -m opencode_monitor.analytics.migrations.001_add_error_data_json --rollback
```

### Testing

```bash
# Run test suite
python scripts/test_error_data_json.py
```

### JSON Query Examples

```sql
-- Get error types distribution
SELECT 
    error_data->>'error_type' as error_type,
    COUNT(*) as count
FROM parts 
WHERE error_data IS NOT NULL
GROUP BY error_type
ORDER BY count DESC;

-- Find timeout errors
SELECT 
    id,
    tool_name,
    error_data->>'error_message' as message,
    error_data->>'error_code' as code
FROM parts
WHERE error_data->>'error_type' = 'timeout';

-- Get all error codes
SELECT DISTINCT
    error_data->>'error_code' as error_code
FROM parts
WHERE error_data IS NOT NULL
ORDER BY error_code;
```

### Backward Compatibility

- `error_message` column is retained for backward compatibility
- Both columns are populated during indexing
- Existing code using `error_message` continues to work

### Migration Safety

1. ✅ Backs up existing error_message data to `parts_error_backup` table
2. ✅ Idempotent - safe to run multiple times
3. ✅ Validates migration success before completing
4. ✅ Provides rollback procedure
5. ✅ Tests JSON query functionality

### Files Modified

- `src/opencode_monitor/analytics/db.py` - Added error_data column to schema
- `src/opencode_monitor/analytics/indexer/parsers.py` - Structure error data
- `src/opencode_monitor/analytics/indexer/handlers.py` - Insert error_data
- `src/opencode_monitor/analytics/indexer/queries.py` - Bulk load error_data
- `src/opencode_monitor/analytics/migrations/001_add_error_data_json.py` - Migration script
- `scripts/test_error_data_json.py` - Test suite

## Future Migrations

Add new migration scripts as `00X_description.py` with:
- Backup procedure
- Migration logic
- Verification tests
- Rollback procedure
- Documentation in this README
