"""
Tests for new tracing features in session_queries.py.

Plan 45: Tests for new and enhanced methods:
- get_session_file_parts() - NEW: file parts with data URLs
- get_session_messages() - ENHANCED: error_name, error_data, root_path, summary_title
- get_session_tool_operations() - ENHANCED: tool_title, result_summary, cost, tokens
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from opencode_monitor.analytics.db import AnalyticsDB
from opencode_monitor.analytics.tracing import TracingDataService


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def tracing_db(tmp_path):
    """Create a fresh AnalyticsDB with tracing tables for testing."""
    db_path = tmp_path / "test_tracing.duckdb"
    db = AnalyticsDB(db_path)
    db.connect()
    yield db
    db.close()


@pytest.fixture
def service(tracing_db):
    """Create TracingDataService instance."""
    return TracingDataService(db=tracing_db)


@pytest.fixture
def populated_db(tracing_db):
    """Populate database with comprehensive test data for tracing tests."""
    conn = tracing_db.connect()

    session_id = "sess-tracing-001"

    # Insert session
    conn.execute(
        """
        INSERT INTO sessions (id, directory, title, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            session_id,
            "/home/user/project",
            "Tracing Test Session",
            datetime.now(),
            datetime.now(),
        ],
    )

    # Insert messages with new fields (error_name, error_data, root_path, summary_title)
    messages = [
        # Normal user message
        (
            "msg-001",
            session_id,
            "user",
            "main",
            100,
            0,
            None,
            None,
            "/home/user/project",
            "User asks about feature",
        ),
        # Normal assistant message with summary_title
        (
            "msg-002",
            session_id,
            "assistant",
            "executor",
            0,
            500,
            None,
            None,
            "/home/user/project",
            "Implementing the feature",
        ),
        # Error message with error fields
        (
            "msg-003",
            session_id,
            "assistant",
            "executor",
            0,
            100,
            "RateLimitError",
            '{"retry_after": 60}',
            "/home/user/project",
            None,
        ),
    ]

    for msg in messages:
        conn.execute(
            """
            INSERT INTO messages (
                id, session_id, role, agent, tokens_input, tokens_output,
                error_name, error_data, root_path, summary_title, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            list(msg),
        )

    # Insert parts with enhanced tool fields
    # Text part
    conn.execute(
        """
        INSERT INTO parts (
            id, session_id, message_id, part_type, content, created_at
        )
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        ["part-text-001", session_id, "msg-001", "text", "Please implement feature X"],
    )

    # Tool part with tool_title, result_summary, cost, tokens
    conn.execute(
        """
        INSERT INTO parts (
            id, session_id, message_id, part_type, tool_name, tool_status,
            content, arguments, duration_ms, tool_title, result_summary,
            cost, tokens_input, tokens_output, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        [
            "part-tool-001",
            session_id,
            "msg-002",
            "tool",
            "bash",
            "completed",
            "ls -la output",
            '{"command": "ls -la"}',
            150,
            "List directory contents",  # tool_title
            "Found 15 files in directory",  # result_summary
            0.0025,  # cost
            50,  # tokens_input
            100,  # tokens_output
        ],
    )

    # Tool part without optional fields (backward compatibility test)
    conn.execute(
        """
        INSERT INTO parts (
            id, session_id, message_id, part_type, tool_name, tool_status,
            content, duration_ms, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        [
            "part-tool-002",
            session_id,
            "msg-002",
            "tool",
            "read",
            "completed",
            "file content...",
            75,
        ],
    )

    # File parts (for get_session_file_parts tests)
    # PNG image
    conn.execute(
        """
        INSERT INTO parts (
            id, session_id, message_id, part_type, file_name, file_mime, 
            file_url, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        [
            "part-file-001",
            session_id,
            "msg-001",
            "file",
            "screenshot.png",
            "image/png",
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        ],
    )

    # JPEG image
    conn.execute(
        """
        INSERT INTO parts (
            id, session_id, message_id, part_type, file_name, file_mime,
            file_url, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        [
            "part-file-002",
            session_id,
            "msg-001",
            "file",
            "photo.jpg",
            "image/jpeg",
            "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAMCAgMCAgMDAwMEAwMEBQgFBQQEBQoHBwYIDAoMCwsKCwsNDhIQDQ4RDgsLEBYQERMUFRUVDA8XGBYUGBIUFRT/wAALCAABAAEBAREA/8QAFAABAAAAAAAAAAAAAAAAAAAAB//EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AN//Z",
        ],
    )

    # File without URL (edge case)
    conn.execute(
        """
        INSERT INTO parts (
            id, session_id, message_id, part_type, file_name, file_mime,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        [
            "part-file-003",
            session_id,
            "msg-001",
            "file",
            None,
            None,  # Missing filename and mime
        ],
    )

    return tracing_db, session_id


# =============================================================================
# Test get_session_file_parts()
# =============================================================================


class TestGetSessionFileParts:
    """Tests for get_session_file_parts() method."""

    def test_returns_file_parts_with_data_urls(self, populated_db):
        """Should return file parts with their base64 data URLs."""
        db, session_id = populated_db
        service = TracingDataService(db=db)

        result = service.get_session_file_parts(session_id)

        assert "meta" in result
        assert result["meta"]["session_id"] == session_id
        assert "files" in result
        assert "summary" in result

        # Should have 3 file parts
        assert len(result["files"]) == 3

    def test_file_part_contains_expected_fields(self, populated_db):
        """Should include id, message_id, filename, mime_type, timestamp."""
        db, session_id = populated_db
        service = TracingDataService(db=db)

        result = service.get_session_file_parts(session_id)
        files = result["files"]

        # Check first file (PNG)
        png_file = next(f for f in files if f.get("filename") == "screenshot.png")
        assert png_file["id"] == "part-file-001"
        assert png_file["message_id"] == "msg-001"
        assert png_file["mime_type"] == "image/png"
        assert "timestamp" in png_file
        assert "data_url" in png_file
        assert png_file["data_url"].startswith("data:image/png;base64,")

    def test_calculates_size_from_base64(self, populated_db):
        """Should calculate approximate size from base64 data URL."""
        db, session_id = populated_db
        service = TracingDataService(db=db)

        result = service.get_session_file_parts(session_id)

        # Find a file with data_url
        file_with_url = next((f for f in result["files"] if f.get("data_url")), None)
        assert file_with_url is not None
        assert "size_bytes" in file_with_url
        assert file_with_url["size_bytes"] > 0

    def test_handles_missing_file_url(self, populated_db):
        """Should handle files without data URLs gracefully."""
        db, session_id = populated_db
        service = TracingDataService(db=db)

        result = service.get_session_file_parts(session_id)

        # Find file without URL
        file_without_url = next(
            (f for f in result["files"] if f.get("filename") == "unknown"), None
        )
        assert file_without_url is not None
        assert "data_url" not in file_without_url
        assert "size_bytes" not in file_without_url

    def test_summary_contains_mime_type_counts(self, populated_db):
        """Should summarize files by MIME type."""
        db, session_id = populated_db
        service = TracingDataService(db=db)

        result = service.get_session_file_parts(session_id)
        summary = result["summary"]

        assert summary["total_files"] == 3
        assert "by_mime_type" in summary

        # Check mime type breakdown
        mime_types = {m["mime_type"]: m["count"] for m in summary["by_mime_type"]}
        assert mime_types.get("image/png") == 1
        assert mime_types.get("image/jpeg") == 1

    def test_returns_empty_for_nonexistent_session(self, tracing_db):
        """Should return empty result for non-existent session."""
        service = TracingDataService(db=tracing_db)

        result = service.get_session_file_parts("nonexistent-session")

        assert result["summary"]["total_files"] == 0
        assert result["files"] == []

    def test_handles_database_error_gracefully(self, tracing_db):
        """Should handle database errors without crashing."""
        service = TracingDataService(db=tracing_db)

        # Mock the db connection at the source
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = Exception("Database error")

        with patch.object(tracing_db, "connect", return_value=mock_conn):
            result = service.get_session_file_parts("sess-001")

            assert "error" in result["meta"]
            assert result["files"] == []


# =============================================================================
# Test get_session_messages() - Enhanced Fields
# =============================================================================


class TestGetSessionMessagesEnhanced:
    """Tests for enhanced get_session_messages() with new fields."""

    def test_returns_error_info_when_present(self, populated_db):
        """Should include error info (error_name, error_data) when present."""
        db, session_id = populated_db
        service = TracingDataService(db=db)

        messages = service.get_session_messages(session_id)

        # Find the error message
        error_msg = next((m for m in messages if m.get("error")), None)
        assert error_msg is not None
        assert error_msg["error"]["name"] == "RateLimitError"
        assert error_msg["error"]["data"] == '{"retry_after": 60}'

    def test_returns_root_path_when_present(self, populated_db):
        """Should include root_path field when present."""
        db, session_id = populated_db
        service = TracingDataService(db=db)

        messages = service.get_session_messages(session_id)

        # All messages should have root_path in our test data
        msg_with_root = next((m for m in messages if m.get("root_path")), None)
        assert msg_with_root is not None
        assert msg_with_root["root_path"] == "/home/user/project"

    def test_returns_summary_title_when_present(self, populated_db):
        """Should include summary_title (hook) when present."""
        db, session_id = populated_db
        service = TracingDataService(db=db)

        messages = service.get_session_messages(session_id)

        # Find message with summary_title
        msg_with_title = next((m for m in messages if m.get("summary_title")), None)
        assert msg_with_title is not None
        assert "summary_title" in msg_with_title

    def test_omits_error_when_not_present(self, populated_db):
        """Should not include error key when no error occurred."""
        db, session_id = populated_db
        service = TracingDataService(db=db)

        messages = service.get_session_messages(session_id)

        # Find a non-error message
        normal_msg = next((m for m in messages if m["role"] == "user"), None)
        assert normal_msg is not None
        assert "error" not in normal_msg


# =============================================================================
# Test get_session_tool_operations() - Enhanced Fields
# =============================================================================


class TestGetSessionToolOperationsEnhanced:
    """Tests for enhanced get_session_tool_operations() with new fields."""

    def test_returns_tool_title_when_present(self, populated_db):
        """Should include title (from tool_title) when present."""
        db, session_id = populated_db
        service = TracingDataService(db=db)

        operations = service.get_session_tool_operations(session_id)

        # Find tool with title
        tool_with_title = next((op for op in operations if op.get("title")), None)
        assert tool_with_title is not None
        assert tool_with_title["title"] == "List directory contents"

    def test_returns_result_summary_when_present(self, populated_db):
        """Should include result_summary when present."""
        db, session_id = populated_db
        service = TracingDataService(db=db)

        operations = service.get_session_tool_operations(session_id)

        # Find tool with result_summary
        tool_with_summary = next(
            (op for op in operations if op.get("result_summary")), None
        )
        assert tool_with_summary is not None
        assert tool_with_summary["result_summary"] == "Found 15 files in directory"

    def test_returns_cost_when_present(self, populated_db):
        """Should include cost when present."""
        db, session_id = populated_db
        service = TracingDataService(db=db)

        operations = service.get_session_tool_operations(session_id)

        # Find tool with cost
        tool_with_cost = next((op for op in operations if op.get("cost")), None)
        assert tool_with_cost is not None
        assert tool_with_cost["cost"] == 0.0025

    def test_returns_tokens_when_present(self, populated_db):
        """Should include tokens object (input, output) when present."""
        db, session_id = populated_db
        service = TracingDataService(db=db)

        operations = service.get_session_tool_operations(session_id)

        # Find tool with tokens
        tool_with_tokens = next((op for op in operations if op.get("tokens")), None)
        assert tool_with_tokens is not None
        assert tool_with_tokens["tokens"]["input"] == 50
        assert tool_with_tokens["tokens"]["output"] == 100

    def test_omits_optional_fields_when_not_present(self, populated_db):
        """Should not include optional fields when they're not set."""
        db, session_id = populated_db
        service = TracingDataService(db=db)

        operations = service.get_session_tool_operations(session_id)

        # Find tool without optional fields (read tool)
        basic_tool = next((op for op in operations if op["tool_name"] == "read"), None)
        assert basic_tool is not None
        # Optional fields should not be present
        assert "title" not in basic_tool
        assert "result_summary" not in basic_tool
        assert "cost" not in basic_tool
        assert "tokens" not in basic_tool

    def test_returns_standard_fields(self, populated_db):
        """Should always include standard fields."""
        db, session_id = populated_db
        service = TracingDataService(db=db)

        operations = service.get_session_tool_operations(session_id)

        for op in operations:
            assert "id" in op
            assert "tool_name" in op
            assert "status" in op
            assert "display_info" in op
            assert "timestamp" in op
            assert "duration_ms" in op


# =============================================================================
# Test Edge Cases and Error Handling
# =============================================================================


class TestSessionQueriesEdgeCases:
    """Test edge cases and error handling."""

    def test_file_parts_with_empty_session(self, tracing_db):
        """Should handle session with no file parts."""
        conn = tracing_db.connect()

        # Create session without file parts
        conn.execute(
            """
            INSERT INTO sessions (id, directory, title, created_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            ["sess-empty", "/path", "Empty Session"],
        )

        service = TracingDataService(db=tracing_db)
        result = service.get_session_file_parts("sess-empty")

        assert result["summary"]["total_files"] == 0
        assert result["files"] == []
        assert result["summary"]["by_mime_type"] == []

    def test_messages_with_null_optional_fields(self, tracing_db):
        """Should handle messages where optional fields are NULL."""
        conn = tracing_db.connect()

        session_id = "sess-null-fields"

        # Create session
        conn.execute(
            """
            INSERT INTO sessions (id, directory, title, created_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            [session_id, "/path", "Null Fields Session"],
        )

        # Create message with all optional fields NULL
        conn.execute(
            """
            INSERT INTO messages (
                id, session_id, role, agent, tokens_input, tokens_output,
                error_name, error_data, root_path, summary_title, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, CURRENT_TIMESTAMP)
            """,
            ["msg-null", session_id, "user", "main", 100, 0],
        )

        # Create a text part
        conn.execute(
            """
            INSERT INTO parts (id, session_id, message_id, part_type, content, created_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            ["part-null", session_id, "msg-null", "text", "Hello"],
        )

        service = TracingDataService(db=tracing_db)
        messages = service.get_session_messages(session_id)

        assert len(messages) >= 1
        msg = messages[0]
        assert "error" not in msg
        assert "root_path" not in msg or msg.get("root_path") is None
        assert "summary_title" not in msg or msg.get("summary_title") is None

    def test_tool_operations_order_by_created_at(self, tracing_db):
        """Should return tool operations ordered by created_at ASC."""
        from datetime import timedelta

        conn = tracing_db.connect()

        session_id = "sess-order"
        base_time = datetime.now()

        conn.execute(
            """
            INSERT INTO sessions (id, directory, title, created_at)
            VALUES (?, ?, ?, ?)
            """,
            [session_id, "/path", "Order Test", base_time],
        )

        # Insert tools with explicit timestamps (oldest first)
        tools_with_times = [
            ("first", base_time - timedelta(seconds=20)),
            ("second", base_time - timedelta(seconds=10)),
            ("third", base_time),
        ]

        for tool, ts in tools_with_times:
            conn.execute(
                """
                INSERT INTO parts (
                    id, session_id, message_id, part_type, tool_name, tool_status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [f"part-{tool}", session_id, "msg-001", "tool", tool, "completed", ts],
            )

        service = TracingDataService(db=tracing_db)
        operations = service.get_session_tool_operations(session_id)

        # Should be ordered by timestamp ascending (first, second, third)
        tool_names = [op["tool_name"] for op in operations]
        assert tool_names == ["first", "second", "third"]


# =============================================================================
# API Endpoint Tests
# =============================================================================


class TestFilePartsApiEndpoint:
    """Tests for GET /api/session/<id>/file-parts endpoint."""

    @pytest.fixture
    def app(self):
        """Create test Flask app with sessions blueprint."""
        from flask import Flask
        from opencode_monitor.api.routes.sessions import sessions_bp

        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(sessions_bp)
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return app.test_client()

    @pytest.fixture
    def mock_service(self):
        """Create mock tracing service."""
        return MagicMock()

    def test_file_parts_endpoint_success(self, client, mock_service):
        """Should return file parts on success."""
        mock_service.get_session_file_parts.return_value = {
            "meta": {"session_id": "sess-001"},
            "summary": {"total_files": 2, "by_mime_type": []},
            "files": [
                {"id": "f1", "filename": "image.png", "mime_type": "image/png"},
                {"id": "f2", "filename": "photo.jpg", "mime_type": "image/jpeg"},
            ],
        }

        with (
            patch("opencode_monitor.api.routes.sessions.get_db_lock") as mock_lock,
            patch(
                "opencode_monitor.api.routes.sessions.get_service",
                return_value=mock_service,
            ),
        ):
            mock_lock.return_value.__enter__ = MagicMock()
            mock_lock.return_value.__exit__ = MagicMock()

            response = client.get("/api/session/sess-001/file-parts")

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert len(data["data"]["files"]) == 2

    def test_file_parts_endpoint_empty_session(self, client, mock_service):
        """Should return empty result for session without files."""
        mock_service.get_session_file_parts.return_value = {
            "meta": {"session_id": "sess-empty"},
            "summary": {"total_files": 0, "by_mime_type": []},
            "files": [],
        }

        with (
            patch("opencode_monitor.api.routes.sessions.get_db_lock") as mock_lock,
            patch(
                "opencode_monitor.api.routes.sessions.get_service",
                return_value=mock_service,
            ),
        ):
            mock_lock.return_value.__enter__ = MagicMock()
            mock_lock.return_value.__exit__ = MagicMock()

            response = client.get("/api/session/sess-empty/file-parts")

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert data["data"]["summary"]["total_files"] == 0

    def test_file_parts_endpoint_service_error(self, client, mock_service):
        """Should return 500 on service error."""
        mock_service.get_session_file_parts.side_effect = Exception("Service error")

        with (
            patch("opencode_monitor.api.routes.sessions.get_db_lock") as mock_lock,
            patch(
                "opencode_monitor.api.routes.sessions.get_service",
                return_value=mock_service,
            ),
        ):
            mock_lock.return_value.__enter__ = MagicMock()
            mock_lock.return_value.__exit__ = MagicMock()

            response = client.get("/api/session/sess-001/file-parts")

            assert response.status_code == 500
            data = response.get_json()
            assert data["success"] is False
            assert "error" in data
