# Test Data Builders

Fluent API for creating test data with sensible defaults.

## Quick Start

```python
from tests.builders import SessionBuilder, MessageBuilder, TraceBuilder

# Create a session dict
session = SessionBuilder().with_title("My Test").build()

# Create and insert into database
session_id = SessionBuilder(db).with_tokens(1000, 500).insert()

# Create trace tree
tree = (TraceBuilder()
    .with_root("sess-001", "Main")
    .add_delegation("trace-001", "executor")
    .build())
```

## Using Fixtures

The builders are available as pytest fixtures in `conftest.py`:

```python
def test_with_builders(session_builder, message_builder):
    """Fixtures come pre-configured with database."""
    session_id = session_builder.with_title("Test").insert()
    message_id = message_builder.for_session(session_id).insert()
    # ...assertions
```

## SessionBuilder

Creates session test data (dicts, JSON files, or DB records).

### Methods

| Method | Description |
|--------|-------------|
| `with_id(id)` | Set session ID |
| `with_title(title)` | Set session title |
| `with_directory(dir)` | Set working directory |
| `with_tokens(in, out, cache_read, cache_write)` | Set token counts |
| `with_parent(parent_id)` | Set parent session (for sub-sessions) |
| `with_git_stats(add, del, files)` | Set git metrics |
| `with_timestamps(created, updated)` | Set timestamps |

### Output Methods

| Method | Description |
|--------|-------------|
| `build()` | Returns dict |
| `build_json()` | Returns OpenCode JSON format |
| `insert()` | Inserts into database, returns ID |
| `write_file(path)` | Writes JSON file to storage |

### Example

```python
# Create with custom tokens and git stats
session = (SessionBuilder()
    .with_id("sess-custom")
    .with_title("Feature Implementation")
    .with_tokens(2000, 1000, cache_read=500)
    .with_git_stats(additions=100, deletions=20, files_changed=5)
    .build())
```

## MessageBuilder

Creates message test data.

### Methods

| Method | Description |
|--------|-------------|
| `with_id(id)` | Set message ID |
| `for_session(session_id)` | Set parent session |
| `with_agent(agent)` | Set agent type |
| `with_role(role)` | Set message role |
| `with_model(model_id, provider)` | Set model info |
| `with_tokens(in, out, reasoning, cache_read, cache_write)` | Set tokens |
| `as_user()` | Configure as user message |
| `as_assistant(agent)` | Configure as assistant message |

### Example

```python
# Create assistant message with custom agent
message = (MessageBuilder()
    .for_session("sess-001")
    .as_assistant("executor")
    .with_tokens(500, 250)
    .build())
```

## TraceBuilder

Creates trace tree hierarchies (sessions with delegations).

### Methods

| Method | Description |
|--------|-------------|
| `with_root(session_id, title, directory)` | Set root session |
| `add_delegation(trace_id, subagent_type, ...)` | Add delegation under root |
| `add_child_delegation(parent, trace_id, ...)` | Add nested delegation |
| `add_message(trace_id, message_id, ...)` | Add message to trace |

### Example

```python
# Create complex trace tree
tree = (TraceBuilder()
    .with_root("sess-001", "Complex Session")
    .add_delegation("trace-001", "coordinator", tokens_in=1000)
    .add_child_delegation("trace-001", "trace-002", "executor")
    .add_child_delegation("trace-001", "trace-003", "tester")
    .add_message("trace-002", "msg-001")
    .build())

# Access parts
print(tree["session"])   # Root session info
print(tree["traces"])    # List of traces
print(tree["messages"])  # List of messages
```

## When to Use Builders vs Factories

| Scenario | Use |
|----------|-----|
| Simple test data with defaults | Factories in `tests/mocks/models.py` |
| Custom data with many options | Builders |
| Database insertion needed | Builders with `insert()` |
| File system testing | Builders with `write_file()` |
| Complex hierarchical data | `TraceBuilder` |

## Migration Guide

### Before (manual helper functions)

```python
def test_old_style(analytics_db):
    insert_session(db, "sess-001", datetime.now(), title="Test")
    insert_message(db, "msg-001", "sess-001", datetime.now(), agent="exec")
```

### After (builders)

```python
def test_new_style(session_builder, message_builder):
    sess_id = session_builder.with_title("Test").insert()
    msg_id = message_builder.for_session(sess_id).as_assistant("exec").insert()
```
