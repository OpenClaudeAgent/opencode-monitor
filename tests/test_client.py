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
        "raw,expected",
        [
            # Control chars removed
            ('{"key": "value\x00\x08\x0b"}', '{"key": "value   "}'),
            # Valid JSON with newlines/tabs preserved
            ('{\n\t"key": "value"\n}', '{\n\t"key": "value"\n}'),
            # Empty string unchanged
            ("", ""),
            # Multiple control characters (3 before + 1 after = 4 spaces total)
            ("\x00\x01\x02abc\x1f", "   abc "),
            # Tab and newline preserved (0x09, 0x0a, 0x0d)
            ("line1\nline2\ttab\rcarriage", "line1\nline2\ttab\rcarriage"),
        ],
        ids=[
            "control_chars_replaced",
            "valid_json_preserved",
            "empty_string",
            "multiple_control_chars",
            "whitespace_preserved",
        ],
    )
    def test_clean_json_behavior(self, raw, expected):
        """Control characters replaced with spaces, valid content preserved."""
        result = _clean_json(raw)
        assert result == expected
        assert len(result) == len(raw)


# =====================================================
# Sync HTTP Tests - Consolidated
# =====================================================


class TestSyncHttp:
    """Tests for synchronous HTTP functions (_sync_get and _sync_get_json)."""

    @pytest.mark.parametrize(
        "response_data,exception,expected_result,custom_timeout",
        [
            # Success case
            (b"response body", None, "response body", None),
            # Error cases
            (None, Exception("URLError"), None, None),
            (None, Exception("Generic error"), None, None),
            # Custom timeout
            (b"data", None, "data", 5.0),
        ],
        ids=["success", "url_error", "generic_error", "custom_timeout"],
    )
    @patch("opencode_monitor.core.client.urllib.request.urlopen")
    @patch("opencode_monitor.core.client.urllib.request.Request")
    def test_sync_get_all_cases(
        self,
        mock_request,
        mock_urlopen,
        response_data,
        exception,
        expected_result,
        custom_timeout,
    ):
        """Sync GET handles success, errors, and custom timeout."""
        if exception:
            mock_urlopen.side_effect = exception
        else:
            mock_response = MagicMock()
            mock_response.read.return_value = response_data
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

        timeout = custom_timeout if custom_timeout else REQUEST_TIMEOUT
        result = _sync_get("http://example.com/api", timeout=timeout)

        assert result == expected_result
        if not exception:
            call_kwargs = mock_urlopen.call_args
            assert call_kwargs[1]["timeout"] == timeout

    @pytest.mark.parametrize(
        "raw_response,expected_result,custom_timeout",
        [
            # Valid JSON
            ('{"status": "ok", "count": 42}', {"status": "ok", "count": 42}, None),
            # Null response
            (None, None, None),
            # Invalid JSON
            ("not valid json {", None, None),
            # Control chars cleaned
            ('{"key": "value\x00"}', {"key": "value "}, None),
            # Custom timeout
            ('{"data": true}', {"data": True}, 10.0),
        ],
        ids=[
            "valid_json",
            "null_response",
            "invalid_json",
            "cleaned_control_chars",
            "custom_timeout",
        ],
    )
    @patch("opencode_monitor.core.client._sync_get")
    def test_sync_get_json_all_cases(
        self, mock_sync_get, raw_response, expected_result, custom_timeout
    ):
        """Sync GET JSON handles valid, null, invalid, dirty JSON and timeout."""
        mock_sync_get.return_value = raw_response
        timeout = custom_timeout if custom_timeout else REQUEST_TIMEOUT

        result = _sync_get_json("http://example.com/api", timeout=timeout)

        assert result == expected_result
        mock_sync_get.assert_called_once_with("http://example.com/api", timeout)


# =====================================================
# Async HTTP Tests - Consolidated
# =====================================================


class TestAsyncHttp:
    """Tests for async HTTP functions (get and get_json)."""

    @pytest.mark.parametrize(
        "func,mock_target,mock_return,expected,timeout",
        [
            # get function
            (get, "_sync_get", "response data", "response data", None),
            (get, "_sync_get", None, None, None),
            (get, "_sync_get", "data", "data", 3.0),
            # get_json function
            (get_json, "_sync_get_json", {"key": "value"}, {"key": "value"}, None),
            (get_json, "_sync_get_json", None, None, None),
            (get_json, "_sync_get_json", {"x": 1}, {"x": 1}, 5.0),
        ],
        ids=[
            "get_success",
            "get_error",
            "get_timeout",
            "get_json_success",
            "get_json_error",
            "get_json_timeout",
        ],
    )
    def test_async_functions_all_cases(
        self, func, mock_target, mock_return, expected, timeout
    ):
        """Async get/get_json delegate to sync counterparts with correct params."""
        with patch(f"opencode_monitor.core.client.{mock_target}") as mock_sync:
            mock_sync.return_value = mock_return
            url = "http://example.com/api"

            if timeout:
                result = run_async(func(url, timeout=timeout))
                mock_sync.assert_called_once_with(url, timeout)
            else:
                result = run_async(func(url))
                assert mock_sync.call_count == 1

            assert result == expected


# =====================================================
# OpenCode Port Detection Tests
# =====================================================


class TestCheckOpencodePort:
    """Tests for OpenCode port detection."""

    @pytest.mark.parametrize(
        "response,exception,expected",
        [
            # Valid OpenCode responses
            ("{}", None, True),
            ('{"ses_abc123": {"status": "idle"}}', None, True),
            # Invalid responses
            (None, None, False),
            ('{"error": "not opencode"}', None, False),
            # Exception handling
            (None, Exception("Network error"), False),
        ],
        ids=[
            "empty_object_is_opencode",
            "session_response_is_opencode",
            "none_response",
            "unexpected_format",
            "network_error",
        ],
    )
    @patch("opencode_monitor.core.client.get")
    def test_check_port_all_cases(self, mock_get, response, exception, expected):
        """Port check handles all response types and exceptions."""
        if exception:
            mock_get.side_effect = exception
        else:
            mock_get.return_value = response

        result = run_async(check_opencode_port(8080))

        assert result == expected
        mock_get.assert_called_with("http://127.0.0.1:8080/session/status", timeout=0.5)


# =====================================================
# Parallel Requests Tests
# =====================================================


class TestParallelRequests:
    """Tests for parallel HTTP requests."""

    @pytest.mark.parametrize(
        "side_effects,urls,expected_results,custom_timeout",
        [
            # All success
            (
                [{"id": 1}, {"id": 2}, {"id": 3}],
                ["http://1", "http://2", "http://3"],
                [{"id": 1}, {"id": 2}, {"id": 3}],
                None,
            ),
            # Mixed success/failure
            (
                [{"id": 1}, None, {"id": 3}],
                ["http://1", "http://fail", "http://3"],
                [{"id": 1}, None, {"id": 3}],
                None,
            ),
            # Empty list
            ([], [], [], None),
            # Custom timeout
            (
                [{"a": 1}, {"b": 2}],
                ["http://a", "http://b"],
                [{"a": 1}, {"b": 2}],
                5.0,
            ),
        ],
        ids=["all_success", "mixed_results", "empty_list", "custom_timeout"],
    )
    @patch("opencode_monitor.core.client.get_json")
    def test_parallel_requests_all_cases(
        self, mock_get_json, side_effects, urls, expected_results, custom_timeout
    ):
        """Parallel requests handles all cases with correct timeout."""
        if side_effects:
            mock_get_json.side_effect = side_effects

        if custom_timeout:
            results = run_async(parallel_requests(urls, timeout=custom_timeout))
        else:
            results = run_async(parallel_requests(urls))

        assert results == expected_results
        assert len(results) == len(urls)

        if not urls:
            assert mock_get_json.call_count == 0
        else:
            assert mock_get_json.call_count == len(urls)
            if custom_timeout:
                for call in mock_get_json.call_args_list:
                    assert call[0][1] == custom_timeout


# =====================================================
# OpenCodeClient Tests - Consolidated
# =====================================================


class TestOpenCodeClient:
    """Tests for OpenCodeClient initialization and API methods."""

    def test_init_and_constants(self):
        """Client initialization and module constants."""
        client = OpenCodeClient(port=9000)

        # Initialization
        assert client.port == 9000
        assert client.base_url == "http://127.0.0.1:9000"

        # Different port
        client2 = OpenCodeClient(port=8080)
        assert client2.port == 8080
        assert client2.base_url == "http://127.0.0.1:8080"

        # Module constant
        assert REQUEST_TIMEOUT == 2

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
    def test_api_methods_endpoints(
        self, mock_get_json, method, method_args, expected_endpoint
    ):
        """API methods call correct endpoints with proper parameters."""
        mock_get_json.return_value = {}
        client = OpenCodeClient(port=8080)

        run_async(getattr(client, method)(**method_args))

        expected_url = f"http://127.0.0.1:8080{expected_endpoint}"
        mock_get_json.assert_called_once_with(expected_url)
        assert mock_get_json.call_count == 1

    @pytest.mark.parametrize(
        "info_response,messages_response,todos_response",
        [
            # Full success
            (
                {"id": "ses_abc", "path": "/project"},
                [{"role": "user", "content": "Hello"}],
                [{"id": "todo_1"}],
            ),
            # Partial failure
            ({"id": "ses_abc"}, None, None),
            # All None
            (None, None, None),
        ],
        ids=["full_success", "partial_failure", "all_none"],
    )
    @patch("opencode_monitor.core.client.get_json")
    def test_fetch_session_data_aggregation(
        self, mock_get_json, info_response, messages_response, todos_response
    ):
        """fetch_session_data aggregates info, messages, and todos correctly."""
        mock_get_json.side_effect = [info_response, messages_response, todos_response]

        client = OpenCodeClient(port=8080)
        result = run_async(client.fetch_session_data("ses_abc"))

        assert result["info"] == info_response
        assert result["messages"] == messages_response
        assert result["todos"] == todos_response
        assert mock_get_json.call_count == 3
        assert list(result.keys()) == ["info", "messages", "todos"]
