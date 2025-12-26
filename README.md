# OpenCode SwiftBar Monitor

Monitor OpenCode instances and Claude usage directly from your macOS menu bar using SwiftBar.

## Features

✨ **Real-time Monitoring**
- View active OpenCode instances
- See running agents and their status
- Monitor permission requests
- Track active todos (pending/in progress)

📊 **Claude Usage Tracking**
- 5-hour window utilization
- 7-day utilization
- Reset time countdown

🔌 **Daemon Architecture**
- `opencode-eventd`: Monitors OpenCode instances via SSE events
- `opencode-usaged`: Fetches Claude API usage statistics

🎨 **SwiftBar Plugin**
- Clean, minimal menu bar display
- Click to focus OpenCode tab in iTerm2
- Detailed dropdown with all information

## Installation

### Requirements

- **macOS** (tested on macOS 13+)
- **Bash 5.3+** (from Homebrew)
- **SwiftBar** ([download](https://swiftbar.app))
- **OpenCode** with CLI access

### Quick Install

```bash
# Clone or download this project
cd opencode-swiftbar-monitor

# Run installation script
bash install.sh
```

The script will:
1. Install SwiftBar (if not already installed)
2. Copy daemons to `~/.local/bin/`
3. Copy plugin to `~/Library/Application Support/SwiftBar/Plugins/`
4. Configure and load launchd services
5. Verify installation

### Manual Installation

If you prefer manual installation:

```bash
# Copy daemons
cp bin/opencode-eventd ~/.local/bin/
cp bin/opencode-usaged ~/.local/bin/
chmod +x ~/.local/bin/opencode-*

# Copy plugin
cp plugins/opencode.2s.sh ~/Library/Application\ Support/SwiftBar/Plugins/
chmod +x ~/Library/Application\ Support/SwiftBar/Plugins/opencode.2s.sh

# Install launchd services
cp launchd/com.opencode.eventd.plist ~/Library/LaunchAgents/
cp launchd/com.opencode.usaged.plist ~/Library/LaunchAgents/

# Load services
launchctl load ~/Library/LaunchAgents/com.opencode.eventd.plist
launchctl load ~/Library/LaunchAgents/com.opencode.usaged.plist
```

## Project Structure

```
opencode-swiftbar-monitor/
├── bin/
│   ├── opencode-eventd          # SSE listener daemon
│   └── opencode-usaged          # Usage statistics daemon
├── plugins/
│   └── opencode.2s.sh           # SwiftBar plugin (2s refresh)
├── launchd/
│   ├── com.opencode.eventd.plist
│   └── com.opencode.usaged.plist
├── examples/
│   ├── model.json               # Sample API response
│   ├── opencode-state.json      # Sample daemon state
│   └── opencode-usage.json      # Sample usage state
├── install.sh                   # Installation script
├── uninstall.sh                 # Uninstallation script
└── README.md                    # This file
```

## Configuration

### Daemon Configuration

**opencode-eventd** (SSE listener)
- Monitors all OpenCode instances
- Updates state file: `/tmp/opencode-state.json`
- Watches for: instances, agents, todos, tools, permissions

**opencode-usaged** (Usage tracker)
- Fetches Claude API usage every 5 minutes
- Updates state file: `/tmp/opencode-usage.json`
- Requires: `~/.local/share/opencode/auth.json`

### Plugin Configuration

Edit `~/Library/Application Support/SwiftBar/Plugins/opencode.2s.sh` to customize:
- Refresh interval (default: 2 seconds)
- Colors and icons
- Display format

## Usage

### Monitor in Menu Bar

Once installed, you should see the OpenCode icon in your menu bar. Click to see:

```
🤖 Status Display
├── Instances (showing active sessions)
├── Tools (showing running tools)
├── Todos (pending and in progress)
└── Usage (Claude API consumption)
```

### View Logs

```bash
# Event daemon logs
tail -f /tmp/opencode-eventd.log

# Usage daemon logs  
tail -f /tmp/opencode-usaged.log
```

### Restart Services

```bash
# Restart eventd
launchctl unload ~/Library/LaunchAgents/com.opencode.eventd.plist
launchctl load ~/Library/LaunchAgents/com.opencode.eventd.plist

# Restart usaged
launchctl unload ~/Library/LaunchAgents/com.opencode.usaged.plist
launchctl load ~/Library/LaunchAgents/com.opencode.usaged.plist
```

## Troubleshooting

### Plugin not showing in menu bar

1. Check if plugin is executable:
   ```bash
   ls -l ~/Library/Application\ Support/SwiftBar/Plugins/opencode.2s.sh
   ```

2. Verify SwiftBar is running (check Activity Monitor)

3. Refresh SwiftBar:
   ```bash
   open -g "swiftbar://refreshplugin?name=opencode"
   ```

### Daemons not running

1. Check launchd status:
   ```bash
   launchctl list | grep opencode
   ```

2. Check logs:
   ```bash
   cat /tmp/opencode-eventd.log
   cat /tmp/opencode-usaged.log
   ```

3. Reload services:
   ```bash
   bash install.sh
   ```

### No OpenCode instances detected

1. Ensure OpenCode is running with the CLI flag
2. Check that instances are accessible on `http://127.0.0.1:PORT`
3. Check eventd logs for connection errors

## Data Flow

```
OpenCode Instances
    ↓
opencode-eventd (SSE listener)
    ↓
/tmp/opencode-state.json
    ↓
SwiftBar Plugin
    ↓
Menu Bar Display
```

```
Claude API
    ↓
opencode-usaged (HTTP requests)
    ↓
/tmp/opencode-usage.json
    ↓
SwiftBar Plugin
    ↓
Usage Display
```

## Uninstallation

```bash
bash uninstall.sh
```

This will:
- Stop launchd services
- Remove daemons
- Remove SwiftBar plugin
- Remove launchd configuration

## API Reference

### State File Format: `/tmp/opencode-state.json`

```json
{
  "instances": [
    {
      "port": 4096,
      "tty": "ttys000",
      "agents": [
        {
          "id": "ses_xxx",
          "title": "Agent Title",
          "status": "busy|idle",
          "permission_pending": false
        }
      ],
      "agent_count": 1,
      "busy_count": 1
    }
  ],
  "instance_count": 1,
  "agent_count": 1,
  "busy_count": 1,
  "todos": {
    "pending": 0,
    "in_progress": 0
  },
  "permissions_pending": 0,
  "tools_running": [],
  "updated": 1766768000,
  "connected": true
}
```

### Usage File Format: `/tmp/opencode-usage.json`

```json
{
  "five_hour": {
    "utilization": 45,
    "resets_at": "2025-12-26T23:00:00Z"
  },
  "seven_day": {
    "utilization": 62,
    "resets_at": "2025-12-29T00:00:00Z"
  },
  "updated": 1766768000
}
```

## Contributing

Feel free to improve the plugin, add features, or fix bugs.

## License

MIT License

## Support

For issues or questions:
1. Check the logs
2. Review troubleshooting section
3. Verify OpenCode is running correctly

## Changelog

### v1.0.0
- Initial release
- Event daemon with SSE support
- Usage tracking daemon
- SwiftBar plugin with 2s refresh
- Installation scripts
