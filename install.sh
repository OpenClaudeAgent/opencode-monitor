#!/opt/homebrew/bin/bash
#
# OpenCode SwiftBar Monitor - Installation Script
# Installe les démons et le plugin SwiftBar
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
INSTALL_PATH="${HOME}/.local/bin"
SWIFTBAR_PLUGINS="${HOME}/Library/Application Support/SwiftBar/Plugins"
LAUNCHD_AGENTS="${HOME}/Library/LaunchAgents"

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}  OpenCode SwiftBar Monitor Setup${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""

# Check if SwiftBar is installed
if [[ ! -d "$SWIFTBAR_PLUGINS" ]]; then
    echo -e "${YELLOW}⚠️  SwiftBar n'est pas installé${NC}"
    echo "Installation de SwiftBar via Homebrew..."
    brew install --cask swiftbar 2>/dev/null || {
        echo -e "${RED}❌ Impossible d'installer SwiftBar${NC}"
        echo "Installer manuellement: https://swiftbar.app"
        exit 1
    }
fi

# Create directories
echo -e "${YELLOW}📁 Création des répertoires...${NC}"
mkdir -p "$INSTALL_PATH"
mkdir -p "$SWIFTBAR_PLUGINS"
mkdir -p "$LAUNCHD_AGENTS"

# Install daemons
echo -e "${YELLOW}📤 Installation des démons...${NC}"
cp "$SCRIPT_DIR/bin/opencode-eventd" "$INSTALL_PATH/"
cp "$SCRIPT_DIR/bin/opencode-usaged" "$INSTALL_PATH/"
chmod +x "$INSTALL_PATH/opencode-eventd"
chmod +x "$INSTALL_PATH/opencode-usaged"
echo -e "${GREEN}✅ Démons installés${NC}"

# Install SwiftBar plugin
echo -e "${YELLOW}📦 Installation du plugin SwiftBar...${NC}"
cp "$SCRIPT_DIR/plugins/opencode.2s.sh" "$SWIFTBAR_PLUGINS/"
chmod +x "$SWIFTBAR_PLUGINS/opencode.2s.sh"
echo -e "${GREEN}✅ Plugin installé${NC}"

# Install launchd agents
echo -e "${YELLOW}⚙️  Configuration des services...${NC}"

# Update plist paths
sed "s|INSTALL_PATH|$INSTALL_PATH|g" "$SCRIPT_DIR/launchd/com.opencode.eventd.plist" > "$LAUNCHD_AGENTS/com.opencode.eventd.plist"
sed "s|INSTALL_PATH|$INSTALL_PATH|g" "$SCRIPT_DIR/launchd/com.opencode.usaged.plist" > "$LAUNCHD_AGENTS/com.opencode.usaged.plist"
chmod 644 "$LAUNCHD_AGENTS/com.opencode.eventd.plist"
chmod 644 "$LAUNCHD_AGENTS/com.opencode.usaged.plist"

# Load services
launchctl load "$LAUNCHD_AGENTS/com.opencode.eventd.plist" 2>/dev/null || {
    echo -e "${YELLOW}⚠️  Service eventd déjà chargé (reload)${NC}"
    launchctl unload "$LAUNCHD_AGENTS/com.opencode.eventd.plist" 2>/dev/null || true
    launchctl load "$LAUNCHD_AGENTS/com.opencode.eventd.plist"
}

launchctl load "$LAUNCHD_AGENTS/com.opencode.usaged.plist" 2>/dev/null || {
    echo -e "${YELLOW}⚠️  Service usaged déjà chargé (reload)${NC}"
    launchctl unload "$LAUNCHD_AGENTS/com.opencode.usaged.plist" 2>/dev/null || true
    launchctl load "$LAUNCHD_AGENTS/com.opencode.usaged.plist"
}

echo -e "${GREEN}✅ Services configurés et lancés${NC}"

# Verify installation
echo ""
echo -e "${YELLOW}🔍 Vérification de l'installation...${NC}"
sleep 2

if [[ -f /tmp/opencode-state.json ]]; then
    echo -e "${GREEN}✅ Démon eventd actif${NC}"
else
    echo -e "${RED}❌ Démon eventd pas actif${NC}"
fi

if pgrep -f "opencode-usaged" > /dev/null; then
    echo -e "${GREEN}✅ Démon usaged actif${NC}"
else
    echo -e "${RED}❌ Démon usaged pas actif${NC}"
fi

if [[ -f "$SWIFTBAR_PLUGINS/opencode.2s.sh" ]]; then
    echo -e "${GREEN}✅ Plugin SwiftBar installé${NC}"
else
    echo -e "${RED}❌ Plugin SwiftBar absent${NC}"
fi

echo ""
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}  ✅ Installation terminée !${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo "📍 Emplacements d'installation:"
echo "   Démons: $INSTALL_PATH"
echo "   Plugin: $SWIFTBAR_PLUGINS"
echo "   Services: $LAUNCHD_AGENTS"
echo ""
echo "📖 Logs disponibles:"
echo "   Eventd: tail -f /tmp/opencode-eventd.log"
echo "   Usaged: tail -f /tmp/opencode-usaged.log"
echo ""
echo "🔄 Redémarrer les services:"
echo "   launchctl unload ~/Library/LaunchAgents/com.opencode.eventd.plist"
echo "   launchctl load ~/Library/LaunchAgents/com.opencode.eventd.plist"
echo ""
