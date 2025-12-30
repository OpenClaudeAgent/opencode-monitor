"""
Tests for opencode_monitor.dashboard.widgets

Coverage target: 100% for all widget classes
Tests widget creation, properties, methods, and signals.
"""

import pytest
from unittest.mock import patch, MagicMock

# PyQt6 imports with QApplication fixture
from PyQt6.QtWidgets import QApplication, QWidget, QPushButton, QLabel
from PyQt6.QtCore import Qt, QSignalBlocker
from PyQt6.QtGui import QColor


# Ensure QApplication exists for all tests
@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance for all tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def widget_parent(qapp):
    """Create a parent widget for testing."""
    parent = QWidget()
    yield parent
    parent.deleteLater()


# =============================================================================
# Utility Function Tests
# =============================================================================


class TestFormatTokens:
    """Tests for format_tokens utility function."""

    @pytest.mark.parametrize(
        "count,expected",
        [
            (0, "0"),
            (1, "1"),
            (100, "100"),
            (999, "999"),
            (1000, "1K"),
            (1500, "2K"),
            (10000, "10K"),
            (100000, "100K"),
            (999999, "1000K"),
            (1000000, "1.0M"),
            (1500000, "1.5M"),
            (10000000, "10.0M"),
            (1234567890, "1234.6M"),
        ],
    )
    def test_format_tokens(self, count, expected):
        """format_tokens returns correct formatted string."""
        from opencode_monitor.dashboard.styles import format_tokens

        assert format_tokens(count) == expected


class TestFormatDurationMs:
    """Tests for format_duration_ms utility function."""

    @pytest.mark.parametrize(
        "elapsed_ms,expected",
        [
            (0, "0ms"),
            (1, "1ms"),
            (100, "100ms"),
            (999, "999ms"),
            (1000, "1s"),
            (1500, "1s"),
            (5000, "5s"),
            (59999, "59s"),
            (60000, "1m 0s"),
            (61000, "1m 1s"),
            (90000, "1m 30s"),
            (120000, "2m 0s"),
            (3661000, "61m 1s"),
        ],
    )
    def test_format_duration_ms(self, elapsed_ms, expected):
        """format_duration_ms returns correct formatted string."""
        from opencode_monitor.dashboard.styles import format_duration_ms

        assert format_duration_ms(elapsed_ms) == expected


# =============================================================================
# MetricCard Tests
# =============================================================================


class TestMetricCard:
    """Tests for MetricCard widget."""

    def test_creation_basic(self, qapp, widget_parent):
        """MetricCard can be created with value and label."""
        from opencode_monitor.dashboard.widgets import MetricCard

        card = MetricCard("42", "Sessions", parent=widget_parent)
        assert card is not None
        assert isinstance(card, QWidget)

    def test_creation_with_accent(self, qapp, widget_parent):
        """MetricCard can be created with custom accent."""
        from opencode_monitor.dashboard.widgets import MetricCard

        card = MetricCard("100", "Requests", accent="success", parent=widget_parent)
        assert card._accent == "success"

    @pytest.mark.parametrize(
        "accent,expected_in_map",
        [
            ("primary", True),
            ("success", True),
            ("warning", True),
            ("error", True),
            ("muted", True),
            ("invalid", False),
        ],
    )
    def test_accent_mapping(self, qapp, widget_parent, accent, expected_in_map):
        """MetricCard accent colors are correctly mapped."""
        from opencode_monitor.dashboard.widgets import MetricCard

        card = MetricCard("0", "Test", accent=accent, parent=widget_parent)
        if expected_in_map:
            assert card._accent_color == card.ACCENT_MAP[accent]
        else:
            # Invalid accent falls back to muted
            from opencode_monitor.dashboard.styles import COLORS

            assert card._accent_color == COLORS["text_muted"]

    def test_set_value(self, qapp, widget_parent):
        """MetricCard.set_value updates the displayed value."""
        from opencode_monitor.dashboard.widgets import MetricCard

        card = MetricCard("0", "Count", parent=widget_parent)
        card.set_value("999")
        assert card._value_label.text() == "999"

    def test_label_is_uppercase(self, qapp, widget_parent):
        """MetricCard label is displayed in uppercase."""
        from opencode_monitor.dashboard.widgets import MetricCard

        card = MetricCard("0", "sessions", parent=widget_parent)
        assert card._label.text() == "SESSIONS"

    def test_minimum_dimensions(self, qapp, widget_parent):
        """MetricCard has minimum dimensions set."""
        from opencode_monitor.dashboard.widgets import MetricCard

        card = MetricCard("0", "Test", parent=widget_parent)
        assert card.minimumWidth() >= 160
        assert card.minimumHeight() >= 120

    def test_shadow_effect_applied(self, qapp, widget_parent):
        """MetricCard has shadow effect."""
        from opencode_monitor.dashboard.widgets import MetricCard
        from PyQt6.QtWidgets import QGraphicsDropShadowEffect

        card = MetricCard("0", "Test", parent=widget_parent)
        effect = card.graphicsEffect()
        assert effect is not None
        assert isinstance(effect, QGraphicsDropShadowEffect)


# =============================================================================
# StatusBadge Tests
# =============================================================================


class TestStatusBadge:
    """Tests for StatusBadge widget."""

    def test_creation_basic(self, qapp, widget_parent):
        """StatusBadge can be created with text."""
        from opencode_monitor.dashboard.widgets import StatusBadge

        badge = StatusBadge("BUSY", parent=widget_parent)
        assert badge is not None
        assert badge.text() == "BUSY"

    def test_creation_with_variant(self, qapp, widget_parent):
        """StatusBadge can be created with variant."""
        from opencode_monitor.dashboard.widgets import StatusBadge

        badge = StatusBadge("Active", variant="success", parent=widget_parent)
        assert badge is not None

    @pytest.mark.parametrize(
        "variant",
        [
            "success",
            "warning",
            "error",
            "info",
            "neutral",
            "critical",
            "high",
            "medium",
            "low",
        ],
    )
    def test_valid_variants(self, qapp, widget_parent, variant):
        """StatusBadge supports all documented variants."""
        from opencode_monitor.dashboard.widgets import StatusBadge

        badge = StatusBadge("Test", variant=variant, parent=widget_parent)
        # Variant should be in VARIANTS mapping
        assert variant in StatusBadge.VARIANTS

    def test_set_variant(self, qapp, widget_parent):
        """StatusBadge.set_variant changes the badge appearance."""
        from opencode_monitor.dashboard.widgets import StatusBadge

        badge = StatusBadge("Status", variant="neutral", parent=widget_parent)
        # Change variant
        badge.set_variant("success")
        # Should not raise and badge should still be valid
        assert badge.text() == "Status"

    def test_invalid_variant_fallback(self, qapp, widget_parent):
        """StatusBadge with invalid variant falls back to neutral."""
        from opencode_monitor.dashboard.widgets import StatusBadge

        badge = StatusBadge("Test", variant="nonexistent", parent=widget_parent)
        # Should not raise, uses neutral fallback
        assert badge is not None

    def test_is_qlabel(self, qapp, widget_parent):
        """StatusBadge is a QLabel subclass."""
        from opencode_monitor.dashboard.widgets import StatusBadge

        badge = StatusBadge("Test", parent=widget_parent)
        assert isinstance(badge, QLabel)


# =============================================================================
# RiskBadge Tests
# =============================================================================


class TestRiskBadge:
    """Tests for RiskBadge widget."""

    def test_creation_basic(self, qapp, widget_parent):
        """RiskBadge can be created with level."""
        from opencode_monitor.dashboard.widgets import RiskBadge

        badge = RiskBadge("critical", parent=widget_parent)
        assert badge is not None

    @pytest.mark.parametrize(
        "level,expected_upper",
        [
            ("critical", "CRITICAL"),
            ("high", "HIGH"),
            ("medium", "MEDIUM"),
            ("low", "LOW"),
            ("CRITICAL", "CRITICAL"),  # Already uppercase
            ("High", "HIGH"),  # Mixed case
        ],
    )
    def test_level_text_uppercase(self, qapp, widget_parent, level, expected_upper):
        """RiskBadge displays level in uppercase."""
        from opencode_monitor.dashboard.widgets import RiskBadge

        badge = RiskBadge(level, parent=widget_parent)
        assert badge.text() == expected_upper

    @pytest.mark.parametrize(
        "level",
        ["critical", "high", "medium", "low"],
    )
    def test_valid_levels(self, qapp, widget_parent, level):
        """RiskBadge supports all risk levels."""
        from opencode_monitor.dashboard.widgets import RiskBadge

        badge = RiskBadge(level, parent=widget_parent)
        assert level in RiskBadge.VARIANTS

    def test_invalid_level_fallback(self, qapp, widget_parent):
        """RiskBadge with invalid level uses fallback colors."""
        from opencode_monitor.dashboard.widgets import RiskBadge

        badge = RiskBadge("unknown", parent=widget_parent)
        # Should not raise
        assert badge.text() == "UNKNOWN"

    def test_is_badge_subclass(self, qapp, widget_parent):
        """RiskBadge is a Badge subclass."""
        from opencode_monitor.dashboard.widgets import RiskBadge, Badge

        badge = RiskBadge("high", parent=widget_parent)
        assert isinstance(badge, Badge)


# =============================================================================
# TypeBadge Tests
# =============================================================================


class TestTypeBadge:
    """Tests for TypeBadge widget."""

    def test_creation_basic(self, qapp, widget_parent):
        """TypeBadge can be created with operation type."""
        from opencode_monitor.dashboard.widgets import TypeBadge

        badge = TypeBadge("bash", parent=widget_parent)
        assert badge is not None

    @pytest.mark.parametrize(
        "op_type,expected_upper",
        [
            ("command", "COMMAND"),
            ("bash", "BASH"),
            ("read", "READ"),
            ("write", "WRITE"),
            ("edit", "EDIT"),
            ("webfetch", "WEBFETCH"),
            ("web_fetch", "WEB_FETCH"),
            ("glob", "GLOB"),
            ("grep", "GREP"),
            ("skill", "SKILL"),
        ],
    )
    def test_operation_types(self, qapp, widget_parent, op_type, expected_upper):
        """TypeBadge displays operation type in uppercase."""
        from opencode_monitor.dashboard.widgets import TypeBadge

        badge = TypeBadge(op_type, parent=widget_parent)
        assert badge.text() == expected_upper

    def test_case_insensitive(self, qapp, widget_parent):
        """TypeBadge handles case-insensitive operation types."""
        from opencode_monitor.dashboard.widgets import TypeBadge

        badge1 = TypeBadge("BASH", parent=widget_parent)
        badge2 = TypeBadge("bash", parent=widget_parent)
        badge3 = TypeBadge("Bash", parent=widget_parent)

        # All should display same text
        assert badge1.text() == "BASH"
        assert badge2.text() == "BASH"
        assert badge3.text() == "BASH"

    def test_invalid_type_fallback(self, qapp, widget_parent):
        """TypeBadge with unknown type uses fallback colors."""
        from opencode_monitor.dashboard.widgets import TypeBadge

        badge = TypeBadge("unknown_tool", parent=widget_parent)
        # Should not raise
        assert badge.text() == "UNKNOWN_TOOL"

    def test_is_badge_subclass(self, qapp, widget_parent):
        """TypeBadge is a Badge subclass."""
        from opencode_monitor.dashboard.widgets import TypeBadge, Badge

        badge = TypeBadge("read", parent=widget_parent)
        assert isinstance(badge, Badge)


# =============================================================================
# SegmentedControl Tests
# =============================================================================


class TestSegmentedControl:
    """Tests for SegmentedControl widget."""

    def test_creation_basic(self, qapp, widget_parent):
        """SegmentedControl can be created with options."""
        from opencode_monitor.dashboard.widgets import SegmentedControl

        control = SegmentedControl(["Day", "Week", "Month"], parent=widget_parent)
        assert control is not None

    def test_options_count(self, qapp, widget_parent):
        """SegmentedControl creates correct number of buttons."""
        from opencode_monitor.dashboard.widgets import SegmentedControl

        options = ["A", "B", "C", "D"]
        control = SegmentedControl(options, parent=widget_parent)
        assert len(control._buttons) == 4

    def test_initial_selection(self, qapp, widget_parent):
        """SegmentedControl selects first option by default."""
        from opencode_monitor.dashboard.widgets import SegmentedControl

        control = SegmentedControl(["First", "Second"], parent=widget_parent)
        assert control.current_index() == 0
        assert control._buttons[0].isChecked()

    def test_set_current_index(self, qapp, widget_parent):
        """SegmentedControl.set_current_index changes selection."""
        from opencode_monitor.dashboard.widgets import SegmentedControl

        control = SegmentedControl(["A", "B", "C"], parent=widget_parent)
        control.set_current_index(2)
        assert control.current_index() == 2
        assert control._buttons[2].isChecked()

    def test_set_current_index_out_of_bounds(self, qapp, widget_parent):
        """SegmentedControl ignores out-of-bounds index."""
        from opencode_monitor.dashboard.widgets import SegmentedControl

        control = SegmentedControl(["A", "B"], parent=widget_parent)
        control.set_current_index(10)  # Out of bounds
        # Should remain unchanged
        assert control.current_index() == 0

    def test_set_current_index_negative(self, qapp, widget_parent):
        """SegmentedControl ignores negative index."""
        from opencode_monitor.dashboard.widgets import SegmentedControl

        control = SegmentedControl(["A", "B"], parent=widget_parent)
        control.set_current_index(1)
        control.set_current_index(-1)  # Negative
        # Should remain unchanged (at 1)
        assert control.current_index() == 1

    def test_selection_changed_signal(self, qapp, widget_parent):
        """SegmentedControl emits selection_changed signal."""
        from opencode_monitor.dashboard.widgets import SegmentedControl

        control = SegmentedControl(["A", "B", "C"], parent=widget_parent)

        # Track signal emissions
        signal_received = []
        control.selection_changed.connect(lambda idx: signal_received.append(idx))

        # Change selection
        control.set_current_index(2)

        assert len(signal_received) == 1
        assert signal_received[0] == 2

    def test_clicking_same_button_no_signal(self, qapp, widget_parent):
        """Clicking already selected button doesn't emit signal."""
        from opencode_monitor.dashboard.widgets import SegmentedControl

        control = SegmentedControl(["A", "B"], parent=widget_parent)

        signal_count = []
        control.selection_changed.connect(lambda idx: signal_count.append(idx))

        # Click the already-selected first button
        control._on_button_clicked(0)

        # No signal should be emitted
        assert len(signal_count) == 0

    def test_buttons_are_checkable(self, qapp, widget_parent):
        """SegmentedControl buttons are checkable."""
        from opencode_monitor.dashboard.widgets import SegmentedControl

        control = SegmentedControl(["A", "B"], parent=widget_parent)
        for btn in control._buttons:
            assert btn.isCheckable()

    def test_only_one_checked(self, qapp, widget_parent):
        """Only one button is checked at a time."""
        from opencode_monitor.dashboard.widgets import SegmentedControl

        control = SegmentedControl(["A", "B", "C"], parent=widget_parent)

        for i in range(3):
            control.set_current_index(i)
            checked_count = sum(1 for btn in control._buttons if btn.isChecked())
            assert checked_count == 1


# =============================================================================
# DataTable Tests
# =============================================================================


class TestDataTable:
    """Tests for DataTable widget."""

    def test_creation_basic(self, qapp, widget_parent):
        """DataTable can be created with headers."""
        from opencode_monitor.dashboard.widgets import DataTable

        table = DataTable(["Name", "Value", "Status"], parent=widget_parent)
        assert table is not None

    def test_column_count(self, qapp, widget_parent):
        """DataTable has correct column count."""
        from opencode_monitor.dashboard.widgets import DataTable

        headers = ["Col1", "Col2", "Col3", "Col4"]
        table = DataTable(headers, parent=widget_parent)
        assert table.columnCount() == 4

    def test_initial_row_count(self, qapp, widget_parent):
        """DataTable starts with zero rows."""
        from opencode_monitor.dashboard.widgets import DataTable

        table = DataTable(["A", "B"], parent=widget_parent)
        assert table.rowCount() == 0

    def test_add_row_simple(self, qapp, widget_parent):
        """DataTable.add_row adds a row with string data."""
        from opencode_monitor.dashboard.widgets import DataTable

        table = DataTable(["Name", "Value"], parent=widget_parent)
        table.add_row(["Test", "123"])

        assert table.rowCount() == 1
        assert table.item(0, 0).text() == "Test"
        assert table.item(0, 1).text() == "123"

    def test_add_row_with_variant(self, qapp, widget_parent):
        """DataTable.add_row supports tuple (value, variant) format."""
        from opencode_monitor.dashboard.widgets import DataTable

        table = DataTable(["Status", "Risk"], parent=widget_parent)
        table.add_row([("BUSY", "status-busy"), ("HIGH", "risk-high")])

        assert table.rowCount() == 1
        assert table.item(0, 0).text() == "BUSY"
        assert table.item(0, 1).text() == "HIGH"

    def test_add_multiple_rows(self, qapp, widget_parent):
        """DataTable can add multiple rows."""
        from opencode_monitor.dashboard.widgets import DataTable

        table = DataTable(["ID", "Name"], parent=widget_parent)
        table.add_row(["1", "Alpha"])
        table.add_row(["2", "Beta"])
        table.add_row(["3", "Gamma"])

        assert table.rowCount() == 3

    def test_clear_data(self, qapp, widget_parent):
        """DataTable.clear_data removes all rows."""
        from opencode_monitor.dashboard.widgets import DataTable

        table = DataTable(["Col"], parent=widget_parent)
        table.add_row(["A"])
        table.add_row(["B"])
        assert table.rowCount() == 2

        table.clear_data()
        assert table.rowCount() == 0

    def test_row_height_constant(self, qapp, widget_parent):
        """DataTable has ROW_HEIGHT class constant."""
        from opencode_monitor.dashboard.widgets import DataTable

        assert hasattr(DataTable, "ROW_HEIGHT")
        assert DataTable.ROW_HEIGHT == 48

    def test_header_height_constant(self, qapp, widget_parent):
        """DataTable has HEADER_HEIGHT class constant."""
        from opencode_monitor.dashboard.widgets import DataTable

        assert hasattr(DataTable, "HEADER_HEIGHT")
        assert DataTable.HEADER_HEIGHT == 44

    def test_sorting_enabled(self, qapp, widget_parent):
        """DataTable has sorting enabled."""
        from opencode_monitor.dashboard.widgets import DataTable

        table = DataTable(["Col"], parent=widget_parent)
        assert table.isSortingEnabled()

    def test_items_not_editable(self, qapp, widget_parent):
        """DataTable items are not editable."""
        from opencode_monitor.dashboard.widgets import DataTable

        table = DataTable(["Col"], parent=widget_parent)
        table.add_row(["Value"])

        item = table.item(0, 0)
        # ItemIsEditable flag should NOT be set
        assert not (item.flags() & Qt.ItemFlag.ItemIsEditable)

    def test_add_row_with_tooltip(self, qapp, widget_parent):
        """DataTable.add_row sets tooltip for long values."""
        from opencode_monitor.dashboard.widgets import DataTable

        table = DataTable(["Path"], parent=widget_parent)
        long_path = "/very/long/path/to/some/deeply/nested/file.txt"
        table.add_row([long_path], full_values=[long_path])

        item = table.item(0, 0)
        # Tooltip should be set for long values (> 30 chars)
        assert item.toolTip() == long_path

    @pytest.mark.parametrize(
        "variant,color_key",
        [
            ("status-busy", "success"),
            ("status-idle", "text_muted"),
            ("risk-critical", "risk_critical"),
            ("risk-high", "risk_high"),
            ("risk-medium", "risk_medium"),
            ("risk-low", "risk_low"),
            ("type-command", "type_command"),
            ("type-bash", "type_bash"),
            ("type-read", "type_read"),
            ("type-write", "type_write"),
        ],
    )
    def test_variant_colors(self, qapp, widget_parent, variant, color_key):
        """DataTable applies correct colors for variants."""
        from opencode_monitor.dashboard.widgets import DataTable
        from opencode_monitor.dashboard.styles import COLORS

        table = DataTable(["Col"], parent=widget_parent)
        table.add_row([("Value", variant)])

        item = table.item(0, 0)
        expected_color = QColor(COLORS[color_key])
        assert item.foreground().color() == expected_color


# =============================================================================
# SectionHeader Tests
# =============================================================================


class TestSectionHeader:
    """Tests for SectionHeader widget."""

    def test_creation_basic(self, qapp, widget_parent):
        """SectionHeader can be created with title."""
        from opencode_monitor.dashboard.widgets import SectionHeader

        header = SectionHeader("Sessions", parent=widget_parent)
        assert header is not None

    def test_creation_with_subtitle(self, qapp, widget_parent):
        """SectionHeader can be created with title and subtitle."""
        from opencode_monitor.dashboard.widgets import SectionHeader

        header = SectionHeader(
            "Sessions", subtitle="Active monitoring", parent=widget_parent
        )
        assert header is not None
        assert header._title.text() == "Sessions"
        assert header._subtitle.text() == "Active monitoring"

    def test_title_text(self, qapp, widget_parent):
        """SectionHeader displays correct title."""
        from opencode_monitor.dashboard.widgets import SectionHeader

        header = SectionHeader("My Title", parent=widget_parent)
        assert header._title.text() == "My Title"

    def test_no_subtitle_attribute(self, qapp, widget_parent):
        """SectionHeader without subtitle has no _subtitle attribute."""
        from opencode_monitor.dashboard.widgets import SectionHeader

        header = SectionHeader("Title Only", parent=widget_parent)
        assert not hasattr(header, "_subtitle")

    def test_add_action(self, qapp, widget_parent):
        """SectionHeader.add_action adds widget to actions layout."""
        from opencode_monitor.dashboard.widgets import SectionHeader

        header = SectionHeader("Title", parent=widget_parent)
        button = QPushButton("Action", parent=widget_parent)
        header.add_action(button)

        # Check the actions layout has the widget
        assert header._actions_layout.count() == 1


# =============================================================================
# Badge Base Class Tests
# =============================================================================


class TestBadge:
    """Tests for Badge base class."""

    def test_creation(self, qapp, widget_parent):
        """Badge can be created directly."""
        from opencode_monitor.dashboard.widgets import Badge

        badge = Badge("test", "#ff0000", "#ffffff", parent=widget_parent)
        assert badge is not None

    def test_text_uppercase(self, qapp, widget_parent):
        """Badge displays text in uppercase."""
        from opencode_monitor.dashboard.widgets import Badge

        badge = Badge("hello", "#000", "#fff", parent=widget_parent)
        assert badge.text() == "HELLO"

    def test_is_qlabel(self, qapp, widget_parent):
        """Badge is a QLabel subclass."""
        from opencode_monitor.dashboard.widgets import Badge

        badge = Badge("test", "#000", "#fff", parent=widget_parent)
        assert isinstance(badge, QLabel)


# =============================================================================
# MetricsRow Tests
# =============================================================================


class TestMetricsRow:
    """Tests for MetricsRow widget."""

    def test_creation(self, qapp, widget_parent):
        """MetricsRow can be created."""
        from opencode_monitor.dashboard.widgets import MetricsRow

        row = MetricsRow(parent=widget_parent)
        assert row is not None

    def test_add_metric(self, qapp, widget_parent):
        """MetricsRow.add_metric adds a MetricCard."""
        from opencode_monitor.dashboard.widgets import MetricsRow, MetricCard

        row = MetricsRow(parent=widget_parent)
        card = row.add_metric("sessions", "5", "Sessions")

        assert isinstance(card, MetricCard)
        assert "sessions" in row._cards

    def test_update_metric(self, qapp, widget_parent):
        """MetricsRow.update_metric updates card value."""
        from opencode_monitor.dashboard.widgets import MetricsRow

        row = MetricsRow(parent=widget_parent)
        row.add_metric("count", "0", "Count")
        row.update_metric("count", "100")

        assert row._cards["count"]._value_label.text() == "100"

    def test_update_nonexistent_metric(self, qapp, widget_parent):
        """MetricsRow.update_metric ignores nonexistent keys."""
        from opencode_monitor.dashboard.widgets import MetricsRow

        row = MetricsRow(parent=widget_parent)
        # Should not raise
        row.update_metric("nonexistent", "value")

    def test_add_stretch(self, qapp, widget_parent):
        """MetricsRow.add_stretch adds stretch to layout."""
        from opencode_monitor.dashboard.widgets import MetricsRow

        row = MetricsRow(parent=widget_parent)
        row.add_stretch()
        # Should not raise
        assert row._layout is not None
