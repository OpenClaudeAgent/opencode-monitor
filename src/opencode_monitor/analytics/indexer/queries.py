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
LOAD_MESSAGES_SQL = """
INSERT OR REPLACE INTO messages (
    id, session_id, parent_id, role, agent, model_id, provider_id,
    mode, cost, finish_reason, working_dir,
    tokens_input, tokens_output, tokens_reasoning,
    tokens_cache_read, tokens_cache_write, created_at, completed_at
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
    path.cwd as working_dir,
    COALESCE(tokens."input", 0) as tokens_input,
    COALESCE(tokens.output, 0) as tokens_output,
    COALESCE(tokens.reasoning, 0) as tokens_reasoning,
    COALESCE(tokens."cache".read, 0) as tokens_cache_read,
    COALESCE(tokens."cache".write, 0) as tokens_cache_write,
    to_timestamp(time.created / 1000.0) as created_at,
    to_timestamp(time.completed / 1000.0) as completed_at
FROM read_json_auto('{path}/**/*.json',
    maximum_object_size=10485760,
    ignore_errors=true
)
{time_filter}
"""

# Template for loading parts from JSON files
# IMPORTANT: Uses explicit columns schema to ensure both 'time' and 'state.time'
# columns exist even if some JSON files don't have them. Without this, DuckDB fails
# with "column not found" error when referencing missing struct keys.
LOAD_PARTS_SQL = """
INSERT OR REPLACE INTO parts (
    id, session_id, message_id, part_type, content, tool_name, tool_status,
    call_id, created_at, ended_at, duration_ms, arguments, error_message
)
SELECT 
    id,
    sessionID as session_id,
    messageID as message_id,
    type as part_type,
    text as content,
    tool as tool_name,
    TRY(state.status) as tool_status,
    callID as call_id,
    -- Use state.time for tool parts, time for others
    -- TRY() handles NULL values, explicit schema handles missing columns
    COALESCE(
        to_timestamp(TRY(state."time"."start") / 1000.0),
        to_timestamp(TRY("time"."start") / 1000.0)
    ) as created_at,
    COALESCE(
        to_timestamp(TRY(state."time"."end") / 1000.0),
        to_timestamp(TRY("time"."end") / 1000.0)
    ) as ended_at,
    CASE 
        WHEN TRY(state."time"."end") IS NOT NULL AND TRY(state."time"."start") IS NOT NULL 
        THEN (TRY(state."time"."end") - TRY(state."time"."start")) 
        WHEN TRY("time"."end") IS NOT NULL AND TRY("time"."start") IS NOT NULL 
        THEN (TRY("time"."end") - TRY("time"."start")) 
        ELSE NULL 
    END as duration_ms,
    to_json(TRY(state."input")) as arguments,
    NULL as error_message
FROM read_json_auto('{path}/**/*.json',
    maximum_object_size=10485760,
    ignore_errors=true,
    union_by_name=true,
    columns={{
        'id': 'VARCHAR',
        'sessionID': 'VARCHAR',
        'messageID': 'VARCHAR',
        'type': 'VARCHAR',
        'text': 'VARCHAR',
        'tool': 'VARCHAR',
        'callID': 'VARCHAR',
        'state': 'STRUCT(status VARCHAR, "input" JSON, "time" STRUCT("start" BIGINT, "end" BIGINT))',
        'time': 'STRUCT("start" BIGINT, "end" BIGINT)'
    }}
)
"""

# Query for creating root traces for sessions without parent
CREATE_ROOT_TRACES_SQL = """
INSERT OR IGNORE INTO agent_traces (
    trace_id, session_id, parent_trace_id, parent_agent, subagent_type,
    prompt_input, prompt_output, started_at, ended_at, duration_ms,
    tokens_in, tokens_out, status, child_session_id
)
SELECT 
    'root_' || id as trace_id,
    id as session_id,
    NULL as parent_trace_id,
    NULL as parent_agent,
    'user' as subagent_type,
    title as prompt_input,
    NULL as prompt_output,
    created_at as started_at,
    updated_at as ended_at,
    NULL as duration_ms,
    0 as tokens_in,
    0 as tokens_out,
    'completed' as status,
    id as child_session_id
FROM sessions
WHERE parent_id IS NULL
"""

# Query for counting root traces
COUNT_ROOT_TRACES_SQL = """
SELECT COUNT(*) FROM agent_traces WHERE trace_id LIKE 'root_%'
"""

# Query for creating delegation traces from task parts
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
    json_extract_string(p.arguments, '$.session_id') as child_session_id
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
