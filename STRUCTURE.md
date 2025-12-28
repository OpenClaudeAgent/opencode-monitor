# Project Structure

```
opencode-swiftbar-monitor/
│
├── 📄 README.md                          # Main documentation
├── 📄 QUICKSTART.md                      # 5-minute setup guide  
├── 📄 DEVELOPMENT.md                     # Development guide
├── 📄 STRUCTURE.md                       # This file
│
├── 🚀 Makefile                           # Build/dev commands (make help)
├── 🚀 install.sh                         # Installation script
├── 🚀 uninstall.sh                       # Uninstallation script
│
├── 📁 bin/
│   ├── opencode-eventd                   # Daemon: Monitor OpenCode instances
│   └── opencode-usaged                   # Daemon: Track Claude API usage
│
├── 📁 plugins/
│   └── opencode.2s.sh                    # SwiftBar plugin (2s refresh)
│
├── 📁 launchd/
│   ├── com.opencode.eventd.plist         # LaunchAgent config for eventd
│   └── com.opencode.usaged.plist         # LaunchAgent config for usaged
│
├── 📁 examples/
│   ├── model.json                        # Sample: LLM model config
│   ├── opencode-state.json               # Sample: Daemon state output
│   └── opencode-usage.json               # Sample: Usage statistics
│
├── .gitignore                            # Git ignore patterns
├── .gitattributes                        # Git attributes (line endings)
└── .git/                                 # Git repository
```

## File Descriptions

### Scripts (Root Level)

| File | Purpose |
|------|---------|
| `install.sh` | Automated installation of all components |
| `uninstall.sh` | Clean uninstallation of all components |

### Bin Directory (`bin/`)

#### opencode-eventd
- **Type**: Bash daemon
- **Purpose**: Monitor OpenCode instances in real-time
- **Mechanism**: SSE listener + HTTP polling
- **Output**: `/tmp/opencode-state.json`
- **Frequency**: Real-time updates + 30s polling fallback
- **Dependencies**: `curl`, `jq`, `lsof`

#### opencode-usaged
- **Type**: Bash daemon
- **Purpose**: Fetch Claude API usage statistics
- **Mechanism**: HTTP requests to Anthropic API
- **Output**: `/tmp/opencode-usage.json`
- **Frequency**: Every 5 minutes
- **Dependencies**: `curl`, `jq`
- **Auth**: Reads from `~/.local/share/opencode/auth.json`

### Plugins Directory (`plugins/`)

#### opencode.2s.sh
- **Type**: SwiftBar plugin
- **Purpose**: Display monitor data in macOS menu bar
- **Refresh**: Every 2 seconds (configurable via filename)
- **Input**: Reads `/tmp/opencode-state.json` and `/tmp/opencode-usage.json`
- **Output**: SwiftBar-formatted text (menu bar display)
- **Dependencies**: `jq`, `bash`

### Launchd Directory (`launchd/`)

#### com.opencode.eventd.plist
- **Type**: LaunchAgent configuration
- **Purpose**: Auto-start eventd daemon on login
- **User**: Current user (LaunchAgent, not LaunchDaemon)
- **Logs**: `/tmp/opencode-eventd.log`

#### com.opencode.usaged.plist
- **Type**: LaunchAgent configuration
- **Purpose**: Auto-start usaged daemon on login
- **User**: Current user (LaunchAgent, not LaunchDaemon)
- **Logs**: `/tmp/opencode-usaged.log`

### Examples Directory (`examples/`)

Sample data files showing expected formats:

- `model.json`: OpenCode model configuration
- `opencode-state.json`: Typical daemon state output
- `opencode-usage.json`: Typical usage statistics output

## Data Flow

### Event Monitoring

```
OpenCode Instances (http://127.0.0.1:PORT)
        ↓
   eventd daemon
        ↓
   - Port discovery (lsof)
   - SSE listener (persistent connection)
   - HTTP polling (every 30s)
        ↓
/tmp/opencode-state.json
        ↓
  opencode.2s.sh plugin
        ↓
  SwiftBar Menu Bar Display
```

### Usage Tracking

```
Anthropic Claude API
        ↓
   usaged daemon
        ↓
   HTTP GET request (every 5 minutes)
   Auth: ~/.local/share/opencode/auth.json
        ↓
/tmp/opencode-usage.json
        ↓
  opencode.2s.sh plugin
        ↓
  SwiftBar Menu Bar Display
```

## Installation Paths

After running `install.sh`, files are placed in:

```
~/.local/bin/
  ├── opencode-eventd          (copied from bin/)
  └── opencode-usaged          (copied from bin/)

~/Library/Application Support/SwiftBar/Plugins/
  └── opencode.2s.sh           (copied from plugins/)

~/Library/LaunchAgents/
  ├── com.opencode.eventd.plist    (from launchd/)
  └── com.opencode.usaged.plist    (from launchd/)

/tmp/
  ├── opencode-state.json      (created by eventd)
  ├── opencode-usage.json      (created by usaged)
  ├── opencode-eventd.log      (created by eventd)
  └── opencode-usaged.log      (created by usaged)
```

## Dependencies

### System Requirements
- macOS 10.15+ (for LaunchAgents)
- Bash 4.0+ (compatible with /bin/bash or /opt/homebrew/bin/bash)

### Command Dependencies
- `curl`: HTTP requests
- `jq`: JSON parsing
- `lsof`: Port discovery
- `sed`: Text processing
- `md5`: Checksum verification

### Software Dependencies
- **OpenCode**: Accessible at http://127.0.0.1:PORT
- **SwiftBar**: Menu bar plugin system
- **Homebrew** (optional): For automatic SwiftBar installation

## Development Structure

```
Development Workflow:
1. Clone/fork repository
2. Make changes to bin/ or plugins/
3. Test locally (install.sh)
4. Verify functionality
5. Commit with clear messages
6. Create pull request or push to branch
```

## Version Control

### Repository Info
- **VCS**: Git
- **Initial Branch**: master
- **License**: MIT
- **.gitignore**: Excludes logs, macOS files, IDE files

### Typical Workflow
```bash
# Create feature branch
git checkout -b feature/new-feature

# Make changes
# Commit often with clear messages

# Test thoroughly
bash install.sh

# Push to remote (when configured)
git push origin feature/new-feature
```

## File Permissions

After installation:
- Daemons: `755` (executable)
- Plugin: `755` (executable)
- Config: `644` (readable)
- LaunchAgent plists: `644` (readable)

## Future Structure (Planned)

```
(Future additions)

├── 📁 tests/                  # Unit tests
├── 📁 ci/                     # CI/CD configuration
├── .github/
│   └── workflows/             # GitHub Actions (if public)
```
