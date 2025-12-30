# Development Guide

## Quick Start

```bash
# Run the app
make run

# Run tests
make test

# Run tests with coverage
make coverage
```

## Architecture

### Single App Architecture

OpenCode Monitor is a native macOS menu bar app built with [rumps](https://github.com/jaredks/rumps).

```
┌─────────────────────────────────────────────┐
│           OpenCodeApp (rumps.App)           │
│                                             │
│  ┌─────────────────┐  ┌──────────────────┐  │
│  │ Background      │  │ UI Thread        │  │
│  │ Thread          │  │ (main)           │  │
│  │                 │  │                  │  │
│  │ - fetch state   │  │ - build menu     │  │
│  │ - fetch usage   │──▶ - update title   │  │
│  │ - security scan │  │ - handle clicks  │  │
│  └─────────────────┘  └──────────────────┘  │
│                                             │
│  State: self._state, self._usage (in-memory)│
└─────────────────────────────────────────────┘
```

### Key Components

| Module | Purpose |
|--------|---------|
| `app.py` | Main rumps application, orchestration |
| `core/monitor.py` | Async detection of OpenCode instances |
| `core/usage.py` | Claude API usage fetching |
| `core/models.py` | Data classes (State, Agent, etc.) |
| `core/client.py` | OpenCode HTTP client |
| `security/analyzer.py` | Risk analysis for commands/files/URLs |
| `security/auditor.py` | Background security scanner |
| `security/db/` | SQLite storage for audit data |
| `analytics/db.py` | DuckDB database for analytics |
| `analytics/loader.py` | OpenCode JSON data loader |
| `analytics/queries.py` | Analytics queries (periods, agents, tools) |
| `analytics/report.py` | Report generation |
| `ui/menu.py` | Menu construction |
| `utils/settings.py` | Preferences persistence |

## Adding Features

### Add a New Setting

1. Add field to `Settings` dataclass in `utils/settings.py`:
```python
@dataclass
class Settings:
    usage_refresh_interval: int = 60
    my_new_setting: bool = False  # Add here
```

2. Add UI in `app.py` `_build_static_menu()`:
```python
my_item = rumps.MenuItem("My Setting", callback=self._toggle_my_setting)
my_item.state = 1 if settings.my_new_setting else 0
prefs_menu.add(my_item)
```

3. Add callback:
```python
def _toggle_my_setting(self, sender):
    settings = get_settings()
    settings.my_new_setting = not settings.my_new_setting
    save_settings()
    sender.state = 1 if settings.my_new_setting else 0
```

### Add New Data to State

1. Add field to model in `core/models.py`:
```python
@dataclass
class Agent:
    # ... existing fields
    my_field: str = ""
```

2. Extract in `core/monitor.py` `fetch_instance()`:
```python
my_field = info.get("myField", "")
agent = Agent(
    # ... existing
    my_field=my_field,
)
```

3. Display in `ui/menu.py` `build_agent_items()`:
```python
if agent.my_field:
    items.append(rumps.MenuItem(f"📌 {agent.my_field}"))
```

### Add Security Pattern

1. Add pattern in `security/analyzer.py`:

For commands:
```python
DANGEROUS_PATTERNS = [
    # ...
    (r"my_pattern", 50, "Description", []),
]
```

For files/URLs, add to `SENSITIVE_FILE_PATTERNS` or `SENSITIVE_URL_PATTERNS`.

## Testing

### Run Tests

```bash
# All tests
make test

# With coverage
make coverage

# Specific test file
uv run python -m pytest tests/test_risk_analyzer.py -v
```

### Manual Testing

```bash
# Run and watch logs
uv run python3 bin/opencode-menubar

# Test usage API
uv run python3 -c "
from opencode_monitor.core.usage import fetch_usage
u = fetch_usage()
print(f'Session: {u.five_hour.utilization}%')
"

# Test instance detection
uv run python3 -c "
import asyncio
from opencode_monitor.core.monitor import fetch_all_instances
state = asyncio.run(fetch_all_instances())
print(f'Instances: {state.instance_count}')
"

# Test security analyzer
uv run python3 -c "
from opencode_monitor.security.analyzer import analyze_command
alert = analyze_command('rm -rf /')
print(f'Score: {alert.score}, Level: {alert.level}')
"

# Test analytics
uv run python3 -c "
from opencode_monitor.analytics import AnalyticsDB, load_opencode_data, generate_report
db = AnalyticsDB()
load_opencode_data(db)
report = generate_report(days=7, db=db)
print(report.to_text())
"
```

### Check Settings & Database

```bash
# Settings
cat ~/.config/opencode-monitor/settings.json

# Security database stats
sqlite3 ~/.config/opencode-monitor/security.db "
SELECT 'Commands:', COUNT(*) FROM commands;
SELECT 'Reads:', COUNT(*) FROM file_reads;
SELECT 'Writes:', COUNT(*) FROM file_writes;
"

# Analytics database stats
uv run python3 -c "
from opencode_monitor.analytics import AnalyticsDB
db = AnalyticsDB()
stats = db.get_stats()
for table, count in stats.items():
    print(f'{table}: {count}')
"
```

## Debugging

### Enable Debug Logging

In `utils/logger.py`, debug messages go to stderr. Run the app from terminal to see them:

```bash
uv run python3 bin/opencode-menubar 2>&1 | tee /tmp/opencode-debug.log
```

### Common Issues

**App not appearing in menu bar:**
- Check if another instance is running: `pgrep -f opencode`
- Kill and restart: `pkill -f opencode_monitor && make run`

**Usage not updating:**
- Check auth file: `cat ~/.local/share/opencode/auth.json`
- Check settings interval: `cat ~/.config/opencode-monitor/settings.json`

**Instances not detected:**
- Verify OpenCode is running: `lsof -i :4096`
- Check netstat: `netstat -an | grep LISTEN | grep 127.0.0.1`

## Dependencies

Defined in `pyproject.toml`:

- **rumps**: macOS menu bar framework
- **aiohttp**: Async HTTP client
- **duckdb**: Analytics database (fast columnar queries)
- **pytest**: Testing framework
- **pytest-cov**: Coverage reporting

Install with:
```bash
uv sync
```

## Git Workflow

```bash
# Development
git checkout -b feature/my-feature
# ... make changes ...
make test  # Ensure tests pass
git commit -m "feat(scope): description"

# Merge to main
git checkout master
git merge feature/my-feature
git tag -a vX.Y.Z -m "description"
```
