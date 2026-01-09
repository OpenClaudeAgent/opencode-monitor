"""
Tests for new tracing features in session_queries.py.

Plan 45: Tests for new and enhanced methods:
- get_session_file_parts() - NEW: file parts with data URLs
- get_session_messages() - ENHANCED: error_name, error_data, root_path, summary_title
- get_session_tool_operations() - ENHANCED: tool_title, result_summary, cost, tokens

Refactored to use shared fixtures from conftest.py and builders.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from tests.builders import SessionBuilder, MessageBuilder, PartBuilder


# =============================================================================
# Fixtures - Use shared fixtures from conftest.py
# =============================================================================

# Sample base64 images for file part tests
PNG_DATA_URL = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
JPEG_DATA_URL = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAMCAgMCAgMDAwMEAwMEBQgFBQQEBQoHBwYIDAoMCwsKCwsNDhIQDQ4RDgsLEBYQERMUFRUVDA8XGBYUGBIUFRT/wAALCAABAAEBAREA/8QAFAABAAAAAAAAAAAAAAAAAAAAB//EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AN//Z"


@pytest.fixture
def tracing_test_data(analytics_db):
    """Create comprehensive test data for tracing tests using builders.

    Returns:
        tuple: (db, session_id) for use in tests
    """
    session_id = "sess-tracing-001"

    # Create session
    SessionBuilder(analytics_db).with_id(session_id).with_title("Tracing Test").insert()

    # Create messages with enhanced fields
    conn = analytics_db.connect()

    # Message 1: User message with root_path and summary_title
    conn.execute(
        """
        INSERT INTO messages (id, session_id, role, agent, tokens_input, tokens_output,
            root_path, summary_title, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        [
            "msg-001",
            session_id,
            "user",
            "main",
            100,
            0,
            "/home/user/project",
            "User asks about feature",
        ],
    )

    # Message 2: Assistant message with summary_title
    conn.execute(
        """
        INSERT INTO messages (id, session_id, role, agent, tokens_input, tokens_output,
            root_path, summary_title, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        [
            "msg-002",
            session_id,
            "assistant",
            "executor",
            0,
            500,
            "/home/user/project",
            "Implementing feature",
        ],
    )

    # Message 3: Error message
    conn.execute(
        """
        INSERT INTO messages (id, session_id, role, agent, tokens_input, tokens_output,
            error_name, error_data, root_path, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        [
            "msg-003",
            session_id,
            "assistant",
            "executor",
            0,
            100,
            "RateLimitError",
            '{"retry_after": 60}',
            "/home/user/project",
        ],
    )

    # Create parts using PartBuilder
    # Text part
    PartBuilder(analytics_db).with_id("part-text-001").for_session(
        session_id
    ).for_message("msg-001").as_text("Please implement feature X").insert()

    # Tool part with all enhanced fields
    PartBuilder(analytics_db).with_id("part-tool-001").for_session(
        session_id
    ).for_message("msg-002").as_tool("bash", "completed").with_arguments(
        {"command": "ls -la"}
    ).with_content("ls -la output").with_duration(150).with_tool_title(
        "List directory contents"
    ).with_result_summary("Found 15 files in directory").with_cost(0.0025).with_tokens(
        50, 100
    ).insert()

    # Tool part without optional fields (backward compat)
    PartBuilder(analytics_db).with_id("part-tool-002").for_session(
        session_id
    ).for_message("msg-002").as_tool("read", "completed").with_content(
        "file content..."
    ).with_duration(75).insert()

    # File parts
    PartBuilder(analytics_db).with_id("part-file-001").for_session(
        session_id
    ).for_message("msg-001").as_file("screenshot.png", "image/png").with_file_url(
        PNG_DATA_URL
    ).insert()

    PartBuilder(analytics_db).with_id("part-file-002").for_session(
        session_id
    ).for_message("msg-001").as_file("photo.jpg", "image/jpeg").with_file_url(
        JPEG_DATA_URL
    ).insert()

    # File part without URL (edge case)
    PartBuilder(analytics_db).with_id("part-file-003").for_session(
        session_id
    ).for_message("msg-001").as_file(None, None).insert()

    return analytics_db, session_id


# =============================================================================
# Test get_session_file_parts()
# =============================================================================


class TestGetSessionFileParts:
    """Tests for get_session_file_parts() method."""

    def test_returns_file_parts_with_data_urls(
        self, tracing_test_data, tracing_service
    ):
        """Should return file parts with their base64 data URLs."""
        _, session_id = tracing_test_data
        result = tracing_service.get_session_file_parts(session_id)

        assert result["meta"]["session_id"] == session_id
        assert len(result["files"]) == 3
        assert "summary" in result

    def test_file_part_contains_expected_fields(
        self, tracing_test_data, tracing_service
    ):
        """Should include id, message_id, filename, mime_type, timestamp."""
        _, session_id = tracing_test_data
        result = tracing_service.get_session_file_parts(session_id)

        png_file = next(
            f for f in result["files"] if f.get("filename") == "screenshot.png"
        )
        assert png_file["id"] == "part-file-001"
        assert png_file["message_id"] == "msg-001"
        assert png_file["mime_type"] == "image/png"
        assert png_file["data_url"].startswith("data:image/png;base64,")

    def test_calculates_size_from_base64(self, tracing_test_data, tracing_service):
        """Should calculate approximate size from base64 data URL."""
        _, session_id = tracing_test_data
        result = tracing_service.get_session_file_parts(session_id)

        file_with_url = next((f for f in result["files"] if f.get("data_url")), None)
        assert file_with_url is not None
        assert file_with_url["size_bytes"] > 0

    def test_handles_missing_file_url(self, tracing_test_data, tracing_service):
        """Should handle files without data URLs gracefully."""
        _, session_id = tracing_test_data
        result = tracing_service.get_session_file_parts(session_id)

        file_without_url = next(
            (f for f in result["files"] if f.get("filename") == "unknown"), None
        )
        assert file_without_url is not None
        assert "data_url" not in file_without_url

    def test_summary_contains_mime_type_counts(
        self, tracing_test_data, tracing_service
    ):
        """Should summarize files by MIME type."""
        _, session_id = tracing_test_data
        result = tracing_service.get_session_file_parts(session_id)

        assert result["summary"]["total_files"] == 3
        mime_types = {
            m["mime_type"]: m["count"] for m in result["summary"]["by_mime_type"]
        }
        assert mime_types.get("image/png") == 1
        assert mime_types.get("image/jpeg") == 1

    def test_returns_empty_for_nonexistent_session(self, tracing_service):
        """Should return empty result for non-existent session."""
        result = tracing_service.get_session_file_parts("nonexistent-session")
        assert result["summary"]["total_files"] == 0
        assert result["files"] == []

    def test_handles_database_error_gracefully(self, analytics_db, tracing_service):
        """Should handle database errors without crashing."""
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = Exception("Database error")

        with patch.object(analytics_db, "connect", return_value=mock_conn):
            result = tracing_service.get_session_file_parts("sess-001")
            assert "error" in result["meta"]
            assert result["files"] == []


# =============================================================================
# Test get_session_messages() - Enhanced Fields
# =============================================================================


class TestGetSessionMessagesEnhanced:
    """Tests for enhanced get_session_messages() with new fields."""

    def test_returns_error_info_when_present(self, tracing_test_data, tracing_service):
        """Should include error info when present."""
        _, session_id = tracing_test_data
        messages = tracing_service.get_session_messages(session_id)

        error_msg = next((m for m in messages if m.get("error")), None)
        assert error_msg is not None
        assert error_msg["error"]["name"] == "RateLimitError"
        assert error_msg["error"]["data"] == '{"retry_after": 60}'

    def test_returns_root_path_when_present(self, tracing_test_data, tracing_service):
        """Should include root_path field when present."""
        _, session_id = tracing_test_data
        messages = tracing_service.get_session_messages(session_id)

        msg_with_root = next((m for m in messages if m.get("root_path")), None)
        assert msg_with_root is not None
        assert msg_with_root["root_path"] == "/home/user/project"

    def test_returns_summary_title_when_present(
        self, tracing_test_data, tracing_service
    ):
        """Should include summary_title (hook) when present."""
        _, session_id = tracing_test_data
        messages = tracing_service.get_session_messages(session_id)

        msg_with_title = next((m for m in messages if m.get("summary_title")), None)
        assert msg_with_title is not None
        assert "summary_title" in msg_with_title

    def test_omits_error_when_not_present(self, tracing_test_data, tracing_service):
        """Should not include error key when no error occurred."""
        _, session_id = tracing_test_data
        messages = tracing_service.get_session_messages(session_id)

        normal_msg = next((m for m in messages if m["role"] == "user"), None)
        assert normal_msg is not None
        assert "error" not in normal_msg


# =============================================================================
# Test get_session_tool_operations() - Enhanced Fields
# =============================================================================


class TestGetSessionToolOperationsEnhanced:
    """Tests for enhanced get_session_tool_operations() with new fields."""

    def test_returns_tool_title_when_present(self, tracing_test_data, tracing_service):
        """Should include title when present."""
        _, session_id = tracing_test_data
        operations = tracing_service.get_session_tool_operations(session_id)

        tool_with_title = next((op for op in operations if op.get("title")), None)
        assert tool_with_title is not None
        assert tool_with_title["title"] == "List directory contents"

    def test_returns_result_summary_when_present(
        self, tracing_test_data, tracing_service
    ):
        """Should include result_summary when present."""
        _, session_id = tracing_test_data
        operations = tracing_service.get_session_tool_operations(session_id)

        tool_with_summary = next(
            (op for op in operations if op.get("result_summary")), None
        )
        assert tool_with_summary is not None
        assert tool_with_summary["result_summary"] == "Found 15 files in directory"

    def test_returns_cost_when_present(self, tracing_test_data, tracing_service):
        """Should include cost when present."""
        _, session_id = tracing_test_data
        operations = tracing_service.get_session_tool_operations(session_id)

        tool_with_cost = next((op for op in operations if op.get("cost")), None)
        assert tool_with_cost is not None
        assert tool_with_cost["cost"] == 0.0025

    def test_returns_tokens_when_present(self, tracing_test_data, tracing_service):
        """Should include tokens object when present."""
        _, session_id = tracing_test_data
        operations = tracing_service.get_session_tool_operations(session_id)

        tool_with_tokens = next((op for op in operations if op.get("tokens")), None)
        assert tool_with_tokens is not None
        assert tool_with_tokens["tokens"]["input"] == 50
        assert tool_with_tokens["tokens"]["output"] == 100

    def test_omits_optional_fields_when_not_present(
        self, tracing_test_data, tracing_service
    ):
        """Should not include optional fields when not set."""
        _, session_id = tracing_test_data
        operations = tracing_service.get_session_tool_operations(session_id)

        basic_tool = next((op for op in operations if op["tool_name"] == "read"), None)
        assert basic_tool is not None
        assert "title" not in basic_tool
        assert "result_summary" not in basic_tool
        assert "cost" not in basic_tool
        assert "tokens" not in basic_tool

    def test_returns_standard_fields(self, tracing_test_data, tracing_service):
        """Should always include standard fields."""
        _, session_id = tracing_test_data
        operations = tracing_service.get_session_tool_operations(session_id)

        for op in operations:
            assert "id" in op
            assert "tool_name" in op
            assert "status" in op
            assert "timestamp" in op


# =============================================================================
# Test Edge Cases
# =============================================================================


class TestSessionQueriesEdgeCases:
    """Test edge cases and error handling."""

    def test_file_parts_with_empty_session(self, analytics_db, tracing_service):
        """Should handle session with no file parts."""
        SessionBuilder(analytics_db).with_id("sess-empty").with_title("Empty").insert()

        result = tracing_service.get_session_file_parts("sess-empty")
        assert result["summary"]["total_files"] == 0
        assert result["files"] == []

    def test_messages_with_null_optional_fields(self, analytics_db, tracing_service):
        """Should handle messages where optional fields are NULL."""
        session_id = "sess-null-fields"
        SessionBuilder(analytics_db).with_id(session_id).with_title(
            "Null Fields"
        ).insert()

        conn = analytics_db.connect()
        conn.execute(
            """
            INSERT INTO messages (id, session_id, role, agent, tokens_input, tokens_output,
                error_name, error_data, root_path, summary_title, created_at)
            VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, CURRENT_TIMESTAMP)
            """,
            ["msg-null", session_id, "user", "main", 100, 0],
        )
        PartBuilder(analytics_db).for_session(session_id).for_message(
            "msg-null"
        ).as_text("Hello").insert()

        messages = tracing_service.get_session_messages(session_id)
        assert len(messages) >= 1
        assert "error" not in messages[0]

    def test_tool_operations_order_by_created_at(self, analytics_db, tracing_service):
        """Should return tool operations ordered by created_at ASC."""
        session_id = "sess-order"
        base_time = datetime.now()

        SessionBuilder(analytics_db).with_id(session_id).with_title(
            "Order Test"
        ).insert()

        # Insert tools with explicit timestamps
        for i, name in enumerate(["first", "second", "third"]):
            ts = base_time - timedelta(seconds=20 - i * 10)
            PartBuilder(analytics_db).with_id(f"part-{name}").for_session(
                session_id
            ).for_message("msg-001").as_tool(name, "completed").at_time(ts).insert()

        operations = tracing_service.get_session_tool_operations(session_id)
        tool_names = [op["tool_name"] for op in operations]
        assert tool_names == ["first", "second", "third"]


# =============================================================================
# API Endpoint Tests - Use shared fixtures
# =============================================================================


class TestFilePartsApiEndpoint:
    """Tests for GET /api/session/<id>/file-parts endpoint."""

    def test_file_parts_endpoint_success(
        self, sessions_client, api_mocks, mock_tracing_service
    ):
        """Should return file parts on success."""
        mock_tracing_service.get_session_file_parts.return_value = {
            "meta": {"session_id": "sess-001"},
            "summary": {"total_files": 2, "by_mime_type": []},
            "files": [{"id": "f1", "filename": "image.png"}],
        }

        with api_mocks:
            response = sessions_client.get("/api/session/sess-001/file-parts")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert len(data["data"]["files"]) == 1

    def test_file_parts_endpoint_empty_session(
        self, sessions_client, api_mocks, mock_tracing_service
    ):
        """Should return empty result for session without files."""
        mock_tracing_service.get_session_file_parts.return_value = {
            "meta": {"session_id": "sess-empty"},
            "summary": {"total_files": 0, "by_mime_type": []},
            "files": [],
        }

        with api_mocks:
            response = sessions_client.get("/api/session/sess-empty/file-parts")

        assert response.status_code == 200
        assert response.get_json()["data"]["summary"]["total_files"] == 0

    def test_file_parts_endpoint_service_error(
        self, sessions_client, api_mocks, mock_tracing_service
    ):
        """Should return 500 on service error."""
        mock_tracing_service.get_session_file_parts.side_effect = Exception(
            "Service error"
        )

        with api_mocks:
            response = sessions_client.get("/api/session/sess-001/file-parts")

        assert response.status_code == 500
        assert response.get_json()["success"] is False
