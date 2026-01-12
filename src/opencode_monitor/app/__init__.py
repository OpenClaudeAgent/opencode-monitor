"""
OpenCode Monitor - rumps menu bar application.

This package provides the OpenCodeApp class for macOS menu bar monitoring.

Modules:
- core: Main OpenCodeApp class with state and lifecycle management
- menu: Menu building mixin
- handlers: Callback handlers mixin
"""

# Re-exports for backwards compatibility with existing imports and tests
from ..core.models import State, SessionStatus, Usage
from ..core.monitor import fetch_all_instances
from ..core.usage import fetch_usage
from ..utils.settings import get_settings, save_settings
from ..utils.logger import info, error, debug
from ..security.analyzer import SecurityAlert, RiskLevel
from ..security.auditor import get_auditor, start_auditor
from ..security.reporter import SecurityReporter
from ..ui.terminal import focus_iterm2
from ..ui.menu import (
    MenuBuilder,
    truncate_with_tooltip,
    TITLE_MAX_LENGTH,
    TOOL_ARG_MAX_LENGTH,
    TODO_CURRENT_MAX_LENGTH,
    TODO_PENDING_MAX_LENGTH,
)
from ..analytics import AnalyticsDB, load_opencode_data
from ..dashboard import show_dashboard

# Now import the main class (after dependencies are set up)
from .core import OpenCodeApp, main

# Re-export for backwards compatibility with tests
_truncate_with_tooltip = truncate_with_tooltip

__all__ = [
    # Main exports
    "OpenCodeApp",
    "main",
    # Backwards compatibility re-exports
    "State",
    "SessionStatus",
    "Usage",
    "fetch_all_instances",
    "fetch_usage",
    "get_settings",
    "save_settings",
    "info",
    "error",
    "debug",
    "SecurityAlert",
    "RiskLevel",
    "get_auditor",
    "start_auditor",
    "SecurityReporter",
    "focus_iterm2",
    "MenuBuilder",
    "truncate_with_tooltip",
    "_truncate_with_tooltip",
    "TITLE_MAX_LENGTH",
    "TOOL_ARG_MAX_LENGTH",
    "TODO_CURRENT_MAX_LENGTH",
    "TODO_PENDING_MAX_LENGTH",
    "AnalyticsDB",
    "load_opencode_data",
    "show_dashboard",
]
