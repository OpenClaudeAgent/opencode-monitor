# Project Structure

```
opencode-swiftbar-monitor/
│
├── bin/
│   └── opencode-menubar              # Entry point script
│
├── src/
│   └── opencode_monitor/             # Main Python package
│       ├── __init__.py
│       ├── app.py                    # rumps menu bar application
│       │
│       ├── core/                     # Core monitoring functionality
│       │   ├── client.py             # OpenCode HTTP client
│       │   ├── models.py             # Data classes (State, Agent, etc.)
│       │   ├── monitor.py            # Instance detection & port scanning
│       │   └── usage.py              # Claude API usage fetching
│       │
│       ├── security/                 # Security audit system
│       │   ├── analyzer.py           # Command & file risk analysis
│       │   ├── auditor.py            # Background scanner
│       │   ├── reporter.py           # Report generation
│       │   └── db/                   # Database layer
│       │       ├── models.py         # Audit data classes
│       │       └── repository.py     # SQLite operations
│       │
│       ├── ui/                       # UI components
│       │   ├── menu.py               # Menu builder
│       │   └── terminal.py           # iTerm2 focus (AppleScript)
│       │
│       └── utils/                    # Utilities
│           ├── logger.py             # Logging to stderr
│           └── settings.py           # Configuration management
│
├── tests/                            # Unit tests
│   ├── test_database.py              # SecurityDatabase tests
│   ├── test_reporter.py              # SecurityReporter tests
│   ├── test_risk_analyzer.py         # Analyzer tests
│   └── test_tooltips.py              # Truncation tests
│
├── roadmap/
│   ├── README.md                     # Roadmap overview
│   └── plan-XX-*.md                  # Feature plans
│
├── .gitignore
├── .python-version                   # Python version (3.12)
├── pyproject.toml                    # Python project config (uv)
├── uv.lock                           # Dependency lock file
├── Makefile                          # Dev commands
├── README.md                         # Main documentation
├── STRUCTURE.md                      # This file
└── LICENSE                           # MIT License
```

## Module Descriptions

### `bin/opencode-menubar`

Entry point script that launches the rumps application. Adds `src/` to Python path and calls `main()`.

### `src/opencode_monitor/`

#### `app.py`
Main application class `OpenCodeApp(rumps.App)`:
- Menu bar icon and title management
- Background thread for monitoring
- UI refresh timer (2s)
- Preferences submenu
- Click-to-focus terminal integration

#### `core/client.py`
HTTP client for OpenCode API:
- Async HTTP requests with thread pool
- Session status fetching
- Session data (info, messages, todos)

#### `core/models.py`
Data classes:
- `State`, `Instance`, `Agent`, `Tool`
- `Usage`, `UsagePeriod`
- `Todos`, `AgentTodos`

#### `core/monitor.py`
OpenCode instance detection:
- Port scanning via `netstat`
- Async fetching of instance data
- Agent and sub-agent extraction
- TTY detection for terminal focus

#### `core/usage.py`
Claude API usage:
- OAuth token reading from OpenCode auth file
- Anthropic usage API calls
- 5-hour and 7-day utilization parsing

#### `security/analyzer.py`
Risk analysis for commands, files, and URLs:
- `analyze_command()` - bash command risk scoring
- `RiskAnalyzer` - file path and URL analysis
- Pattern-based scoring with context adjustments

#### `security/auditor.py`
Background scanner:
- Scans OpenCode storage files
- Analyzes commands for security risks
- Stores results in SQLite database

#### `security/db/models.py`
Audit data classes:
- `AuditedCommand`, `AuditedFileRead`
- `AuditedFileWrite`, `AuditedWebFetch`

#### `security/db/repository.py`
SQLite operations:
- CRUD for all audit types
- Statistics queries
- Risk level filtering

#### `security/reporter.py`
Report generation:
- Summary reports
- Full export functionality

#### `ui/menu.py`
Menu construction:
- `MenuBuilder` class
- Dynamic menu items
- Security submenu
- Usage display

#### `ui/terminal.py`
iTerm2 integration via AppleScript.

#### `utils/logger.py`
Simple logging to stderr with timestamps.

#### `utils/settings.py`
Configuration management:
- `Settings` dataclass with defaults
- JSON persistence (`~/.config/opencode-monitor/settings.json`)
- `get_settings()` / `save_settings()` functions

## Data Flow

```
OpenCode Instances (http://127.0.0.1:PORT)
        ↓
    core/monitor.py (async port scan + HTTP)
        ↓
    core/models.py (State object)
        ↓
    app.py (in-memory state)
        ↓
    ui/menu.py (MenuBuilder)
        ↓
    rumps Menu Bar Display
```

```
OpenCode Storage Files (~/.local/share/opencode/storage)
        ↓
    security/auditor.py (background scan)
        ↓
    security/analyzer.py (risk scoring)
        ↓
    security/db/repository.py (SQLite)
        ↓
    ui/menu.py (Security submenu)
```

## Configuration

Settings stored in `~/.config/opencode-monitor/settings.json`:

```json
{
  "usage_refresh_interval": 60
}
```

Security audit database: `~/.config/opencode-monitor/security.db`

## Development

```bash
# Run the app
make run

# Run tests
make test

# Run tests with coverage
make coverage

# Show roadmap
make roadmap
```
