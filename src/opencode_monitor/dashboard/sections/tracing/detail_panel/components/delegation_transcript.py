"""
DelegationTranscriptPanel - Scrollable panel showing complete delegation timeline.
"""

from typing import Optional
import json

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QScrollArea,
)
from PyQt6.QtCore import Qt

from opencode_monitor.dashboard.styles import COLORS, SPACING, FONTS, RADIUS
from ..handlers import DataLoaderMixin
from ..strategies.types import DelegationData


class DelegationTranscriptPanel(DataLoaderMixin, QFrame):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("delegation-transcript")

        self._child_session_id: Optional[str] = None
        self._subagent_type: Optional[str] = None

        self._setup_styles()
        self._setup_ui()

    def _setup_styles(self) -> None:
        self.setStyleSheet(f"""
            QFrame#delegation-transcript {{
                background-color: {COLORS["bg_surface"]};
                border: none;
            }}
        """)

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._header = self._create_header()
        main_layout.addWidget(self._header)

        scroll = self._create_scroll_area()
        self._content = QWidget()
        self._content.setStyleSheet("background-color: transparent;")

        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(
            SPACING["md"], SPACING["md"], SPACING["md"], SPACING["md"]
        )
        self._content_layout.setSpacing(SPACING["sm"])
        self._content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(self._content)
        main_layout.addWidget(scroll, stretch=1)

    def _create_header(self) -> QFrame:
        header = QFrame()
        header.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS["bg_elevated"]};
                border-bottom: 1px solid {COLORS["border_default"]};
            }}
        """)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(
            SPACING["lg"], SPACING["md"], SPACING["lg"], SPACING["md"]
        )

        self._agent_label = QLabel("🤖 Agent")
        self._agent_label.setStyleSheet(f"""
            color: {COLORS["text_primary"]};
            font-size: {FONTS["size_xl"]}px;
            font-weight: {FONTS["weight_bold"]};
        """)
        layout.addWidget(self._agent_label)

        layout.addStretch()

        self._status_label = QLabel("")
        self._status_label.setStyleSheet(f"""
            color: {COLORS["text_secondary"]};
            font-size: {FONTS["size_md"]}px;
        """)
        layout.addWidget(self._status_label)

        return header

    def _create_scroll_area(self) -> QScrollArea:
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
                width: 10px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {COLORS["border_default"]};
                border-radius: 5px;
                min-height: 40px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {COLORS["text_muted"]};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)
        return scroll

    def load_delegation(self, delegation_data: DelegationData) -> None:
        self._child_session_id = delegation_data.get("child_session_id")
        self._subagent_type = delegation_data.get("subagent_type")
        status = delegation_data.get("status", "completed")
        duration_ms = delegation_data.get("duration_ms", 0)

        agent_text = f"🤖 {self._subagent_type}" if self._subagent_type else "🤖 Agent"
        self._agent_label.setText(agent_text)

        status_icon = (
            "✓" if status == "completed" else "✗" if status == "error" else "◐"
        )
        duration_str = self._format_duration(duration_ms)
        self._status_label.setText(f"{status_icon} {status} • {duration_str}")

        self._clear_content()

        if self._child_session_id:
            self._load_timeline()
        else:
            self._show_message("No child session ID available", COLORS["text_muted"])

    def _load_timeline(self) -> None:
        child_session_id = self._child_session_id
        if not child_session_id:
            return

        client = self._get_api_client()
        if not client.is_available:
            self._show_message("API not available", COLORS["error"])
            return

        data = client.get_delegation_timeline(child_session_id)
        if not data:
            self._show_message("No timeline data available", COLORS["text_muted"])
            return

        prompt_input = data.get("prompt_input")
        if prompt_input:
            self._add_prompt_input_widget(prompt_input)

        timeline = data.get("timeline", [])
        if not timeline:
            self._show_message("No activity recorded", COLORS["text_muted"])
            return

        for item in timeline:
            self._add_timeline_item(item)

        self._content_layout.addStretch()

    def _add_prompt_input_widget(self, prompt: str) -> None:
        frame = self._create_item_frame(COLORS["type_read_bg"])
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(
            SPACING["sm"], SPACING["sm"], SPACING["sm"], SPACING["sm"]
        )
        layout.setSpacing(SPACING["xs"])

        header = QLabel("📥 Prompt Input")
        header.setStyleSheet(f"""
            color: {COLORS["type_read"]};
            font-size: {FONTS["size_lg"]}px;
            font-weight: {FONTS["weight_bold"]};
        """)
        layout.addWidget(header)

        text_widget = self._create_text_widget(prompt)
        layout.addWidget(text_widget)

        self._content_layout.addWidget(frame)

    def _add_timeline_item(self, item: dict) -> None:
        item_type = item.get("type")

        if item_type == "reasoning":
            self._add_reasoning_widget(item)
        elif item_type == "text":
            self._add_text_widget(item)
        elif item_type == "tool":
            self._add_tool_widget(item)

    def _add_reasoning_widget(self, item: dict) -> None:
        content = item.get("content", "")
        if not content:
            return

        frame = self._create_item_frame(COLORS["type_skill_bg"])
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(
            SPACING["sm"], SPACING["sm"], SPACING["sm"], SPACING["sm"]
        )
        layout.setSpacing(SPACING["xs"])

        header = QLabel("🧠 Reasoning")
        header.setStyleSheet(f"""
            color: {COLORS["type_skill"]};
            font-size: {FONTS["size_lg"]}px;
            font-weight: {FONTS["weight_bold"]};
        """)
        layout.addWidget(header)

        text_widget = self._create_text_widget(content)
        layout.addWidget(text_widget)

        self._content_layout.addWidget(frame)

    def _add_text_widget(self, item: dict) -> None:
        content = item.get("content", "")
        if not content:
            return

        frame = self._create_item_frame(COLORS["success_muted"])
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(
            SPACING["sm"], SPACING["sm"], SPACING["sm"], SPACING["sm"]
        )
        layout.setSpacing(SPACING["xs"])

        header = QLabel("💬 Response")
        header.setStyleSheet(f"""
            color: {COLORS["success"]};
            font-size: {FONTS["size_lg"]}px;
            font-weight: {FONTS["weight_bold"]};
        """)
        layout.addWidget(header)

        text_widget = self._create_text_widget(content)
        layout.addWidget(text_widget)

        self._content_layout.addWidget(frame)

    def _add_tool_widget(self, item: dict) -> None:
        tool_name = item.get("tool_name", "unknown")
        tool_status = item.get("tool_status", "")
        arguments = item.get("arguments", "")
        result = item.get("result", "")
        duration_ms = item.get("duration_ms", 0)
        error = item.get("error")

        bg_color = COLORS["error_muted"] if error else COLORS["type_command_bg"]
        frame = self._create_item_frame(bg_color)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(
            SPACING["sm"], SPACING["sm"], SPACING["sm"], SPACING["sm"]
        )
        layout.setSpacing(SPACING["xs"])

        header_layout = QHBoxLayout()
        header_layout.setSpacing(SPACING["xs"])

        status_icon = "✓" if tool_status == "success" else "✗" if error else "◐"
        tool_label = QLabel(f"🔧 {tool_name}")
        tool_label.setStyleSheet(f"""
            color: {COLORS["warning"]};
            font-size: {FONTS["size_lg"]}px;
            font-weight: {FONTS["weight_bold"]};
        """)
        header_layout.addWidget(tool_label)

        header_layout.addStretch()

        if duration_ms:
            duration_label = QLabel(
                f"{status_icon} {self._format_duration(duration_ms)}"
            )
            duration_label.setStyleSheet(f"""
                color: {COLORS["text_secondary"]};
                font-size: {FONTS["size_md"]}px;
            """)
            header_layout.addWidget(duration_label)

        layout.addLayout(header_layout)

        if arguments:
            self._add_tool_section(layout, "Input", arguments, COLORS["bg_elevated"])

        if result:
            result_color = COLORS["bg_elevated"] if not error else COLORS["error_muted"]
            self._add_tool_section(layout, "Output", result, result_color)

        if error:
            error_label = QLabel(f"⚠️ Error: {error}")
            error_label.setStyleSheet(f"""
                color: {COLORS["error"]};
                font-size: {FONTS["size_md"]}px;
                font-weight: {FONTS["weight_semibold"]};
            """)
            error_label.setWordWrap(True)
            layout.addWidget(error_label)

        self._content_layout.addWidget(frame)

    def _add_tool_section(
        self, layout: QVBoxLayout, title: str, content: str, bg_color: str
    ) -> None:
        section_label = QLabel(title)
        section_label.setStyleSheet(f"""
            color: {COLORS["text_secondary"]};
            font-size: {FONTS["size_md"]}px;
            font-weight: {FONTS["weight_semibold"]};
        """)
        layout.addWidget(section_label)

        display_content = content
        if content.startswith("{") or content.startswith("["):
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict) and "filePath" in parsed:
                    display_content = parsed["filePath"]
                elif isinstance(parsed, dict) and "command" in parsed:
                    display_content = parsed["command"]
                elif isinstance(parsed, dict) and "pattern" in parsed:
                    display_content = f"pattern: {parsed['pattern']}"
            except json.JSONDecodeError:
                pass

        if len(display_content) > 500:
            display_content = display_content[:500] + "..."

        content_widget = self._create_text_widget(display_content, bg_color=bg_color)
        layout.addWidget(content_widget)

    def _create_item_frame(self, bg_color: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 1px solid {COLORS["border_strong"]};
                border-radius: {RADIUS["lg"]}px;
            }}
        """)
        return frame

    def _create_text_widget(self, text: str, bg_color: str | None = None) -> QLabel:
        widget = QLabel(text)
        widget.setWordWrap(True)
        widget.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )

        bg = bg_color or COLORS["bg_surface"]
        widget.setStyleSheet(f"""
            QLabel {{
                background-color: {bg};
                color: {COLORS["text_primary"]};
                border: none;
                border-radius: {RADIUS["md"]}px;
                padding: {SPACING["sm"]}px;
                font-family: {FONTS["family"]};
                font-size: {FONTS["size_md"]}px;
                line-height: 1.5;
            }}
        """)
        return widget

    def _show_message(self, message: str, color: str) -> None:
        label = QLabel(message)
        label.setStyleSheet(f"""
            color: {color};
            font-size: {FONTS["size_lg"]}px;
            font-weight: {FONTS["weight_medium"]};
            padding: {SPACING["2xl"]}px;
        """)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._content_layout.addWidget(label)

    def _clear_content(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget() if item else None
            if widget:
                widget.deleteLater()

    def _format_duration(self, ms: int) -> str:
        if ms < 1000:
            return f"{ms}ms"
        seconds = ms / 1000
        if seconds < 60:
            return f"{seconds:.1f}s"
        minutes = seconds / 60
        if minutes < 60:
            secs = int(seconds % 60)
            return f"{int(minutes)}m {secs}s"
        hours = minutes / 60
        mins = int(minutes % 60)
        return f"{int(hours)}h {mins}m"

    def clear(self) -> None:
        self._child_session_id = None
        self._subagent_type = None
        self._agent_label.setText("🤖 Agent")
        self._status_label.setText("")
        self._clear_content()
