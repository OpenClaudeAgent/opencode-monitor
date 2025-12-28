# OpenCode SwiftBar Monitor - Makefile
#
# Usage: make <target>
#   make install       - Full installation
#   make reload        - Reload all components
#   make reload-plugin - Reload only SwiftBar plugin
#   make status        - Show service status

.PHONY: help install uninstall reload reload-plugin reload-eventd reload-usaged \
        run-eventd run-usaged logs logs-eventd logs-usaged status clean \
        sync-roadmap sync-from-roadmap roadmap \
        debug-record debug-analyze

# Paths
INSTALL_PATH := $(HOME)/.local/bin
SWIFTBAR_PLUGINS := $(HOME)/Library/Application Support/SwiftBar/Plugins
LAUNCHD_AGENTS := $(HOME)/Library/LaunchAgents

# Default target
help:
	@echo "OpenCode SwiftBar Monitor"
	@echo ""
	@echo "Installation:"
	@echo "  make install        Full installation"
	@echo "  make uninstall      Remove all components"
	@echo ""
	@echo "Development:"
	@echo "  make reload         Reload all (daemons + plugin)"
	@echo "  make reload-plugin  Reload SwiftBar plugin only"
	@echo "  make reload-eventd  Restart eventd daemon"
	@echo "  make reload-usaged  Restart usaged daemon"
	@echo ""
	@echo "Debug:"
	@echo "  make run-eventd     Run eventd in foreground"
	@echo "  make run-usaged     Run usaged in foreground"
	@echo "  make logs           Tail all logs"
	@echo "  make logs-eventd    Tail eventd logs"
	@echo "  make logs-usaged    Tail usaged logs"
	@echo "  make status         Show service status"
	@echo "  make debug-record   Record OpenCode events for analysis"
	@echo "  make debug-analyze  Analyze recorded events"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean          Remove temp files"
	@echo ""
	@echo "Worktrees:"
	@echo "  make roadmap        Show roadmap status"
	@echo "  make sync-roadmap   Sync master -> roadmap worktree"
	@echo "  make sync-from-roadmap  Merge roadmap -> master"

# === Installation ===

install:
	@bash install.sh

uninstall:
	@bash uninstall.sh

# === Development ===

reload: reload-eventd reload-usaged reload-plugin
	@echo "All components reloaded"

reload-plugin:
	@cp plugins/opencode.2s.sh "$(SWIFTBAR_PLUGINS)/"
	@chmod +x "$(SWIFTBAR_PLUGINS)/opencode.2s.sh"
	@open -g "swiftbar://refreshplugin?name=opencode" 2>/dev/null || true
	@echo "Plugin reloaded"

reload-eventd:
	@cp bin/opencode-eventd "$(INSTALL_PATH)/"
	@chmod +x "$(INSTALL_PATH)/opencode-eventd"
	@launchctl unload "$(LAUNCHD_AGENTS)/com.opencode.eventd.plist" 2>/dev/null || true
	@launchctl load "$(LAUNCHD_AGENTS)/com.opencode.eventd.plist"
	@echo "eventd reloaded"

reload-usaged:
	@cp bin/opencode-usaged "$(INSTALL_PATH)/"
	@chmod +x "$(INSTALL_PATH)/opencode-usaged"
	@launchctl unload "$(LAUNCHD_AGENTS)/com.opencode.usaged.plist" 2>/dev/null || true
	@launchctl load "$(LAUNCHD_AGENTS)/com.opencode.usaged.plist"
	@echo "usaged reloaded"

# === Debug ===

run-eventd:
	@echo "Running eventd in foreground (Ctrl+C to stop)..."
	@launchctl unload "$(LAUNCHD_AGENTS)/com.opencode.eventd.plist" 2>/dev/null || true
	@bash bin/opencode-eventd

run-usaged:
	@echo "Running usaged in foreground (Ctrl+C to stop)..."
	@launchctl unload "$(LAUNCHD_AGENTS)/com.opencode.usaged.plist" 2>/dev/null || true
	@bash bin/opencode-usaged

logs:
	@tail -f /tmp/opencode-eventd.log /tmp/opencode-usaged.log

logs-eventd:
	@tail -f /tmp/opencode-eventd.log

logs-usaged:
	@tail -f /tmp/opencode-usaged.log

status:
	@echo "=== LaunchD Services ==="
	@launchctl list | grep opencode || echo "No services loaded"
	@echo ""
	@echo "=== Running Processes ==="
	@pgrep -fl "opencode-(eventd|usaged)" | head -5 || echo "No processes"
	@echo ""
	@echo "=== State Files ==="
	@ls -la /tmp/opencode-*.json 2>/dev/null || echo "No state files"
	@echo ""
	@echo "=== Current State ==="
	@cat /tmp/opencode-state.json 2>/dev/null | jq -c '{connected, instances: .instance_count, agents: .agent_count, busy: .busy_count}' 2>/dev/null || echo "No state"

debug-record:
	@bash bin/opencode-debug record

debug-analyze:
	@bash bin/opencode-debug analyze

# === Maintenance ===

clean:
	@rm -f /tmp/opencode-state.json
	@rm -f /tmp/opencode-usage.json
	@rm -f /tmp/opencode-eventd.log
	@rm -f /tmp/opencode-usaged.log
	@rm -f /tmp/opencode-events.fifo
	@rm -rf /tmp/opencode-eventd.lock
	@rm -rf /tmp/opencode-usaged.lock
	@echo "Temp files cleaned"

# === Worktrees ===

roadmap:
	@echo "=== Roadmap ==="
	@cat worktrees/roadmap/roadmap/README.md 2>/dev/null || cat roadmap/README.md 2>/dev/null || echo "No roadmap found"

sync-roadmap:
	@echo "Syncing master -> roadmap worktree..."
	@cd worktrees/roadmap && git checkout worktree/roadmap && git merge master --no-edit
	@echo "Roadmap worktree synced with master"

sync-from-roadmap:
	@echo "Syncing roadmap -> master..."
	@git merge worktree/roadmap --no-edit
	@echo "Master synced with roadmap changes"
