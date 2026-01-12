"""SQL queries for bulk loading OpenCode data into DuckDB.

This module contains SQL templates used by BulkLoader to efficiently load
JSON files directly into DuckDB using read_json_auto().

Query templates use placeholders:
- {path}: Path to JSON files directory
- {time_filter}: Optional WHERE clause for time-based filtering
"""

# Template for loading sessions from JSON files
LOAD_SESSIONS_SQL = """
INSERT OR REPLACE INTO sessions (
    id, project_id, directory, title, parent_id, version,
    additions, deletions, files_changed, created_at, updated_at
)
SELECT 
    id,
    projectID as project_id,
    directory,
    title,
    parentID as parent_id,
    version,
    COALESCE(summary.additions, 0) as additions,
    COALESCE(summary.deletions, 0) as deletions,
    COALESCE(summary.files, 0) as files_changed,
    to_timestamp(time.created / 1000.0) as created_at,
    to_timestamp(time.updated / 1000.0) as updated_at
FROM read_json_auto('{path}/**/*.json',
    maximum_object_size=10485760,
    ignore_errors=true
)
{time_filter}
"""

# Template for loading messages from JSON files
# IMPORTANT: Uses explicit columns schema to ensure 'summary' struct exists even if
# some JSON files don't have it. Without this, DuckDB fails with "column not found" error.
# Plan 45+: Added summary_title (the "hook" - auto-generated title for each message)
# Plan 45+: Added error_name, error_data, root_path for complete data loading
LOAD_MESSAGES_SQL = """
INSERT OR REPLACE INTO messages (
    id, session_id, parent_id, role, agent, model_id, provider_id,
    mode, cost, finish_reason, working_dir,
    tokens_input, tokens_output, tokens_reasoning,
    tokens_cache_read, tokens_cache_write, created_at, completed_at,
    summary_title, error_name, error_data, root_path
)
SELECT 
    id,
    sessionID as session_id,
    parentID as parent_id,
    role,
    agent,
    COALESCE(modelID, model.modelID) as model_id,
    COALESCE(providerID, model.providerID) as provider_id,
    mode,
    cost,
    finish as finish_reason,
    TRY(path.cwd) as working_dir,
    COALESCE(tokens."input", 0) as tokens_input,
    COALESCE(tokens.output, 0) as tokens_output,
    COALESCE(tokens.reasoning, 0) as tokens_reasoning,
    COALESCE(tokens."cache".read, 0) as tokens_cache_read,
    COALESCE(tokens."cache".write, 0) as tokens_cache_write,
    to_timestamp(time.created / 1000.0) as created_at,
    to_timestamp(time.completed / 1000.0) as completed_at,
    -- Plan 45+: summary_title is the "hook" - auto-generated title for each prompt
    TRY(summary.title) as summary_title,
    -- Plan 45+: Error information
    TRY(error.name) as error_name,
    TRY(CAST(error.data AS VARCHAR)) as error_data,
    -- Plan 45+: Project root path
    TRY(path.root) as root_path
FROM read_json_auto('{path}/**/*.json',
    maximum_object_size=10485760,
    ignore_errors=true,
    union_by_name=true,
    columns={{
        'id': 'VARCHAR',
        'sessionID': 'VARCHAR',
        'parentID': 'VARCHAR',
        'role': 'VARCHAR',
        'agent': 'VARCHAR',
        'modelID': 'VARCHAR',
        'providerID': 'VARCHAR',
        'model': 'STRUCT(modelID VARCHAR, providerID VARCHAR)',
        'mode': 'VARCHAR',
        'cost': 'DOUBLE',
        'finish': 'VARCHAR',
        'path': 'STRUCT(cwd VARCHAR, root VARCHAR)',
        'tokens': 'STRUCT("input" BIGINT, output BIGINT, reasoning BIGINT, "cache" STRUCT(read BIGINT, write BIGINT))',
        'time': 'STRUCT(created BIGINT, completed BIGINT)',
        'summary': 'STRUCT(title VARCHAR)',
        'error': 'STRUCT(name VARCHAR, data JSON)'
    }}
)
{time_filter}
"""

# Template for loading parts from JSON files
# IMPORTANT: Uses read_text + TRY(::JSON) to handle malformed JSON files gracefully.
# DuckDB's read_json_auto with ignore_errors=true does NOT work for standard JSON format,
# only for newline_delimited. This approach reads files as text, then parses JSON with TRY()
# which returns NULL for any parsing errors, effectively skipping corrupted files.
# NOTE: state.metadata.sessionId is extracted for task delegations to link child sessions.
# Plan 34: Enriched columns added - reasoning_text, anthropic_signature, compaction_auto, file_mime, file_name
# Plan 45+: Added file_url for complete file part data
LOAD_PARTS_SQL = """
INSERT OR REPLACE INTO parts (
    id, session_id, message_id, part_type, content, tool_name, tool_status,
    call_id, created_at, ended_at, duration_ms, arguments, error_message, error_data, child_session_id,
    reasoning_text, anthropic_signature, compaction_auto, file_mime, file_name, file_url,
    result_summary, cost, tokens_input, tokens_output, tokens_reasoning, 
    tokens_cache_read, tokens_cache_write, tool_title
)
SELECT 
    json_extract_string(j, '$.id') as id,
    json_extract_string(j, '$.sessionID') as session_id,
    json_extract_string(j, '$.messageID') as message_id,
    json_extract_string(j, '$.type') as part_type,
    json_extract_string(j, '$.text') as content,
    json_extract_string(j, '$.tool') as tool_name,
    json_extract_string(j, '$.state.status') as tool_status,
    json_extract_string(j, '$.callID') as call_id,
    -- Use state.time for tool parts, time for others
    COALESCE(
        to_timestamp(CAST(json_extract(j, '$.state.time.start') AS BIGINT) / 1000.0),
        to_timestamp(CAST(json_extract(j, '$.time.start') AS BIGINT) / 1000.0)
    ) as created_at,
    COALESCE(
        to_timestamp(CAST(json_extract(j, '$.state.time.end') AS BIGINT) / 1000.0),
        to_timestamp(CAST(json_extract(j, '$.time.end') AS BIGINT) / 1000.0)
    ) as ended_at,
    CASE 
        WHEN json_extract(j, '$.state.time.end') IS NOT NULL AND json_extract(j, '$.state.time.start') IS NOT NULL 
        THEN CAST(json_extract(j, '$.state.time.end') AS BIGINT) - CAST(json_extract(j, '$.state.time.start') AS BIGINT)
        WHEN json_extract(j, '$.time.end') IS NOT NULL AND json_extract(j, '$.time.start') IS NOT NULL 
        THEN CAST(json_extract(j, '$.time.end') AS BIGINT) - CAST(json_extract(j, '$.time.start') AS BIGINT)
        ELSE NULL 
    END as duration_ms,
    CAST(json_extract(j, '$.state.input') AS VARCHAR) as arguments,
    json_extract_string(j, '$.state.error') as error_message,
    CAST(json_extract(j, '$.state') AS VARCHAR) as error_data,
    -- Extract child_session_id from state.metadata.sessionId for task delegations
    json_extract_string(j, '$.state.metadata.sessionId') as child_session_id,
    -- Plan 34: Enriched columns
    -- reasoning_text: extract from 'reasoning' (Claude extended thinking) or 'text' (OpenCode format)
    -- NULLIF handles empty strings so COALESCE can fall back properly
    CASE WHEN json_extract_string(j, '$.type') = 'reasoning' 
         THEN COALESCE(NULLIF(json_extract_string(j, '$.reasoning'), ''), json_extract_string(j, '$.text')) 
         ELSE NULL END as reasoning_text,
    -- anthropic_signature: extract from metadata.anthropic.signature
    json_extract_string(j, '$.metadata.anthropic.signature') as anthropic_signature,
    -- compaction_auto: extract auto flag when type='compaction'
    CASE WHEN json_extract_string(j, '$.type') = 'compaction' 
         THEN COALESCE(CAST(json_extract(j, '$.auto') AS BOOLEAN), FALSE) ELSE NULL END as compaction_auto,
    -- file_mime: extract mime when type='file'
    CASE WHEN json_extract_string(j, '$.type') = 'file' 
         THEN json_extract_string(j, '$.mime') ELSE NULL END as file_mime,
    -- file_name: extract filename when type='file'
    CASE WHEN json_extract_string(j, '$.type') = 'file' 
         THEN json_extract_string(j, '$.filename') ELSE NULL END as file_name,
    -- file_url: extract base64 data URL when type='file'
    CASE WHEN json_extract_string(j, '$.type') = 'file' 
         THEN json_extract_string(j, '$.url') ELSE NULL END as file_url,
    -- Plan 45: result_summary - FULL tool output, NO TRUNCATION
    CAST(json_extract(j, '$.state.output') AS VARCHAR) as result_summary,
    -- Plan 45+: Additional data completeness fields
    CAST(json_extract(j, '$.cost') AS DOUBLE) as cost,
    CAST(json_extract(j, '$.tokens.input') AS INTEGER) as tokens_input,
    CAST(json_extract(j, '$.tokens.output') AS INTEGER) as tokens_output,
    CAST(json_extract(j, '$.tokens.reasoning') AS INTEGER) as tokens_reasoning,
    CAST(json_extract(j, '$.tokens.cache.read') AS INTEGER) as tokens_cache_read,
    CAST(json_extract(j, '$.tokens.cache.write') AS INTEGER) as tokens_cache_write,
    json_extract_string(j, '$.state.title') as tool_title
FROM (
    SELECT TRY(content::JSON) as j
    FROM read_text('{path}/**/*.json')
)
WHERE j IS NOT NULL
  AND json_extract_string(j, '$.id') IS NOT NULL
"""

# Query for creating root traces for sessions without parent
# DQ-001: Aggregate tokens from messages instead of hardcoding 0
# Tokens are initially 0 but will be backfilled by backfill_missing_tokens()
# after messages are indexed
CREATE_ROOT_TRACES_SQL = """
INSERT OR REPLACE INTO agent_traces (
    trace_id, session_id, parent_trace_id, parent_agent, subagent_type,
    prompt_input, prompt_output, started_at, ended_at, duration_ms,
    tokens_in, tokens_out, status, child_session_id
)
SELECT 
    'root_' || s.id as trace_id,
    s.id as session_id,
    NULL as parent_trace_id,
    NULL as parent_agent,
    'user' as subagent_type,
    s.title as prompt_input,
    NULL as prompt_output,
    s.created_at as started_at,
    s.updated_at as ended_at,
    CASE 
        WHEN s.updated_at IS NOT NULL AND s.created_at IS NOT NULL 
        THEN CAST(EXTRACT(EPOCH FROM (s.updated_at - s.created_at)) * 1000 AS INTEGER)
        ELSE NULL 
    END as duration_ms,
    COALESCE(token_agg.total_in, 0) as tokens_in,
    COALESCE(token_agg.total_out, 0) as tokens_out,
    'completed' as status,
    s.id as child_session_id
FROM sessions s
LEFT JOIN (
    SELECT 
        session_id,
        SUM(tokens_input) as total_in,
        SUM(tokens_output) as total_out
    FROM messages
    GROUP BY session_id
) token_agg ON token_agg.session_id = s.id
WHERE s.parent_id IS NULL
"""

# Query for counting root traces
COUNT_ROOT_TRACES_SQL = """
SELECT COUNT(*) FROM agent_traces WHERE trace_id LIKE 'root_%'
"""

# Query for creating delegation traces from task parts
# NOTE: child_session_id is now extracted directly from state.metadata.sessionId
# during parts loading (not from arguments which contains state.input)
CREATE_DELEGATION_TRACES_SQL = """
INSERT OR IGNORE INTO agent_traces (
    trace_id, session_id, parent_trace_id, parent_agent, subagent_type,
    prompt_input, prompt_output, started_at, ended_at, duration_ms,
    tokens_in, tokens_out, status, child_session_id
)
SELECT 
    'del_' || p.id as trace_id,
    p.session_id,
    'root_' || p.session_id as parent_trace_id,
    m.agent as parent_agent,
    COALESCE(
        json_extract_string(p.arguments, '$.subagent_type'),
        'task'
    ) as subagent_type,
    COALESCE(
        json_extract_string(p.arguments, '$.prompt'),
        json_extract_string(p.arguments, '$.description'),
        ''
    ) as prompt_input,
    NULL as prompt_output,
    p.created_at as started_at,
    p.ended_at as ended_at,
    p.duration_ms,
    0 as tokens_in,
    0 as tokens_out,
    CASE p.tool_status
        WHEN 'completed' THEN 'completed'
        WHEN 'error' THEN 'error'
        ELSE 'running'
    END as status,
    p.child_session_id as child_session_id
FROM parts p
LEFT JOIN messages m ON p.message_id = m.id
WHERE p.tool_name = 'task'
  AND p.tool_status IS NOT NULL
  AND p.created_at IS NOT NULL
"""

# Query for counting delegation traces
COUNT_DELEGATION_TRACES_SQL = """
SELECT COUNT(*) FROM agent_traces WHERE trace_id LIKE 'del_%'
"""

# Template for loading step events (step-start, step-finish) into step_events table
# These are parts with type='step-start' or type='step-finish'
# Uses read_text + TRY(::JSON) to handle malformed JSON files gracefully.
LOAD_STEP_EVENTS_SQL = """
INSERT OR REPLACE INTO step_events (
    id, session_id, message_id, event_type, reason, snapshot_hash,
    cost, tokens_input, tokens_output, tokens_reasoning,
    tokens_cache_read, tokens_cache_write, created_at
)
SELECT 
    json_extract_string(j, '$.id') as id,
    json_extract_string(j, '$.sessionID') as session_id,
    json_extract_string(j, '$.messageID') as message_id,
    CASE json_extract_string(j, '$.type')
        WHEN 'step-start' THEN 'start'
        WHEN 'step-finish' THEN 'finish'
    END as event_type,
    json_extract_string(j, '$.reason') as reason,
    json_extract_string(j, '$.snapshot') as snapshot_hash,
    COALESCE(CAST(json_extract(j, '$.cost') AS DOUBLE), 0) as cost,
    COALESCE(CAST(json_extract(j, '$.tokens.input') AS BIGINT), 0) as tokens_input,
    COALESCE(CAST(json_extract(j, '$.tokens.output') AS BIGINT), 0) as tokens_output,
    COALESCE(CAST(json_extract(j, '$.tokens.reasoning') AS BIGINT), 0) as tokens_reasoning,
    COALESCE(CAST(json_extract(j, '$.tokens.cacheRead') AS BIGINT), 0) as tokens_cache_read,
    COALESCE(CAST(json_extract(j, '$.tokens.cacheWrite') AS BIGINT), 0) as tokens_cache_write,
    COALESCE(
        to_timestamp(CAST(json_extract(j, '$.time.start') AS BIGINT) / 1000.0),
        to_timestamp(CAST(json_extract(j, '$.time.created') AS BIGINT) / 1000.0)
    ) as created_at
FROM (
    SELECT TRY(content::JSON) as j
    FROM read_text('{path}/**/*.json')
)
WHERE j IS NOT NULL
  AND json_extract_string(j, '$.type') IN ('step-start', 'step-finish')
"""

# Template for loading patches into patches table
# These are parts with type='patch'
# Uses read_text + TRY(::JSON) to handle malformed JSON files gracefully.
LOAD_PATCHES_SQL = """
INSERT OR REPLACE INTO patches (
    id, session_id, message_id, git_hash, files, created_at
)
SELECT 
    json_extract_string(j, '$.id') as id,
    json_extract_string(j, '$.sessionID') as session_id,
    json_extract_string(j, '$.messageID') as message_id,
    json_extract_string(j, '$.hash') as git_hash,
    COALESCE(CAST(json_extract(j, '$.files') AS VARCHAR[]), ARRAY[]::VARCHAR[]) as files,
    to_timestamp(CAST(json_extract(j, '$.time.start') AS BIGINT) / 1000.0) as created_at
FROM (
    SELECT TRY(content::JSON) as j
    FROM read_text('{path}/**/*.json')
)
WHERE j IS NOT NULL
  AND json_extract_string(j, '$.type') = 'patch' 
  AND json_extract_string(j, '$.hash') IS NOT NULL
"""

# Template for loading file operations (read/write/edit) into file_operations table
# Extracts file path from state.input.filePath or state.input.path
LOAD_FILE_OPERATIONS_SQL = """
INSERT OR REPLACE INTO file_operations (
    id, session_id, trace_id, operation, file_path, timestamp, risk_level, risk_reason
)
SELECT 
    json_extract_string(j, '$.id') as id,
    json_extract_string(j, '$.sessionID') as session_id,
    NULL as trace_id,
    json_extract_string(j, '$.tool') as operation,
    COALESCE(
        json_extract_string(j, '$.state.input.filePath'),
        json_extract_string(j, '$.state.input.path')
    ) as file_path,
    COALESCE(
        to_timestamp(CAST(json_extract(j, '$.state.time.start') AS BIGINT) / 1000.0),
        to_timestamp(CAST(json_extract(j, '$.time.start') AS BIGINT) / 1000.0)
    ) as timestamp,
    'normal' as risk_level,
    NULL as risk_reason
FROM (
    SELECT TRY(content::JSON) as j
    FROM read_text('{path}/**/*.json')
)
WHERE j IS NOT NULL
  AND json_extract_string(j, '$.tool') IN ('read', 'write', 'edit')
  AND COALESCE(
      json_extract_string(j, '$.state.input.filePath'),
      json_extract_string(j, '$.state.input.path')
  ) IS NOT NULL
"""
