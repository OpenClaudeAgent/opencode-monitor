# Useful Commands Reference

Quick reference for common tasks with OpenCode SwiftBar Monitor.

## Installation & Setup

```bash
# Navigate to project
cd ~/Projects/opencode-swiftbar-monitor

# Install all components
bash install.sh

# Uninstall everything
bash uninstall.sh

# Check installation
git status
git log --oneline
```

## Verification

```bash
# Check if daemons are running
ps aux | grep opencode | grep -v grep

# View state files
cat /tmp/opencode-state.json | jq .
cat /tmp/opencode-usage.json | jq .

# Check if plugin exists
ls ~/Library/Application\ Support/SwiftBar/Plugins/opencode.2s.sh

# Check launchd agents
launchctl list | grep opencode
ls ~/Library/LaunchAgents/com.opencode.*.plist
```

## Logs & Debugging

```bash
# Real-time eventd logs
tail -f /tmp/opencode-eventd.log

# Real-time usaged logs
tail -f /tmp/opencode-usaged.log

# Show last 50 lines
tail -50 /tmp/opencode-eventd.log
tail -50 /tmp/opencode-usaged.log

# Search logs for errors
grep -i error /tmp/opencode-eventd.log
grep -i error /tmp/opencode-usaged.log

# Clear logs
rm /tmp/opencode-*.log
```

## Service Management

```bash
# Restart eventd daemon
launchctl unload ~/Library/LaunchAgents/com.opencode.eventd.plist
launchctl load ~/Library/LaunchAgents/com.opencode.eventd.plist

# Restart usaged daemon
launchctl unload ~/Library/LaunchAgents/com.opencode.usaged.plist
launchctl load ~/Library/LaunchAgents/com.opencode.usaged.plist

# Stop eventd (unload but don't reload)
launchctl unload ~/Library/LaunchAgents/com.opencode.eventd.plist

# Stop usaged (unload but don't reload)
launchctl unload ~/Library/LaunchAgents/com.opencode.usaged.plist

# Kill stuck daemon processes
pkill -9 -f opencode-eventd
pkill -9 -f opencode-usaged

# Check launchd status
launchctl list com.opencode.eventd
launchctl list com.opencode.usaged
```

## SwiftBar Plugin

```bash
# Manually run plugin to test output
bash ~/Library/Application\ Support/SwiftBar/Plugins/opencode.2s.sh

# Refresh plugin in menu bar
open -g "swiftbar://refreshplugin?name=opencode"

# Restart SwiftBar
pkill SwiftBar
open /Applications/SwiftBar.app

# Check plugin syntax
bash -n ~/Library/Application\ Support/SwiftBar/Plugins/opencode.2s.sh
```

## File Management

```bash
# Find all opencode files
find ~ -name "*opencode*" -type f 2>/dev/null

# List all installed files
ls -la ~/.local/bin/opencode-*
ls -la ~/Library/Application\ Support/SwiftBar/Plugins/opencode.2s.sh
ls -la ~/Library/LaunchAgents/com.opencode.*

# Show file sizes
du -sh ~/.local/bin/opencode-*
du -sh ~/Library/Application\ Support/SwiftBar/Plugins/opencode.2s.sh
```

## Network & Ports

```bash
# Find OpenCode ports
/usr/sbin/lsof -i -P 2>/dev/null | grep opencode

# Check port 4096
lsof -i :4096

# Test connection to OpenCode instance
curl -s http://127.0.0.1:4096/session/status | jq .

# Monitor port changes
watch -n 2 "/usr/sbin/lsof -i -P 2>/dev/null | grep opencode"
```

## Data & State

```bash
# Pretty print state file
jq '.' /tmp/opencode-state.json

# Show only instances
jq '.instances' /tmp/opencode-state.json

# Show only usage info
jq '.' /tmp/opencode-usage.json

# Count active instances
jq '.instance_count' /tmp/opencode-state.json

# Count agents
jq '.agent_count' /tmp/opencode-state.json

# Show permissions pending
jq '.permissions_pending' /tmp/opencode-state.json

# Show todos
jq '.todos' /tmp/opencode-state.json
```

## Git Operations

```bash
# Check git status
cd ~/Projects/opencode-swiftbar-monitor
git status

# View commit history
git log --oneline
git log --oneline -10

# View detailed history
git log -p
git log --stat

# Show current branch
git branch

# List all files
git ls-files

# Show file history
git log -p -- bin/opencode-eventd

# View current version
git tag
```

## Development & Testing

```bash
# Test eventd syntax
bash -n ~/.local/bin/opencode-eventd

# Test usaged syntax
bash -n ~/.local/bin/opencode-usaged

# Test plugin syntax
bash -n ~/Library/Application\ Support/SwiftBar/Plugins/opencode.2s.sh

# Run plugin with debug
bash -x ~/Library/Application\ Support/SwiftBar/Plugins/opencode.2s.sh

# Edit files
nano ~/.local/bin/opencode-eventd
nano ~/Library/Application\ Support/SwiftBar/Plugins/opencode.2s.sh
```

## Cleanup

```bash
# Remove all opencode files
bash ~/Projects/opencode-swiftbar-monitor/uninstall.sh

# Remove state files
rm /tmp/opencode-state.json
rm /tmp/opencode-usage.json
rm /tmp/opencode-*.log

# Remove from git
cd ~/Projects/opencode-swiftbar-monitor
rm -rf .git
git init
git add .
git commit -m "Fresh start"
```

## System Information

```bash
# Show bash version
bash --version

# Check bash location
which bash
which -a bash

# Show date/time
date
date +%s  # Unix timestamp

# Show current user
whoami
echo $HOME

# Show available shells
cat /etc/shells
```
