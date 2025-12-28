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
    # Test 1: Short text is not truncated and has no tooltip
    # =========================================================

    def test_short_text_not_truncated(self, mock_menu_item):
        """Text shorter than max_length should not be truncated."""
        MockMenuItem, mock_instance = mock_menu_item
        _truncate_with_tooltip = self._import_function()

        short_text = "Short title"
        max_length = TITLE_MAX_LENGTH

        result = _truncate_with_tooltip(short_text, max_length)

        # Verify MenuItem was created with exact text (no truncation)
        MockMenuItem.assert_called_once_with(short_text, callback=None)
        assert result == mock_instance

    def test_short_text_no_tooltip(self, mock_menu_item):
        """Text shorter than max_length should have no tooltip set."""
        MockMenuItem, mock_instance = mock_menu_item
        _truncate_with_tooltip = self._import_function()

        short_text = "Short title"
        max_length = TITLE_MAX_LENGTH

        _truncate_with_tooltip(short_text, max_length)

        # Verify setToolTip_ was NOT called
        mock_instance._menuitem.setToolTip_.assert_not_called()

    def test_exact_length_text_not_truncated(self, mock_menu_item):
        """Text exactly at max_length should not be truncated."""
        MockMenuItem, mock_instance = mock_menu_item
        _truncate_with_tooltip = self._import_function()

        # Create text exactly at max_length
        exact_text = "x" * TITLE_MAX_LENGTH
        assert len(exact_text) == TITLE_MAX_LENGTH

        _truncate_with_tooltip(exact_text, TITLE_MAX_LENGTH)

        # Verify no truncation
        MockMenuItem.assert_called_once_with(exact_text, callback=None)
        mock_instance._menuitem.setToolTip_.assert_not_called()

    # =========================================================
    # Test 2: Long text is truncated with "..."
    # =========================================================

    def test_long_text_is_truncated(self, mock_menu_item):
        """Text longer than max_length should be truncated with '...'."""
        MockMenuItem, mock_instance = mock_menu_item
        _truncate_with_tooltip = self._import_function()

        long_text = "This is a very long title that exceeds the maximum length"
        max_length = 30

        _truncate_with_tooltip(long_text, max_length)

        # Expected: first 27 chars + "..." = 30 chars
        expected_display = long_text[: max_length - 3] + "..."
        assert len(expected_display) == max_length

        MockMenuItem.assert_called_once_with(expected_display, callback=None)

    def test_truncation_preserves_exact_length(self, mock_menu_item):
        """Truncated text should be exactly max_length characters."""
        MockMenuItem, mock_instance = mock_menu_item
        _truncate_with_tooltip = self._import_function()

        long_text = "A" * 100  # Very long text
        max_length = 25

        _truncate_with_tooltip(long_text, max_length)

        # Get the actual call argument
        call_args = MockMenuItem.call_args[0][0]
        assert len(call_args) == max_length
        assert call_args.endswith("...")

    # =========================================================
    # Test 3: Tooltip contains full text when truncated
    # =========================================================

    def test_truncated_text_has_tooltip_with_full_text(self, mock_menu_item):
        """When text is truncated, tooltip should contain the full original text."""
        MockMenuItem, mock_instance = mock_menu_item
        _truncate_with_tooltip = self._import_function()

        full_text = "This is the complete text that will be truncated in the menu"
        max_length = 30

        _truncate_with_tooltip(full_text, max_length)

        # Verify tooltip was set with FULL original text
        mock_instance._menuitem.setToolTip_.assert_called_once_with(full_text)

    def test_tooltip_shows_original_not_truncated_text(self, mock_menu_item):
        """Tooltip should show original text, not the truncated version."""
        MockMenuItem, mock_instance = mock_menu_item
        _truncate_with_tooltip = self._import_function()

        original = (
            "Read: /Users/developer/projects/my-super-long-project-name/src/app.py"
        )
        max_length = TOOL_ARG_MAX_LENGTH

        _truncate_with_tooltip(original, max_length)

        # Tooltip should have the full path, not truncated
        tooltip_arg = mock_instance._menuitem.setToolTip_.call_args[0][0]
        assert tooltip_arg == original
        assert "..." not in tooltip_arg

    # =========================================================
    # Test 4: Different max_length values
    # =========================================================

    @pytest.mark.parametrize(
        "max_length,text_length,should_truncate",
        [
            (TITLE_MAX_LENGTH, 39, False),  # Below limit
            (TITLE_MAX_LENGTH, 40, False),  # At limit
            (TITLE_MAX_LENGTH, 41, True),  # Above limit
            (TOOL_ARG_MAX_LENGTH, 29, False),  # Below limit
            (TOOL_ARG_MAX_LENGTH, 30, False),  # At limit
            (TOOL_ARG_MAX_LENGTH, 31, True),  # Above limit
            (TODO_CURRENT_MAX_LENGTH, 35, False),
            (TODO_CURRENT_MAX_LENGTH, 36, True),
            (TODO_PENDING_MAX_LENGTH, 30, False),
            (TODO_PENDING_MAX_LENGTH, 31, True),
        ],
    )
    def test_truncation_at_boundary(
        self, mock_menu_item, max_length, text_length, should_truncate
    ):
        """Test truncation behavior at various boundary conditions."""
        MockMenuItem, mock_instance = mock_menu_item
        _truncate_with_tooltip = self._import_function()

        text = "a" * text_length

        _truncate_with_tooltip(text, max_length)

        if should_truncate:
            # Should have tooltip
            mock_instance._menuitem.setToolTip_.assert_called_once()
            # Display should end with ...
            call_args = MockMenuItem.call_args[0][0]
            assert call_args.endswith("...")
        else:
            # Should NOT have tooltip
            mock_instance._menuitem.setToolTip_.assert_not_called()
            # Display should be unchanged
            call_args = MockMenuItem.call_args[0][0]
            assert call_args == text

    def test_small_max_length(self, mock_menu_item):
        """Test with a very small max_length value."""
        MockMenuItem, mock_instance = mock_menu_item
        _truncate_with_tooltip = self._import_function()

        text = "Hello World"
        max_length = 8

        _truncate_with_tooltip(text, max_length)

        # Expected: "Hello" + "..." = 8 chars
        call_args = MockMenuItem.call_args[0][0]
        assert len(call_args) == max_length
        assert call_args == "Hello..."

    # =========================================================
    # Test 5: Prefix handling
    # =========================================================

    def test_prefix_prepended_to_short_text(self, mock_menu_item):
        """Prefix should be prepended to short text."""
        MockMenuItem, mock_instance = mock_menu_item
        _truncate_with_tooltip = self._import_function()

        text = "Short"
        prefix = "  -> "
        max_length = 40

        _truncate_with_tooltip(text, max_length, prefix=prefix)

        MockMenuItem.assert_called_once_with(f"{prefix}{text}", callback=None)

    def test_prefix_prepended_to_truncated_text(self, mock_menu_item):
        """Prefix should be prepended to truncated text."""
        MockMenuItem, mock_instance = mock_menu_item
        _truncate_with_tooltip = self._import_function()

        text = "This is a very long text that will definitely be truncated"
        prefix = "    "
        max_length = 25

        _truncate_with_tooltip(text, max_length, prefix=prefix)

        # Get call args
        call_args = MockMenuItem.call_args[0][0]

        # Should start with prefix
        assert call_args.startswith(prefix)
        # Should end with ...
        assert call_args.endswith("...")

    def test_prefix_does_not_affect_truncation_length(self, mock_menu_item):
        """Truncation length is based on text only, prefix is separate."""
        MockMenuItem, mock_instance = mock_menu_item
        _truncate_with_tooltip = self._import_function()

        text = "A" * 35  # Longer than max_length
        prefix = "ICON "
        max_length = 30

        _truncate_with_tooltip(text, max_length, prefix=prefix)

        call_args = MockMenuItem.call_args[0][0]
        # Prefix + truncated text
        expected_display = prefix + text[: max_length - 3] + "..."
        assert call_args == expected_display

    def test_emoji_prefix(self, mock_menu_item):
        """Test with emoji prefix (common in menu items)."""
        MockMenuItem, mock_instance = mock_menu_item
        _truncate_with_tooltip = self._import_function()

        text = "Very long todo item description here"
        prefix = "    -> "
        max_length = 20

        _truncate_with_tooltip(text, max_length, prefix=prefix)

        call_args = MockMenuItem.call_args[0][0]
        assert call_args.startswith("    -> ")
        assert call_args.endswith("...")

    # =========================================================
    # Additional edge cases
    # =========================================================

    def test_callback_passed_to_menu_item(self, mock_menu_item):
        """Callback should be passed to MenuItem."""
        MockMenuItem, mock_instance = mock_menu_item
        _truncate_with_tooltip = self._import_function()

        def my_callback(sender):
            pass

        text = "Click me"
        max_length = 40

        _truncate_with_tooltip(text, max_length, callback=my_callback)

        MockMenuItem.assert_called_once_with(text, callback=my_callback)

    def test_callback_with_truncated_text(self, mock_menu_item):
        """Callback should work with truncated text too."""
        MockMenuItem, mock_instance = mock_menu_item
        _truncate_with_tooltip = self._import_function()

        callback = MagicMock()
        text = "This is a very long text that should be truncated"
        max_length = 20

        _truncate_with_tooltip(text, max_length, callback=callback)

        # Callback should be passed regardless of truncation
        assert MockMenuItem.call_args[1]["callback"] == callback

    def test_empty_text(self, mock_menu_item):
        """Empty text should not be truncated or have tooltip."""
        MockMenuItem, mock_instance = mock_menu_item
        _truncate_with_tooltip = self._import_function()

        _truncate_with_tooltip("", 40)

        MockMenuItem.assert_called_once_with("", callback=None)
        mock_instance._menuitem.setToolTip_.assert_not_called()

    def test_empty_prefix(self, mock_menu_item):
        """Empty prefix should work correctly."""
        MockMenuItem, mock_instance = mock_menu_item
        _truncate_with_tooltip = self._import_function()

        text = "Some text"
        _truncate_with_tooltip(text, 40, prefix="")

        MockMenuItem.assert_called_once_with(text, callback=None)

    def test_unicode_text(self, mock_menu_item):
        """Unicode characters should be handled correctly."""
        MockMenuItem, mock_instance = mock_menu_item
        _truncate_with_tooltip = self._import_function()

        # Text with unicode characters
        text = "Japanese file name.py"
        max_length = 15

        _truncate_with_tooltip(text, max_length)

        # Should truncate based on character count, not bytes
        call_args = MockMenuItem.call_args[0][0]
        assert len(call_args) == max_length
        mock_instance._menuitem.setToolTip_.assert_called_once_with(text)


class TestTruncationConstants:
    """Tests to verify the truncation constants are correctly defined."""

    def test_title_max_length_is_40(self):
        """TITLE_MAX_LENGTH should be 40."""
        from opencode_monitor.app import TITLE_MAX_LENGTH as APP_TITLE_MAX

        assert APP_TITLE_MAX == 40

    def test_tool_arg_max_length_is_30(self):
        """TOOL_ARG_MAX_LENGTH should be 30."""
        from opencode_monitor.app import TOOL_ARG_MAX_LENGTH as APP_TOOL_MAX

        assert APP_TOOL_MAX == 30

    def test_todo_current_max_length_is_35(self):
        """TODO_CURRENT_MAX_LENGTH should be 35."""
        from opencode_monitor.app import TODO_CURRENT_MAX_LENGTH as APP_TODO_CURRENT

        assert APP_TODO_CURRENT == 35

    def test_todo_pending_max_length_is_30(self):
        """TODO_PENDING_MAX_LENGTH should be 30."""
        from opencode_monitor.app import TODO_PENDING_MAX_LENGTH as APP_TODO_PENDING

        assert APP_TODO_PENDING == 30


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

    def test_long_file_path_tool(self, mock_menu_item):
        """Test with a realistic long file path."""
        MockMenuItem, mock_instance = mock_menu_item
        _truncate_with_tooltip = self._import_function()

        tool_text = "Read: /Users/developer/projects/opencode-swiftbar-monitor/src/opencode_monitor/app.py"

        _truncate_with_tooltip(tool_text, TOOL_ARG_MAX_LENGTH, prefix="    ")

        # Should be truncated
        call_args = MockMenuItem.call_args[0][0]
        assert call_args.endswith("...")

        # Tooltip should have full path
        mock_instance._menuitem.setToolTip_.assert_called_once_with(tool_text)

    def test_long_todo_label(self, mock_menu_item):
        """Test with a realistic long todo label."""
        MockMenuItem, mock_instance = mock_menu_item
        _truncate_with_tooltip = self._import_function()

        todo_text = "Implement the authentication flow with OAuth2 and JWT tokens"

        _truncate_with_tooltip(todo_text, TODO_CURRENT_MAX_LENGTH, prefix="    ")

        # Should be truncated
        mock_instance._menuitem.setToolTip_.assert_called_once_with(todo_text)

    def test_short_agent_title(self, mock_menu_item):
        """Test with a short agent title (should not truncate)."""
        MockMenuItem, mock_instance = mock_menu_item
        _truncate_with_tooltip = self._import_function()

        title = "my-project"

        _truncate_with_tooltip(title, TITLE_MAX_LENGTH, prefix=" ")

        # Should NOT be truncated
        call_args = MockMenuItem.call_args[0][0]
        assert call_args == f" {title}"
        mock_instance._menuitem.setToolTip_.assert_not_called()

    def test_long_agent_title_with_path(self, mock_menu_item):
        """Test with a long agent title containing a path."""
        MockMenuItem, mock_instance = mock_menu_item
        _truncate_with_tooltip = self._import_function()

        title = "opencode-swiftbar-monitor (feature/add-tooltips)"

        _truncate_with_tooltip(title, TITLE_MAX_LENGTH, prefix=" ")

        # Should be truncated (49 > 40)
        call_args = MockMenuItem.call_args[0][0]
        assert call_args.endswith("...")
        mock_instance._menuitem.setToolTip_.assert_called_once_with(title)
