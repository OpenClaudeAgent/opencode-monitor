# Development Guide

This document explains the project structure and how to develop/modify components.

## Architecture Overview

### Components

#### 1. Eventd Daemon (`bin/opencode-eventd`)
- **Purpose**: Monitor OpenCode instances in real-time
- **Mechanism**: 
  - Discovers OpenCode instances via port scanning
  - Connects to each instance via HTTP
  - Listens to SSE (Server-Sent Events) stream
  - Polls for state updates every 30 seconds (fallback)
- **Output**: `/tmp/opencode-state.json`
- **Frequency**: Real-time + polling fallback

**Key Functions:**
- `find_opencode_ports()`: Discover running instances
- `fetch_and_write_state()`: Gather state from all instances
- `listen_instance_events()`: SSE stream listener
- `process_event()`: Handle incoming events

#### 2. Usaged Daemon (`bin/opencode-usaged`)
- **Purpose**: Track Claude API usage
- **Mechanism**: HTTP requests to Anthropic API
- **Output**: `/tmp/opencode-usage.json`
- **Frequency**: Every 5 minutes
- **Auth**: Reads from `~/.local/share/opencode/auth.json`

#### 3. SwiftBar Plugin (`plugins/opencode.2s.sh`)
- **Purpose**: Display monitor data in menu bar
- **Mechanism**: 
  - Reads JSON files from /tmp
  - Formats for SwiftBar display
  - Refreshes every 2 seconds
- **Output**: Menu bar display

### Data Flow

```
OpenCode Instances
        ↓
  Port Discovery (lsof)
        ↓
  HTTP Polling & SSE Listening
        ↓
  /tmp/opencode-state.json (updated real-time)
        ↓
  SwiftBar Plugin reads JSON
        ↓
  Menu Bar Display
```

## Development

### Modifying the Eventd Daemon

**File**: `bin/opencode-eventd`

**Common modifications:**

1. **Change polling interval** (line ~365):
   ```bash
   local poll_interval=30  # seconds
   ```

2. **Add new event type** (in `process_event()`):
   ```bash
   case "$event_type" in
       my.new.event)
           log "Handling my new event"
           fetch_and_write_state
           ;;
   esac
   ```

3. **Extract additional data from API**:
   Edit the `fetch_and_write_state()` function to add more jq processing

### Modifying the Usaged Daemon

**File**: `bin/opencode-usaged`

**Common modifications:**

1. **Change fetch interval** (line ~19):
   ```bash
   FETCH_INTERVAL=300  # 5 minutes (in seconds)
   ```

2. **Add new fields** to API response parsing:
   Use jq to extract and format additional data

### Modifying the Plugin

**File**: `plugins/opencode.2s.sh`

**Common modifications:**

1. **Change refresh interval** (filename):
   - `opencode.2s.sh` → `opencode.5s.sh` (5 second refresh)
   - SwiftBar uses filename to determine refresh rate

2. **Add new display sections**:
   ```bash
   if [[ -n "$MY_DATA" ]]; then
       echo "My Section | size=12 color=gray"
       echo "  Data: $MY_DATA | size=11"
   fi
   ```

3. **Add custom colors**:
   Valid values: `red`, `green`, `blue`, `gray`, `orange`, `yellow`, `#RRGGBB`

## Testing

### Test Eventd Locally

```bash
# Run daemon in foreground for debugging
bash -x bin/opencode-eventd

# Check state file
jq '.' /tmp/opencode-state.json

# Monitor logs
tail -f /tmp/opencode-eventd.log
```

### Test Plugin Manually

```bash
# Run plugin directly
bash plugins/opencode.2s.sh

# Check output format
bash plugins/opencode.2s.sh | head -20
```

### Test Data Files

```bash
# Create sample state
cat > /tmp/opencode-state.json << 'EOF'
{
  "instances": [],
  "instance_count": 0,
  "agent_count": 0,
  "busy_count": 0,
  "todos": {"pending": 0, "in_progress": 0},
  "permissions_pending": 0,
  "tools_running": [],
  "updated": $(date +%s),
  "connected": false
}
EOF

# Test plugin with sample data
bash plugins/opencode.2s.sh
```

## Building for Release

### 1. Update Version
Edit `README.md` and `DEVELOPMENT.md` with version info

### 2. Test All Components
```bash
bash install.sh
bash plugins/opencode.2s.sh
tail -f /tmp/opencode-eventd.log
```

### 3. Create Git Tags
```bash
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0
```

## Debugging

### Enable Verbose Logging

Edit `bin/opencode-eventd` and uncomment debug statements:

```bash
# Add near functions you want to debug
set -x  # Enable debug mode
# ... function code ...
set +x  # Disable debug mode
```

### Check System State

```bash
# Find OpenCode ports
/usr/sbin/lsof -i -P 2>/dev/null | grep opencode

# Check daemon processes
ps aux | grep opencode

# Check launchd services
launchctl list | grep opencode

# Check loaded agents
ls -la ~/Library/LaunchAgents/com.opencode.*
```

## Common Issues & Solutions

### Daemon not finding OpenCode instances
- Verify OpenCode is running: `ps aux | grep opencode`
- Check ports: `lsof -i :4096` (replace 4096 with actual port)
- Check eventd logs: `tail -f /tmp/opencode-eventd.log`

### Plugin not updating
- Verify state file exists: `ls -la /tmp/opencode-state.json`
- Check plugin syntax: `bash -n plugins/opencode.2s.sh`
- Check SwiftBar plugin directory: `ls ~/Library/Application\ Support/SwiftBar/Plugins/`

### Services not starting
- Check plist syntax: `plutil -lint ~/Library/LaunchAgents/com.opencode.eventd.plist`
- Reload: `launchctl unload ... && launchctl load ...`
- Check launchd logs: `log stream --predicate 'process == "launchd"'`

## Performance Considerations

### Memory Usage
- Daemons: ~7-8 MB each
- Keep JSON files compact (jq -c flag)

### CPU Usage
- Polling every 30s (configurable)
- SSE listeners have minimal CPU
- Plugin refresh every 2s (configurable)

### Network Usage
- One HTTP request per instance per 30s poll
- One HTTPS request to Anthropic API every 5 minutes
- SSE stream connection (persistent, low bandwidth)

## Future Enhancements

- [ ] Add sound notifications
- [ ] Custom alert thresholds
- [ ] Database for historical data
- [ ] Web dashboard
- [ ] Multiple user support
- [ ] Configuration file support
