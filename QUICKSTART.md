# Quick Start Guide

Get OpenCode SwiftBar Monitor running in 5 minutes.

## 1. Installation

```bash
# Navigate to project directory
cd ~/Projects/opencode-swiftbar-monitor

# Run installation
bash install.sh
```

That's it! The installer will:
- ✅ Install SwiftBar (if needed)
- ✅ Copy daemons to `~/.local/bin/`
- ✅ Copy plugin to SwiftBar plugins folder
- ✅ Configure and start services

## 2. Verify Installation

Check if everything is running:

```bash
# Check if daemons are running
ps aux | grep opencode

# View the state file
cat /tmp/opencode-state.json | jq .

# View the usage file
cat /tmp/opencode-usage.json | jq .
```

## 3. Look in Menu Bar

You should see the OpenCode icon (🤖) in your menu bar!

Click it to see:
- Active instances
- Running agents
- Pending todos
- Claude API usage

## 4. Common Actions

### Refresh SwiftBar Plugin
```bash
open -g "swiftbar://refreshplugin?name=opencode"
```

### View Logs
```bash
tail -f /tmp/opencode-eventd.log
tail -f /tmp/opencode-usaged.log
```

### Restart Daemons
```bash
launchctl unload ~/Library/LaunchAgents/com.opencode.eventd.plist
launchctl load ~/Library/LaunchAgents/com.opencode.eventd.plist
```

### Uninstall
```bash
cd ~/Projects/opencode-swiftbar-monitor
bash uninstall.sh
```

## 5. Customize

### Change Plugin Refresh Rate

Rename the plugin file to change refresh interval:

```bash
# Refresh every 5 seconds instead of 2
cd ~/Library/Application\ Support/SwiftBar/Plugins
mv opencode.2s.sh opencode.5s.sh
```

Valid intervals: `.1s`, `.2s`, `10s`, `1m`, `5m`, `1h`

### Modify Daemon Polling

Edit `~/.local/bin/opencode-eventd`:

```bash
# Find this line (~365):
local poll_interval=30  # Change to desired seconds
```

Then reload:
```bash
launchctl unload ~/Library/LaunchAgents/com.opencode.eventd.plist
launchctl load ~/Library/LaunchAgents/com.opencode.eventd.plist
```

## 6. Troubleshooting

### Plugin not visible
```bash
# Check if plugin exists
ls ~/Library/Application\ Support/SwiftBar/Plugins/opencode.2s.sh

# Check if executable
chmod +x ~/Library/Application\ Support/SwiftBar/Plugins/opencode.2s.sh

# Refresh SwiftBar
open -g "swiftbar://refreshplugin?name=opencode"
```

### No instances detected
```bash
# Check if OpenCode is running
ps aux | grep opencode | grep -v grep

# Check eventd logs
tail -20 /tmp/opencode-eventd.log

# Find OpenCode ports
/usr/sbin/lsof -i -P | grep opencode
```

### Daemons not starting
```bash
# Check launchd status
launchctl list | grep opencode

# Check plist files
plutil -lint ~/Library/LaunchAgents/com.opencode.eventd.plist

# Reload services
bash ~/Projects/opencode-swiftbar-monitor/install.sh
```

## 7. File Locations

After installation, files are located at:

```
~/.local/bin/
  ├── opencode-eventd
  └── opencode-usaged

~/Library/Application Support/SwiftBar/Plugins/
  └── opencode.2s.sh

~/Library/LaunchAgents/
  ├── com.opencode.eventd.plist
  └── com.opencode.usaged.plist

/tmp/
  ├── opencode-state.json
  ├── opencode-usage.json
  ├── opencode-eventd.log
  └── opencode-usaged.log
```

## 8. Data Files

The monitor stores data in JSON files:

### `/tmp/opencode-state.json`
Updated in real-time when OpenCode instances change:
- Instances (ports, TTY)
- Agents (status, permissions)
- Todos (pending, in progress)
- Tools running

### `/tmp/opencode-usage.json`
Updated every 5 minutes from Claude API:
- 5-hour window usage
- 7-day window usage
- Reset times

## 9. Next Steps

- Read [README.md](README.md) for full documentation
- Read [DEVELOPMENT.md](DEVELOPMENT.md) to modify components
- Check [examples/](examples/) for sample data formats
- Review logs for any issues

## Support

Having issues? Check:
1. Logs: `tail -f /tmp/opencode-eventd.log`
2. Status: `launchctl list | grep opencode`
3. Files: `ls -la ~/Library/LaunchAgents/com.opencode.*`
4. Running processes: `ps aux | grep opencode`

---

**Enjoying the monitor?** Consider starring the repo or contributing improvements! 🌟
