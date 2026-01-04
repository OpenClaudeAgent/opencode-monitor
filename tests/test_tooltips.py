"""
Tests for tooltips feature on truncated elements.

Tests the _truncate_with_tooltip function from app.py which:
- Truncates text that exceeds max_length (with "...")
- Adds a native macOS tooltip with full text when truncated
- Leaves short text unchanged with no tooltip
"""

import pytest
from unittest.mock import MagicMock, patch


# Constants from app.py
TITLE_MAX_LENGTH = 40
TOOL_ARG_MAX_LENGTH = 30
TODO_CURRENT_MAX_LENGTH = 35
TODO_PENDING_MAX_LENGTH = 30


class TestTruncateWithTooltip:
    """Tests for the _truncate_with_tooltip function."""

    @pytest.fixture
    def mock_menu_item(self):
        """Create a mock rumps.MenuItem with _menuitem attribute."""
        with patch("rumps.MenuItem") as MockMenuItem:
            mock_instance = MagicMock()
            mock_instance._menuitem = MagicMock()
            MockMenuItem.return_value = mock_instance
            yield MockMenuItem, mock_instance

    def _import_function(self):
        """Import the function under test (after mocking rumps)."""
        from opencode_monitor.app import _truncate_with_tooltip

        return _truncate_with_tooltip

    # =========================================================
    # Consolidated: Short/exact length text tests
    # =========================================================

    @pytest.mark.parametrize(
        "text,max_length,should_truncate",
        [
            ("Short title", TITLE_MAX_LENGTH, False),
            ("x" * TITLE_MAX_LENGTH, TITLE_MAX_LENGTH, False),  # Exact length
            ("x" * (TITLE_MAX_LENGTH + 1), TITLE_MAX_LENGTH, True),  # Above limit
            ("a" * 29, TOOL_ARG_MAX_LENGTH, False),
            ("a" * 30, TOOL_ARG_MAX_LENGTH, False),
            ("a" * 31, TOOL_ARG_MAX_LENGTH, True),
            ("a" * 35, TODO_CURRENT_MAX_LENGTH, False),
            ("a" * 36, TODO_CURRENT_MAX_LENGTH, True),
            ("a" * 30, TODO_PENDING_MAX_LENGTH, False),
            ("a" * 31, TODO_PENDING_MAX_LENGTH, True),
        ],
    )
    def test_truncation_at_boundary(
        self, mock_menu_item, text, max_length, should_truncate
    ):
        """Test truncation behavior at various boundary conditions."""
        MockMenuItem, mock_instance = mock_menu_item
        _truncate_with_tooltip = self._import_function()

        _truncate_with_tooltip(text, max_length)

        call_args = MockMenuItem.call_args[0][0]
        if should_truncate:
            mock_instance._menuitem.setToolTip_.assert_called_once()
            assert call_args.endswith("...")
            assert len(call_args) == max_length
        else:
            mock_instance._menuitem.setToolTip_.assert_not_called()
            assert call_args == text

    # =========================================================
    # Consolidated: Truncation behavior tests
    # =========================================================

    @pytest.mark.parametrize(
        "text,max_length,expected_suffix",
        [
            ("This is a very long title that exceeds the maximum length", 30, "..."),
            ("A" * 100, 25, "..."),
            ("Hello World", 8, "..."),
        ],
    )
    def test_long_text_truncation(
        self, mock_menu_item, text, max_length, expected_suffix
    ):
        """Long text is truncated with '...' and has tooltip with full text."""
        MockMenuItem, mock_instance = mock_menu_item
        _truncate_with_tooltip = self._import_function()

        _truncate_with_tooltip(text, max_length)

        call_args = MockMenuItem.call_args[0][0]
        # Verify truncation
        assert len(call_args) == max_length
        assert call_args.endswith(expected_suffix)
        # Verify tooltip contains full original text
        mock_instance._menuitem.setToolTip_.assert_called_once_with(text)

    # =========================================================
    # Consolidated: Prefix handling tests
    # =========================================================

    @pytest.mark.parametrize(
        "text,prefix,max_length,should_truncate",
        [
            ("Short", "  -> ", 40, False),
            (
                "This is a very long text that will definitely be truncated",
                "    ",
                25,
                True,
            ),
            ("A" * 35, "ICON ", 30, True),
            ("Very long todo item description here", "    -> ", 20, True),
        ],
    )
    def test_prefix_handling(
        self, mock_menu_item, text, prefix, max_length, should_truncate
    ):
        """Prefix is prepended correctly to both short and truncated text."""
        MockMenuItem, mock_instance = mock_menu_item
        _truncate_with_tooltip = self._import_function()

        _truncate_with_tooltip(text, max_length, prefix=prefix)

        call_args = MockMenuItem.call_args[0][0]
        assert call_args.startswith(prefix)
        if should_truncate:
            assert call_args.endswith("...")

    # =========================================================
    # Consolidated: Callback and edge cases
    # =========================================================

    @pytest.mark.parametrize(
        "text,max_length,use_callback",
        [
            ("Click me", 40, True),
            ("This is a very long text that should be truncated", 20, True),
            ("", 40, False),
        ],
    )
    def test_callback_and_edge_cases(
        self, mock_menu_item, text, max_length, use_callback
    ):
        """Callback is passed correctly; empty text handled properly."""
        MockMenuItem, mock_instance = mock_menu_item
        _truncate_with_tooltip = self._import_function()

        callback = MagicMock() if use_callback else None
        _truncate_with_tooltip(text, max_length, callback=callback)

        # Verify callback is passed
        if use_callback:
            assert MockMenuItem.call_args[1]["callback"] == callback
        else:
            MockMenuItem.assert_called_once_with("", callback=None)
            mock_instance._menuitem.setToolTip_.assert_not_called()

    def test_empty_prefix_works(self, mock_menu_item):
        """Empty prefix should work correctly."""
        MockMenuItem, mock_instance = mock_menu_item
        _truncate_with_tooltip = self._import_function()

        text = "Some text"
        _truncate_with_tooltip(text, 40, prefix="")

        MockMenuItem.assert_called_once_with(text, callback=None)

    def test_unicode_text_handled_by_char_count(self, mock_menu_item):
        """Unicode characters are handled by character count, not bytes."""
        MockMenuItem, mock_instance = mock_menu_item
        _truncate_with_tooltip = self._import_function()

        text = "Japanese file name.py"
        max_length = 15

        _truncate_with_tooltip(text, max_length)

        call_args = MockMenuItem.call_args[0][0]
        assert len(call_args) == max_length
        mock_instance._menuitem.setToolTip_.assert_called_once_with(text)


class TestTruncationConstants:
    """Tests to verify the truncation constants are correctly defined."""

    @pytest.mark.parametrize(
        "constant_name,expected_value",
        [
            ("TITLE_MAX_LENGTH", 40),
            ("TOOL_ARG_MAX_LENGTH", 30),
            ("TODO_CURRENT_MAX_LENGTH", 35),
            ("TODO_PENDING_MAX_LENGTH", 30),
        ],
    )
    def test_truncation_constants(self, constant_name, expected_value):
        """Verify truncation constants have correct values."""
        from opencode_monitor import app

        actual = getattr(app, constant_name)
        assert actual == expected_value, f"{constant_name} should be {expected_value}"


class TestRealWorldScenarios:
    """Integration-like tests with realistic data."""

    @pytest.fixture
    def mock_menu_item(self):
        """Create a mock rumps.MenuItem."""
        with patch("rumps.MenuItem") as MockMenuItem:
            mock_instance = MagicMock()
            mock_instance._menuitem = MagicMock()
            MockMenuItem.return_value = mock_instance
            yield MockMenuItem, mock_instance

    def _import_function(self):
        from opencode_monitor.app import _truncate_with_tooltip

        return _truncate_with_tooltip

    @pytest.mark.parametrize(
        "text,max_length,prefix,should_truncate,description",
        [
            # Long file path (tool)
            (
                "Read: /Users/developer/projects/opencode-swiftbar-monitor/src/opencode_monitor/app.py",
                TOOL_ARG_MAX_LENGTH,
                "    ",
                True,
                "Long file path is truncated with tooltip",
            ),
            # Long todo
            (
                "Implement the authentication flow with OAuth2 and JWT tokens",
                TODO_CURRENT_MAX_LENGTH,
                "    ",
                True,
                "Long todo is truncated with tooltip",
            ),
            # Short agent title
            (
                "my-project",
                TITLE_MAX_LENGTH,
                " ",
                False,
                "Short agent title not truncated",
            ),
            # Long agent title with path
            (
                "opencode-swiftbar-monitor (feature/add-tooltips)",
                TITLE_MAX_LENGTH,
                " ",
                True,
                "Long agent title truncated",
            ),
        ],
    )
    def test_real_world_scenario(
        self, mock_menu_item, text, max_length, prefix, should_truncate, description
    ):
        """Test realistic menu item scenarios."""
        MockMenuItem, mock_instance = mock_menu_item
        _truncate_with_tooltip = self._import_function()

        _truncate_with_tooltip(text, max_length, prefix=prefix)

        call_args = MockMenuItem.call_args[0][0]
        if should_truncate:
            assert call_args.endswith("..."), description
            mock_instance._menuitem.setToolTip_.assert_called_once_with(text)
        else:
            assert call_args == f"{prefix}{text}", description
            mock_instance._menuitem.setToolTip_.assert_not_called()
