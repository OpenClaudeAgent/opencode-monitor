"""
TraceDetailPanel package - Modular detail panel for trace viewing.

Structure:
    - panel.py: Main TraceDetailPanel class
    - controller.py: PanelController for handling selections
    - components/: Reusable UI components (MetricsBar, StatusBadge)
    - handlers/: Data loading mixins
    - strategies/: Strategy pattern for content generation
"""

from .panel import TraceDetailPanel
from .controller import PanelController

__all__ = ["TraceDetailPanel", "PanelController"]
