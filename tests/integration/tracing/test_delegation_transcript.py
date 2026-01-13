"""Integration tests for DelegationTranscriptPanel display."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from PyQt6.QtWidgets import QLabel, QFrame, QVBoxLayout
from PyQt6.QtCore import Qt

from tests.mocks import MockAnalyticsAPIClient, MockAPIResponses

pytestmark = [
    pytest.mark.integration,
    pytest.mark.xdist_group(name="qt_tracing"),  # Force same worker for Qt UI tests
]

FIXED_TEST_DATE = datetime(2024, 1, 15, 10, 30, 0)


def create_delegation_timeline_data():
    """Create realistic delegation timeline data for tests."""
    base_time = FIXED_TEST_DATE
    return {
        "meta": {
            "session_id": "sess-delegation-test",
            "title": "Test delegation",
            "count": 5,
        },
        "prompt_input": "Analyze the codebase structure",
        "timeline": [
            {
                "id": "part-001",
                "type": "reasoning",
                "content": "Let me examine the project files.",
                "timestamp": (base_time + timedelta(seconds=2)).isoformat(),
            },
            {
                "id": "part-002",
                "type": "tool",
                "tool_name": "mcp_bash",
                "tool_status": "success",
                "arguments": '{"command": "ls -la"}',
                "result": "total 10\ndrwxr-xr-x 5 user staff 160 Jan 11 src",
                "duration_ms": 100,
                "error": None,
                "timestamp": (base_time + timedelta(seconds=5)).isoformat(),
            },
            {
                "id": "part-003",
                "type": "tool",
                "tool_name": "mcp_read",
                "tool_status": "success",
                "arguments": '{"filePath": "/src/main.py"}',
                "result": "def main(): pass",
                "duration_ms": 50,
                "error": None,
                "timestamp": (base_time + timedelta(seconds=8)).isoformat(),
            },
            {
                "id": "part-004",
                "type": "reasoning",
                "content": "The structure looks clean. I found the entry point.",
                "timestamp": (base_time + timedelta(seconds=10)).isoformat(),
            },
            {
                "id": "part-005",
                "type": "text",
                "content": "The project has a modular structure with main.py as entry.",
                "timestamp": (base_time + timedelta(seconds=12)).isoformat(),
            },
        ],
    }


class TestDelegationTranscriptPanelDisplay:
    @pytest.fixture
    def panel(self, qapp):
        from opencode_monitor.dashboard.sections.tracing.detail_panel.components import (
            DelegationTranscriptPanel,
        )

        panel = DelegationTranscriptPanel()
        yield panel
        panel.deleteLater()

    @pytest.fixture
    def mock_client(self):
        responses = {
            "delegation_timeline": create_delegation_timeline_data(),
            "health": True,
        }
        return MockAnalyticsAPIClient(responses)

    def test_panel_displays_prompt_input_first(self, panel, mock_client, qtbot):
        """GIVEN delegation data with prompt_input
        WHEN panel loads the delegation
        THEN prompt input widget appears as first content item
        """
        with patch(
            "opencode_monitor.api.get_api_client",
            return_value=mock_client,
        ):
            delegation_data = {
                "child_session_id": "sess-delegation-test",
                "subagent_type": "explore",
                "status": "completed",
                "duration_ms": 15000,
            }
            panel.load_delegation(delegation_data)
            qtbot.wait(50)

        content_layout = panel._content_layout
        assert content_layout.count() > 0

        first_widget = content_layout.itemAt(0).widget()
        assert first_widget is not None

        labels = first_widget.findChildren(QLabel)
        header_texts = [label.text() for label in labels]

        assert any("Prompt Input" in text for text in header_texts)

    def test_panel_displays_reasoning_sections(self, panel, mock_client, qtbot):
        """GIVEN delegation data with reasoning entries
        WHEN panel loads the delegation
        THEN reasoning sections are displayed with correct content
        """
        with patch(
            "opencode_monitor.api.get_api_client",
            return_value=mock_client,
        ):
            delegation_data = {
                "child_session_id": "sess-delegation-test",
                "subagent_type": "explore",
                "status": "completed",
                "duration_ms": 15000,
            }
            panel.load_delegation(delegation_data)
            qtbot.wait(50)

        all_labels = panel.findChildren(QLabel)
        all_texts = [label.text() for label in all_labels]

        reasoning_headers = [t for t in all_texts if "Reasoning" in t]
        assert len(reasoning_headers) >= 1

        reasoning_content_found = any(
            "examine the project" in t.lower() for t in all_texts
        )
        assert reasoning_content_found

    def test_panel_displays_tool_calls_with_name(self, panel, mock_client, qtbot):
        """GIVEN delegation data with tool calls
        WHEN panel loads the delegation
        THEN tool calls show tool name in header
        """
        with patch(
            "opencode_monitor.api.get_api_client",
            return_value=mock_client,
        ):
            delegation_data = {
                "child_session_id": "sess-delegation-test",
                "subagent_type": "explore",
                "status": "completed",
                "duration_ms": 15000,
            }
            panel.load_delegation(delegation_data)
            qtbot.wait(50)

        all_labels = panel.findChildren(QLabel)
        all_texts = [label.text() for label in all_labels]

        bash_tool_found = any("mcp_bash" in t for t in all_texts)
        read_tool_found = any("mcp_read" in t for t in all_texts)

        assert bash_tool_found, f"mcp_bash not found in: {all_texts}"
        assert read_tool_found, f"mcp_read not found in: {all_texts}"

    def test_panel_displays_tool_input_and_output(self, panel, mock_client, qtbot):
        """GIVEN delegation data with tool calls that have arguments and results
        WHEN panel loads the delegation
        THEN tool sections show Input and Output labels
        """
        with patch(
            "opencode_monitor.api.get_api_client",
            return_value=mock_client,
        ):
            delegation_data = {
                "child_session_id": "sess-delegation-test",
                "subagent_type": "explore",
                "status": "completed",
                "duration_ms": 15000,
            }
            panel.load_delegation(delegation_data)
            qtbot.wait(50)

        all_labels = panel.findChildren(QLabel)
        all_texts = [label.text() for label in all_labels]

        input_labels = [t for t in all_texts if t == "Input"]
        output_labels = [t for t in all_texts if t == "Output"]

        assert len(input_labels) >= 2, "Should have Input labels for tool calls"
        assert len(output_labels) >= 2, "Should have Output labels for tool calls"

    def test_panel_displays_response_section(self, panel, mock_client, qtbot):
        """GIVEN delegation data with text response
        WHEN panel loads the delegation
        THEN response section is displayed with correct content
        """
        with patch(
            "opencode_monitor.api.get_api_client",
            return_value=mock_client,
        ):
            delegation_data = {
                "child_session_id": "sess-delegation-test",
                "subagent_type": "explore",
                "status": "completed",
                "duration_ms": 15000,
            }
            panel.load_delegation(delegation_data)
            qtbot.wait(50)

        all_labels = panel.findChildren(QLabel)
        all_texts = [label.text() for label in all_labels]

        response_headers = [t for t in all_texts if "Response" in t]
        assert len(response_headers) >= 1

        response_content_found = any("modular structure" in t for t in all_texts)
        assert response_content_found

    def test_panel_timeline_order_is_chronological(self, panel, mock_client, qtbot):
        """GIVEN delegation data with multiple timeline items
        WHEN panel loads the delegation
        THEN items appear in chronological order: prompt, reasoning, tools, response
        """
        with patch(
            "opencode_monitor.api.get_api_client",
            return_value=mock_client,
        ):
            delegation_data = {
                "child_session_id": "sess-delegation-test",
                "subagent_type": "explore",
                "status": "completed",
                "duration_ms": 15000,
            }
            panel.load_delegation(delegation_data)
            qtbot.wait(50)

        content_layout = panel._content_layout
        item_types = []

        for i in range(content_layout.count()):
            item = content_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                labels = widget.findChildren(QLabel)
                for label in labels:
                    text = label.text()
                    if "Prompt Input" in text:
                        item_types.append("prompt")
                        break
                    elif "Reasoning" in text:
                        item_types.append("reasoning")
                        break
                    elif "🔧" in text:
                        item_types.append("tool")
                        break
                    elif "Response" in text:
                        item_types.append("response")
                        break

        assert item_types[0] == "prompt", "First item should be prompt input"

        if "response" in item_types:
            response_idx = item_types.index("response")
            prompt_idx = item_types.index("prompt")
            assert response_idx > prompt_idx, "Response should come after prompt"


class TestDelegationTranscriptPanelEdgeCases:
    @pytest.fixture
    def panel(self, qapp):
        from opencode_monitor.dashboard.sections.tracing.detail_panel.components import (
            DelegationTranscriptPanel,
        )

        panel = DelegationTranscriptPanel()
        yield panel
        panel.deleteLater()

    def test_panel_handles_empty_timeline(self, panel, qapp, qtbot):
        """GIVEN delegation data with empty timeline
        WHEN panel loads the delegation
        THEN panel shows appropriate empty state message
        """
        responses = {
            "delegation_timeline": {
                "meta": {"session_id": "empty", "count": 0},
                "prompt_input": None,
                "timeline": [],
            },
            "health": True,
        }
        mock_client = MockAnalyticsAPIClient(responses)

        with patch(
            "opencode_monitor.api.get_api_client",
            return_value=mock_client,
        ):
            delegation_data = {
                "child_session_id": "empty",
                "subagent_type": "explore",
                "status": "completed",
                "duration_ms": 0,
            }
            panel.load_delegation(delegation_data)
            qtbot.wait(50)

        all_labels = panel.findChildren(QLabel)
        all_texts = [label.text().lower() for label in all_labels]

        empty_message_found = any(
            "no" in t and ("activity" in t or "timeline" in t or "data" in t)
            for t in all_texts
        )
        assert empty_message_found or panel._content_layout.count() <= 1

    def test_panel_handles_tool_with_error(self, panel, qapp, qtbot):
        """GIVEN delegation data with a failed tool call
        WHEN panel loads the delegation
        THEN error is displayed in tool section
        """
        responses = {
            "delegation_timeline": {
                "meta": {"session_id": "error-test", "count": 1},
                "prompt_input": "Run tests",
                "timeline": [
                    {
                        "id": "part-001",
                        "type": "tool",
                        "tool_name": "mcp_bash",
                        "tool_status": "error",
                        "arguments": '{"command": "pytest"}',
                        "result": None,
                        "duration_ms": 5000,
                        "error": "Exit code 1: Tests failed",
                        "timestamp": FIXED_TEST_DATE.isoformat(),
                    },
                ],
            },
            "health": True,
        }
        mock_client = MockAnalyticsAPIClient(responses)

        with patch(
            "opencode_monitor.api.get_api_client",
            return_value=mock_client,
        ):
            delegation_data = {
                "child_session_id": "error-test",
                "subagent_type": "explore",
                "status": "error",
                "duration_ms": 5000,
            }
            panel.load_delegation(delegation_data)
            qtbot.wait(50)

        all_labels = panel.findChildren(QLabel)
        all_texts = [label.text() for label in all_labels]

        error_displayed = any("Error" in t or "failed" in t.lower() for t in all_texts)
        assert error_displayed

    def test_panel_handles_missing_child_session_id(self, panel, qapp, qtbot):
        """GIVEN delegation data without child_session_id
        WHEN panel loads the delegation
        THEN panel shows appropriate message
        """
        delegation_data = {
            "child_session_id": None,
            "subagent_type": "explore",
            "status": "completed",
            "duration_ms": 0,
        }
        panel.load_delegation(delegation_data)
        qtbot.wait(50)

        all_labels = panel.findChildren(QLabel)
        all_texts = [label.text().lower() for label in all_labels]

        message_found = any("no" in t and "session" in t for t in all_texts)
        assert message_found or panel._content_layout.count() <= 1


class TestDelegationTranscriptPanelUserTextFiltering:
    """Tests to verify user text parts are NOT shown as response (prevents duplicate prompt)."""

    @pytest.fixture
    def panel(self, qapp):
        from opencode_monitor.dashboard.sections.tracing.detail_panel.components import (
            DelegationTranscriptPanel,
        )

        panel = DelegationTranscriptPanel()
        yield panel
        panel.deleteLater()

    def test_prompt_input_not_duplicated_as_response(self, panel, qapp, qtbot):
        """GIVEN delegation data where API correctly filters user text
        WHEN panel loads the delegation
        THEN prompt input appears only once, not also as Response
        """
        prompt_text = "Analyze the codebase structure"

        responses = {
            "delegation_timeline": {
                "meta": {"session_id": "test", "count": 2},
                "prompt_input": prompt_text,
                "timeline": [
                    {
                        "id": "part-001",
                        "type": "reasoning",
                        "content": "Let me analyze this.",
                        "timestamp": FIXED_TEST_DATE.isoformat(),
                    },
                    {
                        "id": "part-002",
                        "type": "text",
                        "content": "Analysis complete: found 3 modules.",
                        "timestamp": (
                            FIXED_TEST_DATE + timedelta(seconds=5)
                        ).isoformat(),
                    },
                ],
            },
            "health": True,
        }
        mock_client = MockAnalyticsAPIClient(responses)

        with patch(
            "opencode_monitor.api.get_api_client",
            return_value=mock_client,
        ):
            delegation_data = {
                "child_session_id": "test",
                "subagent_type": "explore",
                "status": "completed",
                "duration_ms": 5000,
            }
            panel.load_delegation(delegation_data)
            qtbot.wait(50)

        all_labels = panel.findChildren(QLabel)
        all_texts = [label.text() for label in all_labels]

        prompt_occurrences = sum(1 for t in all_texts if prompt_text in t)
        assert prompt_occurrences == 1, (
            f"Prompt should appear exactly once, found {prompt_occurrences}"
        )

        response_content = "Analysis complete: found 3 modules."
        response_found = any(response_content in t for t in all_texts)
        assert response_found, "Actual response content should be displayed"
