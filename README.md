# OpenCode Monitor

> **Note** : Ce projet est entièrement *vibe-codé* avec [OpenCode](https://github.com/sst/opencode) ❤️ et Claude Opus 4.5.

Native macOS menu bar app to monitor [OpenCode](https://github.com/sst/opencode) instances and API usage.

## Features

### Menu Bar
- **Real-time monitoring** of OpenCode instances
- **Agent hierarchy** with main agents and sub-agents
- **Tools display** showing currently running tools
- **Permission detection** 🔒 heuristic indicator for tools waiting approval
- **MCP Notify tracking** 🔔 indicator when agent awaits user response
- **Todos tracking** with progress indicators
- **Claude API usage** (session + weekly)
- **Click to focus** iTerm2 on the agent's terminal
- **Configurable settings** via menu

### PyQt6 Dashboard
- **Monitoring section** - real-time instance overview
- **Analytics section** - token usage statistics (by period, agent, tool, skill)
- **Tracing section** - agent delegation tree with timeline and transcript
- **Security section** - risk analysis with MITRE ATT&CK mapping
- **Analytics visualization** with interactive dashboard

## Installation

### Requirements

- macOS 12+
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- OpenCode CLI running

### Setup

```bash
# Clone the repository
git clone <repo-url>
cd opencode-monitor

# Run the app
make run
```

## Usage

Once running, the app appears in your menu bar with a 🤖 icon.

### Menu Bar Display

```
🤖 2 💤 3 🔒 🔔 ⏳ 3 🟢 45%
```

- `🤖` - App icon
- `2` - Number of busy agents
- `💤 3` - Number of idle instances
- `🔒` - Permission may be pending (tool running > 5s)
- `🔔` - Agent awaits user response (MCP Notify ask_user)
- `⏳3` - Total pending todos
- `🟢45%` - Claude API session usage

### Menu Contents

Click the icon to see:

```
🤖 Agent Title                    ← Click to focus terminal
    🔧 bash: git status           ← Running tool
    🔒 bash: npm install          ← May need permission (running 15s)
    🔄 Current task               ← In-progress todo
    ⏳ Next task (+2)             ← Pending todos
    └ ● Sub-agent                 ← Sub-agent (busy)
    └ ○ Sub-agent                 ← Sub-agent (idle)
🔔 Agent Question                 ← Awaiting user response
    ❓ Validation requise         ← Question title
---
🟢 Session: 45% (reset 2h30m)
📅 Weekly: 29% (reset Mon 0h)
🌐 Open Claude Usage
---
📊 Dashboard                      ← Opens PyQt6 dashboard
---
*🛡️ Security analysis available in Dashboard → Security tab*
---
Refresh
---
⚙️ Preferences ▸
    🔄 Usage refresh ▸
        30s / 1m ✓ / 2m / 5m / 10m
    🔔 Ask user timeout ▸
        5m / 15m / 30m ✓ / 1h
---
Quit
```

### Preferences

Access via **⚙️ Preferences** in the menu:

- **🔄 Usage refresh**: How often to fetch Claude API usage (30s - 10m)
- **🔔 Ask user timeout**: How long to show 🔔 before dismissing (5m - 1h)

Settings are saved to `~/.config/opencode-monitor/settings.json`

## Development

```bash
# Run the app
make run

# Run tests
make test

# Run tests with coverage
make coverage
```

### Project Structure

```
opencode-monitor/
├── bin/
│   └── opencode-menubar          # Entry point script
├── src/
│   └── opencode_monitor/         # Python package
│       ├── app/                  # Menu bar application
│       │   ├── core.py           # OpenCodeApp main class
│       │   ├── handlers.py       # Event callbacks
│       │   └── menu.py           # Menu building
│       ├── core/                 # Core monitoring
│       │   ├── client.py         # OpenCode API client
│       │   ├── models.py         # Data classes
│       │   ├── monitor/          # Instance detection
│       │   └── usage.py          # Claude API usage
│       ├── api/                  # REST API (Flask)
│       │   ├── server.py         # Flask server
│       │   ├── client.py         # API client
│       │   └── routes/           # API endpoints
│       ├── analytics/            # Usage analytics (DuckDB)
│       │   ├── db.py             # Database management
│       │   ├── indexer/          # Real-time + backfill indexer
│       │   ├── loaders/          # Data loaders
│       │   ├── queries/          # SQL queries
│       │   └── tracing/          # Tracing service
│       ├── dashboard/            # PyQt6 dashboard
│       │   ├── sections/         # UI sections
│       │   ├── widgets/          # Reusable components
│       │   ├── styles/           # Design system
│       │   └── window/           # Main window
│       ├── security/             # Security audit
│       │   ├── analyzer/         # Risk analysis
│       │   ├── auditor/          # Background scanner
│       │   ├── db/               # DuckDB storage (unified)
│       │   └── sequences.py      # Kill chain detection
│       ├── ui/                   # Menu bar UI
│       │   ├── menu.py           # Menu builder
│       │   └── terminal.py       # iTerm2 focus
│       └── utils/                # Utilities
├── tools/pycode/                 # Python analysis CLI
├── tests/                        # Unit & integration tests
├── docs/                         # Documentation
├── pyproject.toml                # Python dependencies
└── Makefile                      # Dev commands
```

## Roadmap

See [docs/backlog/](docs/backlog/) for planned features and [docs/archive/](docs/archive/) for completed plans.

## Changelog

| Version | Date | Description |
|---------|------|-------------|
| v2.23.0 | 2026-01-04 | Python Analysis CLI - jedi/radon/vulture tools, 10 commands, `.opencode/AGENTS.md` |
| v2.13.0 | 2025-12-30 | Analytics dashboard - DuckDB, PyQt6 visualization, delegation metrics |
| v2.12.0 | 2025-12-30 | Display idle session count in menu bar title |
| v2.11.0 | 2025-12-29 | MCP Notify ask_user detection - bell icon when agent awaits response |
| v2.10.0 | 2025-12-29 | Permission detection heuristic - lock icon on tools running > 5s |
| v2.9.0 | 2025-12-28 | Refactoring - Extract database, risk_analyzer, reporter, terminal modules |
| v2.8.0 | 2025-12-28 | Security audit module - analyze commands, reads, writes, webfetches |
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
| v1.0.0 | 2025-12-28 | Initial release |

## License

MIT
