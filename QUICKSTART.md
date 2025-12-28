# Quick Start

Get OpenCode Monitor running in 2 minutes.

## 1. Install

```bash
cd opencode-swiftbar-monitor
make run
```

That's it! The app will appear in your menu bar with a 🤖 icon.

## 2. What You'll See

### Menu Bar
```
🤖 2 ⏳3 🟢45%
```
- Number of busy agents
- Pending todos count
- Claude API usage %

### Click to Open Menu
```
🤖 My Agent Task
    🔧 bash: running command
    🔄 Current todo
    └ ● Sub-agent
⚪ Idle Instance (idle)
---
🟢 Session: 45%
📅 Weekly: 29%
📊 Open Claude Usage
---
⚙️ Preferences
---
Quit
```

## 3. Features

- **Click agent** → Focus its terminal in iTerm2
- **⚙️ Preferences** → Configure refresh rate and sounds
- **📊 Open Claude Usage** → Open Claude usage page

## 4. Configure

Click **⚙️ Preferences** to:

- Set usage refresh interval (30s - 10m)
- Enable/disable completion sounds

## 5. Stop

- Click **Quit** in the menu, or
- `pkill -f opencode-menubar`

## 6. Run Again

```bash
make run
```

## Troubleshooting

**No icon in menu bar?**
```bash
pkill -f opencode-menubar
make run
```

**No instances showing?**
- Make sure OpenCode is running
- Check: `lsof -i :4096` (or your OpenCode port)

**Need logs?**
```bash
uv run python3 bin/opencode-menubar 2>&1 | tee debug.log
```
