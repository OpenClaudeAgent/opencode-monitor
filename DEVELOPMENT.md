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

### Multi-Process Architecture

OpenCode Monitor consists of two main components:

1. **Menu Bar App** (rumps) - Real-time monitoring
2. **PyQt6 Dashboard** - Analytics and tracing visualization

```
┌───────────────────────────────────────────────────────────────────┐
│                     OpenCodeApp (rumps.App)                       │
│                                                                   │
│  ┌─────────────────┐  ┌──────────────────┐  ┌─────────────────┐  │
│  │ Background      │  │ UI Thread        │  │ Services        │  │
│  │ Thread          │  │ (main)           │  │                 │  │
│  │                 │  │                  │  │ - API Server    │  │
│  │ - fetch state   │  │ - build menu     │  │ - Indexer       │  │
│  │ - fetch usage   │──▶ - update title   │  │ - Auditor       │  │
│  │ - security scan │  │ - handle clicks  │  │                 │  │
│  └─────────────────┘  └──────────────────┘  └─────────────────┘  │
│                                                                   │
│  Database: DuckDB (analytics + security) - unified                │
└───────────────────────────────────────────────────────────────────┘
                               │
                               │ REST API (127.0.0.1:19876)
                               ▼
┌───────────────────────────────────────────────────────────────────┐
│                         PyQt6 Dashboard                           │
│                                                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────┐ │
│  │ Monitoring  │  │ Security    │  │ Analytics   │  │ Tracing  │ │
│  │ Section     │  │ Section     │  │ Section     │  │ Section  │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └──────────┘ │
└───────────────────────────────────────────────────────────────────┘
```

### Key Components

| Module | Purpose |
|--------|---------|
| **Menu Bar App** | |
| `app/core.py` | Main rumps application, orchestration |
| `app/handlers.py` | Event callbacks (HandlersMixin) |
| `app/menu.py` | Menu building (MenuMixin) |
| **Core Monitoring** | |
| `core/monitor/` | Async detection of OpenCode instances |
| `core/usage.py` | Claude API usage fetching |
| `core/models.py` | Data classes (State, Agent, etc.) |
| `core/client.py` | OpenCode HTTP client |
| **REST API** | |
| `api/server.py` | Flask API server |
| `api/client.py` | API client for dashboard |
| `api/routes/` | API endpoints |
| **Analytics** | |
| `analytics/db.py` | DuckDB database management (15 tables) |
| `analytics/indexer/` | Unified indexer (real-time + backfill) |
| `analytics/indexer/unified/` | Modular indexer components |
| `analytics/loaders/` | Specialized data loaders |
| `analytics/queries/` | SQL query modules |
| `analytics/tracing/` | Tracing data service |
| `analytics/report/` | HTML report generation |
| **Dashboard** | |
| `dashboard/window/` | PyQt6 main window |
| `dashboard/sections/` | UI sections (monitoring, security, analytics, tracing) |
| `dashboard/widgets/` | Reusable UI components |
| `dashboard/styles/` | Design system |
| **Security** | |
| `security/analyzer/` | Risk analysis for commands/files/URLs |
| `security/auditor/` | Background security scanner |
| `security/db/` | DuckDB storage (unified with analytics) |
| `security/mitre_utils.py` | MITRE ATT&CK mapping |
| `security/sequences.py` | Kill chain detection |
| `security/correlator.py` | Event correlation across sessions |
| **Utilities** | |
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

2. Extract in `core/monitor/fetcher.py` `fetch_instance()`:
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

1. Add pattern in `security/analyzer/patterns.py`:

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
from opencode_monitor.core.monitor import fetch_instances
state = asyncio.run(fetch_instances())
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

### Python Code Analysis Tools

The project includes built-in CLI tools for Python code analysis in `tools/pycode/`:

```bash
# Navigation - goto definition, find references, hover, symbols
uv run python -m tools.pycode goto src/opencode_monitor/app.py:50:4
uv run python -m tools.pycode refs src/opencode_monitor/app.py:50:4
uv run python -m tools.pycode hover src/opencode_monitor/app.py:50:4
uv run python -m tools.pycode symbols src/opencode_monitor/app.py

# Diagnostics - lint and format check
uv run python -m tools.pycode lint src/
uv run python -m tools.pycode check src/

# Metrics - complexity and maintainability
uv run python -m tools.pycode complexity src/opencode_monitor/
uv run python -m tools.pycode maintainability src/opencode_monitor/

# Dead code detection
uv run python -m tools.pycode dead-code src/

# Combined report
uv run python -m tools.pycode report src/opencode_monitor/utils/

# JSON output for parsing
uv run python -m tools.pycode --json symbols src/opencode_monitor/app.py
```

### Check Settings & Database

```bash
# Settings
cat ~/.config/opencode-monitor/settings.json

# Database stats (unified DuckDB)
uv run python3 -c "
from opencode_monitor.analytics import AnalyticsDB
db = AnalyticsDB()
stats = db.get_stats()
for table, count in stats.items():
    print(f'{table}: {count}')
"

# Security stats via API
curl -s http://127.0.0.1:19876/api/security | jq '.data.stats'
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

**Runtime:**
- **rumps**: macOS menu bar framework
- **aiohttp**: Async HTTP client
- **duckdb**: Analytics database (fast columnar queries)
- **PyQt6**: Dashboard UI framework
- **plotly**: Chart generation
- **flask**: REST API server
- **watchdog**: File system monitoring

**Development:**
- **pytest**: Testing framework
- **pytest-cov**: Coverage reporting
- **pytest-qt**: PyQt6 testing
- **pytest-asyncio**: Async test support
- **ruff**: Linting
- **jedi/radon/vulture**: Code analysis tools

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
