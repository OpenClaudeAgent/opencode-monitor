"""
Navigation helpers for integration tests.

Provides functions to navigate the dashboard UI through
real clicks (simulating user interaction).
"""

import pytest

# Signal wait time for UI updates
SIGNAL_WAIT_MS = 200


@pytest.fixture
def click_nav(qtbot):
    """Helper to click sidebar navigation buttons.

    This simulates real user interaction by clicking on sidebar nav items
    instead of directly manipulating internal state.

    Usage:
        click_nav(dashboard_window, SECTION_MONITORING)
        click_nav(dashboard_window, SECTION_TRACING)
    """
    from PyQt6.QtCore import Qt

    def _click(dashboard_window, section_index: int) -> None:
        """Click on sidebar nav item to navigate to section.

        Args:
            dashboard_window: The dashboard window
            section_index: 0=Monitoring, 1=Security, 2=Analytics, 3=Tracing
        """
        sidebar = dashboard_window._sidebar
        nav_items = sidebar._nav_items
        if 0 <= section_index < len(nav_items):
            qtbot.mouseClick(nav_items[section_index], Qt.MouseButton.LeftButton)
            qtbot.wait(SIGNAL_WAIT_MS)

    return _click


@pytest.fixture
def click_tab(qtbot):
    """Helper to click on QTabWidget tabs.

    This simulates real user interaction by clicking on tab bar
    instead of directly calling setCurrentIndex().

    Usage:
        click_tab(detail._tabs, 0)  # Click first tab
        click_tab(detail._tabs, 1)  # Click second tab
    """
    from PyQt6.QtCore import Qt

    def _click(tab_widget, tab_index: int) -> None:
        """Click on a tab by index.

        Args:
            tab_widget: QTabWidget instance
            tab_index: Index of the tab to click
        """
        tab_bar = tab_widget.tabBar()
        tab_rect = tab_bar.tabRect(tab_index)
        qtbot.mouseClick(tab_bar, Qt.MouseButton.LeftButton, pos=tab_rect.center())
        qtbot.wait(SIGNAL_WAIT_MS)

    return _click


@pytest.fixture
def select_first_session(qtbot):
    """Helper to select first session in tracing tree.

    Eliminates duplication of session selection pattern across tests.
    Returns the selected root item for further assertions.

    Usage:
        def test_with_session(tracing_with_data, select_first_session):
            tracing, _ = tracing_with_data
            root_item = select_first_session(tracing)
            # Now session is selected, detail panel is updated
    """

    def _select(tracing):
        root_item = tracing._tree.topLevelItem(0)
        assert root_item is not None, "Expected at least one session in tree"
        tracing._tree.setCurrentItem(root_item)
        tracing._on_item_clicked(root_item, 0)
        qtbot.wait(SIGNAL_WAIT_MS)
        return root_item

    return _select
