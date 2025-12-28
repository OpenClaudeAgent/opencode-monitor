# OpenCode Monitor

Native macOS menu bar app to monitor OpenCode (Claude Code CLI) instances and Claude API usage.

## Features

- **Real-time monitoring** of OpenCode instances
- **Agent hierarchy** with main agents and sub-agents
- **Tools display** showing currently running tools
- **Todos tracking** with progress indicators
- **Claude API usage** (session + weekly)
- **Click to focus** iTerm2 on the agent's terminal
- **Sound notifications** on task completion
- **Configurable settings** via menu

## Installation

### Requirements

- macOS 12+
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- OpenCode CLI running

### Setup

```bash
# Clone the repository
git clone <repo-url>
cd opencode-swiftbar-monitor

# Run the app
make run
```

## Usage

Once running, the app appears in your menu bar with a 🤖 icon.

### Menu Bar Display

```
🤖 2 ⏳3 🟢45%
```

- `🤖` - App icon
- `2` - Number of busy agents
- `⏳3` - Total pending todos
- `🟢45%` - Claude API session usage

### Menu Contents

Click the icon to see:

```
🤖 Agent Title                    ← Click to focus terminal
    🔧 bash: git status           ← Running tool
    🔄 Current task               ← In-progress todo
    ⏳ Next task (+2)             ← Pending todos
    └ ● Sub-agent                 ← Sub-agent (busy)
    └ ○ Sub-agent                 ← Sub-agent (idle)
---
🟢 Session: 45% (reset 2h30m)
📅 Weekly: 29% (reset Mon 0h)
📊 Open Claude Usage
---
Refresh
---
⚙️ Preferences ▸
    Usage refresh ▸
        30s / 1m ✓ / 2m / 5m / 10m
    Sounds ▸
        ✓ Completion sound
---
Quit
```

### Preferences

Access via **⚙️ Preferences** in the menu:

- **Usage refresh**: How often to fetch Claude API usage (30s - 10m)
- **Sounds**: Enable/disable completion sound notification

Settings are saved to `~/.config/opencode-monitor/settings.json`

## Development

```bash
# Run in development
make run

# Run with debug output
uv run python3 bin/opencode-menubar
```

### Project Structure

```
opencode-swiftbar-monitor/
├── bin/
│   └── opencode-menubar      # Entry point script
├── src/
│   └── opencode_monitor/     # Python package
│       ├── app.py            # Main rumps application
│       ├── settings.py       # Configuration management
│       ├── monitor.py        # Instance detection
│       ├── usage.py          # Claude API usage
│       ├── sounds.py         # Sound notifications
│       ├── models.py         # Data classes
│       ├── client.py         # OpenCode API client
│       └── logger.py         # Logging
├── roadmap/                  # Feature plans
├── pyproject.toml            # Python dependencies
└── Makefile                  # Dev commands
```

## Roadmap

See [roadmap/README.md](roadmap/README.md) for planned features.

## Changelog

| Version | Date | Description |
|---------|------|-------------|
| v2.7.0 | 2025-12-28 | Tooltips on truncated menu items |
| v2.6.1 | 2025-12-28 | Preferences and menu fixes |
| v2.6.0 | 2025-12-28 | Settings panel (usage refresh, sounds) |
| v2.5.0 | 2025-12-28 | Minimal unicode icons for sub-agents |
| v2.4.0 | 2025-12-28 | Migration to native rumps app |
| v2.3.0 | 2025-12-28 | Todos displayed under each agent |
| v2.2.0 | 2025-12-28 | Sound notifications |
| v2.1.0 | 2025-12-28 | Tools displayed under each agent |
| v2.0.0 | 2025-12-28 | Python async backend |
| v1.1.0 | 2025-12-28 | Debug and logging tools |
| v1.0.0 | 2025-12-28 | Initial release (SwiftBar) |

## License

MIT
