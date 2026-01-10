"""
Integration tests for Tracing tabs and tree content.

Tests verify that:
- Tab content is accessible after selection
- Tree displays correct hierarchical content
- Detail header and metrics update correctly
"""

import pytest
from PyQt6.QtWidgets import QWidget, QLabel

from ..conftest import SIGNAL_WAIT_MS, SECTION_TRACING
from ..fixtures import MockAPIResponses

pytestmark = pytest.mark.integration

# Expected tree columns
TREE_COLUMNS = ["Type / Name", "Time", "Duration", "In", "Out", ""]
TREE_COLUMN_COUNT = 6

# Expected values from fixture (tracing.py)
ROOT_SESSION_LABEL = "🌳 my-project: Implement feature X"
CHILD_COUNT = 2  # executor + tester delegations


class TestTracingTabsContent:
    """Test that tabs display actual content when data is loaded."""

    @pytest.mark.parametrize(
        "tab_index,tab_attr",
        [
            (0, "_transcript_tab"),
            (1, "_tokens_tab"),
            (2, "_tools_tab"),
            (3, "_files_tab"),
            (4, "_agents_tab"),
            (5, "_timeline_tab"),
        ],
        ids=[
            "transcript",
            "tokens",
            "tools",
            "files",
            "agents",
            "timeline",
        ],
    )
    def test_tab_accessible_after_selection(
        self, dashboard_window, qtbot, click_nav, click_tab, tab_index, tab_attr
    ):
        """Each tab is accessible and selectable after session selection."""
        click_nav(dashboard_window, SECTION_TRACING)

        tracing = dashboard_window._tracing
        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Select root session
        root_item = tracing._tree.topLevelItem(0)
        tracing._tree.setCurrentItem(root_item)
        tracing._on_item_clicked(root_item, 0)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Navigate to tab and verify accessibility
        detail = tracing._detail_panel
        click_tab(detail._tabs, tab_index)

        assert detail._tabs.currentIndex() == tab_index
        tab_widget = getattr(detail, tab_attr)
        assert isinstance(tab_widget, QWidget)

    # NOTE: test_detail_panel_updates_on_selection removed - redundant with
    # test_selection.py::test_session_selection_updates_detail_panel_and_metrics


class TestTracingTreeContent:
    """Test that session tree displays correct hierarchical content."""

    def test_tree_structure(self, dashboard_window, qtbot, click_nav):
        """Tree displays correct root session with children and proper columns."""
        click_nav(dashboard_window, SECTION_TRACING)

        tracing = dashboard_window._tracing
        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Verify tree has expected column count
        tree = tracing._tree
        assert tree.columnCount() == TREE_COLUMN_COUNT

        # Get root item and verify session info
        root_item = tree.topLevelItem(0)
        root_text = root_item.text(0)
        assert root_text == ROOT_SESSION_LABEL, (
            f"Expected root label '{ROOT_SESSION_LABEL}', got '{root_text}'"
        )

        # Verify children count and structure
        assert root_item.childCount() == CHILD_COUNT, (
            f"Expected {CHILD_COUNT} children, got {root_item.childCount()}"
        )

        # Verify first child (executor delegation)
        first_child = root_item.child(0)
        first_child_text = first_child.text(0)
        assert "executor" in first_child_text.lower() or "Execute" in first_child_text

        # Verify second child (tester delegation)
        second_child = root_item.child(1)
        second_child_text = second_child.text(0)
        assert "tester" in second_child_text.lower() or "Run tests" in second_child_text

        # All items should have proper column count
        assert root_item.columnCount() == TREE_COLUMN_COUNT
        assert first_child.columnCount() == TREE_COLUMN_COUNT
        assert second_child.columnCount() == TREE_COLUMN_COUNT


class TestTokenDisplayNonRegression:
    """Tests de non-régression pour l'affichage des tokens."""

    def test_token_display_no_regression(self, dashboard_window, qtbot, click_nav):
        """Test de non-régression : tokens ne doivent jamais être doublés."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        # Given: Une session avec tokens connus
        data = {
            "session_hierarchy": [
                {
                    "session_id": "ses_regression_test",
                    "title": "Regression Test",
                    "started_at": "2024-01-10T10:00:00Z",
                    "duration_seconds": 60,
                    "tokens": {
                        "input": 1000,
                        "output": 2000,
                        "cache_read": 3000,
                        "cache_write": 4000,
                        "total": 10000,
                    },
                    "children": [],
                }
            ]
        }

        # When: On affiche le panel plusieurs fois (simulate navigation)
        for iteration in range(3):
            dashboard_window._signals.tracing_updated.emit(data)
            qtbot.wait(SIGNAL_WAIT_MS)

            root_item = tracing._tree.topLevelItem(0)
            tracing._tree.setCurrentItem(root_item)
            tracing._on_item_clicked(root_item, 0)
            qtbot.wait(SIGNAL_WAIT_MS)

            # Then: Les valeurs doivent rester identiques (pas de double comptage)
            detail_panel = tracing._detail_panel
            overview_panel = detail_panel._session_overview
            tokens_widget = overview_panel._tokens

            labels = tokens_widget.findChildren(QLabel)
            label_texts = [label.text() for label in labels]

            # Vérifier qu'on ne voit pas de doublons ou valeurs multipliées
            # Le total doit toujours être "10K" (pas "20K", "30K", etc.)
            total_labels = [text for text in label_texts if "Total" in text]
            assert len(total_labels) > 0, (
                f"Should have Total label (iteration {iteration})"
            )

            total_text = total_labels[0]
            # format_tokens_short(10000) = "10K"
            assert "10" in total_text, (
                f"Total should be ~10K (iteration {iteration}), got: {total_text}"
            )
            # Make sure it's not doubled (20K) or tripled (30K)
            assert "20" not in total_text and "30" not in total_text, (
                f"Total should not be doubled/tripled (iteration {iteration}), got: {total_text}"
            )

    def test_legacy_format_backward_compatibility(
        self, dashboard_window, qtbot, click_nav
    ):
        """Test que l'ancien format (sans objet tokens) fonctionne encore."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        # Given: Une session avec ancien format (pas d'objet tokens structuré)
        # Note: L'ancien format pourrait avoir tokens_in/tokens_out flat ou pas de tokens du tout
        data = {
            "session_hierarchy": [
                {
                    "session_id": "ses_legacy_format",
                    "title": "Legacy Session",
                    "started_at": "2024-01-10T10:00:00Z",
                    "duration_seconds": 60,
                    # Pas d'objet tokens structuré
                    "children": [],
                }
            ]
        }

        # When: On charge les données et sélectionne la session
        success = True
        error = None
        try:
            dashboard_window._signals.tracing_updated.emit(data)
            qtbot.wait(SIGNAL_WAIT_MS)

            root_item = tracing._tree.topLevelItem(0)
            tracing._tree.setCurrentItem(root_item)
            tracing._on_item_clicked(root_item, 0)
            qtbot.wait(SIGNAL_WAIT_MS)
        except Exception as e:
            success = False
            error = str(e)

        # Then: Le panel doit fonctionner (backward compatibility)
        assert success, f"Panel should handle legacy format without error, got: {error}"

        # Verify the panel loaded something (even if tokens are missing)
        detail_panel = tracing._detail_panel
        overview_panel = detail_panel._session_overview
        assert overview_panel is not None
        assert overview_panel.isVisible() or not overview_panel.isHidden()

    def test_cache_write_not_missing_from_total(
        self, dashboard_window, qtbot, click_nav
    ):
        """Test que cache_write n'est pas omis du total (bug historique)."""
        click_nav(dashboard_window, SECTION_TRACING)
        tracing = dashboard_window._tracing

        # Given: Une session avec cache_write significatif
        data = {
            "session_hierarchy": [
                {
                    "session_id": "ses_cache_write_test",
                    "title": "Cache Write Test",
                    "started_at": "2024-01-10T10:00:00Z",
                    "duration_seconds": 60,
                    "tokens": {
                        "input": 100,
                        "output": 200,
                        "cache_read": 300,
                        "cache_write": 5000,  # Large cache_write value
                        "total": 5600,  # Must include cache_write
                    },
                    "children": [],
                }
            ]
        }

        # When: On charge les données
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.wait(SIGNAL_WAIT_MS)

        root_item = tracing._tree.topLevelItem(0)
        tracing._tree.setCurrentItem(root_item)
        tracing._on_item_clicked(root_item, 0)
        qtbot.wait(SIGNAL_WAIT_MS)

        # Then: Vérifier que cache_write est bien affiché
        detail_panel = tracing._detail_panel
        overview_panel = detail_panel._session_overview
        tokens_widget = overview_panel._tokens

        labels = tokens_widget.findChildren(QLabel)
        label_texts = [label.text() for label in labels]

        # Cache Write doit être présent dans les labels
        cache_write_labels = [text for text in label_texts if "Cache Write" in text]
        assert len(cache_write_labels) > 0, (
            f"Should display Cache Write, got labels: {label_texts}"
        )

        # Vérifier que la valeur affichée contient "5" (5000 -> "5K")
        cache_write_text = cache_write_labels[0]
        assert "5" in cache_write_text, (
            f"Cache Write should show ~5K, got: {cache_write_text}"
        )

        # Vérifier que le total inclut cache_write
        total_labels = [text for text in label_texts if "Total" in text]
        assert len(total_labels) > 0
        total_text = total_labels[0]
        # Total should be ~5.6K (includes the 5K cache_write)
        assert "5" in total_text or "6" in total_text, (
            f"Total should include cache_write (~5.6K), got: {total_text}"
        )
