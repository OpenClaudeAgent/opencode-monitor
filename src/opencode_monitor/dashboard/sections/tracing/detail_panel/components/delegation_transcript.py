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
from ...helpers import format_duration


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

        scroll = self._create_scroll_area()
        self._content = QWidget()
        self._content.setStyleSheet("background-color: transparent;")

        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(
            SPACING["sm"], SPACING["xs"], SPACING["sm"], SPACING["sm"]
        )
        self._content_layout.setSpacing(SPACING["sm"])
        self._content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(self._content)
        main_layout.addWidget(scroll, stretch=1)

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
        card = self._create_content_card(
            bg_color=COLORS["type_read_bg"],
            emoji="📥",
            title="Prompt Input",
            title_color=COLORS["type_read"],
            content=prompt,
        )
        self._content_layout.addWidget(card)

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

        card = self._create_content_card(
            bg_color=COLORS["type_skill_bg"],
            emoji="🧠",
            title="Reasoning",
            title_color=COLORS["type_skill"],
            content=content,
        )
        self._content_layout.addWidget(card)

    def _add_text_widget(self, item: dict) -> None:
        content = item.get("content", "")
        if not content:
            return

        card = self._create_content_card(
            bg_color=COLORS["success_muted"],
            emoji="💬",
            title="Response",
            title_color=COLORS["success"],
            content=content,
        )
        self._content_layout.addWidget(card)

    def _add_tool_widget(self, item: dict) -> None:
        tool_name = item.get("tool_name", "unknown")
        tool_status = item.get("tool_status", "")
        arguments = item.get("arguments", "")
        result = item.get("result", "")
        duration_ms = item.get("duration_ms", 0)
        error = item.get("error")

        bg_color = COLORS["error_muted"] if error else COLORS["type_command_bg"]
        frame = self._create_item_frame(bg_color)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(
            SPACING["xs"], SPACING["xs"], SPACING["xs"], SPACING["xs"]
        )

        inner = QFrame()
        inner.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS["bg_surface"]};
                border-radius: {RADIUS["md"]}px;
                padding: {SPACING["sm"]}px;
            }}
        """)
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        inner_layout.setSpacing(SPACING["xs"])

        header_layout = QHBoxLayout()
        header_layout.setSpacing(SPACING["xs"])

        status_icon = "✓" if tool_status == "success" else "✗" if error else "◐"
        tool_label = QLabel(f"🔧 {tool_name}")
        tool_label.setStyleSheet(f"""
            background: transparent;
            color: {COLORS["warning"]};
            font-size: {FONTS["size_lg"]}px;
            font-weight: {FONTS["weight_bold"]};
        """)
        header_layout.addWidget(tool_label)

        header_layout.addStretch()

        if duration_ms:
            duration_label = QLabel(f"{status_icon} {format_duration(duration_ms)}")
            duration_label.setStyleSheet(f"""
                background: transparent;
                color: {COLORS["text_secondary"]};
                font-size: {FONTS["size_md"]}px;
            """)
            header_layout.addWidget(duration_label)

        inner_layout.addLayout(header_layout)

        if arguments:
            self._add_tool_section(inner_layout, "Input", arguments)

        if result:
            self._add_tool_section(inner_layout, "Output", result)

        if error:
            error_label = QLabel(f"⚠️ Error: {error}")
            error_label.setStyleSheet(f"""
                background: transparent;
                color: {COLORS["error"]};
                font-size: {FONTS["size_md"]}px;
                font-weight: {FONTS["weight_semibold"]};
            """)
            error_label.setWordWrap(True)
            inner_layout.addWidget(error_label)

        frame_layout.addWidget(inner)
        self._content_layout.addWidget(frame)

    def _add_tool_section(self, layout: QVBoxLayout, title: str, content: str) -> None:
        section_label = QLabel(title)
        section_label.setStyleSheet(f"""
            background: transparent;
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

        content_label = QLabel(display_content)
        content_label.setWordWrap(True)
        content_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        content_label.setStyleSheet(f"""
            background-color: {COLORS["bg_elevated"]};
            color: {COLORS["text_primary"]};
            border-radius: {RADIUS["sm"]}px;
            padding: {SPACING["xs"]}px;
            font-size: {FONTS["size_md"]}px;
        """)
        layout.addWidget(content_label)

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

    def _create_content_card(
        self, bg_color: str, emoji: str, title: str, title_color: str, content: str
    ) -> QFrame:
        frame = self._create_item_frame(bg_color)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(
            SPACING["xs"], SPACING["xs"], SPACING["xs"], SPACING["xs"]
        )

        inner = QFrame()
        inner.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS["bg_surface"]};
                border-radius: {RADIUS["md"]}px;
                padding: {SPACING["sm"]}px;
            }}
        """)
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        inner_layout.setSpacing(SPACING["xs"])

        header = QLabel(f"{emoji} {title}")
        header.setStyleSheet(f"""
            background: transparent;
            color: {title_color};
            font-size: {FONTS["size_lg"]}px;
            font-weight: {FONTS["weight_bold"]};
        """)
        inner_layout.addWidget(header)

        text_label = QLabel(content)
        text_label.setWordWrap(True)
        text_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        text_label.setStyleSheet(f"""
            color: {COLORS["text_primary"]};
            font-size: {FONTS["size_md"]}px;
        """)
        inner_layout.addWidget(text_label)

        frame_layout.addWidget(inner)
        return frame

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

    def clear(self) -> None:
        self._child_session_id = None
        self._subagent_type = None
        self._clear_content()
