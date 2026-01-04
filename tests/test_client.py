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


def run_async(coro):
    """Helper to run async coroutines in tests."""
    return asyncio.run(coro)


# =====================================================
# JSON Cleaning Tests
# =====================================================


class TestCleanJson:
    """Tests for JSON cleaning function."""

    @pytest.mark.parametrize(
        "raw,expected_chars_removed,expected_chars_kept",
        [
            # Control chars removed, content preserved
            (
                '{"key": "value\x00\x08\x0b"}',
                ["\x00", "\x08", "\x0b"],
                ["key", "value"],
            ),
            # Valid JSON with newlines/tabs preserved
            ('{\n\t"key": "value"\n}', [], ["\n", "\t", "key", "value"]),
            # Empty string unchanged
            ("", [], []),
        ],
        ids=["control_chars", "valid_json_preserved", "empty_string"],
    )
    def test_clean_json_behavior(
        self, raw, expected_chars_removed, expected_chars_kept
    ):
        """Control characters removed, valid content preserved."""
        result = _clean_json(raw)

        for char in expected_chars_removed:
            assert char not in result
        for char in expected_chars_kept:
            assert char in result or result == ""


# =====================================================
# Sync HTTP Tests
# =====================================================


class TestSyncGet:
    """Tests for synchronous HTTP GET function."""

    @pytest.mark.parametrize(
        "response_data,exception,expected_result",
        [
            (b"response body", None, "response body"),
            (None, Exception("URLError"), None),
            (None, Exception("Generic error"), None),
        ],
        ids=["success", "url_error", "generic_error"],
    )
    @patch("opencode_monitor.core.client.urllib.request.urlopen")
    @patch("opencode_monitor.core.client.urllib.request.Request")
    def test_sync_get_responses(
        self, mock_request, mock_urlopen, response_data, exception, expected_result
    ):
        """Sync GET handles success and various error conditions."""
        if exception:
            mock_urlopen.side_effect = exception
        else:
            mock_response = MagicMock()
            mock_response.read.return_value = response_data
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

        result = _sync_get("http://example.com/api")
        assert result == expected_result

    @patch("opencode_monitor.core.client.urllib.request.urlopen")
    @patch("opencode_monitor.core.client.urllib.request.Request")
    def test_sync_get_uses_custom_timeout(self, mock_request, mock_urlopen):
        """Custom timeout is passed to urlopen."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"data"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        _sync_get("http://example.com/api", timeout=5.0)

        call_kwargs = mock_urlopen.call_args
        assert call_kwargs[1]["timeout"] == 5.0


class TestSyncGetJson:
    """Tests for synchronous HTTP GET with JSON parsing."""

    @pytest.mark.parametrize(
        "raw_response,expected_result",
        [
            ('{"status": "ok", "count": 42}', {"status": "ok", "count": 42}),
            (None, None),
            ("not valid json {", None),
            ('{"key": "value\x00"}', {"key": "value "}),  # Control chars cleaned
        ],
        ids=["valid_json", "null_response", "invalid_json", "cleaned_control_chars"],
    )
    @patch("opencode_monitor.core.client._sync_get")
    def test_sync_get_json_responses(
        self, mock_sync_get, raw_response, expected_result
    ):
        """Sync GET JSON handles valid, null, invalid and dirty JSON."""
        mock_sync_get.return_value = raw_response
        result = _sync_get_json("http://example.com/api")
        assert result == expected_result

    @patch("opencode_monitor.core.client._sync_get")
    def test_sync_get_json_passes_timeout(self, mock_sync_get):
        """Custom timeout is passed through."""
        mock_sync_get.return_value = "{}"
        _sync_get_json("http://example.com/api", timeout=10.0)
        mock_sync_get.assert_called_once_with("http://example.com/api", 10.0)


# =====================================================
# Async HTTP Tests - Consolidated
# =====================================================


class TestAsyncHttp:
    """Tests for async HTTP functions (get and get_json)."""

    @pytest.mark.parametrize(
        "func,mock_target,mock_return,expected",
        [
            (get, "_sync_get", "response data", "response data"),
            (get, "_sync_get", None, None),
            (get_json, "_sync_get_json", {"key": "value"}, {"key": "value"}),
            (get_json, "_sync_get_json", None, None),
        ],
        ids=["get_success", "get_error", "get_json_success", "get_json_error"],
    )
    def test_async_functions_delegate_correctly(
        self, func, mock_target, mock_return, expected
    ):
        """Async get/get_json delegate to sync counterparts."""
        with patch(f"opencode_monitor.core.client.{mock_target}") as mock_sync:
            mock_sync.return_value = mock_return
            result = run_async(func("http://example.com/api"))
            assert result == expected

    @pytest.mark.parametrize(
        "func,mock_target,timeout",
        [
            (get, "_sync_get", 3.0),
            (get_json, "_sync_get_json", 5.0),
        ],
        ids=["get_timeout", "get_json_timeout"],
    )
    def test_async_functions_pass_timeout(self, func, mock_target, timeout):
        """Async functions pass timeout to sync counterparts."""
        with patch(f"opencode_monitor.core.client.{mock_target}") as mock_sync:
            mock_sync.return_value = {} if "json" in mock_target else "data"
            run_async(func("http://example.com/api", timeout=timeout))
            mock_sync.assert_called_once_with("http://example.com/api", timeout)


# =====================================================
# OpenCode Port Detection Tests
# =====================================================


class TestCheckOpencodePort:
    """Tests for OpenCode port detection."""

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
    def test_check_port_calls_correct_url_and_handles_exception(self, mock_get):
        """Check port calls correct endpoint and handles exceptions."""
        # Test correct URL
        mock_get.return_value = "{}"
        run_async(check_opencode_port(8080))
        mock_get.assert_called_with("http://127.0.0.1:8080/session/status", timeout=0.5)

        # Test exception handling
        mock_get.side_effect = Exception("Network error")
        result = run_async(check_opencode_port(8080))
        assert result is False


# =====================================================
# Parallel Requests Tests
# =====================================================


class TestParallelRequests:
    """Tests for parallel HTTP requests."""

    @pytest.mark.parametrize(
        "side_effects,urls,expected_results",
        [
            # All success
            (
                [{"id": 1}, {"id": 2}, {"id": 3}],
                ["http://1", "http://2", "http://3"],
                [{"id": 1}, {"id": 2}, {"id": 3}],
            ),
            # Mixed success/failure
            (
                [{"id": 1}, None, {"id": 3}],
                ["http://1", "http://fail", "http://3"],
                [{"id": 1}, None, {"id": 3}],
            ),
            # Empty list
            ([], [], []),
        ],
        ids=["all_success", "mixed_results", "empty_list"],
    )
    @patch("opencode_monitor.core.client.get_json")
    def test_parallel_requests_results(
        self, mock_get_json, side_effects, urls, expected_results
    ):
        """Parallel requests handles success, failure and empty cases."""
        if side_effects:
            mock_get_json.side_effect = side_effects

        results = run_async(parallel_requests(urls))

        assert results == expected_results
        if not urls:
            mock_get_json.assert_not_called()

    @patch("opencode_monitor.core.client.get_json")
    def test_parallel_requests_custom_timeout(self, mock_get_json):
        """Custom timeout is passed to all requests."""
        mock_get_json.return_value = {}

        urls = ["http://example.com/1", "http://example.com/2"]
        run_async(parallel_requests(urls, timeout=5.0))

        assert mock_get_json.call_count == 2
        for call in mock_get_json.call_args_list:
            assert call[0][1] == 5.0  # timeout argument


# =====================================================
# OpenCodeClient Tests - Consolidated
# =====================================================


class TestOpenCodeClient:
    """Tests for OpenCodeClient initialization and API methods."""

    def test_init_sets_port_and_base_url(self):
        """Client stores port and constructs correct base URL."""
        client = OpenCodeClient(port=9000)
        assert client.port == 9000
        assert client.base_url == "http://127.0.0.1:9000"

    @pytest.mark.parametrize(
        "method,method_args,expected_endpoint",
        [
            ("get_status", {}, "/session/status"),
            ("get_all_sessions", {}, "/session"),
            ("get_session_info", {"session_id": "ses_abc"}, "/session/ses_abc"),
            (
                "get_session_messages",
                {"session_id": "ses_abc", "limit": 5},
                "/session/ses_abc/message?limit=5",
            ),
            (
                "get_session_messages",
                {"session_id": "ses_abc"},
                "/session/ses_abc/message?limit=1",
            ),
            ("get_session_todos", {"session_id": "ses_abc"}, "/session/ses_abc/todo"),
        ],
        ids=[
            "get_status",
            "get_all_sessions",
            "get_session_info",
            "get_messages_with_limit",
            "get_messages_default_limit",
            "get_todos",
        ],
    )
    @patch("opencode_monitor.core.client.get_json")
    def test_api_methods_call_correct_endpoints(
        self, mock_get_json, method, method_args, expected_endpoint
    ):
        """API methods call correct endpoints with proper parameters."""
        mock_get_json.return_value = {}
        client = OpenCodeClient(port=8080)

        getattr(client, method)(**method_args) if asyncio.iscoroutinefunction(
            getattr(client, method)
        ) and False else run_async(getattr(client, method)(**method_args))

        mock_get_json.assert_called_once_with(
            f"http://127.0.0.1:8080{expected_endpoint}"
        )

    @patch("opencode_monitor.core.client.get_json")
    def test_fetch_session_data_aggregates_all(self, mock_get_json):
        """fetch_session_data aggregates info, messages, and todos."""
        mock_get_json.side_effect = [
            {"id": "ses_abc", "path": "/project"},  # info
            [{"role": "user", "content": "Hello"}],  # messages
            [{"id": "todo_1"}],  # todos
        ]

        client = OpenCodeClient(port=8080)
        result = run_async(client.fetch_session_data("ses_abc"))

        assert result["info"] == {"id": "ses_abc", "path": "/project"}
        assert result["messages"] == [{"role": "user", "content": "Hello"}]
        assert result["todos"] == [{"id": "todo_1"}]

    @patch("opencode_monitor.core.client.get_json")
    def test_fetch_session_data_handles_partial_failure(self, mock_get_json):
        """fetch_session_data handles partial API failures."""
        mock_get_json.side_effect = [
            {"id": "ses_abc"},  # info succeeds
            None,  # messages fail
            None,  # todos fail
        ]

        client = OpenCodeClient(port=8080)
        result = run_async(client.fetch_session_data("ses_abc"))

        assert result["info"] == {"id": "ses_abc"}
        assert result["messages"] is None
        assert result["todos"] is None


# =====================================================
# Constants Tests
# =====================================================


class TestConstants:
    """Tests for module constants."""

    def test_request_timeout_value(self):
        """REQUEST_TIMEOUT has expected default value."""
        assert REQUEST_TIMEOUT == 2
