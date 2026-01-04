"""
Tests for opencode_monitor.core.usage module.
Coverage target: 100%
"""

import json
import urllib.error
from contextlib import contextmanager
from unittest.mock import MagicMock, mock_open, patch

import pytest

from opencode_monitor.core.usage import fetch_usage, read_auth_token


# =============================================================================
# Test Helpers
# =============================================================================


@contextmanager
def mock_usage_api(api_response: dict, token: str = "valid-token"):
    """Context manager to mock the usage API call.

    Args:
        api_response: The JSON response to return from the API.
        token: The auth token to use (default: "valid-token").

    Yields:
        The mock response object for additional assertions if needed.
    """
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(api_response).encode("utf-8")
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("opencode_monitor.core.usage.read_auth_token", return_value=token):
        with patch("urllib.request.urlopen", return_value=mock_response):
            yield mock_response


# =============================================================================
# Tests for read_auth_token()
# =============================================================================


class TestReadAuthToken:
    """Tests for the read_auth_token function."""

    def test_returns_token_when_valid_auth_file_exists(self):
        """Valid auth file with token should return the token."""
        auth_data = {"anthropic": {"access": "test-token-123"}}

        with patch("builtins.open", mock_open(read_data=json.dumps(auth_data))):
            result = read_auth_token()

        assert result == "test-token-123"

    @pytest.mark.parametrize(
        "scenario,open_config",
        [
            ("file_not_found", {"side_effect": FileNotFoundError()}),
            ("permission_denied", {"side_effect": PermissionError()}),
            ("invalid_json", {"read_data": "not valid json {"}),
            (
                "missing_anthropic_key",
                {"read_data": json.dumps({"other": {"access": "t"}})},
            ),
            (
                "missing_access_key",
                {"read_data": json.dumps({"anthropic": {"refresh": "t"}})},
            ),
        ],
        ids=[
            "file_not_found",
            "permission_denied",
            "invalid_json",
            "missing_anthropic",
            "missing_access",
        ],
    )
    def test_returns_none_on_error_conditions(self, scenario, open_config):
        """Various error conditions should return None."""
        if "side_effect" in open_config:
            mock_fn = MagicMock(side_effect=open_config["side_effect"])
        else:
            mock_fn = mock_open(read_data=open_config["read_data"])

        with patch("builtins.open", mock_fn):
            result = read_auth_token()

        assert result is None


# =============================================================================
# Tests for fetch_usage()
# =============================================================================


class TestFetchUsage:
    """Tests for the fetch_usage function."""

    def test_returns_error_when_no_token(self):
        """No auth token should return Usage with error message."""
        with patch("opencode_monitor.core.usage.read_auth_token", return_value=None):
            result = fetch_usage()

        assert result.error == "No auth token found"
        assert result.five_hour.utilization == 0
        assert result.seven_day.utilization == 0

    @pytest.mark.parametrize(
        "http_code,expected_error",
        [
            (401, "Token expired"),
            (403, "HTTP 403"),
            (500, "HTTP 500"),
            (502, "HTTP 502"),
            (503, "HTTP 503"),
        ],
        ids=[
            "401_token_expired",
            "403_forbidden",
            "500_server_error",
            "502_bad_gateway",
            "503_unavailable",
        ],
    )
    def test_returns_appropriate_error_on_http_errors(self, http_code, expected_error):
        """HTTP errors should return appropriate error messages."""
        with patch(
            "opencode_monitor.core.usage.read_auth_token",
            return_value="valid-token",
        ):
            http_error = urllib.error.HTTPError(
                url="https://api.anthropic.com/api/oauth/usage",
                code=http_code,
                msg="Error",
                hdrs=MagicMock(),
                fp=None,
            )
            with patch("urllib.request.urlopen", side_effect=http_error):
                result = fetch_usage()

        assert result.error == expected_error

    @pytest.mark.parametrize(
        "exception,expected_error",
        [
            (TimeoutError("Connection timed out"), "Connection timed out"),
            (
                urllib.error.URLError("Name resolution failed"),
                "<urlopen error Name resolution failed>",
            ),
            (ConnectionRefusedError("Connection refused"), "Connection refused"),
        ],
        ids=["timeout", "url_error", "connection_refused"],
    )
    def test_returns_error_on_network_exceptions(self, exception, expected_error):
        """Network exceptions should return error string."""
        with patch(
            "opencode_monitor.core.usage.read_auth_token",
            return_value="valid-token",
        ):
            with patch("urllib.request.urlopen", side_effect=exception):
                result = fetch_usage()

        assert result.error == expected_error

    @pytest.mark.parametrize(
        "api_response,expected",
        [
            # Full response with all fields
            (
                {
                    "five_hour": {
                        "utilization": 25,
                        "resets_at": "2025-01-01T12:00:00Z",
                    },
                    "seven_day": {
                        "utilization": 50,
                        "resets_at": "2025-01-07T00:00:00Z",
                    },
                },
                {
                    "error": None,
                    "five_hour_util": 25,
                    "five_hour_resets": "2025-01-01T12:00:00Z",
                    "seven_day_util": 50,
                    "seven_day_resets": "2025-01-07T00:00:00Z",
                },
            ),
            # Empty response uses defaults
            (
                {},
                {
                    "error": None,
                    "five_hour_util": 0,
                    "five_hour_resets": None,
                    "seven_day_util": 0,
                    "seven_day_resets": None,
                },
            ),
            # Partial response
            (
                {"five_hour": {"utilization": 75}},
                {
                    "error": None,
                    "five_hour_util": 75,
                    "five_hour_resets": None,
                    "seven_day_util": 0,
                    "seven_day_resets": None,
                },
            ),
        ],
        ids=["full_response", "empty_defaults", "partial_response"],
    )
    def test_returns_usage_on_successful_response(self, api_response, expected):
        """Successful API response should return parsed Usage."""
        with mock_usage_api(api_response):
            result = fetch_usage()

        assert result.error == expected["error"]
        assert result.five_hour.utilization == expected["five_hour_util"]
        assert result.five_hour.resets_at == expected["five_hour_resets"]
        assert result.seven_day.utilization == expected["seven_day_util"]
        assert result.seven_day.resets_at == expected["seven_day_resets"]

    def test_returns_parse_error_on_invalid_data_format(self):
        """Invalid data format should return parse error."""
        api_response = {"five_hour": {"utilization": "not-a-number"}}

        with mock_usage_api(api_response):
            result = fetch_usage()

        assert (
            result.error
            == "Parse error: invalid literal for int() with base 10: 'not-a-number'"
        )

    def test_request_headers_are_correctly_set(self):
        """Verify that the request headers are correctly set."""
        api_response = {"five_hour": {}, "seven_day": {}}

        with mock_usage_api(api_response, token="test-bearer-token"):
            with patch("urllib.request.Request") as mock_request_class:
                mock_request = MagicMock()
                mock_request_class.return_value = mock_request

                fetch_usage()

                mock_request_class.assert_called_once_with(
                    "https://api.anthropic.com/api/oauth/usage"
                )

                calls = mock_request.add_header.call_args_list
                headers_added = {call[0][0]: call[0][1] for call in calls}

                assert headers_added == {
                    "Authorization": "Bearer test-bearer-token",
                    "anthropic-beta": "oauth-2025-04-20",
                    "Content-Type": "application/json",
                }
