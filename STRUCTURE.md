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
│       ├── settings.py               # Configuration management
│       ├── monitor.py                # OpenCode instance detection
│       ├── usage.py                  # Claude API usage fetching
│       ├── sounds.py                 # Sound notifications
│       ├── models.py                 # Data classes (State, Agent, etc.)
│       ├── client.py                 # OpenCode HTTP client
│       └── logger.py                 # Logging utilities
│
├── roadmap/
│   ├── README.md                     # Roadmap overview and tracking
│   └── plan-XX-*.md                  # Feature plans (00-11)
│
├── worktrees/
│   ├── feature/                      # Development worktree
│   └── roadmap/                      # Planning worktree
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

#### `settings.py`
Configuration management:
- `Settings` dataclass with defaults
- JSON persistence (`~/.config/opencode-monitor/settings.json`)
- `get_settings()` / `save_settings()` functions

#### `monitor.py`
OpenCode instance detection:
- Port scanning via `netstat`
- Async fetching of instance data
- Agent and sub-agent extraction
- TTY detection for terminal focus

#### `usage.py`
Claude API usage:
- OAuth token reading from OpenCode auth file
- Anthropic usage API calls
- 5-hour and 7-day utilization parsing

#### `sounds.py`
Sound notifications:
- Completion sound (Glass.aiff)
- Respects settings for enable/disable
- Anti-spam tracking

#### `models.py`
Data classes:
- `State`, `Instance`, `Agent`, `Tool`
- `Usage`, `UsagePeriod`
- `Todos`, `AgentTodos`

#### `client.py`
HTTP client for OpenCode API:
- Session status fetching
- Session data (info, messages, todos)
- Port validation

#### `logger.py`
Simple logging to stderr with timestamps.

## Data Flow

```
OpenCode Instances (http://127.0.0.1:PORT)
        ↓
    monitor.py (async port scan + HTTP)
        ↓
    models.py (State object)
        ↓
    app.py (in-memory state)
        ↓
    rumps Menu Bar Display
```

```
Anthropic API
        ↓
    usage.py (HTTP request)
        ↓
    models.py (Usage object)
        ↓
    app.py (in-memory usage)
        ↓
    Menu Bar Display
```

## Configuration

Settings stored in `~/.config/opencode-monitor/settings.json`:

```json
{
  "usage_refresh_interval": 60,
  "sound_completion": true
}
```

## Development

```bash
# Run the app
make run

# Or directly
uv run python3 bin/opencode-menubar
```
