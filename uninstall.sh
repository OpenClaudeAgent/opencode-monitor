#!/opt/homebrew/bin/bash
#
# OpenCode SwiftBar Monitor - Uninstallation Script
# Désinstalle les démons et le plugin SwiftBar
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

INSTALL_PATH="${HOME}/.local/bin"
SWIFTBAR_PLUGINS="${HOME}/Library/Application Support/SwiftBar/Plugins"
LAUNCHD_AGENTS="${HOME}/Library/LaunchAgents"

echo -e "${YELLOW}======================================${NC}"
echo -e "${YELLOW}  OpenCode SwiftBar Monitor${NC}"
echo -e "${YELLOW}  Désinstallation${NC}"
echo -e "${YELLOW}======================================${NC}"
echo ""

# Unload services
echo -e "${YELLOW}⏹️  Arrêt des services...${NC}"
launchctl unload "$LAUNCHD_AGENTS/com.opencode.eventd.plist" 2>/dev/null || true
launchctl unload "$LAUNCHD_AGENTS/com.opencode.usaged.plist" 2>/dev/null || true

# Remove files
echo -e "${YELLOW}🗑️  Suppression des fichiers...${NC}"
rm -f "$INSTALL_PATH/opencode-eventd"
rm -f "$INSTALL_PATH/opencode-usaged"
rm -f "$SWIFTBAR_PLUGINS/opencode.2s.sh"
rm -f "$LAUNCHD_AGENTS/com.opencode.eventd.plist"
rm -f "$LAUNCHD_AGENTS/com.opencode.usaged.plist"

# Kill any remaining processes
pkill -f "opencode-eventd" 2>/dev/null || true
pkill -f "opencode-usaged" 2>/dev/null || true

echo -e "${GREEN}✅ Désinstallation terminée${NC}"
echo ""
