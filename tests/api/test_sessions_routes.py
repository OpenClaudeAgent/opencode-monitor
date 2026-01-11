"""
Tests for API sessions routes - including error handling.

Covers:
- Valid request handling
- Invalid inputs / boundary values
- Error response format
- Database error handling

LEGACY: These tests use mocks. Migrated to tests/integration/api/ with real Flask app.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from opencode_monitor.api.routes.sessions import sessions_bp

pytestmark = pytest.mark.legacy


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def app():
    """Create test Flask app with sessions blueprint."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(sessions_bp)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def mock_db():
    """Create mock database."""
    mock = MagicMock()
    mock.connect.return_value = mock
    return mock


@pytest.fixture
def mock_service():
    """Create mock tracing service."""
    return MagicMock()


# =============================================================================
# /api/sessions Tests
# =============================================================================


class TestGetSessions:
    """Tests for GET /api/sessions endpoint."""

    def test_get_sessions_success(self, client, mock_db):
        """Should return sessions list on success."""
        # Mock database response
        mock_db.execute.return_value.fetchall.return_value = [
            ("sess-001", "Title 1", "/dir1", datetime.now(), datetime.now()),
            ("sess-002", "Title 2", "/dir2", datetime.now(), datetime.now()),
        ]

        with (
            patch("opencode_monitor.api.routes.sessions.get_db_lock") as mock_lock,
            patch(
                "opencode_monitor.api.routes.sessions.get_analytics_db",
                return_value=mock_db,
            ),
        ):
            mock_lock.return_value.__enter__ = MagicMock()
            mock_lock.return_value.__exit__ = MagicMock()

            response = client.get("/api/sessions")

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert len(data["data"]) == 2
            assert data["data"][0]["id"] == "sess-001"

    @pytest.mark.parametrize(
        "days,limit,expected_days,expected_limit",
        [
            (None, None, 30, 100),  # Defaults
            ("7", None, 7, 100),  # Custom days
            (None, "50", 30, 50),  # Custom limit
            ("14", "25", 14, 25),  # Both custom
        ],
    )
    def test_get_sessions_respects_query_params(
        self, client, mock_db, days, limit, expected_days, expected_limit
    ):
        """Should respect days and limit query parameters."""
        mock_db.execute.return_value.fetchall.return_value = []

        with (
            patch("opencode_monitor.api.routes.sessions.get_db_lock") as mock_lock,
            patch(
                "opencode_monitor.api.routes.sessions.get_analytics_db",
                return_value=mock_db,
            ),
        ):
            mock_lock.return_value.__enter__ = MagicMock()
            mock_lock.return_value.__exit__ = MagicMock()

            params = {}
            if days:
                params["days"] = days
            if limit:
                params["limit"] = limit

            response = client.get("/api/sessions", query_string=params)

            assert response.status_code == 200
            # Verify the execute was called with correct limit
            call_args = mock_db.execute.call_args[0]
            assert call_args[1][1] == expected_limit

    def test_get_sessions_database_error_returns_500(self, client):
        """Should return 500 on database error."""
        with (
            patch("opencode_monitor.api.routes.sessions.get_db_lock") as mock_lock,
            patch(
                "opencode_monitor.api.routes.sessions.get_analytics_db",
                side_effect=Exception("DB connection failed"),
            ),
        ):
            mock_lock.return_value.__enter__ = MagicMock()
            mock_lock.return_value.__exit__ = MagicMock()

            response = client.get("/api/sessions")

            assert response.status_code == 500
            data = response.get_json()
            assert data["success"] is False
            assert "error" in data
            # Error message may vary depending on where exception is caught


# =============================================================================
# /api/session/<id>/summary Tests
# =============================================================================


class TestGetSessionSummary:
    """Tests for GET /api/session/<id>/summary endpoint."""

    def test_get_session_summary_success(self, client, mock_service):
        """Should return session summary on success."""
        mock_service.get_session_summary.return_value = {
            "id": "sess-001",
            "title": "Test Session",
            "tokens_in": 1000,
            "tokens_out": 500,
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

            response = client.get("/api/session/sess-001/summary")

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert data["data"]["id"] == "sess-001"

    def test_get_session_summary_not_found(self, client, mock_service):
        """Should handle session not found gracefully."""
        mock_service.get_session_summary.return_value = None

        with (
            patch("opencode_monitor.api.routes.sessions.get_db_lock") as mock_lock,
            patch(
                "opencode_monitor.api.routes.sessions.get_service",
                return_value=mock_service,
            ),
        ):
            mock_lock.return_value.__enter__ = MagicMock()
            mock_lock.return_value.__exit__ = MagicMock()

            response = client.get("/api/session/nonexistent/summary")

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert data["data"] is None

    def test_get_session_summary_service_error_returns_500(self, client, mock_service):
        """Should return 500 on service error."""
        mock_service.get_session_summary.side_effect = Exception("Service error")

        with (
            patch("opencode_monitor.api.routes.sessions.get_db_lock") as mock_lock,
            patch(
                "opencode_monitor.api.routes.sessions.get_service",
                return_value=mock_service,
            ),
        ):
            mock_lock.return_value.__enter__ = MagicMock()
            mock_lock.return_value.__exit__ = MagicMock()

            response = client.get("/api/session/sess-001/summary")

            assert response.status_code == 500
            data = response.get_json()
            assert data["success"] is False
            assert "error" in data


# =============================================================================
# /api/session/<id>/tokens Tests
# =============================================================================


class TestGetSessionTokens:
    """Tests for GET /api/session/<id>/tokens endpoint."""

    def test_get_session_tokens_success(self, client, mock_service):
        """Should return token breakdown on success."""
        mock_service.get_session_tokens.return_value = {
            "total_in": 5000,
            "total_out": 2500,
            "by_agent": [{"agent": "executor", "in": 3000, "out": 1500}],
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

            response = client.get("/api/session/sess-001/tokens")

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert data["data"]["total_in"] == 5000

    def test_get_session_tokens_error_returns_500(self, client, mock_service):
        """Should return 500 on error."""
        mock_service.get_session_tokens.side_effect = RuntimeError("Query failed")

        with (
            patch("opencode_monitor.api.routes.sessions.get_db_lock") as mock_lock,
            patch(
                "opencode_monitor.api.routes.sessions.get_service",
                return_value=mock_service,
            ),
        ):
            mock_lock.return_value.__enter__ = MagicMock()
            mock_lock.return_value.__exit__ = MagicMock()

            response = client.get("/api/session/sess-001/tokens")

            assert response.status_code == 500
            data = response.get_json()
            assert data["success"] is False


# =============================================================================
# /api/session/<id>/tools Tests
# =============================================================================


class TestGetSessionTools:
    """Tests for GET /api/session/<id>/tools endpoint."""

    def test_get_session_tools_success(self, client, mock_service):
        """Should return tools list on success."""
        mock_service.get_session_tools.return_value = [
            {"tool": "bash", "count": 10, "errors": 1},
            {"tool": "read", "count": 5, "errors": 0},
        ]

        with (
            patch("opencode_monitor.api.routes.sessions.get_db_lock") as mock_lock,
            patch(
                "opencode_monitor.api.routes.sessions.get_service",
                return_value=mock_service,
            ),
        ):
            mock_lock.return_value.__enter__ = MagicMock()
            mock_lock.return_value.__exit__ = MagicMock()

            response = client.get("/api/session/sess-001/tools")

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert len(data["data"]) == 2


# =============================================================================
# /api/session/<id>/files Tests
# =============================================================================


class TestGetSessionFiles:
    """Tests for GET /api/session/<id>/files endpoint."""

    def test_get_session_files_success(self, client, mock_service):
        """Should return files list on success."""
        mock_service.get_session_files.return_value = [
            {"path": "/src/main.py", "reads": 5, "writes": 2},
        ]

        with (
            patch("opencode_monitor.api.routes.sessions.get_db_lock") as mock_lock,
            patch(
                "opencode_monitor.api.routes.sessions.get_service",
                return_value=mock_service,
            ),
        ):
            mock_lock.return_value.__enter__ = MagicMock()
            mock_lock.return_value.__exit__ = MagicMock()

            response = client.get("/api/session/sess-001/files")

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True


# =============================================================================
# /api/session/<id>/agents Tests
# =============================================================================


class TestGetSessionAgents:
    """Tests for GET /api/session/<id>/agents endpoint."""

    def test_get_session_agents_success(self, client, mock_service):
        """Should return agents list on success."""
        mock_service.get_session_agents.return_value = [
            {"agent": "executor", "messages": 10},
            {"agent": "tester", "messages": 5},
        ]

        with (
            patch("opencode_monitor.api.routes.sessions.get_db_lock") as mock_lock,
            patch(
                "opencode_monitor.api.routes.sessions.get_service",
                return_value=mock_service,
            ),
        ):
            mock_lock.return_value.__enter__ = MagicMock()
            mock_lock.return_value.__exit__ = MagicMock()

            response = client.get("/api/session/sess-001/agents")

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True


# =============================================================================
# /api/session/<id>/timeline Tests
# =============================================================================


class TestGetSessionTimeline:
    """Tests for GET /api/session/<id>/timeline endpoint."""

    def test_get_session_timeline_success(self, client, mock_service):
        """Should return timeline events on success."""
        mock_service.get_session_timeline.return_value = [
            {"type": "message", "timestamp": "2024-01-01T12:00:00"},
            {"type": "tool", "timestamp": "2024-01-01T12:01:00"},
        ]

        with (
            patch("opencode_monitor.api.routes.sessions.get_db_lock") as mock_lock,
            patch(
                "opencode_monitor.api.routes.sessions.get_service",
                return_value=mock_service,
            ),
        ):
            mock_lock.return_value.__enter__ = MagicMock()
            mock_lock.return_value.__exit__ = MagicMock()

            response = client.get("/api/session/sess-001/timeline")

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert len(data["data"]) == 2


# =============================================================================
# /api/session/<id>/prompts Tests
# =============================================================================


class TestGetSessionPrompts:
    """Tests for GET /api/session/<id>/prompts endpoint."""

    def test_get_session_prompts_success(self, client, mock_service):
        """Should return prompts on success."""
        mock_service.get_session_prompts.return_value = {
            "first_prompt": "What is X?",
            "last_response": "X is Y.",
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

            response = client.get("/api/session/sess-001/prompts")

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True


# =============================================================================
# /api/session/<id>/messages Tests
# =============================================================================


class TestGetSessionMessages:
    """Tests for GET /api/session/<id>/messages endpoint."""

    def test_get_session_messages_success(self, client, mock_service):
        """Should return messages on success."""
        mock_service.get_session_messages.return_value = [
            {"id": "msg-001", "role": "user", "content": "Hello"},
            {"id": "msg-002", "role": "assistant", "content": "Hi there"},
        ]

        with (
            patch("opencode_monitor.api.routes.sessions.get_db_lock") as mock_lock,
            patch(
                "opencode_monitor.api.routes.sessions.get_service",
                return_value=mock_service,
            ),
        ):
            mock_lock.return_value.__enter__ = MagicMock()
            mock_lock.return_value.__exit__ = MagicMock()

            response = client.get("/api/session/sess-001/messages")

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert len(data["data"]) == 2


# =============================================================================
# Error Response Format Tests
# =============================================================================


class TestErrorResponseFormat:
    """Tests for consistent error response format."""

    @pytest.mark.parametrize(
        "endpoint",
        [
            "/api/session/test/summary",
            "/api/session/test/tokens",
            "/api/session/test/tools",
            "/api/session/test/files",
            "/api/session/test/agents",
            "/api/session/test/timeline",
            "/api/session/test/prompts",
            "/api/session/test/messages",
            # Plan 34: Enriched Parts Endpoints
            "/api/session/test/reasoning",
            "/api/session/test/steps",
            "/api/session/test/git-history",
            "/api/session/test/file-parts",
            "/api/session/test/precise-cost",
            # Plan 45: Timeline & Aggregation Endpoints
            "/api/session/test/exchanges",
            "/api/session/test/delegations",
        ],
    )
    def test_all_endpoints_return_consistent_error_format(self, client, endpoint):
        """All endpoints should return consistent error response format."""
        with (
            patch("opencode_monitor.api.routes.sessions.get_db_lock") as mock_lock,
            patch(
                "opencode_monitor.api.routes.sessions.get_service",
                side_effect=Exception("Test error"),
            ),
        ):
            mock_lock.return_value.__enter__ = MagicMock()
            mock_lock.return_value.__exit__ = MagicMock()

            response = client.get(endpoint)

            assert response.status_code == 500
            data = response.get_json()
            assert "success" in data
            assert data["success"] is False
            assert "error" in data
            assert isinstance(data["error"], str)
