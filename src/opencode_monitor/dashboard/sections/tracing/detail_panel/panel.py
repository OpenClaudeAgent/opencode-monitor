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
    QStackedWidget,
)
from PyQt6.QtCore import Qt

from opencode_monitor.dashboard.styles import COLORS, SPACING, FONTS, RADIUS
from opencode_monitor.utils.logger import debug

from ..helpers import format_duration, format_tokens_short
from ..tabs import (
    TokensTab,
    ToolsTab,
    FilesTab,
    AgentsTab,
    TimelineTab,
    TranscriptTab,
    DelegationsTab,
)
from .components import MetricsBar, StatusBadge, SessionOverviewPanel
from .handlers import DataLoaderMixin
from .strategies import PanelContent

if TYPE_CHECKING:
    from opencode_monitor.analytics import TracingDataService


class TraceDetailPanel(DataLoaderMixin, QFrame):
    """Panel showing detailed trace/session information with tabbed sections."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("trace-detail")
        self.setMinimumWidth(400)

        # State
        self._service: Optional["TracingDataService"] = None
        self._current_session_id: Optional[str] = None
        self._current_data: dict = {}
        self._tree_data: dict = {}

        self._setup_styles()
        self._setup_ui()

    def _setup_styles(self) -> None:
        """Apply panel styles."""
        self.setStyleSheet(f"""
            QFrame#trace-detail {{
                background-color: {COLORS["bg_surface"]};
                border: 1px solid {COLORS["border_default"]};
                border-radius: {RADIUS["lg"]}px;
            }}
        """)

    def _setup_ui(self) -> None:
        """Setup the main UI structure."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Scroll area for content
        scroll = self._create_scroll_area()
        content = QWidget()
        content.setStyleSheet("background-color: transparent;")

        layout = QVBoxLayout(content)
        layout.setContentsMargins(
            SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"]
        )
        layout.setSpacing(SPACING["md"])

        # Setup sections
        self._setup_breadcrumb(layout)
        self._setup_header(layout)
        self._setup_metrics(layout)
        self._setup_separator(layout)

        # Stacked widget for contextual content
        self._content_stack = QStackedWidget()

        # Page 0: Session overview (for root sessions)
        self._session_overview = SessionOverviewPanel()
        self._content_stack.addWidget(self._session_overview)

        # Page 1: Tabs container (for child elements)
        self._tabs_container = QWidget()
        self._tabs_container.setStyleSheet("background-color: transparent;")
        tabs_layout = QVBoxLayout(self._tabs_container)
        tabs_layout.setContentsMargins(0, 0, 0, 0)
        tabs_layout.setSpacing(0)
        self._setup_tabs(tabs_layout)
        self._content_stack.addWidget(self._tabs_container)

        layout.addWidget(self._content_stack)

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def _create_scroll_area(self) -> QScrollArea:
        """Create styled scroll area."""
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
        return scroll

    def _setup_breadcrumb(self, layout: QVBoxLayout) -> None:
        """Setup breadcrumb navigation."""
        self._breadcrumb = QLabel("")
        self._breadcrumb.setStyleSheet(f"""
            font-size: {FONTS["size_sm"]}px;
            color: {COLORS["text_muted"]};
            padding: {SPACING["xs"]}px 0;
        """)
        self._breadcrumb.setWordWrap(True)
        self._breadcrumb.hide()
        layout.addWidget(self._breadcrumb)

    def _update_breadcrumb(self, path: list[str]) -> None:
        """Update breadcrumb with navigation path."""
        if not path:
            self._breadcrumb.hide()
            return

        self._breadcrumb.setText(" › ".join(path))
        self._breadcrumb.show()

    def _setup_header(self, layout: QVBoxLayout) -> None:
        """Setup header with title and status."""
        header_row = QHBoxLayout()
        header_row.setSpacing(SPACING["sm"])

        self._header = QLabel("Select a session")
        self._set_header_style(muted=True)
        header_row.addWidget(self._header)
        header_row.addStretch()

        self._status_badge = StatusBadge()
        header_row.addWidget(self._status_badge)

        layout.addLayout(header_row)

    def _set_header_style(self, muted: bool = False, color: str | None = None) -> None:
        """Set header text style."""
        text_color = (
            color
            if color
            else (COLORS["text_muted"] if muted else COLORS["text_primary"])
        )
        self._header.setStyleSheet(f"""
            font-size: {FONTS["size_lg"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {text_color};
        """)

    def _setup_metrics(self, layout: QVBoxLayout) -> None:
        """Setup metrics bar."""
        self._metrics_bar = MetricsBar()
        layout.addWidget(self._metrics_bar)

    def _setup_separator(self, layout: QVBoxLayout) -> None:
        """Add horizontal separator."""
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {COLORS['border_default']};")
        sep.setFixedHeight(1)
        layout.addWidget(sep)

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
        self._timeline_tab.event_selected.connect(self._on_timeline_event_selected)

        # Delegations tab
        self._delegations_tab = DelegationsTab()
        self._delegations_tab.session_selected.connect(
            self._on_delegation_session_selected
        )

        # Add tabs with icons
        self._tabs.addTab(self._transcript_tab, "📜")
        self._tabs.addTab(self._tokens_tab, "📊")
        self._tabs.addTab(self._tools_tab, "🔧")
        self._tabs.addTab(self._files_tab, "📁")
        self._tabs.addTab(self._agents_tab, "🤖")
        self._tabs.addTab(self._timeline_tab, "⏱")
        self._tabs.addTab(self._delegations_tab, "🌲")

        # Tooltips
        tooltips = [
            "Transcript - Full conversation",
            "Tokens - Usage breakdown",
            "Tools - Tool calls",
            "Files - File operations",
            "Agents - Agent hierarchy",
            "Timeline - Event timeline",
            "Delegations - Agent tree",
        ]
        for i, tip in enumerate(tooltips):
            self._tabs.setTabToolTip(i, tip)

        # Connect tab change for lazy loading
        self._tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self._tabs)

    # ===== Display Methods =====

    def show_session_summary(
        self, session_id: str, tree_data: dict | None = None
    ) -> None:
        """Show session summary - main entry point for displaying session details."""
        debug(f"[TraceDetailPanel] show_session_summary called for: {session_id}")
        self._current_session_id = session_id
        self._tree_data = tree_data or {}
        self._clear_tabs()

        agent_type = self._tree_data.get("agent_type")
        is_root = agent_type is None or agent_type == "user"

        if is_root:
            self._show_root_session(session_id, self._tree_data)
        else:
            self._show_child_session(self._tree_data)

    def _show_root_session(self, session_id: str, tree_data: dict) -> None:
        """Show root session with SessionOverviewPanel."""
        client = self._get_api_client()
        if not client.is_available:
            debug("[TraceDetailPanel] API not available, using fallback")
            self._header.setText("API not available")
            self._set_header_style(muted=True)
            return

        summary = client.get_session_summary(session_id)
        debug(f"[TraceDetailPanel] Got summary: {summary is not None}")

        if summary is None:
            summary = {"meta": {}, "summary": {}, "details": {}}

        self._current_data = summary
        meta = summary.get("meta", {})
        s = summary.get("summary", {})

        directory = meta.get("directory", "")
        project_name = os.path.basename(directory) if directory else "Session"
        title = tree_data.get("title") or meta.get("title") or ""

        self._header.setText(f"🌳 {project_name}")
        self._set_header_style(muted=False)
        self._update_breadcrumb([f"🌳 {project_name}"])
        self._status_badge.set_status(s.get("status", "completed"))

        duration_ms = tree_data.get("duration_ms") or s.get("duration_ms", 0)
        self._metrics_bar.update_all(
            duration=format_duration(duration_ms),
            tokens=format_tokens_short(s.get("total_tokens", 0)),
            tools=str(s.get("total_tool_calls", 0)),
            files=str(s.get("total_files", 0)),
            agents=str(tree_data.get("children_count", s.get("unique_agents", 0))),
        )

        overview_data = {
            "project": project_name,
            "title": title,
            "directory": directory,
            "duration_ms": duration_ms,
            "tokens_in": tree_data.get("tokens_in") or s.get("tokens_in", 0),
            "tokens_out": tree_data.get("tokens_out") or s.get("tokens_out", 0),
            "cache_read": tree_data.get("cache_read", 0),
            "children": tree_data.get("children", []),
        }
        self._session_overview.load_session(overview_data)
        self._content_stack.setCurrentIndex(0)

    def _show_child_session(self, tree_data: dict) -> None:
        """Show details for a child session (sub-agent trace)."""
        self._content_stack.setCurrentIndex(1)

        agent_type = tree_data.get("agent_type", "agent")
        parent_agent = tree_data.get("parent_agent", "user")
        title = tree_data.get("title", "")
        status = tree_data.get("status", "completed")

        # Header with delegation chain
        icon = "💬" if parent_agent == "user" else "🔗"
        header_text = (
            f"{icon} {parent_agent} → {agent_type}"
            if parent_agent
            else f"🤖 {agent_type}"
        )
        self._header.setText(header_text)
        self._set_header_style(muted=False)

        # Breadcrumb
        breadcrumb_path = ["🌳 ROOT"]
        if parent_agent and parent_agent != "user":
            breadcrumb_path.append(f"🔗 {parent_agent}")
        breadcrumb_path.append(f"🤖 {agent_type}")
        self._update_breadcrumb(breadcrumb_path)

        # Status
        self._status_badge.set_status(status)

        # Metrics
        duration_ms = tree_data.get("duration_ms") or 0
        tokens_in = tree_data.get("tokens_in") or 0
        tokens_out = tree_data.get("tokens_out") or 0

        self._metrics_bar.update_all(
            duration=format_duration(duration_ms),
            tokens=format_tokens_short(tokens_in + tokens_out),
            tools="-",
            files="-",
            agents=str(tree_data.get("children_count") or 0),
        )

        # Transcript data
        prompt_input = (
            tree_data.get("prompt_input") or title or f"Task delegated to {agent_type}"
        )
        prompt_output = tree_data.get("prompt_output") or (
            f"Agent: {agent_type}\n"
            f"Duration: {format_duration(duration_ms)}\n"
            f"Tokens: {format_tokens_short(tokens_in)} in / {format_tokens_short(tokens_out)} out\n"
            f"Status: {status}"
        )

        self._current_data = {
            "user_content": prompt_input,
            "assistant_content": prompt_output,
        }
        self._transcript_tab.load_data(self._current_data)  # type: ignore[attr-defined]
        self._tabs.setCurrentIndex(0)

    def show_turn(
        self,
        user_content: str,
        assistant_content: Optional[str],
        tokens_in: int = 0,
        tokens_out: int = 0,
        timestamp: Optional[str] = None,
    ) -> None:
        """Display a conversation turn (user prompt + assistant response)."""
        self._prepare_display()

        self._header.setText("💬 Conversation Turn")
        self._set_header_style(muted=False)
        self._status_badge.clear()

        total_tokens = (tokens_in or 0) + (tokens_out or 0)
        self._metrics_bar.update_all(
            duration="-",
            tokens=format_tokens_short(total_tokens),
            tools="-",
            files="-",
            agents="-",
        )

        self._show_transcript(
            user_content, assistant_content or "(Waiting for response...)"
        )

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
        self._prepare_display()

        self._header.setText(f"💬 user → {agent}")
        self._set_header_style(muted=False)
        self._breadcrumb.hide()
        self._status_badge.clear()

        parts = parts or []
        tool_count = sum(1 for p in parts if p.get("tool_name"))

        total_tokens = (tokens_in or 0) + (tokens_out or 0)
        self._metrics_bar.update_all(
            duration="-",
            tokens=format_tokens_short(total_tokens),
            tools=str(tool_count) if tool_count else "-",
            files="-",
            agents="-",
        )

        # Build detailed content
        detailed_content = self._build_parts_summary(assistant_content, parts)
        self._show_transcript(user_content, detailed_content)

    def _build_parts_summary(self, base_content: str, parts: list) -> str:
        """Build detailed content with parts summary."""
        if not parts:
            return base_content or ""

        detailed = base_content or ""
        detailed += "\n\n--- Parts Summary ---\n"

        for p in parts[:20]:
            ptype = p.get("type", "")
            tool_name = p.get("tool_name", "")
            display_info = p.get("display_info", "")
            status = p.get("status", "")

            if tool_name:
                status_icon = (
                    "✓" if status == "completed" else "✗" if status == "error" else "◐"
                )
                info = f": {display_info[:60]}" if display_info else ""
                detailed += f"\n{status_icon} {tool_name}{info}"
            elif ptype == "text":
                content_preview = p.get("content", "")[:50]
                detailed += f"\n💭 {content_preview}..."

        if len(parts) > 20:
            detailed += f"\n... and {len(parts) - 20} more parts"

        return detailed

    def show_message(
        self,
        role: str,
        content: str,
        tokens_in: int = 0,
        tokens_out: int = 0,
        timestamp: Optional[str] = None,
    ) -> None:
        """Display message content (user prompt or assistant response)."""
        self._prepare_display()

        if role == "user":
            self._header.setText("💬 User Message")
            self._set_header_style(color=COLORS.get("info", "#60A5FA"))
        else:
            self._header.setText("🤖 Assistant Response")
            self._set_header_style(color=COLORS.get("success", "#34D399"))

        self._status_badge.clear()

        total_tokens = (tokens_in or 0) + (tokens_out or 0)
        self._metrics_bar.update_all(
            duration="-",
            tokens=format_tokens_short(total_tokens),
            tools="-",
            files="-",
            agents="-",
        )

        user = content if role == "user" else ""
        assistant = content if role == "assistant" else ""
        self._show_transcript(user, assistant)

    def show_tool(
        self,
        tool_name: str,
        display_info: str,
        status: str = "completed",
        duration_ms: int = 0,
        timestamp: Optional[str] = None,
    ) -> None:
        """Display tool operation details."""
        self._prepare_display()

        # Tool icons
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

        header_text = f"{icon} {tool_name}"
        if display_info:
            header_text += f": {display_info}"
        self._header.setText(header_text)
        self._set_header_style(muted=False)

        self._breadcrumb.hide()
        if status in ("completed", "error"):
            self._status_badge.set_status(status)
        else:
            self._status_badge.clear()

        self._metrics_bar.update_all(
            duration=format_duration(duration_ms),
            tokens="-",
            tools="1",
            files="-",
            agents="-",
        )

        tool_info = f"Tool: {tool_name}\n"
        if display_info:
            tool_info += f"Target: {display_info}\n"
        tool_info += f"Status: {status}\n"
        if duration_ms:
            tool_info += f"Duration: {format_duration(duration_ms)}\n"
        if timestamp:
            tool_info += f"Timestamp: {timestamp}\n"

        self._show_transcript(f"Tool: {tool_name}", tool_info)

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
        self._prepare_display()

        self._header.setText(f"Agent: {agent}")
        self._set_header_style(muted=False)
        self._status_badge.set_status(status)

        total_tokens = (tokens_in or 0) + (tokens_out or 0)
        self._metrics_bar.update_all(
            duration=format_duration(duration_ms),
            tokens=format_tokens_short(total_tokens),
            tools=str(len(tools_used)),
            files="-",
            agents="1",
        )

        self._show_transcript(prompt_input, prompt_output or "")

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
        self._prepare_display()

        is_root = parent_agent is None and agent_type is None

        if agent_type and parent_agent:
            icon = "💬" if parent_agent == "user" else "🔗"
            header_text = f"{icon} {agent_type} ← {parent_agent}"
        elif agent_type:
            header_text = f"Agent: {agent_type}"
        else:
            project_name = os.path.basename(directory) if directory else "Session"
            header_text = f"🌳 {project_name}"

        self._header.setText(header_text)
        self._set_header_style(muted=False)
        self._status_badge.set_custom("📁 Session", "info")

        self._metrics_bar.update_all(
            duration="-",
            tokens="-",
            tools="-",
            files=str(trace_count),
            agents=str(children_count),
        )

        output_text = f"Directory: {directory}\n"
        if is_root:
            output_text += "Type: Direct user conversation\n"
        output_text += f"Traces: {trace_count}\nSub-agents: {children_count}"

        self._show_transcript(prompt_input or title or "(No prompt)", output_text)

    # ===== Utility Methods =====

    def _prepare_display(self) -> None:
        """Prepare panel for new display (clear state)."""
        self._current_session_id = None
        self._clear_tabs()
        self._content_stack.setCurrentIndex(1)

    def _show_transcript(self, user_content: str, assistant_content: str) -> None:
        """Load transcript and switch to transcript tab."""
        self._current_data = {
            "user_content": user_content,
            "assistant_content": assistant_content,
        }
        self._transcript_tab.load_data(self._current_data)  # type: ignore[attr-defined]
        self._tabs.setCurrentIndex(0)

    def _clear_tabs(self) -> None:
        """Clear all tab data."""
        self._transcript_tab.clear()  # type: ignore[attr-defined]
        self._tokens_tab.clear()  # type: ignore[attr-defined]
        self._tools_tab.clear()  # type: ignore[attr-defined]
        self._files_tab.clear()  # type: ignore[attr-defined]
        self._agents_tab.clear()  # type: ignore[attr-defined]
        self._timeline_tab.clear()  # type: ignore[attr-defined]
        self._delegations_tab.clear()  # type: ignore[attr-defined]

    def clear(self) -> None:
        """Clear all trace details."""
        self._current_session_id = None
        self._current_data = {}

        self._header.setText("Select a session")
        self._set_header_style(muted=True)
        self._status_badge.clear()
        self._metrics_bar.reset()
        self._clear_tabs()
        self._session_overview.clear()
        self._content_stack.setCurrentIndex(1)

    # ===== Event Handlers =====

    def _on_timeline_event_selected(self, event: dict) -> None:
        """Handle timeline event click - show details in panel."""
        event_type = event.get("type", "")

        if event_type == "tool_call":
            self.show_tool(
                tool_name=event.get("tool_name", ""),
                display_info=event.get("arguments", ""),
                status=event.get("status", "completed"),
                duration_ms=event.get("duration_ms", 0),
                timestamp=event.get("timestamp"),
            )
        elif event_type == "reasoning":
            # Show reasoning as assistant message
            self.show_message(
                role="assistant",
                content=event.get("content", ""),
                timestamp=event.get("timestamp"),
            )
        elif event_type in ("user_prompt", "assistant_response"):
            self.show_message(
                role="user" if event_type == "user_prompt" else "assistant",
                content=event.get("content", ""),
                tokens_in=event.get("tokens_in", 0),
                tokens_out=event.get("tokens_out", 0),
                timestamp=event.get("timestamp"),
            )

    def _on_delegation_session_selected(self, session_id: str) -> None:
        """Handle delegation session selection - navigate to that session."""
        # Load the selected session's details
        self.show_session_summary(session_id)

    # ===== Strategy-based Rendering =====

    def render(self, content: PanelContent) -> None:
        """Render panel content from strategy."""
        debug("[PANEL] render() called")
        debug(f"[PANEL] content_type={content.get('content_type')}")

        self._current_session_id = None
        self._clear_tabs()

        header_icon = content.get("header_icon", "")
        header_text = content.get("header", "")
        self._header.setText(
            f"{header_icon} {header_text}" if header_icon else header_text
        )
        self._set_header_style(muted=False, color=content.get("header_color"))

        breadcrumb = content.get("breadcrumb", [])
        self._update_breadcrumb(breadcrumb)

        status = content.get("status")
        if status:
            self._status_badge.set_status(status)
        else:
            self._status_badge.clear()

        metrics = content.get("metrics", {})
        self._metrics_bar.update_all(
            duration=metrics.get("duration", "-"),
            tokens=metrics.get("tokens", "-"),
            tools=metrics.get("tools", "-"),
            files=metrics.get("files", "-"),
            agents=metrics.get("agents", "-"),
        )

        content_type = content.get("content_type", "tabs")
        if content_type == "overview":
            debug("[PANEL] Switching to SessionOverviewPanel (index 0)")
            overview_data = content.get("overview_data")
            if overview_data:
                self._session_overview.load_session(overview_data)
            self._content_stack.setCurrentIndex(0)
        else:
            debug("[PANEL] Switching to Tabs (index 1)")
            transcript = content.get("transcript")
            if transcript:
                self._current_data = {
                    "user_content": transcript.get("user_content", ""),
                    "assistant_content": transcript.get("assistant_content", ""),
                }
                self._transcript_tab.load_data(self._current_data)  # type: ignore[attr-defined]
            initial_tab = content.get("initial_tab", 0)
            self._tabs.setCurrentIndex(initial_tab)
            self._content_stack.setCurrentIndex(1)

        debug(
            f"[PANEL] Current stack index is now: {self._content_stack.currentIndex()}"
        )
