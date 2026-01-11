import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication


@pytest.fixture
def click_nav(qtbot):
    def _click(dashboard_window, section_index: int) -> None:
        sidebar = dashboard_window._sidebar
        nav_items = sidebar._nav_items
        if 0 <= section_index < len(nav_items):
            qtbot.mouseClick(nav_items[section_index], Qt.MouseButton.LeftButton)
            QApplication.processEvents()

    return _click


@pytest.fixture
def click_tab(qtbot):
    def _click(tab_widget, tab_index: int) -> None:
        tab_bar = tab_widget.tabBar()
        tab_rect = tab_bar.tabRect(tab_index)
        qtbot.mouseClick(tab_bar, Qt.MouseButton.LeftButton, pos=tab_rect.center())
        QApplication.processEvents()

    return _click


@pytest.fixture
def select_first_session(qtbot):
    def _select(tracing):
        root_item = tracing._tree.topLevelItem(0)
        assert root_item is not None, "Expected at least one session in tree"
        tracing._tree.setCurrentItem(root_item)
        tracing._on_item_clicked(root_item, 0)
        QApplication.processEvents()
        return root_item

    return _select
