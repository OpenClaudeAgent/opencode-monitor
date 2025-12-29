"""
Tests for opencode_monitor.core.usage module.
Coverage target: 100%
"""

import json
import urllib.error
from unittest.mock import MagicMock, mock_open, patch

import pytest

from opencode_monitor.core.usage import AUTH_FILE, fetch_usage, read_auth_token
from opencode_monitor.core.models import Usage, UsagePeriod


# =============================================================================
# Tests for read_auth_token()
# =============================================================================


class TestReadAuthToken:
    """Tests for the read_auth_token function."""

    def test_returns_token_when_valid_auth_file_exists(self, tmp_path):
        """Valid auth file with token should return the token."""
        auth_data = {"anthropic": {"access": "test-token-123"}}

        with patch("builtins.open", mock_open(read_data=json.dumps(auth_data))):
            result = read_auth_token()

        assert result == "test-token-123"

    def test_returns_none_when_file_not_found(self):
        """Missing auth file should return None."""
        with patch("builtins.open", side_effect=FileNotFoundError()):
            result = read_auth_token()

        assert result is None

    def test_returns_none_when_json_invalid(self):
        """Invalid JSON should return None."""
        with patch("builtins.open", mock_open(read_data="not valid json {")):
            result = read_auth_token()

        assert result is None

    def test_returns_none_when_anthropic_key_missing(self):
        """Auth file without 'anthropic' key should return None."""
        auth_data = {"other_provider": {"access": "token"}}

        with patch("builtins.open", mock_open(read_data=json.dumps(auth_data))):
            result = read_auth_token()

        assert result is None

    def test_returns_none_when_access_key_missing(self):
        """Auth file without 'access' key should return None."""
        auth_data = {"anthropic": {"refresh": "refresh-token"}}

        with patch("builtins.open", mock_open(read_data=json.dumps(auth_data))):
            result = read_auth_token()

        assert result is None

    def test_returns_none_on_permission_error(self):
        """Permission denied should return None."""
        with patch("builtins.open", side_effect=PermissionError()):
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

    def test_returns_token_expired_on_401_error(self):
        """HTTP 401 should return 'Token expired' error."""
        with patch(
            "opencode_monitor.core.usage.read_auth_token",
            return_value="valid-token",
        ):
            http_error = urllib.error.HTTPError(
                url="https://api.anthropic.com/api/oauth/usage",
                code=401,
                msg="Unauthorized",
                hdrs={},
                fp=None,
            )
            with patch("urllib.request.urlopen", side_effect=http_error):
                result = fetch_usage()

        assert result.error == "Token expired"

    def test_returns_http_error_code_on_other_http_errors(self):
        """Other HTTP errors should return 'HTTP <code>' error."""
        with patch(
            "opencode_monitor.core.usage.read_auth_token",
            return_value="valid-token",
        ):
            http_error = urllib.error.HTTPError(
                url="https://api.anthropic.com/api/oauth/usage",
                code=500,
                msg="Internal Server Error",
                hdrs={},
                fp=None,
            )
            with patch("urllib.request.urlopen", side_effect=http_error):
                result = fetch_usage()

        assert result.error == "HTTP 500"

    def test_returns_error_string_on_network_exception(self):
        """Network exceptions should return error string."""
        with patch(
            "opencode_monitor.core.usage.read_auth_token",
            return_value="valid-token",
        ):
            with patch(
                "urllib.request.urlopen",
                side_effect=TimeoutError("Connection timed out"),
            ):
                result = fetch_usage()

        assert result.error == "Connection timed out"

    def test_returns_usage_on_successful_response(self):
        """Successful API response should return parsed Usage."""
        api_response = {
            "five_hour": {"utilization": 25, "resets_at": "2025-01-01T12:00:00Z"},
            "seven_day": {"utilization": 50, "resets_at": "2025-01-07T00:00:00Z"},
        }

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(api_response).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch(
            "opencode_monitor.core.usage.read_auth_token",
            return_value="valid-token",
        ):
            with patch("urllib.request.urlopen", return_value=mock_response):
                result = fetch_usage()

        assert result.error is None
        assert result.five_hour.utilization == 25
        assert result.five_hour.resets_at == "2025-01-01T12:00:00Z"
        assert result.seven_day.utilization == 50
        assert result.seven_day.resets_at == "2025-01-07T00:00:00Z"

    def test_returns_usage_with_default_values_when_fields_missing(self):
        """API response with missing fields should use defaults."""
        api_response = {}

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(api_response).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch(
            "opencode_monitor.core.usage.read_auth_token",
            return_value="valid-token",
        ):
            with patch("urllib.request.urlopen", return_value=mock_response):
                result = fetch_usage()

        assert result.error is None
        assert result.five_hour.utilization == 0
        assert result.five_hour.resets_at is None
        assert result.seven_day.utilization == 0
        assert result.seven_day.resets_at is None

    def test_returns_parse_error_on_invalid_data_format(self):
        """Invalid data format should return parse error."""
        # utilization expects an int, but we pass something that fails int()
        api_response = {
            "five_hour": {"utilization": "not-a-number"},
        }

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(api_response).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch(
            "opencode_monitor.core.usage.read_auth_token",
            return_value="valid-token",
        ):
            with patch("urllib.request.urlopen", return_value=mock_response):
                result = fetch_usage()

        assert result.error is not None
        assert "Parse error" in result.error

    def test_request_headers_are_correctly_set(self):
        """Verify that the request headers are correctly set."""
        api_response = {"five_hour": {}, "seven_day": {}}

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(api_response).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch(
            "opencode_monitor.core.usage.read_auth_token",
            return_value="test-bearer-token",
        ):
            with patch(
                "urllib.request.urlopen", return_value=mock_response
            ) as mock_urlopen:
                with patch("urllib.request.Request") as mock_request_class:
                    mock_request = MagicMock()
                    mock_request_class.return_value = mock_request

                    fetch_usage()

                    # Verify Request was created with correct URL
                    mock_request_class.assert_called_once_with(
                        "https://api.anthropic.com/api/oauth/usage"
                    )

                    # Verify headers were added
                    calls = mock_request.add_header.call_args_list
                    headers_added = {call[0][0]: call[0][1] for call in calls}

                    assert headers_added["Authorization"] == "Bearer test-bearer-token"
                    assert headers_added["anthropic-beta"] == "oauth-2025-04-20"
                    assert headers_added["Content-Type"] == "application/json"

    def test_handles_403_http_error(self):
        """HTTP 403 Forbidden should return HTTP 403 error (not Token expired)."""
        with patch(
            "opencode_monitor.core.usage.read_auth_token",
            return_value="valid-token",
        ):
            http_error = urllib.error.HTTPError(
                url="https://api.anthropic.com/api/oauth/usage",
                code=403,
                msg="Forbidden",
                hdrs={},
                fp=None,
            )
            with patch("urllib.request.urlopen", side_effect=http_error):
                result = fetch_usage()

        assert result.error == "HTTP 403"

    def test_handles_url_error(self):
        """URLError should return error message."""
        with patch(
            "opencode_monitor.core.usage.read_auth_token",
            return_value="valid-token",
        ):
            url_error = urllib.error.URLError("Name resolution failed")
            with patch("urllib.request.urlopen", side_effect=url_error):
                result = fetch_usage()

        assert "Name resolution failed" in result.error
