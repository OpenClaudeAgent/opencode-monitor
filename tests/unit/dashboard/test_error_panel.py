"""Tests for error panel components in session_overview.py"""

import pytest
from PyQt6.QtWidgets import QWidget


@pytest.fixture
def widget_parent(qapp):
    parent = QWidget()
    yield parent
    parent.deleteLater()


class TestClassifyErrorType:
    @pytest.mark.parametrize(
        "message,expected_type,expected_label",
        [
            ("Connection timeout after 30s", "timeout", "TIMEOUT"),
            ("Tool execution aborted", "timeout", "TIMEOUT"),
            ("AbortError: The operation was aborted.", "timeout", "TIMEOUT"),
            ("Request timed out", "timeout", "TIMEOUT"),
            ("Error: Request failed with status code: 401", "auth", "AUTH"),
            ("Error: Request failed with status code: 403", "auth", "AUTH"),
            ("Error: forbidden access", "auth", "AUTH"),
            ("Permission denied", "auth", "AUTH"),
            ("The user rejected permission", "auth", "AUTH"),
            ("Authentication failed", "auth", "AUTH"),
            ("Connection refused", "network", "NETWORK"),
            ("Network error occurred", "network", "NETWORK"),
            ("SSL certificate verify failed", "network", "NETWORK"),
            ("unknown certificate verification error", "network", "NETWORK"),
            ("DNS lookup failed", "network", "NETWORK"),
            ("Error: Request failed with status code: 404", "not_found", "NOT FOUND"),
            ("File not found: /path/to/file", "not_found", "NOT FOUND"),
            ("Resource not found", "not_found", "NOT FOUND"),
            ("Syntax error on line 42", "syntax", "SYNTAX"),
            ("Parse error: unexpected token", "syntax", "SYNTAX"),
            ("Error: Rate limit exceeded", "rate_limit", "RATE LIMIT"),
            ("Error: Request failed with status code: 429", "rate_limit", "RATE LIMIT"),
            ("Too many requests", "rate_limit", "RATE LIMIT"),
            ("Unknown error occurred", "unknown", "ERROR"),
            ("Something went wrong", "unknown", "ERROR"),
            ("", "unknown", "ERROR"),
        ],
    )
    def test_classify_error_type(self, message, expected_type, expected_label):
        from opencode_monitor.dashboard.sections.tracing.detail_panel.components.session_overview import (
            classify_error_type,
        )

        error_type, color, label = classify_error_type(message)
        assert error_type == expected_type
        assert label == expected_label
        assert isinstance(color, str)
        assert color.startswith("#")

    def test_classify_error_type_case_insensitive(self):
        from opencode_monitor.dashboard.sections.tracing.detail_panel.components.session_overview import (
            classify_error_type,
        )

        upper_case = classify_error_type("TIMEOUT ERROR")
        lower_case = classify_error_type("timeout error")
        mixed_case = classify_error_type("TimeOut Error")

        assert upper_case[0] == lower_case[0] == mixed_case[0] == "timeout"


class TestErrorInfo:
    def test_error_info_creation(self):
        from opencode_monitor.dashboard.sections.tracing.detail_panel.components.session_overview import (
            ErrorInfo,
        )

        error = ErrorInfo(
            timestamp="2025-01-10T10:30:00",
            tool_name="bash",
            message="Tool execution aborted",
        )

        assert error.timestamp == "2025-01-10T10:30:00"
        assert error.tool_name == "bash"
        assert error.message == "Tool execution aborted"

    def test_error_info_with_long_message(self):
        from opencode_monitor.dashboard.sections.tracing.detail_panel.components.session_overview import (
            ErrorInfo,
        )

        long_message = "Error: " + "x" * 500
        error = ErrorInfo(
            timestamp="2025-01-10T10:30:00",
            tool_name="webfetch",
            message=long_message,
        )

        assert len(error.message) == 507
        assert error.message == long_message


class TestErrorItemWidget:
    def test_error_item_creation(self, qapp, widget_parent):
        from opencode_monitor.dashboard.sections.tracing.detail_panel.components.session_overview import (
            ErrorItemWidget,
            ErrorInfo,
        )

        error = ErrorInfo(
            timestamp="2025-01-10T10:30:00",
            tool_name="bash",
            message="Tool execution aborted",
        )

        widget = ErrorItemWidget(error, prefix="├─", parent=widget_parent)

        assert widget._error == error
        assert widget._prefix == "├─"
        assert widget._is_expanded is False

    def test_error_item_toggle_expand(self, qapp, widget_parent):
        from opencode_monitor.dashboard.sections.tracing.detail_panel.components.session_overview import (
            ErrorItemWidget,
            ErrorInfo,
        )

        error = ErrorInfo(
            timestamp="2025-01-10T10:30:00",
            tool_name="webfetch",
            message="Error: Request failed with status code: 403",
        )

        widget = ErrorItemWidget(error, prefix="└─", parent=widget_parent)

        assert widget._is_expanded is False
        assert widget._full_message.isHidden() is True

        widget._toggle_expand()

        assert widget._is_expanded is True
        assert widget._full_message.isHidden() is False
        assert widget._arrow.text() == "▼"

        widget._toggle_expand()

        assert widget._is_expanded is False
        assert widget._full_message.isHidden() is True
        assert widget._arrow.text() == "▶"

    def test_error_item_full_message_visible_when_expanded(self, qapp, widget_parent):
        from opencode_monitor.dashboard.sections.tracing.detail_panel.components.session_overview import (
            ErrorItemWidget,
            ErrorInfo,
        )

        full_msg = 'Error: The user has specified a rule which prevents you from using this specific tool call. Here are some of the relevant rules [{"permission":"*","pattern":"*","action":"allow"}]'
        error = ErrorInfo(
            timestamp="2025-01-10T10:30:00",
            tool_name="todowrite",
            message=full_msg,
        )

        widget = ErrorItemWidget(error, prefix="└─", parent=widget_parent)
        widget._toggle_expand()

        assert widget._full_message.text() == full_msg
        assert widget._full_message.isHidden() is False


class TestErrorsWidget:
    def test_errors_widget_creation(self, qapp, widget_parent):
        from opencode_monitor.dashboard.sections.tracing.detail_panel.components.session_overview import (
            ErrorsWidget,
        )

        widget = ErrorsWidget(parent=widget_parent)

        assert widget._is_expanded is False
        assert widget._errors == []
        assert widget._scroll.isHidden() is True

    def test_errors_widget_load_errors(self, qapp, widget_parent):
        from opencode_monitor.dashboard.sections.tracing.detail_panel.components.session_overview import (
            ErrorsWidget,
            ErrorInfo,
        )

        widget = ErrorsWidget(parent=widget_parent)

        errors = [
            ErrorInfo("2025-01-10T10:30:00", "bash", "Tool execution aborted"),
            ErrorInfo("2025-01-10T10:31:00", "webfetch", "Error: 403 Forbidden"),
            ErrorInfo("2025-01-10T10:32:00", "read", "File not found"),
        ]

        widget.load_errors(errors)

        assert widget._errors == errors
        assert widget._container_layout.count() == 4  # 3 errors + 1 stretch

    def test_errors_widget_empty_list(self, qapp, widget_parent):
        from opencode_monitor.dashboard.sections.tracing.detail_panel.components.session_overview import (
            ErrorsWidget,
        )

        widget = ErrorsWidget(parent=widget_parent)
        widget.load_errors([])

        assert widget._errors == []
        assert widget._container_layout.count() == 0

    def test_errors_widget_toggle_expand(self, qapp, widget_parent):
        from opencode_monitor.dashboard.sections.tracing.detail_panel.components.session_overview import (
            ErrorsWidget,
            ErrorInfo,
        )

        widget = ErrorsWidget(parent=widget_parent)
        widget.load_errors(
            [
                ErrorInfo("2025-01-10T10:30:00", "bash", "Error"),
            ]
        )

        assert widget._scroll.isHidden() is True

        widget._toggle_expand()

        assert widget._is_expanded is True
        assert widget._scroll.isHidden() is False
        assert widget._arrow.text() == "▼"

    def test_errors_widget_toggle_without_errors(self, qapp, widget_parent):
        from opencode_monitor.dashboard.sections.tracing.detail_panel.components.session_overview import (
            ErrorsWidget,
        )

        widget = ErrorsWidget(parent=widget_parent)

        widget._toggle_expand()

        assert widget._is_expanded is False
        assert widget._scroll.isHidden() is True

    def test_errors_widget_reload_clears_previous(self, qapp, widget_parent):
        from opencode_monitor.dashboard.sections.tracing.detail_panel.components.session_overview import (
            ErrorsWidget,
            ErrorInfo,
        )

        widget = ErrorsWidget(parent=widget_parent)

        widget.load_errors(
            [
                ErrorInfo("2025-01-10T10:30:00", "bash", "Error 1"),
                ErrorInfo("2025-01-10T10:31:00", "bash", "Error 2"),
            ]
        )
        assert widget._container_layout.count() == 3  # 2 errors + stretch

        widget.load_errors(
            [
                ErrorInfo("2025-01-10T10:32:00", "bash", "Error 3"),
            ]
        )
        assert widget._container_layout.count() == 2  # 1 error + stretch


class TestExtractFromNode:
    def test_extract_tool_error(self):
        from opencode_monitor.dashboard.sections.tracing.detail_panel.components.session_overview import (
            _extract_from_node,
            SessionData,
        )

        node = {
            "node_type": "tool",
            "tool_name": "bash",
            "tool_status": "error",
            "status": "error",
            "error": "Tool execution aborted",
            "created_at": "2025-01-10T10:30:00",
            "children": [],
        }

        data = SessionData()
        _extract_from_node(node, data)

        assert len(data.errors) == 1
        assert data.errors[0].tool_name == "bash"
        assert data.errors[0].message == "Tool execution aborted"

    def test_extract_tool_error_with_fallback_message(self):
        from opencode_monitor.dashboard.sections.tracing.detail_panel.components.session_overview import (
            _extract_from_node,
            SessionData,
        )

        node = {
            "node_type": "tool",
            "tool_name": "webfetch",
            "tool_status": "error",
            "error": None,
            "display_info": "https://example.com",
            "created_at": "2025-01-10T10:30:00",
            "children": [],
        }

        data = SessionData()
        _extract_from_node(node, data)

        assert len(data.errors) == 1
        assert data.errors[0].message == "https://example.com"

    def test_extract_tool_error_with_generated_message(self):
        from opencode_monitor.dashboard.sections.tracing.detail_panel.components.session_overview import (
            _extract_from_node,
            SessionData,
        )

        node = {
            "node_type": "tool",
            "tool_name": "edit",
            "tool_status": "error",
            "error": "",
            "display_info": "",
            "created_at": "2025-01-10T10:30:00",
            "children": [],
        }

        data = SessionData()
        _extract_from_node(node, data)

        assert len(data.errors) == 1
        assert data.errors[0].message == "edit failed"

    def test_extract_non_tool_error(self):
        from opencode_monitor.dashboard.sections.tracing.detail_panel.components.session_overview import (
            _extract_from_node,
            SessionData,
        )

        node = {
            "node_type": "delegation",
            "status": "error",
            "subagent_type": "oracle",
            "error": "Agent crashed unexpectedly",
            "created_at": "2025-01-10T10:30:00",
            "children": [],
        }

        data = SessionData()
        _extract_from_node(node, data)

        assert len(data.errors) == 1
        assert data.errors[0].tool_name == "oracle"
        assert data.errors[0].message == "Agent crashed unexpectedly"

    def test_extract_nested_errors(self):
        from opencode_monitor.dashboard.sections.tracing.detail_panel.components.session_overview import (
            _extract_from_node,
            SessionData,
        )

        node = {
            "node_type": "user_turn",
            "children": [
                {
                    "node_type": "tool",
                    "tool_name": "bash",
                    "tool_status": "error",
                    "error": "Error 1",
                    "created_at": "2025-01-10T10:30:00",
                    "children": [],
                },
                {
                    "node_type": "tool",
                    "tool_name": "read",
                    "tool_status": "success",
                    "children": [],
                },
                {
                    "node_type": "tool",
                    "tool_name": "webfetch",
                    "tool_status": "error",
                    "error": "Error 2",
                    "created_at": "2025-01-10T10:31:00",
                    "children": [],
                },
            ],
        }

        data = SessionData()
        _extract_from_node(node, data)

        assert len(data.errors) == 2
        assert data.errors[0].tool_name == "bash"
        assert data.errors[1].tool_name == "webfetch"

    def test_extract_success_tool_no_error(self):
        from opencode_monitor.dashboard.sections.tracing.detail_panel.components.session_overview import (
            _extract_from_node,
            SessionData,
        )

        node = {
            "node_type": "tool",
            "tool_name": "bash",
            "tool_status": "success",
            "children": [],
        }

        data = SessionData()
        _extract_from_node(node, data)

        assert len(data.errors) == 0

    def test_extract_preserves_full_error_message(self):
        from opencode_monitor.dashboard.sections.tracing.detail_panel.components.session_overview import (
            _extract_from_node,
            SessionData,
        )

        long_error = 'Error: The user has specified a rule which prevents you from using this specific tool call. Here are some of the relevant rules [{"permission":"*","pattern":"*","action":"allow"},{"permission":"todowrite","pattern":"*","action":"deny"}]'

        node = {
            "node_type": "tool",
            "tool_name": "todowrite",
            "tool_status": "error",
            "error": long_error,
            "created_at": "2025-01-10T10:30:00",
            "children": [],
        }

        data = SessionData()
        _extract_from_node(node, data)

        assert data.errors[0].message == long_error
        assert len(data.errors[0].message) == len(long_error)


class TestErrorItemTreePrefixes:
    def test_single_error_gets_last_prefix(self, qapp, widget_parent):
        from opencode_monitor.dashboard.sections.tracing.detail_panel.components.session_overview import (
            ErrorsWidget,
            ErrorInfo,
            ErrorItemWidget,
        )

        widget = ErrorsWidget(parent=widget_parent)
        widget.load_errors(
            [
                ErrorInfo("2025-01-10T10:30:00", "bash", "Error"),
            ]
        )

        item = widget._container_layout.itemAt(0)
        assert item is not None
        error_widget = item.widget()
        assert isinstance(error_widget, ErrorItemWidget)
        assert error_widget._prefix == "└─"

    def test_multiple_errors_get_correct_prefixes(self, qapp, widget_parent):
        from opencode_monitor.dashboard.sections.tracing.detail_panel.components.session_overview import (
            ErrorsWidget,
            ErrorInfo,
            ErrorItemWidget,
        )

        widget = ErrorsWidget(parent=widget_parent)
        widget.load_errors(
            [
                ErrorInfo("2025-01-10T10:30:00", "bash", "Error 1"),
                ErrorInfo("2025-01-10T10:31:00", "bash", "Error 2"),
                ErrorInfo("2025-01-10T10:32:00", "bash", "Error 3"),
            ]
        )

        first = widget._container_layout.itemAt(0).widget()
        middle = widget._container_layout.itemAt(1).widget()
        last = widget._container_layout.itemAt(2).widget()

        assert isinstance(first, ErrorItemWidget)
        assert isinstance(middle, ErrorItemWidget)
        assert isinstance(last, ErrorItemWidget)

        assert first._prefix == "├─"
        assert middle._prefix == "├─"
        assert last._prefix == "└─"
