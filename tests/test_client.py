"""
Tests for async HTTP client module.

Tests cover all functions in client.py:
- _clean_json: JSON sanitization
- _sync_get: Synchronous HTTP GET
- _sync_get_json: Synchronous HTTP GET with JSON parsing
- get: Async HTTP GET
- get_json: Async HTTP GET with JSON parsing
- check_opencode_port: OpenCode port detection
- parallel_requests: Parallel HTTP requests
- OpenCodeClient: Full API client
"""

import asyncio
import json
from unittest.mock import patch, MagicMock

import pytest

from opencode_monitor.core.client import (
    _clean_json,
    _sync_get,
    _sync_get_json,
    get,
    get_json,
    check_opencode_port,
    parallel_requests,
    OpenCodeClient,
    REQUEST_TIMEOUT,
)


# Use conftest.run_async helper
def run_async(coro):
    """Helper to run async coroutines in tests"""
    return asyncio.run(coro)


# =====================================================
# _clean_json Tests
# =====================================================


class TestCleanJson:
    """Tests for JSON cleaning function"""

    @pytest.mark.parametrize(
        "raw,should_not_contain",
        [
            ('{"key": "value\x00\x08\x0b"}', ["\x00", "\x08", "\x0b"]),
        ],
    )
    def test_clean_json_removes_control_chars(self, raw, should_not_contain):
        """Control characters are replaced with spaces."""
        result = _clean_json(raw)
        for char in should_not_contain:
            assert char not in result
        assert "key" in result
        assert "value" in result

    @pytest.mark.parametrize(
        "raw",
        [
            '{"name": "test", "value": 123}',
            '{\n\t"key": "value"\n}',
            "",
        ],
    )
    def test_clean_json_preserves_valid_content(self, raw):
        """Valid JSON and empty strings are handled correctly."""
        result = _clean_json(raw)
        if raw:
            assert "key" in result or "name" in result
            if "\n" in raw:
                assert "\n" in result
            if "\t" in raw:
                assert "\t" in result
        else:
            assert result == ""


# =====================================================
# _sync_get Tests
# =====================================================


class TestSyncGet:
    """Tests for synchronous HTTP GET function"""

    @patch("opencode_monitor.core.client.urllib.request.urlopen")
    @patch("opencode_monitor.core.client.urllib.request.Request")
    def test_sync_get_success(self, mock_request, mock_urlopen):
        """Successful GET returns response body"""
        mock_response = MagicMock()
        mock_response.read.return_value = b"response body"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = _sync_get("http://example.com/api")

        assert result == "response body"
        mock_request.assert_called_once_with("http://example.com/api")

    @patch("opencode_monitor.core.client.urllib.request.urlopen")
    @patch("opencode_monitor.core.client.urllib.request.Request")
    def test_sync_get_url_error_returns_none(self, mock_request, mock_urlopen):
        """URLError returns None"""
        import urllib.error

        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        result = _sync_get("http://localhost:9999/api")

        assert result is None

    @patch("opencode_monitor.core.client.urllib.request.urlopen")
    @patch("opencode_monitor.core.client.urllib.request.Request")
    def test_sync_get_generic_exception_returns_none(self, mock_request, mock_urlopen):
        """Generic exception returns None"""
        mock_urlopen.side_effect = Exception("Unexpected error")

        result = _sync_get("http://example.com/api")

        assert result is None

    @patch("opencode_monitor.core.client.urllib.request.urlopen")
    @patch("opencode_monitor.core.client.urllib.request.Request")
    def test_sync_get_uses_custom_timeout(self, mock_request, mock_urlopen):
        """Custom timeout is passed to urlopen"""
        mock_response = MagicMock()
        mock_response.read.return_value = b"data"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        _sync_get("http://example.com/api", timeout=5.0)

        mock_urlopen.assert_called_once()
        call_kwargs = mock_urlopen.call_args
        assert call_kwargs[1]["timeout"] == 5.0


# =====================================================
# _sync_get_json Tests
# =====================================================


class TestSyncGetJson:
    """Tests for synchronous HTTP GET with JSON parsing"""

    @patch("opencode_monitor.core.client._sync_get")
    def test_sync_get_json_success(self, mock_sync_get):
        """Valid JSON response is parsed correctly"""
        mock_sync_get.return_value = '{"status": "ok", "count": 42}'

        result = _sync_get_json("http://example.com/api")

        assert result == {"status": "ok", "count": 42}

    @patch("opencode_monitor.core.client._sync_get")
    def test_sync_get_json_null_response_returns_none(self, mock_sync_get):
        """None response from _sync_get returns None"""
        mock_sync_get.return_value = None

        result = _sync_get_json("http://example.com/api")

        assert result is None

    @patch("opencode_monitor.core.client._sync_get")
    def test_sync_get_json_invalid_json_returns_none(self, mock_sync_get):
        """Invalid JSON returns None"""
        mock_sync_get.return_value = "not valid json {"

        result = _sync_get_json("http://example.com/api")

        assert result is None

    @patch("opencode_monitor.core.client._sync_get")
    def test_sync_get_json_cleans_control_chars(self, mock_sync_get):
        """Control characters are cleaned before parsing"""
        mock_sync_get.return_value = '{"key": "value\x00"}'

        result = _sync_get_json("http://example.com/api")

        assert result == {"key": "value "}

    @patch("opencode_monitor.core.client._sync_get")
    def test_sync_get_json_uses_custom_timeout(self, mock_sync_get):
        """Custom timeout is passed through"""
        mock_sync_get.return_value = "{}"

        _sync_get_json("http://example.com/api", timeout=10.0)

        mock_sync_get.assert_called_once_with("http://example.com/api", 10.0)


# =====================================================
# Async get Tests
# =====================================================


class TestAsyncGet:
    """Tests for async HTTP GET function"""

    @patch("opencode_monitor.core.client._sync_get")
    def test_get_returns_response(self, mock_sync_get):
        """Async get returns the response from _sync_get"""
        mock_sync_get.return_value = "response data"

        result = run_async(get("http://example.com/api"))

        assert result == "response data"

    @patch("opencode_monitor.core.client._sync_get")
    def test_get_returns_none_on_error(self, mock_sync_get):
        """Async get returns None when _sync_get fails"""
        mock_sync_get.return_value = None

        result = run_async(get("http://example.com/api"))

        assert result is None

    @patch("opencode_monitor.core.client._sync_get")
    def test_get_passes_timeout(self, mock_sync_get):
        """Async get passes timeout to _sync_get"""
        mock_sync_get.return_value = "data"

        run_async(get("http://example.com/api", timeout=3.0))

        mock_sync_get.assert_called_once_with("http://example.com/api", 3.0)


# =====================================================
# Async get_json Tests
# =====================================================


class TestAsyncGetJson:
    """Tests for async HTTP GET with JSON parsing"""

    @patch("opencode_monitor.core.client._sync_get_json")
    def test_get_json_returns_parsed_data(self, mock_sync_get_json):
        """Async get_json returns parsed JSON"""
        mock_sync_get_json.return_value = {"key": "value"}

        result = run_async(get_json("http://example.com/api"))

        assert result == {"key": "value"}

    @patch("opencode_monitor.core.client._sync_get_json")
    def test_get_json_returns_none_on_error(self, mock_sync_get_json):
        """Async get_json returns None on error"""
        mock_sync_get_json.return_value = None

        result = run_async(get_json("http://example.com/api"))

        assert result is None

    @patch("opencode_monitor.core.client._sync_get_json")
    def test_get_json_passes_timeout(self, mock_sync_get_json):
        """Async get_json passes timeout through"""
        mock_sync_get_json.return_value = {}

        run_async(get_json("http://example.com/api", timeout=5.0))

        mock_sync_get_json.assert_called_once_with("http://example.com/api", 5.0)


# =====================================================
# check_opencode_port Tests
# =====================================================


class TestCheckOpencodePort:
    """Tests for OpenCode port detection"""

    @pytest.mark.parametrize(
        "response,expected,description",
        [
            ("{}", True, "Empty object is OpenCode"),
            (
                '{"ses_abc123": {"status": "idle"}}',
                True,
                "Session response is OpenCode",
            ),
            (None, False, "None response is not OpenCode"),
            ('{"error": "not opencode"}', False, "Unexpected response is not OpenCode"),
        ],
    )
    @patch("opencode_monitor.core.client.get")
    def test_check_port_responses(self, mock_get, response, expected, description):
        """Port check based on response type."""
        mock_get.return_value = response
        result = run_async(check_opencode_port(8080))
        assert result is expected, description

    @patch("opencode_monitor.core.client.get")
    def test_check_port_calls_correct_url(self, mock_get):
        """Check port calls correct endpoint."""
        mock_get.return_value = "{}"
        run_async(check_opencode_port(8080))
        mock_get.assert_called_once_with(
            "http://127.0.0.1:8080/session/status", timeout=0.5
        )

    @patch("opencode_monitor.core.client.get")
    def test_check_port_exception_returns_false(self, mock_get):
        """Exception during check returns False."""
        mock_get.side_effect = Exception("Network error")
        result = run_async(check_opencode_port(8080))
        assert result is False


# =====================================================
# parallel_requests Tests
# =====================================================


class TestParallelRequests:
    """Tests for parallel HTTP requests"""

    @patch("opencode_monitor.core.client.get_json")
    def test_parallel_requests_returns_all_results(self, mock_get_json):
        """All results are returned in order"""
        mock_get_json.side_effect = [
            {"id": 1},
            {"id": 2},
            {"id": 3},
        ]

        urls = [
            "http://example.com/1",
            "http://example.com/2",
            "http://example.com/3",
        ]
        results = run_async(parallel_requests(urls))

        assert len(results) == 3
        assert results[0] == {"id": 1}
        assert results[1] == {"id": 2}
        assert results[2] == {"id": 3}

    @patch("opencode_monitor.core.client.get_json")
    def test_parallel_requests_handles_mixed_results(self, mock_get_json):
        """Mix of success and failure is handled"""
        mock_get_json.side_effect = [
            {"id": 1},
            None,  # Failed request
            {"id": 3},
        ]

        urls = ["http://example.com/1", "http://fail.com", "http://example.com/3"]
        results = run_async(parallel_requests(urls))

        assert results[0] == {"id": 1}
        assert results[1] is None
        assert results[2] == {"id": 3}

    @patch("opencode_monitor.core.client.get_json")
    def test_parallel_requests_empty_list(self, mock_get_json):
        """Empty URL list returns empty results"""
        results = run_async(parallel_requests([]))

        assert results == []
        mock_get_json.assert_not_called()

    @patch("opencode_monitor.core.client.get_json")
    def test_parallel_requests_custom_timeout(self, mock_get_json):
        """Custom timeout is passed to all requests"""
        mock_get_json.return_value = {}

        urls = ["http://example.com/1", "http://example.com/2"]
        run_async(parallel_requests(urls, timeout=5.0))

        # Verify timeout was passed to each call
        assert mock_get_json.call_count == 2
        for call in mock_get_json.call_args_list:
            assert call[0][1] == 5.0  # timeout argument


# =====================================================
# OpenCodeClient Tests
# =====================================================


class TestOpenCodeClientInit:
    """Tests for OpenCodeClient initialization"""

    def test_init_sets_port(self):
        """Client stores the port"""
        client = OpenCodeClient(port=8080)

        assert client.port == 8080

    def test_init_sets_base_url(self):
        """Client constructs correct base URL"""
        client = OpenCodeClient(port=9000)

        assert client.base_url == "http://127.0.0.1:9000"


class TestOpenCodeClientMethods:
    """Tests for OpenCodeClient API methods"""

    @pytest.fixture
    def client(self):
        """Create a test client"""
        return OpenCodeClient(port=8080)

    @patch("opencode_monitor.core.client.get_json")
    def test_get_status(self, mock_get_json, client):
        """get_status calls correct endpoint"""
        mock_get_json.return_value = {"ses_123": {"status": "busy"}}

        result = run_async(client.get_status())

        assert result == {"ses_123": {"status": "busy"}}
        mock_get_json.assert_called_once_with("http://127.0.0.1:8080/session/status")

    @patch("opencode_monitor.core.client.get_json")
    def test_get_all_sessions(self, mock_get_json, client):
        """get_all_sessions calls correct endpoint"""
        mock_get_json.return_value = [{"id": "ses_1"}, {"id": "ses_2"}]

        result = run_async(client.get_all_sessions())

        assert len(result) == 2
        mock_get_json.assert_called_once_with("http://127.0.0.1:8080/session")

    @patch("opencode_monitor.core.client.get_json")
    def test_get_session_info(self, mock_get_json, client):
        """get_session_info calls correct endpoint with session ID"""
        mock_get_json.return_value = {"id": "ses_abc", "path": "/project"}

        result = run_async(client.get_session_info("ses_abc"))

        assert result["id"] == "ses_abc"
        mock_get_json.assert_called_once_with("http://127.0.0.1:8080/session/ses_abc")

    @patch("opencode_monitor.core.client.get_json")
    def test_get_session_messages(self, mock_get_json, client):
        """get_session_messages calls correct endpoint with limit"""
        mock_get_json.return_value = [{"role": "assistant", "content": "Hello"}]

        result = run_async(client.get_session_messages("ses_abc", limit=5))

        assert len(result) == 1
        mock_get_json.assert_called_once_with(
            "http://127.0.0.1:8080/session/ses_abc/message?limit=5"
        )

    @patch("opencode_monitor.core.client.get_json")
    def test_get_session_messages_default_limit(self, mock_get_json, client):
        """get_session_messages uses default limit of 1"""
        mock_get_json.return_value = []

        run_async(client.get_session_messages("ses_abc"))

        mock_get_json.assert_called_once_with(
            "http://127.0.0.1:8080/session/ses_abc/message?limit=1"
        )

    @patch("opencode_monitor.core.client.get_json")
    def test_get_session_todos(self, mock_get_json, client):
        """get_session_todos calls correct endpoint"""
        mock_get_json.return_value = [{"id": "todo_1", "content": "Fix bug"}]

        result = run_async(client.get_session_todos("ses_abc"))

        assert len(result) == 1
        mock_get_json.assert_called_once_with(
            "http://127.0.0.1:8080/session/ses_abc/todo"
        )

    @patch("opencode_monitor.core.client.get_json")
    def test_fetch_session_data_aggregates_all(self, mock_get_json, client):
        """fetch_session_data aggregates info, messages, and todos"""
        mock_get_json.side_effect = [
            {"id": "ses_abc", "path": "/project"},  # info
            [{"role": "user", "content": "Hello"}],  # messages
            [{"id": "todo_1"}],  # todos
        ]

        result = run_async(client.fetch_session_data("ses_abc"))

        assert result["info"] == {"id": "ses_abc", "path": "/project"}
        assert result["messages"] == [{"role": "user", "content": "Hello"}]
        assert result["todos"] == [{"id": "todo_1"}]

    @patch("opencode_monitor.core.client.get_json")
    def test_fetch_session_data_handles_partial_failure(self, mock_get_json, client):
        """fetch_session_data handles partial API failures"""
        mock_get_json.side_effect = [
            {"id": "ses_abc"},  # info succeeds
            None,  # messages fail
            None,  # todos fail
        ]

        result = run_async(client.fetch_session_data("ses_abc"))

        assert result["info"] == {"id": "ses_abc"}
        assert result["messages"] is None
        assert result["todos"] is None


# =====================================================
# Constants Tests
# =====================================================


class TestConstants:
    """Tests for module constants"""

    def test_request_timeout_value(self):
        """REQUEST_TIMEOUT has expected default value"""
        assert REQUEST_TIMEOUT == 2
