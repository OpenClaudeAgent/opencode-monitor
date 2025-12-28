# Development Guide

## Quick Start

```bash
# Run the app
make run

# Or directly with uv
uv run python3 bin/opencode-menubar
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
│  │ - notifications │  │ - handle clicks  │  │
│  └─────────────────┘  └──────────────────┘  │
│                                             │
│  State: self._state, self._usage (in-memory)│
└─────────────────────────────────────────────┘
```

### Key Components

| File | Purpose |
|------|---------|
| `app.py` | Main rumps application, UI, menu building |
| `monitor.py` | Async detection of OpenCode instances |
| `usage.py` | Claude API usage fetching |
| `settings.py` | Preferences persistence |
| `sounds.py` | macOS sound notifications |
| `models.py` | Data classes |
| `client.py` | OpenCode HTTP client |

## Adding Features

### Add a New Setting

1. Add field to `Settings` dataclass in `settings.py`:
```python
@dataclass
class Settings:
    usage_refresh_interval: int = 60
    sound_completion: bool = True
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

### Add a New Sound

1. Add to `SOUNDS` dict in `sounds.py`:
```python
SOUNDS = {
    "completion": "/System/Library/Sounds/Glass.aiff",
    "my_sound": "/System/Library/Sounds/Ping.aiff",
}
```

2. Add setting toggle (see above)

3. Create check function:
```python
def check_and_notify_my_event(condition: bool):
    settings = get_settings()
    if not settings.sound_my_event:
        return
    if condition:
        play_sound("my_sound")
```

### Add New Data to State

1. Add field to model in `models.py`:
```python
@dataclass
class Agent:
    # ... existing fields
    my_field: str = ""
```

2. Extract in `monitor.py` `fetch_instance()`:
```python
my_field = info.get("myField", "")
agent = Agent(
    # ... existing
    my_field=my_field,
)
```

3. Display in `app.py` `_add_agent_to_menu()`:
```python
if agent.my_field:
    self.menu.insert_before("Refresh", 
        rumps.MenuItem(f"    📌 {agent.my_field}"))
```

## Testing

### Manual Testing

```bash
# Run and watch logs
uv run python3 bin/opencode-menubar

# Test usage API
uv run python3 -c "
from src.opencode_monitor.usage import fetch_usage
u = fetch_usage()
print(f'Session: {u.five_hour.utilization}%')
"

# Test instance detection
uv run python3 -c "
import asyncio
from src.opencode_monitor.monitor import fetch_all_instances
state = asyncio.run(fetch_all_instances())
print(f'Instances: {state.instance_count}')
"
```

### Check Settings

```bash
cat ~/.config/opencode-monitor/settings.json
```

## Debugging

### Enable Debug Logging

In `logger.py`, debug messages go to stderr. Run the app from terminal to see them:

```bash
uv run python3 bin/opencode-menubar 2>&1 | tee /tmp/opencode-debug.log
```

### Common Issues

**App not appearing in menu bar:**
- Check if another instance is running: `pgrep -f opencode-menubar`
- Kill and restart: `pkill -f opencode-menubar && make run`

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

Install with:
```bash
uv sync
```

## Git Workflow

```bash
# Development in worktree
cd worktrees/feature
git checkout -b feature/my-feature
# ... make changes ...
git commit -m "feat(scope): description"

# Merge to main
cd /path/to/main/repo
git merge feature/my-feature
git tag -a vX.Y.Z -m "description"
```
