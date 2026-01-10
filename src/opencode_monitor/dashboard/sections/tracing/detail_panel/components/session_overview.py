"""SessionOverviewPanel - Rich overview panel for root sessions.

Layout:
┌─────────────────────────────────────────────────────────────────────────┐
│ TIMELINE                                          TOOLS & FILES         │
│ ┌─────────────────────────────────────────┐  ┌────────────────────────┐ │
│ │ 10:30 💬 "Fix the auth bug..."          │  │ 🔧 Tools               │ │
│ │ 10:32 💬 "Now update the tests..."      │  │ ├─ read (15×)          │ │
│ │ 10:35 💬 "Run the full test suite"      │  │ ├─ edit (8×)           │ │
│ │ 10:38 💬 "Great, commit the changes"    │  │ └─ bash (3×)           │ │
│ │                                         │  ├────────────────────────┤ │
│ │                                         │  │ 📁 Files (12)          │ │
│ │                                         │  │ ├─ src/auth.py         │ │
│ │                                         │  │ └─ +10 more            │ │
│ └─────────────────────────────────────────┘  └────────────────────────┘ │
│ ⚠️ 1 error: mcp_bash failed at 10:36                                    │
└─────────────────────────────────────────────────────────────────────────┘
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from opencode_monitor.dashboard.sections.tracing.helpers import format_tokens_short
from opencode_monitor.dashboard.styles import COLORS, FONTS, RADIUS, SPACING
from opencode_monitor.utils.logger import debug


# ============================================================
# DATA CLASSES
# ============================================================


@dataclass
class Exchange:
    """Represents a user exchange in the timeline."""

    timestamp: str
    prompt: str
    agent: str = ""
    tool_count: int = 0


@dataclass
class ToolUsage:
    """Represents a tool usage."""

    name: str
    count: int
    targets: list[str] = field(default_factory=list)


@dataclass
class FileAction:
    """Represents a file action."""

    path: str
    action: str  # read, edit, write


@dataclass
class ErrorInfo:
    """Represents an error."""

    timestamp: str
    tool_name: str
    message: str


@dataclass
class SessionData:
    """Aggregated session data."""

    exchanges: list[Exchange] = field(default_factory=list)
    tools: Counter = field(default_factory=Counter)
    tool_targets: dict[str, list[str]] = field(default_factory=dict)
    files: dict[str, list[str]] = field(default_factory=dict)  # action -> [paths]
    errors: list[ErrorInfo] = field(default_factory=list)


# ============================================================
# HELPERS
# ============================================================


def format_time(datetime_str: str | None) -> str:
    """Format datetime to HH:MM."""
    if not datetime_str:
        return ""
    try:
        if "T" in datetime_str:
            dt = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(datetime_str)
        return dt.strftime("%H:%M")
    except (ValueError, TypeError):
        return ""


def truncate_text(text: str, max_length: int = 50) -> str:
    """Truncate text with ellipsis."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 1] + "…"


def shorten_tool_name(name: str) -> str:
    """Shorten tool name by removing mcp_ prefix."""
    return name.replace("mcp_", "").replace("lsmcp-typescript_", "ts:")


def extract_file_from_display_info(display_info: str | None) -> str | None:
    """Extract file path from tool display_info."""
    if not display_info:
        return None
    # Handle formats like "src/file.py:L45" or just "src/file.py"
    path = display_info.split(":")[0].strip()
    # Skip if it looks like a command or not a path
    if " " in path or not path:
        return None
    return path


def classify_tool_action(tool_name: str) -> str | None:
    """Classify tool as read/edit/write action."""
    name_lower = tool_name.lower()
    if "read" in name_lower or "glob" in name_lower or "grep" in name_lower:
        return "read"
    if "edit" in name_lower:
        return "edit"
    if "write" in name_lower:
        return "write"
    return None


# ============================================================
# DATA EXTRACTION
# ============================================================


def extract_session_data(tree_data: dict) -> SessionData:
    """Extract structured data from tree_data recursively."""
    data = SessionData()
    _extract_from_node(tree_data, data)
    return data


def _extract_from_node(node: dict, data: SessionData) -> None:
    """Process a node and extract relevant data."""
    node_type = node.get("node_type", "")

    # Extract exchanges (user_turn)
    if node_type == "user_turn":
        prompt = node.get("prompt_input", "") or node.get("title", "")
        timestamp = node.get("started_at", "") or node.get("created_at", "")
        agent = node.get("agent", "")

        # Count tools in this exchange
        tool_count = sum(
            1 for child in node.get("children", []) if child.get("node_type") == "tool"
        )

        data.exchanges.append(
            Exchange(
                timestamp=timestamp,
                prompt=prompt,
                agent=agent,
                tool_count=tool_count,
            )
        )

    # Extract tools
    elif node_type == "tool":
        tool_name = (
            node.get("tool_name", "") or node.get("title", "") or node.get("name", "")
        )
        if tool_name:
            data.tools[tool_name] += 1

            # Track targets (display_info)
            display_info = node.get("display_info", "")
            if display_info:
                if tool_name not in data.tool_targets:
                    data.tool_targets[tool_name] = []
                if display_info not in data.tool_targets[tool_name]:
                    data.tool_targets[tool_name].append(display_info)

            # Extract file if applicable
            action = classify_tool_action(tool_name)
            if action:
                file_path = extract_file_from_display_info(display_info)
                if file_path:
                    if action not in data.files:
                        data.files[action] = []
                    if file_path not in data.files[action]:
                        data.files[action].append(file_path)

        # Check for errors
        status = node.get("status", "")
        if status == "error":
            timestamp = node.get("started_at", "") or node.get("created_at", "")
            message = node.get("error", "") or node.get("display_info", "") or "Error"
            data.errors.append(
                ErrorInfo(
                    timestamp=timestamp,
                    tool_name=tool_name,
                    message=str(message)[:100],
                )
            )

    # Also check for errors in non-tool nodes
    elif node.get("status") == "error":
        timestamp = node.get("started_at", "") or node.get("created_at", "")
        title = node.get("title", "") or node_type
        message = node.get("error", "") or "Error"
        data.errors.append(
            ErrorInfo(
                timestamp=timestamp,
                tool_name=title,
                message=str(message)[:100],
            )
        )

    # Recurse into children
    for child in node.get("children", []):
        _extract_from_node(child, data)


# ============================================================
# TIMELINE WIDGET
# ============================================================


class TimelineWidget(QFrame):
    """Timeline of user exchanges."""

    exchange_clicked = pyqtSignal(int)  # Emit index when clicked

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS["bg_surface"]};
                border: 1px solid {COLORS["border_subtle"]};
                border-radius: {RADIUS["md"]}px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["sm"], SPACING["xs"], SPACING["sm"], SPACING["sm"]
        )
        layout.setSpacing(SPACING["xs"])

        # Header
        header = QLabel("💬 Timeline")
        header.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_muted"]};
            text-transform: uppercase;
            letter-spacing: 0.5px;
        """)
        layout.addWidget(header)

        # List
        self._list = QListWidget()
        self._list.setStyleSheet(f"""
            QListWidget {{
                background-color: transparent;
                border: none;
                outline: none;
            }}
            QListWidget::item {{
                padding: {SPACING["xs"]}px;
                border-radius: {RADIUS["sm"]}px;
                margin-bottom: 2px;
            }}
            QListWidget::item:hover {{
                background-color: {COLORS["bg_hover"]};
            }}
            QListWidget::item:selected {{
                background-color: {COLORS["accent_primary_muted"]};
            }}
        """)
        self._list.setSpacing(0)
        self._list.setWordWrap(True)  # Enable word wrap
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._list, 1)

    def load_exchanges(self, exchanges: list[Exchange]) -> None:
        """Load exchanges into the timeline."""
        self._list.clear()

        if not exchanges:
            item = QListWidgetItem("No exchanges yet")
            item.setForeground(Qt.GlobalColor.darkGray)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self._list.addItem(item)
            return

        for exchange in exchanges:
            time_str = format_time(exchange.timestamp)
            # Display full prompt with word wrap (no truncation)
            text = f"{time_str}  {exchange.prompt}" if time_str else exchange.prompt

            item = QListWidgetItem(text)
            item.setTextAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
            )
            item.setForeground(Qt.GlobalColor.white)
            self._list.addItem(item)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        row = self._list.row(item)
        self.exchange_clicked.emit(row)


# ============================================================
# TOOLS BREAKDOWN WIDGET
# ============================================================


class ToolsBreakdownWidget(QFrame):
    """List of tools used with counts."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS["bg_surface"]};
                border: 1px solid {COLORS["border_subtle"]};
                border-radius: {RADIUS["md"]}px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["sm"], SPACING["xs"], SPACING["sm"], SPACING["sm"]
        )
        layout.setSpacing(SPACING["xs"])

        # Header
        self._header = QLabel("🔧 Tools")
        self._header.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_muted"]};
            text-transform: uppercase;
            letter-spacing: 0.5px;
        """)
        layout.addWidget(self._header)

        # Container for tool labels
        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(2)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidget(self._container)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
        """)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(scroll, 1)

    def load_tools(self, tools: Counter, tool_targets: dict[str, list[str]]) -> None:
        """Load tools into the breakdown."""
        # Clear existing
        while self._container_layout.count():
            item = self._container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not tools:
            label = QLabel("No tools used")
            label.setStyleSheet(f"""
                font-size: {FONTS["size_xs"]}px;
                color: {COLORS["text_muted"]};
                padding: {SPACING["xs"]}px;
            """)
            self._container_layout.addWidget(label)
            self._container_layout.addStretch()
            return

        total = sum(tools.values())
        self._header.setText(f"🔧 Tools ({total})")

        # Sort by count descending
        for tool_name, count in tools.most_common(10):
            short_name = shorten_tool_name(tool_name)
            targets = tool_targets.get(tool_name, [])

            label = QLabel(f"├─ {short_name} ({count}×)")
            label.setStyleSheet(f"""
                font-size: {FONTS["size_xs"]}px;
                font-family: {FONTS["mono"]};
                color: {COLORS["text_secondary"]};
                padding: 2px {SPACING["xs"]}px;
            """)

            # Tooltip with targets
            if targets:
                tooltip = f"{tool_name}\n\nTargets:\n" + "\n".join(
                    f"  • {t}" for t in targets[:5]
                )
                if len(targets) > 5:
                    tooltip += f"\n  ... +{len(targets) - 5} more"
                label.setToolTip(tooltip)
            else:
                label.setToolTip(tool_name)

            self._container_layout.addWidget(label)

        if len(tools) > 10:
            more = QLabel(f"└─ +{len(tools) - 10} more...")
            more.setStyleSheet(f"""
                font-size: {FONTS["size_xs"]}px;
                font-family: {FONTS["mono"]};
                color: {COLORS["text_muted"]};
                padding: 2px {SPACING["xs"]}px;
            """)
            self._container_layout.addWidget(more)

        self._container_layout.addStretch()


# ============================================================
# FILES LIST WIDGET
# ============================================================


class FilesListWidget(QFrame):
    """List of files touched by actions."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS["bg_surface"]};
                border: 1px solid {COLORS["border_subtle"]};
                border-radius: {RADIUS["md"]}px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["sm"], SPACING["xs"], SPACING["sm"], SPACING["sm"]
        )
        layout.setSpacing(SPACING["xs"])

        # Header
        self._header = QLabel("📁 Files")
        self._header.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_muted"]};
            text-transform: uppercase;
            letter-spacing: 0.5px;
        """)
        layout.addWidget(self._header)

        # Container
        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(2)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidget(self._container)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
        """)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(scroll, 1)

    def load_files(self, files: dict[str, list[str]]) -> None:
        """Load files grouped by action."""
        # Clear existing
        while self._container_layout.count():
            item = self._container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Count total unique files
        all_files: set[str] = set()
        for paths in files.values():
            all_files.update(paths)

        if not all_files:
            label = QLabel("No files accessed")
            label.setStyleSheet(f"""
                font-size: {FONTS["size_xs"]}px;
                color: {COLORS["text_muted"]};
                padding: {SPACING["xs"]}px;
            """)
            self._container_layout.addWidget(label)
            self._container_layout.addStretch()
            return

        self._header.setText(f"📁 Files ({len(all_files)})")

        # Action icons and colors
        action_config = {
            "read": ("📖", COLORS["type_read"]),
            "edit": ("✏️", COLORS["type_edit"]),
            "write": ("📝", COLORS["type_write"]),
        }

        files_shown = 0
        max_files = 8

        for action in ["edit", "write", "read"]:  # Prioritize modifications
            paths = files.get(action, [])
            if not paths:
                continue

            icon, color = action_config.get(action, ("📄", COLORS["text_secondary"]))

            for path in paths[: max_files - files_shown]:
                # Get just the filename or last 2 segments
                short_path = "/".join(path.split("/")[-2:]) if "/" in path else path

                label = QLabel(f"{icon} {short_path}")
                label.setStyleSheet(f"""
                    font-size: {FONTS["size_xs"]}px;
                    font-family: {FONTS["mono"]};
                    color: {color};
                    padding: 2px {SPACING["xs"]}px;
                """)
                label.setToolTip(f"{action.capitalize()}: {path}")
                self._container_layout.addWidget(label)
                files_shown += 1

                if files_shown >= max_files:
                    break

            if files_shown >= max_files:
                break

        remaining = len(all_files) - files_shown
        if remaining > 0:
            more = QLabel(f"  +{remaining} more...")
            more.setStyleSheet(f"""
                font-size: {FONTS["size_xs"]}px;
                color: {COLORS["text_muted"]};
                padding: 2px {SPACING["xs"]}px;
            """)
            self._container_layout.addWidget(more)

        self._container_layout.addStretch()


# ============================================================
# TOKENS WIDGET
# ============================================================


class TokensWidget(QFrame):
    """Display token usage breakdown."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS["bg_surface"]};
                border: 1px solid {COLORS["border_subtle"]};
                border-radius: {RADIUS["md"]}px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["sm"], SPACING["xs"], SPACING["sm"], SPACING["sm"]
        )
        layout.setSpacing(SPACING["xs"])

        # Header
        self._header = QLabel("🎫 Tokens")
        self._header.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_muted"]};
            text-transform: uppercase;
            letter-spacing: 0.5px;
        """)
        layout.addWidget(self._header)

        # Container
        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(2)
        layout.addWidget(self._container)

    def load_tokens(
        self,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
        cache_read: int | None = None,
    ) -> None:
        """Load token stats."""
        # Clear existing
        while self._container_layout.count():
            item = self._container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if tokens_in is None and tokens_out is None and cache_read is None:
            label = QLabel("No token data")
            label.setStyleSheet(f"""
                font-size: {FONTS["size_xs"]}px;
                color: {COLORS["text_muted"]};
                padding: {SPACING["xs"]}px;
            """)
            self._container_layout.addWidget(label)
            return

        # Calculate total
        total = (tokens_in or 0) + (tokens_out or 0) + (cache_read or 0)

        # Add token breakdown
        if tokens_in is not None:
            label = QLabel(f"├─ In: {format_tokens_short(tokens_in)}")
            label.setStyleSheet(f"""
                font-size: {FONTS["size_xs"]}px;
                font-family: {FONTS["mono"]};
                color: {COLORS["text_secondary"]};
                padding: 2px {SPACING["xs"]}px;
            """)
            self._container_layout.addWidget(label)

        if tokens_out is not None:
            label = QLabel(f"├─ Out: {format_tokens_short(tokens_out)}")
            label.setStyleSheet(f"""
                font-size: {FONTS["size_xs"]}px;
                font-family: {FONTS["mono"]};
                color: {COLORS["text_secondary"]};
                padding: 2px {SPACING["xs"]}px;
            """)
            self._container_layout.addWidget(label)

        if cache_read is not None:
            label = QLabel(f"├─ Cache: {format_tokens_short(cache_read)}")
            label.setStyleSheet(f"""
                font-size: {FONTS["size_xs"]}px;
                font-family: {FONTS["mono"]};
                color: {COLORS["text_secondary"]};
                padding: 2px {SPACING["xs"]}px;
            """)
            self._container_layout.addWidget(label)

        # Total
        total_label = QLabel(f"└─ Total: {format_tokens_short(total)}")
        total_label.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            font-family: {FONTS["mono"]};
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_primary"]};
            padding: 2px {SPACING["xs"]}px;
        """)
        self._container_layout.addWidget(total_label)


# ============================================================
# AGENTS WIDGET
# ============================================================


class AgentsWidget(QFrame):
    """Display agents/delegations used."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS["bg_surface"]};
                border: 1px solid {COLORS["border_subtle"]};
                border-radius: {RADIUS["md"]}px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["sm"], SPACING["xs"], SPACING["sm"], SPACING["sm"]
        )
        layout.setSpacing(SPACING["xs"])

        # Header
        self._header = QLabel("🤖 Agents")
        self._header.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            font-weight: {FONTS["weight_semibold"]};
            color: {COLORS["text_muted"]};
            text-transform: uppercase;
            letter-spacing: 0.5px;
        """)
        layout.addWidget(self._header)

        # Container
        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(2)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidget(self._container)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
        """)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(scroll, 1)

    def load_agents(self, agents: list[dict[str, Any]]) -> None:
        """Load agents from tree data.

        Args:
            agents: List of dicts with 'agent_type' and optional 'count'
        """
        # Clear existing
        while self._container_layout.count():
            item = self._container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not agents:
            label = QLabel("No agents used")
            label.setStyleSheet(f"""
                font-size: {FONTS["size_xs"]}px;
                color: {COLORS["text_muted"]};
                padding: {SPACING["xs"]}px;
            """)
            self._container_layout.addWidget(label)
            self._container_layout.addStretch()
            return

        # Count agents
        agent_counter: Counter = Counter()
        for agent in agents:
            agent_type = agent.get("agent_type", "unknown")
            agent_counter[agent_type] += 1

        total = len(agents)
        self._header.setText(f"🤖 Agents ({total})")

        # Display agents with counts
        agents_list = agent_counter.most_common()
        for i, (agent_type, count) in enumerate(agents_list):
            prefix = "├─" if i < len(agents_list) - 1 else "└─"
            text = f"{prefix} {agent_type}"
            if count > 1:
                text += f" ({count}×)"

            label = QLabel(text)
            label.setStyleSheet(f"""
                font-size: {FONTS["size_xs"]}px;
                font-family: {FONTS["mono"]};
                color: {COLORS["text_secondary"]};
                padding: 2px {SPACING["xs"]}px;
            """)
            self._container_layout.addWidget(label)

        self._container_layout.addStretch()


# ============================================================
# ERRORS WIDGET
# ============================================================


class ErrorsWidget(QFrame):
    """Display errors if present."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS["error_muted"]};
                border: 1px solid {COLORS["error"]};
                border-radius: {RADIUS["md"]}px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            SPACING["sm"], SPACING["xs"], SPACING["sm"], SPACING["xs"]
        )
        layout.setSpacing(SPACING["sm"])

        self._label = QLabel()
        self._label.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            font-weight: {FONTS["weight_medium"]};
            color: {COLORS["error"]};
        """)
        self._label.setWordWrap(True)
        layout.addWidget(self._label, 1)

    def load_errors(self, errors: list[ErrorInfo]) -> None:
        """Load errors into the widget."""
        if not errors:
            self.hide()
            return

        count = len(errors)
        if count == 1:
            err = errors[0]
            time_str = format_time(err.timestamp)
            tool_short = shorten_tool_name(err.tool_name)
            self._label.setText(
                f"⚠️ {tool_short} failed{' at ' + time_str if time_str else ''}"
            )
            self._label.setToolTip(err.message)
        else:
            self._label.setText(f"⚠️ {count} errors occurred")
            tooltip = "\n".join(
                f"• {shorten_tool_name(e.tool_name)}: {e.message[:50]}"
                for e in errors[:5]
            )
            if count > 5:
                tooltip += f"\n... +{count - 5} more"
            self._label.setToolTip(tooltip)

        self.show()


# ============================================================
# DATA AGGREGATION HELPERS
# ============================================================


def _collect_agents_recursive(node: dict, agents: list[dict], depth: int = 0) -> None:
    """Recursively collect all agents/delegations from tree.

    Args:
        node: Current tree node
        agents: List to append found agents to (mutated)
        depth: Current recursion depth (for logging)
    """
    node_type = node.get("node_type", "")
    agent_type = node.get("agent_type", "")

    debug(
        f"[SessionOverview] Walking node type={node_type} agent_type={agent_type} at depth={depth}"
    )

    # Collect agent/delegation nodes (old way - kept for compatibility)
    if node_type in ["delegation", "agent"]:
        if agent_type:
            debug(f"[SessionOverview] Found agent from delegation: {agent_type}")
            agents.append(node)

    # NEW: Collect agents from user_turn nodes (where agent responds)
    if node_type == "user_turn":
        agent = node.get("agent") or node.get("subagent_type")
        if agent:
            debug(f"[SessionOverview] Found agent from user_turn: {agent}")
            # Only add if not "assistant" (which is the default)
            if agent != "assistant":
                agents.append({"agent_type": agent, "node_type": "user_turn_agent"})

    # Recurse into children
    for child in node.get("children", []):
        _collect_agents_recursive(child, agents, depth + 1)


def _aggregate_tokens_recursive(node: dict, depth: int = 0) -> tuple[int, int, int]:
    """Recursively aggregate tokens from entire tree.

    Args:
        node: Current tree node
        depth: Current recursion depth (for logging)

    Returns:
        Tuple of (tokens_in, tokens_out, cache_read)
    """
    debug(
        f"[SessionOverview] Aggregating tokens for node type={node.get('node_type')} at depth={depth}"
    )

    # Get tokens from current node
    tokens_in = node.get("tokens_in", 0) or 0
    tokens_out = node.get("tokens_out", 0) or 0
    cache_read = node.get("cache_read", 0) or 0

    debug(
        f"[SessionOverview] Node tokens - in: {tokens_in}, out: {tokens_out}, cache: {cache_read}"
    )

    # Aggregate tokens from children
    for child in node.get("children", []):
        child_in, child_out, child_cache = _aggregate_tokens_recursive(child, depth + 1)
        tokens_in += child_in
        tokens_out += child_out
        cache_read += child_cache

    return tokens_in, tokens_out, cache_read


# ============================================================
# MAIN PANEL
# ============================================================


class SessionOverviewPanel(QFrame):
    """Rich overview panel for root sessions with timeline, tools, and files."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QFrame#sessionOverview {{
                background-color: {COLORS["bg_base"]};
                border: none;
            }}
        """)
        self.setObjectName("sessionOverview")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(SPACING["xs"])

        # Main content: 2 columns
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: transparent;
                width: 4px;
            }
        """)

        # Left column: Timeline (60%)
        self._timeline = TimelineWidget()
        splitter.addWidget(self._timeline)

        # Right column: Tools + Files + Tokens + Agents (40%)
        right_column = QWidget()
        right_layout = QVBoxLayout(right_column)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(SPACING["xs"])

        self._tools = ToolsBreakdownWidget()
        right_layout.addWidget(self._tools, 1)

        self._files = FilesListWidget()
        right_layout.addWidget(self._files, 1)

        self._tokens = TokensWidget()
        right_layout.addWidget(self._tokens)

        self._agents = AgentsWidget()
        right_layout.addWidget(self._agents, 1)

        right_layout.addStretch()  # Push widgets to top

        splitter.addWidget(right_column)

        # Set initial sizes (60/40 ratio)
        splitter.setSizes([600, 400])
        splitter.setStretchFactor(0, 6)
        splitter.setStretchFactor(1, 4)

        main_layout.addWidget(splitter, 1)

        # Bottom: Errors (conditional)
        self._errors = ErrorsWidget()
        self._errors.hide()
        main_layout.addWidget(self._errors)

    def load_session(self, tree_data: dict) -> None:
        """Load session data and display rich overview."""
        debug(
            f"[SessionOverview] Loading session with {len(tree_data.get('children', []))} direct children"
        )

        # Extract structured data (exchanges, tools, files, errors)
        data = extract_session_data(tree_data)

        # Aggregate tokens recursively from entire tree
        debug("[SessionOverview] Starting recursive token aggregation...")
        tokens_in, tokens_out, cache_read = _aggregate_tokens_recursive(tree_data)
        debug(
            f"[SessionOverview] Total tokens aggregated - in: {tokens_in}, out: {tokens_out}, cache: {cache_read}"
        )

        # Collect agents recursively from entire tree
        debug("[SessionOverview] Starting recursive agent collection...")
        agents = []
        _collect_agents_recursive(tree_data, agents)
        debug(
            f"[SessionOverview] Found {len(agents)} agents: {[a.get('agent_type', 'unknown') for a in agents]}"
        )

        # Load widgets
        self._timeline.load_exchanges(data.exchanges)
        self._tools.load_tools(data.tools, data.tool_targets)
        self._files.load_files(data.files)
        self._tokens.load_tokens(tokens_in, tokens_out, cache_read)
        self._agents.load_agents(agents)
        self._errors.load_errors(data.errors)

    def clear(self) -> None:
        """Reset the panel to empty state."""
        self._timeline.load_exchanges([])
        self._tools.load_tools(Counter(), {})
        self._files.load_files({})
        self._tokens.load_tokens()
        self._agents.load_agents([])
        self._errors.load_errors([])
