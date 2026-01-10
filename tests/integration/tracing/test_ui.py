"""
Integration tests for Tracing section UI basics.

Tests verify that:
- TracingSection structure is complete (tree, detail panel, empty state)
- Navigation works correctly
- Empty state displays with correct message
- Session list populates with data
"""

import pytest
from PyQt6.QtWidgets import QTreeWidget, QLabel

from opencode_monitor.dashboard.widgets import EmptyState
from opencode_monitor.dashboard.sections.tracing import TracingSection
from opencode_monitor.dashboard.sections.tracing.detail_panel import TraceDetailPanel

from ..conftest import SIGNAL_WAIT_MS, SECTION_TRACING
from ..fixtures import MockAPIResponses

pytestmark = pytest.mark.integration


class TestTracingSectionStructure:
    """Test that tracing section has all required components."""

    def test_tracing_section_structure(self, dashboard_window, qtbot, click_nav):
        """Verify tracing section structure: tree widget, detail panel, and navigation."""
        # 1. Tracing section exists and has correct type
        assert isinstance(dashboard_window._tracing, TracingSection), (
            f"_tracing should be TracingSection, got {type(dashboard_window._tracing).__name__}"
        )
        tracing = dashboard_window._tracing

        # 2. Tree widget exists and has correct type
        assert isinstance(tracing._tree, QTreeWidget), (
            f"_tree should be QTreeWidget, got {type(tracing._tree).__name__}"
        )
        assert tracing._tree.headerItem() is not None, "Tree should have headers"
        assert tracing._tree.columnCount() == 6, "Tree should have 6 columns"

        # 3. Detail panel exists and has correct type
        assert isinstance(tracing._detail_panel, TraceDetailPanel), (
            f"_detail_panel should be TraceDetailPanel, got {type(tracing._detail_panel).__name__}"
        )

        # 4. Empty state widget exists and has correct type
        assert isinstance(tracing._empty, EmptyState), (
            f"_empty should be EmptyState, got {type(tracing._empty).__name__}"
        )

        # 5. Navigation to tracing section works
        click_nav(dashboard_window, SECTION_TRACING)
        assert dashboard_window._pages.currentIndex() == SECTION_TRACING, (
            "Should navigate to tracing section"
        )


class TestTracingEmptyState:
    """Test tracing section empty state behavior."""

    def test_empty_state_displays_with_correct_message(
        self, dashboard_window, qtbot, click_nav
    ):
        """Empty state appears with correct message when no tracing data."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        # Emit empty tracing data
        empty_data = {"session_hierarchy": []}
        dashboard_window._signals.tracing_updated.emit(empty_data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # 1. Tree should be hidden
        assert tracing._tree.isHidden(), "Tree should be hidden with empty data"

        # 2. Empty state should be visible
        assert not tracing._empty.isHidden(), "Empty state should be visible"
        assert tracing._empty.isVisible(), (
            "Empty state should be visible in widget hierarchy"
        )

        # 3. Verify empty state contains correct message
        labels = tracing._empty.findChildren(QLabel)
        label_texts = [label.text() for label in labels]

        assert "No traces found" in label_texts, (
            f"Empty state should contain 'No traces found', got: {label_texts}"
        )
        assert any("task" in text.lower() for text in label_texts), (
            f"Empty state should mention 'task' tool, got: {label_texts}"
        )


class TestTracingSessionList:
    """Test session list display with data."""

    def test_tracing_section_shows_session_list_with_data(
        self, dashboard_window, qtbot, click_nav
    ):
        """Session tree populates when data is provided."""
        click_nav(dashboard_window, SECTION_TRACING)

        tracing = dashboard_window._tracing
        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Tree visible, empty state hidden
        assert tracing._tree.isHidden() is False
        assert tracing._empty.isHidden() is True

        # Fixture has exactly 1 root session
        assert tracing._tree.topLevelItemCount() == 1

    def test_session_tree_shows_hierarchy(self, dashboard_window, qtbot, click_nav):
        """Session tree displays hierarchical structure matching fixture data."""
        click_nav(dashboard_window, SECTION_TRACING)

        tracing = dashboard_window._tracing
        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Root: project "my-project" from fixture directory "/home/dev/my-project"
        root_item = tracing._tree.topLevelItem(0)
        assert root_item.text(0) == "🌳 my-project"

        # Fixture has 2 delegation children
        assert root_item.childCount() == 2

        # Verify delegation labels match fixture data exactly
        assert root_item.child(0).text(0) == "💬 user → executor"
        assert root_item.child(1).text(0) == "🔗 executor → tester"


class TestSessionOverviewPanelTokens:
    """Test SessionOverviewPanel token display."""

    def test_session_overview_panel_displays_tokens(
        self, dashboard_window, qtbot, click_nav
    ):
        """Test que le SessionOverviewPanel affiche bien tous les tokens."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        # Given: Une session avec des tokens connus
        data = {
            "session_hierarchy": [
                {
                    "session_id": "ses_test_tokens",
                    "title": "Test Session",
                    "started_at": "2024-01-10T10:00:00Z",
                    "duration_seconds": 120,
                    "tokens": {
                        "input": 175,
                        "output": 4747,
                        "cache_read": 658693,
                        "cache_write": 61035,
                        "total": 724650,
                    },
                    "children": [],
                }
            ]
        }

        # When: On charge les données et sélectionne la session
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        root_item = tracing._tree.topLevelItem(0)
        tracing._tree.setCurrentItem(root_item)
        tracing._on_item_clicked(root_item, 0)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Then: Vérifier que le panel overview contient un widget tokens
        detail_panel = tracing._detail_panel
        overview_panel = detail_panel._session_overview

        # Le panel overview doit avoir un widget _tokens
        assert hasattr(overview_panel, "_tokens"), (
            "Overview panel should have _tokens widget"
        )

        # Le widget tokens doit être visible (non caché)
        tokens_widget = overview_panel._tokens
        assert tokens_widget is not None, "Tokens widget should exist"
        assert tokens_widget.isVisible() or not tokens_widget.isHidden(), (
            "Tokens widget should be visible"
        )

        # Vérifier que les labels contiennent les tokens (via findChildren)
        labels = tokens_widget.findChildren(QLabel)
        label_texts = [label.text() for label in labels]

        # On s'attend à trouver les tokens formatés dans les labels
        # Note: format_tokens_short() convertit 175 -> "175", 4747 -> "4.7K", etc.
        assert any("Input" in text for text in label_texts), (
            f"Should display Input tokens, got labels: {label_texts}"
        )
        assert any("Output" in text for text in label_texts), (
            f"Should display Output tokens, got labels: {label_texts}"
        )
        assert any("Cache Read" in text for text in label_texts), (
            f"Should display Cache Read tokens, got labels: {label_texts}"
        )
        assert any("Cache Write" in text for text in label_texts), (
            f"Should display Cache Write tokens, got labels: {label_texts}"
        )
        assert any("Total" in text for text in label_texts), (
            f"Should display Total tokens, got labels: {label_texts}"
        )

    def test_session_overview_panel_displays_agents(
        self, dashboard_window, qtbot, click_nav
    ):
        """Test que le panel affiche bien les agents."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        # Given: Une session avec 3 agents "build"
        data = {
            "session_hierarchy": [
                {
                    "session_id": "ses_test_agents",
                    "title": "Test Session",
                    "started_at": "2024-01-10T10:00:00Z",
                    "duration_seconds": 120,
                    "tokens": {"input": 100, "output": 200, "total": 300},
                    "children": [
                        {
                            "node_type": "user_turn",
                            "agent": "build",
                            "prompt_input": "Build the project",
                            "children": [],
                        },
                        {
                            "node_type": "user_turn",
                            "agent": "build",
                            "prompt_input": "Build again",
                            "children": [],
                        },
                        {
                            "node_type": "user_turn",
                            "agent": "build",
                            "prompt_input": "Final build",
                            "children": [],
                        },
                    ],
                }
            ]
        }

        # When: On charge les données et sélectionne la session
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        root_item = tracing._tree.topLevelItem(0)
        tracing._tree.setCurrentItem(root_item)
        tracing._on_item_clicked(root_item, 0)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Then: Vérifier que le panel overview affiche les agents
        detail_panel = tracing._detail_panel
        overview_panel = detail_panel._session_overview
        agents_widget = overview_panel._agents

        # Le widget agents doit exister et être visible
        assert agents_widget is not None
        assert agents_widget.isVisible() or not agents_widget.isHidden()

        # Vérifier le header affiche le count
        header_text = agents_widget._header.text()
        assert "Agents" in header_text
        assert "(3)" in header_text, f"Should show count (3), got: {header_text}"

    def test_session_overview_panel_displays_tools(
        self, dashboard_window, qtbot, click_nav
    ):
        """Test que le panel affiche bien les outils."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        # Given: Une session avec bash(7x) et webfetch(3x)
        data = {
            "session_hierarchy": [
                {
                    "session_id": "ses_test_tools",
                    "title": "Test Session",
                    "started_at": "2024-01-10T10:00:00Z",
                    "duration_seconds": 120,
                    "tokens": {"input": 100, "output": 200, "total": 300},
                    "children": [
                        # 7 bash tools
                        *[
                            {
                                "node_type": "tool",
                                "tool_name": "mcp_bash",
                                "display_info": f"bash command {i}",
                                "status": "success",
                            }
                            for i in range(7)
                        ],
                        # 3 webfetch tools
                        *[
                            {
                                "node_type": "tool",
                                "tool_name": "mcp_webfetch",
                                "display_info": f"fetch url {i}",
                                "status": "success",
                            }
                            for i in range(3)
                        ],
                    ],
                }
            ]
        }

        # When: On charge les données et sélectionne la session
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        root_item = tracing._tree.topLevelItem(0)
        tracing._tree.setCurrentItem(root_item)
        tracing._on_item_clicked(root_item, 0)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Then: Vérifier que le panel overview affiche les tools
        detail_panel = tracing._detail_panel
        overview_panel = detail_panel._session_overview
        tools_widget = overview_panel._tools

        # Le widget tools doit exister et être visible
        assert tools_widget is not None
        assert tools_widget.isVisible() or not tools_widget.isHidden()

        # Vérifier le header affiche le total count
        header_text = tools_widget._header.text()
        assert "Tools" in header_text
        assert "(10)" in header_text, (
            f"Should show total count (10), got: {header_text}"
        )

        # Vérifier que les labels contiennent bash et webfetch avec counts
        labels = tools_widget.findChildren(QLabel)
        label_texts = [label.text() for label in labels]

        assert any("bash" in text and "7" in text for text in label_texts), (
            f"Should display bash (7×), got: {label_texts}"
        )
        assert any("webfetch" in text and "3" in text for text in label_texts), (
            f"Should display webfetch (3×), got: {label_texts}"
        )

    def test_session_overview_panel_displays_timeline(
        self, dashboard_window, qtbot, click_nav
    ):
        """Test que le panel affiche bien la timeline."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        # Given: Une session avec 3 exchanges
        data = {
            "session_hierarchy": [
                {
                    "session_id": "ses_test_timeline",
                    "title": "Test Session",
                    "started_at": "2024-01-10T10:00:00Z",
                    "duration_seconds": 120,
                    "tokens": {"input": 100, "output": 200, "total": 300},
                    "children": [
                        {
                            "node_type": "user_turn",
                            "prompt_input": "Fix the auth bug",
                            "started_at": "2024-01-10T10:30:00Z",
                            "agent": "dev",
                            "children": [],
                        },
                        {
                            "node_type": "user_turn",
                            "prompt_input": "Now update the tests",
                            "started_at": "2024-01-10T10:32:00Z",
                            "agent": "tester",
                            "children": [],
                        },
                        {
                            "node_type": "user_turn",
                            "prompt_input": "Run the full test suite",
                            "started_at": "2024-01-10T10:35:00Z",
                            "agent": "tester",
                            "children": [],
                        },
                    ],
                }
            ]
        }

        # When: On charge les données et sélectionne la session
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        root_item = tracing._tree.topLevelItem(0)
        tracing._tree.setCurrentItem(root_item)
        tracing._on_item_clicked(root_item, 0)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Then: Vérifier que le panel overview affiche la timeline
        detail_panel = tracing._detail_panel
        overview_panel = detail_panel._session_overview
        timeline_widget = overview_panel._timeline

        # Le widget timeline doit exister et être visible
        assert timeline_widget is not None
        assert timeline_widget.isVisible() or not timeline_widget.isHidden()

        # Vérifier que la liste contient les 3 exchanges
        list_widget = timeline_widget._list
        assert list_widget.count() == 3, (
            f"Should have 3 exchanges, got {list_widget.count()}"
        )

        # Vérifier le contenu des exchanges
        exchange_texts = [
            list_widget.item(i).text() for i in range(list_widget.count())
        ]

        assert any("Fix the auth bug" in text for text in exchange_texts), (
            f"Should display first exchange, got: {exchange_texts}"
        )
        assert any("Now update the tests" in text for text in exchange_texts), (
            f"Should display second exchange, got: {exchange_texts}"
        )
        assert any("Run the full test suite" in text for text in exchange_texts), (
            f"Should display third exchange, got: {exchange_texts}"
        )
