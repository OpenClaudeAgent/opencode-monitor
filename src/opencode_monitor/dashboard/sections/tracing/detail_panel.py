"""
TraceDetailPanel - Panel showing detailed trace/session information with tabs.

Features:
- Header with key metrics (duration, tokens, tools, files, agents, status)
- 6 tabs: Transcript, Tokens, Tools, Files, Agents, Timeline
- Lazy loading: only loads data for the active tab
- TracingDataService integration
- Scrollable content for overflow handling
"""

import os
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QTabWidget,
    QScrollArea,
)
from PyQt6.QtCore import Qt

from opencode_monitor.dashboard.styles import COLORS, SPACING, FONTS, RADIUS
from opencode_monitor.utils.logger import debug

from .helpers import format_duration, format_tokens_short
from .tabs import (
    TokensTab,
    ToolsTab,
    FilesTab,
    AgentsTab,
    TimelineTab,
    TranscriptTab,
)

if TYPE_CHECKING:
    from opencode_monitor.analytics import TracingDataService


class TraceDetailPanel(QFrame):
    """Panel showing detailed trace/session information with tabbed sections."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("trace-detail")
        self.setMinimumWidth(400)

        # TracingDataService instance (lazy loaded)
        self._service: Optional["TracingDataService"] = None
        self._current_session_id: Optional[str] = None
        self._current_data: dict = {}
        self._tree_data: dict = {}

        self.setStyleSheet(f"""
            QFrame#trace-detail {{
                background-color: {COLORS["bg_surface"]};
                border: 1px solid {COLORS["border_default"]};
                border-radius: {RADIUS["lg"]}px;
            }}
        """)

        # Main layout with scroll area
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: {COLORS["bg_surface"]};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {COLORS["border_default"]};
                border-radius: 4px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {COLORS["text_muted"]};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)

        # Content widget inside scroll area
        content = QWidget()
        content.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(
            SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"]
        )
        layout.setSpacing(SPACING["md"])

        # === Breadcrumb ===
        self._setup_breadcrumb(layout)

        # === Header Section ===
        self._setup_header(layout)

        # === Metrics Row ===
        self._setup_metrics(layout)

        # === Separator ===
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {COLORS['border_default']};")
        sep.setFixedHeight(1)
        layout.addWidget(sep)

        # === Tab Widget ===
        self._setup_tabs(layout)

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def _setup_breadcrumb(self, layout: QVBoxLayout) -> None:
        """Setup breadcrumb navigation showing path from ROOT to current."""
        self._breadcrumb = QLabel("")
        self._breadcrumb.setStyleSheet(f"""
            font-size: {FONTS["size_sm"]}px;
            color: {COLORS["text_muted"]};
            padding: {SPACING["xs"]}px 0;
        """)
        self._breadcrumb.setWordWrap(True)
        self._breadcrumb.hide()  # Hidden until we have a path
        layout.addWidget(self._breadcrumb)

    def _update_breadcrumb(self, path: list[str]) -> None:
        """Update breadcrumb with navigation path.

        Args:
            path: List of names from root to current (e.g., ["opencode-monitor", "coordinateur", "executeur"])
        """
        if not path:
            self._breadcrumb.hide()
            return

        # Build breadcrumb with arrows
        breadcrumb_text = " › ".join(path)
        self._breadcrumb.setText(breadcrumb_text)
        self._breadcrumb.show()

    def _setup_header(self, layout: QVBoxLayout) -> None:
        """Setup header with title and status."""
        header_row = QHBoxLayout()
        header_row.setSpacing(SPACING["sm"])

        self._header = QLabel("Select a session")
        self._header.setStyleSheet(f"""
            font-size: {FONTS["size_lg"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_muted"]};
        """)
        header_row.addWidget(self._header)
        header_row.addStretch()

        self._status_badge = QLabel("")
        self._status_badge.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            font-weight: {FONTS["weight_semibold"]};
            padding: {SPACING["xs"]}px {SPACING["sm"]}px;
            border-radius: {RADIUS["sm"]}px;
            background-color: {COLORS["success_muted"]};
            color: {COLORS["success"]};
        """)
        self._status_badge.hide()
        header_row.addWidget(self._status_badge)

        layout.addLayout(header_row)

    def _setup_metrics(self, layout: QVBoxLayout) -> None:
        """Setup metrics row with key KPIs."""
        metrics_container = QFrame()
        metrics_container.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS["bg_hover"]};
                border-radius: {RADIUS["md"]}px;
                padding: {SPACING["sm"]}px;
            }}
        """)

        metrics_layout = QHBoxLayout(metrics_container)
        metrics_layout.setContentsMargins(
            SPACING["md"], SPACING["sm"], SPACING["md"], SPACING["sm"]
        )
        metrics_layout.setSpacing(SPACING["lg"])

        # Create metrics labels
        self._metric_duration = self._create_metric("⏱", "0s", "Duration")
        self._metric_tokens = self._create_metric("🎫", "0", "Tokens")
        self._metric_tools = self._create_metric("🔧", "0", "Tools")
        self._metric_files = self._create_metric("📁", "0", "Files")
        self._metric_agents = self._create_metric("🤖", "0", "Agents")

        metrics_layout.addWidget(self._metric_duration)
        metrics_layout.addWidget(self._metric_tokens)
        metrics_layout.addWidget(self._metric_tools)
        metrics_layout.addWidget(self._metric_files)
        metrics_layout.addWidget(self._metric_agents)
        metrics_layout.addStretch()

        layout.addWidget(metrics_container)

    def _create_metric(self, icon: str, value: str, label: str) -> QWidget:
        """Create a single metric widget."""
        widget = QWidget()
        widget_layout = QVBoxLayout(widget)
        widget_layout.setContentsMargins(0, 0, 0, 0)
        widget_layout.setSpacing(2)

        # Value with icon
        value_label = QLabel(f"{icon} {value}")
        value_label.setObjectName("metric_value")
        value_label.setStyleSheet(f"""
            font-size: {FONTS["size_md"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_primary"]};
        """)
        widget_layout.addWidget(value_label)

        # Label
        label_widget = QLabel(label)
        label_widget.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            color: {COLORS["text_muted"]};
        """)
        widget_layout.addWidget(label_widget)

        return widget

    def _update_metric(self, metric_widget: QWidget, icon: str, value: str) -> None:
        """Update a metric widget's value."""
        value_label = metric_widget.findChild(QLabel, "metric_value")
        if value_label:
            value_label.setText(f"{icon} {value}")

    def _setup_tabs(self, layout: QVBoxLayout) -> None:
        """Setup tab widget with 6 sections."""
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {COLORS["border_default"]};
                border-radius: {RADIUS["md"]}px;
                background-color: {COLORS["bg_surface"]};
                padding: {SPACING["sm"]}px;
            }}
            QTabBar::tab {{
                background-color: {COLORS["bg_elevated"]};
                color: {COLORS["text_secondary"]};
                padding: {SPACING["md"]}px {SPACING["lg"]}px;
                margin-right: 4px;
                border-top-left-radius: {RADIUS["sm"]}px;
                border-top-right-radius: {RADIUS["sm"]}px;
                font-size: 16px;
                min-width: 32px;
            }}
            QTabBar::tab:selected {{
                background-color: {COLORS["accent_primary_muted"]};
                color: {COLORS["accent_primary"]};
                font-weight: {FONTS["weight_semibold"]};
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {COLORS["bg_hover"]};
                color: {COLORS["text_primary"]};
            }}
        """)

        # Create tabs
        self._transcript_tab = TranscriptTab()
        self._tokens_tab = TokensTab()
        self._tools_tab = ToolsTab()
        self._files_tab = FilesTab()
        self._agents_tab = AgentsTab()
        self._timeline_tab = TimelineTab()

        # Short tab labels to avoid truncation
        self._tabs.addTab(self._transcript_tab, "📜")
        self._tabs.addTab(self._tokens_tab, "📊")
        self._tabs.addTab(self._tools_tab, "🔧")
        self._tabs.addTab(self._files_tab, "📁")
        self._tabs.addTab(self._agents_tab, "🤖")
        self._tabs.addTab(self._timeline_tab, "⏱")

        # Add tooltips for clarity
        self._tabs.setTabToolTip(0, "Transcript - Full conversation")
        self._tabs.setTabToolTip(1, "Tokens - Usage breakdown")
        self._tabs.setTabToolTip(2, "Tools - Tool calls")
        self._tabs.setTabToolTip(3, "Files - File operations")
        self._tabs.setTabToolTip(4, "Agents - Agent hierarchy")
        self._tabs.setTabToolTip(5, "Timeline - Event timeline")

        # Connect tab change for lazy loading
        self._tabs.currentChanged.connect(self._on_tab_changed)

        layout.addWidget(self._tabs)

    def _get_api_client(self):
        """Get the API client for data access."""
        from opencode_monitor.api import get_api_client

        return get_api_client()

    def _on_tab_changed(self, index: int) -> None:
        """Handle tab change - load data for new tab if needed."""
        if not self._current_session_id:
            return

        # Load data for the selected tab
        self._load_tab_data(index)

    def _load_tab_data(self, tab_index: int) -> None:
        """Load data for a specific tab via API."""
        if not self._current_session_id:
            debug("[TraceDetailPanel] _load_tab_data: no session_id")
            return

        client = self._get_api_client()

        if not client.is_available:
            debug("[TraceDetailPanel] _load_tab_data: API not available")
            return

        try:
            # Tab indices:
            # 0 = Transcript, 1 = Tokens, 2 = Tools, 3 = Files, 4 = Agents, 5 = Timeline
            if tab_index == 0:  # Transcript
                if not self._transcript_tab.is_loaded():
                    debug(
                        f"[TraceDetailPanel] Loading prompts for transcript {self._current_session_id}"
                    )
                    prompts_data = client.get_session_prompts(self._current_session_id)
                    debug(
                        f"[TraceDetailPanel] Prompts data: {prompts_data is not None}"
                    )
                    if prompts_data:
                        # Convert prompts data to transcript format
                        self._transcript_tab.load_data(
                            {
                                "user_content": prompts_data.get("prompt_input", ""),
                                "assistant_content": prompts_data.get(
                                    "prompt_output", ""
                                ),
                            }
                        )
                    else:
                        self._transcript_tab.load_data(
                            {
                                "user_content": "(No prompt data available)",
                                "assistant_content": "(Session may be empty or API unavailable)",
                            }
                        )
            elif tab_index == 1:  # Tokens
                if not self._tokens_tab.is_loaded():
                    data = client.get_session_tokens(self._current_session_id)
                    if data:
                        self._tokens_tab.load_data(data)
            elif tab_index == 2:  # Tools
                if not self._tools_tab.is_loaded():
                    data = client.get_session_tools(self._current_session_id)
                    if data:
                        self._tools_tab.load_data(data)
            elif tab_index == 3:  # Files
                if not self._files_tab.is_loaded():
                    data = client.get_session_files(self._current_session_id)
                    if data:
                        self._files_tab.load_data(data)
            elif tab_index == 4:  # Agents
                if not self._agents_tab.is_loaded():
                    agents = client.get_session_agents(self._current_session_id)
                    if agents:
                        self._agents_tab.load_data(agents)
            elif tab_index == 5:  # Timeline
                if not self._timeline_tab.is_loaded():
                    events = client.get_session_timeline(self._current_session_id)
                    if events:
                        self._timeline_tab.load_data(events)
        except Exception as e:
            debug(f"Failed to load tab data: {e}")

    def show_session_summary(
        self, session_id: str, tree_data: dict | None = None
    ) -> None:
        """Show session summary with data from TracingDataService.

        This is the main entry point for displaying session details.
        Loads summary data and updates all metrics. Tab data is lazy loaded.

        For root sessions: fetches data from API
        For child sessions (sub-agents): uses tree_data directly

        Args:
            session_id: The session ID to display
            tree_data: Optional data from tree item for consistent metrics
        """
        debug(f"[TraceDetailPanel] show_session_summary called for: {session_id}")
        self._current_session_id = session_id
        self._tree_data = tree_data or {}

        # Clear all tabs
        self._clear_tabs()

        # Check if this is a child session (sub-agent trace)
        agent_type = self._tree_data.get("agent_type")
        is_child = agent_type is not None and agent_type != "user"

        if is_child:
            # For child sessions, use tree_data directly (more accurate for specific trace)
            self._show_child_session(tree_data or {})
            return

        # For root sessions, get summary from API
        client = self._get_api_client()

        if not client.is_available:
            debug("[TraceDetailPanel] API not available, using fallback")
            self._header.setText("API not available")
            self._header.setStyleSheet(f"""
                font-size: {FONTS["size_lg"]}px;
                font-weight: {FONTS["weight_semibold"]};
                color: {COLORS["text_muted"]};
            """)
            return

        summary = client.get_session_summary(session_id)
        debug(f"[TraceDetailPanel] Got summary: {summary is not None}")

        if summary is None:
            summary = {"meta": {}, "summary": {}, "details": {}}

        self._current_data = summary
        meta = summary.get("meta", {})
        s = summary.get("summary", {})

        # Update header
        directory = meta.get("directory", "")
        project_name = os.path.basename(directory) if directory else "Session"

        header_text = f"🌳 {project_name}"
        self._header.setText(header_text)
        self._header.setStyleSheet(f"""
            font-size: {FONTS["size_lg"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_primary"]};
        """)

        # Update breadcrumb (root session = just project name)
        self._update_breadcrumb([f"🌳 {project_name}"])

        # Update status badge
        status = s.get("status", "completed")
        self._update_status_badge(status)

        # Update metrics - prefer tree_data for consistency with tree display
        duration_ms = self._tree_data.get("duration_ms") or s.get("duration_ms", 0)
        total_tokens = s.get("total_tokens", 0)
        total_tools = s.get("total_tool_calls", 0)
        total_files = s.get("total_files", 0)
        agents_count = self._tree_data.get("children_count", s.get("unique_agents", 0))

        self._update_metric(self._metric_duration, "⏱", format_duration(duration_ms))
        self._update_metric(
            self._metric_tokens, "🎫", format_tokens_short(total_tokens)
        )
        self._update_metric(self._metric_tools, "🔧", str(total_tools))
        self._update_metric(self._metric_files, "📁", str(total_files))
        self._update_metric(self._metric_agents, "🤖", str(agents_count))

        # Load data for current tab
        self._load_tab_data(self._tabs.currentIndex())

    def _show_child_session(self, tree_data: dict) -> None:
        """Show details for a child session (sub-agent trace)."""
        agent_type = tree_data.get("agent_type", "agent")
        parent_agent = tree_data.get("parent_agent", "user")
        title = tree_data.get("title", "")
        status = tree_data.get("status", "completed")

        # Update header - show delegation chain
        if parent_agent:
            # Use 💬 for user-initiated, 🔗 for agent delegations
            icon = "💬" if parent_agent == "user" else "🔗"
            header_text = f"{icon} {parent_agent} → {agent_type}"
        else:
            header_text = f"🤖 {agent_type}"

        self._header.setText(header_text)
        self._header.setStyleSheet(f"""
            font-size: {FONTS["size_lg"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_primary"]};
        """)

        # Update breadcrumb - show delegation path
        breadcrumb_path = ["🌳 ROOT"]
        if parent_agent and parent_agent != "user":
            breadcrumb_path.append(f"🔗 {parent_agent}")
        breadcrumb_path.append(f"🤖 {agent_type}")
        self._update_breadcrumb(breadcrumb_path)

        # Update status badge
        self._update_status_badge(status)

        # Update metrics from tree_data
        duration_ms = tree_data.get("duration_ms") or 0
        tokens_in = tree_data.get("tokens_in") or 0
        tokens_out = tree_data.get("tokens_out") or 0
        total_tokens = tokens_in + tokens_out
        children_count = tree_data.get("children_count") or 0

        self._update_metric(self._metric_duration, "⏱", format_duration(duration_ms))
        self._update_metric(
            self._metric_tokens, "🎫", format_tokens_short(total_tokens)
        )
        self._update_metric(self._metric_tools, "🔧", "-")
        self._update_metric(self._metric_files, "📁", "-")
        self._update_metric(self._metric_agents, "🤖", str(children_count))

        # Get prompts directly from tree_data
        prompt_input = tree_data.get("prompt_input")
        prompt_output = tree_data.get("prompt_output")

        # Fallback if no prompts found
        if not prompt_input:
            prompt_input = title if title else f"Task delegated to {agent_type}"
        if not prompt_output:
            prompt_output = (
                f"Agent: {agent_type}\n"
                f"Duration: {format_duration(duration_ms)}\n"
                f"Tokens: {format_tokens_short(tokens_in)} in / {format_tokens_short(tokens_out)} out\n"
                f"Status: {status}"
            )

        # Store data for transcript tab
        self._current_data = {
            "user_content": prompt_input,
            "assistant_content": prompt_output,
        }

        # Load transcript tab with local data
        self._transcript_tab.load_data(self._current_data)
        self._tabs.setCurrentIndex(0)

    def _update_status_badge(self, status: str) -> None:
        """Update the status badge appearance."""
        if status == "completed":
            self._status_badge.setText("✅ Completed")
            self._status_badge.setStyleSheet(f"""
                font-size: {FONTS["size_xs"]}px;
                font-weight: {FONTS["weight_semibold"]};
                padding: {SPACING["xs"]}px {SPACING["sm"]}px;
                border-radius: {RADIUS["sm"]}px;
                background-color: {COLORS["success_muted"]};
                color: {COLORS["success"]};
            """)
        elif status == "running":
            self._status_badge.setText("⏳ Running")
            self._status_badge.setStyleSheet(f"""
                font-size: {FONTS["size_xs"]}px;
                font-weight: {FONTS["weight_semibold"]};
                padding: {SPACING["xs"]}px {SPACING["sm"]}px;
                border-radius: {RADIUS["sm"]}px;
                background-color: {COLORS["warning_muted"]};
                color: {COLORS["warning"]};
            """)
        elif status == "error":
            self._status_badge.setText("❌ Error")
            self._status_badge.setStyleSheet(f"""
                font-size: {FONTS["size_xs"]}px;
                font-weight: {FONTS["weight_semibold"]};
                padding: {SPACING["xs"]}px {SPACING["sm"]}px;
                border-radius: {RADIUS["sm"]}px;
                background-color: {COLORS["error_muted"]};
                color: {COLORS["error"]};
            """)
        else:
            self._status_badge.setText(
                f"● {status.capitalize() if status else 'Unknown'}"
            )
            self._status_badge.setStyleSheet(f"""
                font-size: {FONTS["size_xs"]}px;
                font-weight: {FONTS["weight_semibold"]};
                padding: {SPACING["xs"]}px {SPACING["sm"]}px;
                border-radius: {RADIUS["sm"]}px;
                background-color: {COLORS["info_muted"]};
                color: {COLORS["info"]};
            """)
        self._status_badge.show()

    def show_turn(
        self,
        user_content: str,
        assistant_content: Optional[str],
        tokens_in: int = 0,
        tokens_out: int = 0,
        timestamp: Optional[str] = None,
    ) -> None:
        """Display a conversation turn (user prompt + assistant response)."""
        self._current_session_id = None
        self._clear_tabs()

        # Update header
        self._header.setText("💬 Conversation Turn")
        self._header.setStyleSheet(f"""
            font-size: {FONTS["size_lg"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_primary"]};
        """)

        # Hide status badge
        self._status_badge.hide()

        # Update metrics
        total_tokens = (tokens_in or 0) + (tokens_out or 0)
        self._update_metric(self._metric_duration, "⏱", "-")
        self._update_metric(
            self._metric_tokens, "🎫", format_tokens_short(total_tokens)
        )
        self._update_metric(self._metric_tools, "🔧", "-")
        self._update_metric(self._metric_files, "📁", "-")
        self._update_metric(self._metric_agents, "🤖", "-")

        # Store data for reference
        self._current_data = {
            "user_content": user_content,
            "assistant_content": assistant_content or "(Waiting for response...)",
        }

        # Load full content into transcript tab
        self._transcript_tab.load_data(self._current_data)

        # Show transcript tab by default for turns
        self._tabs.setCurrentIndex(0)

    def show_exchange(
        self,
        user_content: str,
        assistant_content: str,
        agent: str = "assistant",
        tokens_in: int = 0,
        tokens_out: int = 0,
        parts: Optional[list] = None,
        timestamp: Optional[str] = None,
    ) -> None:
        """Display an exchange (user → assistant with parts details)."""
        self._current_session_id = None
        self._clear_tabs()

        # Update header
        self._header.setText(f"💬 user → {agent}")
        self._header.setStyleSheet(f"""
            font-size: {FONTS["size_lg"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_primary"]};
        """)

        # Hide breadcrumb and status badge
        self._breadcrumb.hide()
        self._status_badge.hide()

        # Count tools in parts
        parts = parts or []
        tool_count = sum(1 for p in parts if p.get("tool_name"))

        # Update metrics
        total_tokens = (tokens_in or 0) + (tokens_out or 0)
        self._update_metric(self._metric_duration, "⏱", "-")
        self._update_metric(
            self._metric_tokens, "🎫", format_tokens_short(total_tokens)
        )
        self._update_metric(
            self._metric_tools, "🔧", str(tool_count) if tool_count else "-"
        )
        self._update_metric(self._metric_files, "📁", "-")
        self._update_metric(self._metric_agents, "🤖", "-")

        # Build detailed assistant content with parts summary
        detailed_content = assistant_content or ""
        if parts:
            detailed_content += "\n\n--- Parts Summary ---\n"
            for p in parts[:20]:  # Limit to first 20
                ptype = p.get("type", "")
                tool_name = p.get("tool_name", "")
                display_info = p.get("display_info", "")
                status = p.get("status", "")

                if tool_name:
                    status_icon = (
                        "✓"
                        if status == "completed"
                        else "✗"
                        if status == "error"
                        else "◐"
                    )
                    info = f": {display_info[:60]}" if display_info else ""
                    detailed_content += f"\n{status_icon} {tool_name}{info}"
                elif ptype == "text":
                    content_preview = p.get("content", "")[:50]
                    detailed_content += f"\n💭 {content_preview}..."

            if len(parts) > 20:
                detailed_content += f"\n... and {len(parts) - 20} more parts"

        # Store data for reference
        self._current_data = {
            "user_content": user_content,
            "assistant_content": detailed_content,
        }

        # Load into transcript tab
        self._transcript_tab.load_data(self._current_data)
        self._tabs.setCurrentIndex(0)

    def show_message(
        self,
        role: str,
        content: str,
        tokens_in: int = 0,
        tokens_out: int = 0,
        timestamp: Optional[str] = None,
    ) -> None:
        """Display message content (user prompt or assistant response)."""
        self._current_session_id = None
        self._clear_tabs()

        # Update header based on role
        if role == "user":
            self._header.setText("💬 User Message")
            header_color = COLORS.get("info", "#60A5FA")
        else:
            self._header.setText("🤖 Assistant Response")
            header_color = COLORS.get("success", "#34D399")

        self._header.setStyleSheet(f"""
            font-size: {FONTS["size_lg"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {header_color};
        """)

        # Hide status badge for messages
        self._status_badge.hide()

        # Update metrics
        total_tokens = (tokens_in or 0) + (tokens_out or 0)
        self._update_metric(self._metric_duration, "⏱", "-")
        self._update_metric(
            self._metric_tokens, "🎫", format_tokens_short(total_tokens)
        )
        self._update_metric(self._metric_tools, "🔧", "-")
        self._update_metric(self._metric_files, "📁", "-")
        self._update_metric(self._metric_agents, "🤖", "-")

        # Load content into transcript tab
        self._current_data = {
            "user_content": content if role == "user" else "",
            "assistant_content": content if role == "assistant" else "",
        }
        self._transcript_tab.load_data(self._current_data)
        self._tabs.setCurrentIndex(0)

    def show_tool(
        self,
        tool_name: str,
        display_info: str,
        status: str = "completed",
        duration_ms: int = 0,
        timestamp: Optional[str] = None,
    ) -> None:
        """Display tool operation details."""
        self._current_session_id = None
        self._clear_tabs()

        # Choose icon based on tool type
        tool_icons = {
            "read": "📖",
            "edit": "✏️",
            "write": "📝",
            "bash": "🔧",
            "glob": "🔍",
            "grep": "🔎",
            "task": "🤖",
            "webfetch": "🌐",
            "web_fetch": "🌐",
            "todowrite": "📋",
            "todoread": "📋",
        }
        icon = tool_icons.get(tool_name, "⚙️")

        # Update header
        header_text = f"{icon} {tool_name}"
        if display_info:
            header_text += f": {display_info}"
        self._header.setText(header_text)
        self._header.setStyleSheet(f"""
            font-size: {FONTS["size_lg"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_primary"]};
        """)

        # Update breadcrumb - tool operations don't have a path
        self._breadcrumb.hide()

        # Update status badge
        if status == "completed":
            self._status_badge.setText("✅ Completed")
            self._status_badge.setStyleSheet(f"""
                font-size: {FONTS["size_xs"]}px;
                font-weight: {FONTS["weight_semibold"]};
                padding: {SPACING["xs"]}px {SPACING["sm"]}px;
                border-radius: {RADIUS["sm"]}px;
                background-color: {COLORS["success_muted"]};
                color: {COLORS["success"]};
            """)
        elif status == "error":
            self._status_badge.setText("❌ Error")
            self._status_badge.setStyleSheet(f"""
                font-size: {FONTS["size_xs"]}px;
                font-weight: {FONTS["weight_semibold"]};
                padding: {SPACING["xs"]}px {SPACING["sm"]}px;
                border-radius: {RADIUS["sm"]}px;
                background-color: {COLORS["error_muted"]};
                color: {COLORS["error"]};
            """)
        else:
            self._status_badge.hide()

        if status in ("completed", "error"):
            self._status_badge.show()

        # Update metrics
        self._update_metric(self._metric_duration, "⏱", format_duration(duration_ms))
        self._update_metric(self._metric_tokens, "🎫", "-")
        self._update_metric(self._metric_tools, "🔧", "1")
        self._update_metric(self._metric_files, "📁", "-")
        self._update_metric(self._metric_agents, "🤖", "-")

        # Show tool info in transcript tab
        tool_info = f"Tool: {tool_name}\n"
        if display_info:
            tool_info += f"Target: {display_info}\n"
        tool_info += f"Status: {status}\n"
        if duration_ms:
            tool_info += f"Duration: {format_duration(duration_ms)}\n"
        if timestamp:
            tool_info += f"Timestamp: {timestamp}\n"

        self._current_data = {
            "user_content": f"Tool: {tool_name}",
            "assistant_content": tool_info,
        }
        self._transcript_tab.load_data(self._current_data)
        self._tabs.setCurrentIndex(0)

    def show_trace(
        self,
        agent: str,
        duration_ms: Optional[int],
        tokens_in: Optional[int],
        tokens_out: Optional[int],
        status: str,
        prompt_input: str,
        prompt_output: Optional[str],
        tools_used: list[str],
    ) -> None:
        """Display trace details (legacy method for compatibility)."""
        self._current_session_id = None
        self._clear_tabs()

        # Update header
        self._header.setText(f"Agent: {agent}")
        self._header.setStyleSheet(f"""
            font-size: {FONTS["size_lg"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_primary"]};
        """)

        # Update status badge
        self._update_status_badge(status)

        # Update metrics
        total_tokens = (tokens_in or 0) + (tokens_out or 0)
        self._update_metric(self._metric_duration, "⏱", format_duration(duration_ms))
        self._update_metric(
            self._metric_tokens, "🎫", format_tokens_short(total_tokens)
        )
        self._update_metric(self._metric_tools, "🔧", str(len(tools_used)))
        self._update_metric(self._metric_files, "📁", "-")
        self._update_metric(self._metric_agents, "🤖", "1")

        # Store for transcript tab
        self._current_data = {
            "user_content": prompt_input,
            "assistant_content": prompt_output or "",
        }

        # Load transcript tab (default)
        self._transcript_tab.load_data(self._current_data)
        self._tabs.setCurrentIndex(0)

    def show_session(
        self,
        title: str,
        agent_type: Optional[str],
        parent_agent: Optional[str],
        directory: str,
        created_at: Optional[datetime],
        trace_count: int,
        children_count: int,
        prompt_input: Optional[str] = None,
    ) -> None:
        """Display session details (legacy method for compatibility)."""
        self._current_session_id = None
        self._clear_tabs()

        # Determine if this is a ROOT session
        is_root = parent_agent is None and agent_type is None

        # Update header
        if agent_type and parent_agent:
            # Use 💬 for user-initiated, 🔗 for agent delegations
            icon = "💬" if parent_agent == "user" else "🔗"
            header_text = f"{icon} {agent_type} ← {parent_agent}"
        elif agent_type:
            header_text = f"Agent: {agent_type}"
        else:
            project_name = os.path.basename(directory) if directory else "Session"
            header_text = f"🌳 {project_name}"

        self._header.setText(header_text)
        self._header.setStyleSheet(f"""
            font-size: {FONTS["size_lg"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_primary"]};
        """)

        # Status badge
        self._status_badge.setText("📁 Session")
        self._status_badge.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            font-weight: {FONTS["weight_semibold"]};
            padding: {SPACING["xs"]}px {SPACING["sm"]}px;
            border-radius: {RADIUS["sm"]}px;
            background-color: {COLORS["info_muted"]};
            color: {COLORS["info"]};
        """)
        self._status_badge.show()

        # Update metrics
        self._update_metric(self._metric_duration, "⏱", "-")
        self._update_metric(self._metric_tokens, "🎫", "-")
        self._update_metric(self._metric_tools, "🔧", "-")
        self._update_metric(self._metric_files, "📁", str(trace_count))
        self._update_metric(self._metric_agents, "🤖", str(children_count))

        # Store for transcript tab
        output_text = f"Directory: {directory}\n"
        if is_root:
            output_text += "Type: Direct user conversation\n"
        output_text += f"Traces: {trace_count}\n"
        output_text += f"Sub-agents: {children_count}"

        self._current_data = {
            "user_content": prompt_input or title or "(No prompt)",
            "assistant_content": output_text,
        }

        # Load transcript tab
        self._transcript_tab.load_data(self._current_data)
        self._tabs.setCurrentIndex(0)

    def _clear_tabs(self) -> None:
        """Clear all tab data."""
        self._transcript_tab.clear()
        self._tokens_tab.clear()
        self._tools_tab.clear()
        self._files_tab.clear()
        self._agents_tab.clear()
        self._timeline_tab.clear()

    def clear(self) -> None:
        """Clear all trace details."""
        self._current_session_id = None
        self._current_data = {}

        self._header.setText("Select a session")
        self._header.setStyleSheet(f"""
            font-size: {FONTS["size_lg"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_muted"]};
        """)

        self._status_badge.hide()

        # Reset metrics
        self._update_metric(self._metric_duration, "⏱", "0s")
        self._update_metric(self._metric_tokens, "🎫", "0")
        self._update_metric(self._metric_tools, "🔧", "0")
        self._update_metric(self._metric_files, "📁", "0")
        self._update_metric(self._metric_agents, "🤖", "0")

        # Clear tabs
        self._clear_tabs()
