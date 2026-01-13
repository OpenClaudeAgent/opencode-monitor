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
    """Select the first session in the tracing tree (QTreeView/QAbstractItemModel API)."""

    def _select(tracing):
        model = tracing._model
        root_index = model.index(0, 0)
        assert root_index.isValid(), "Expected at least one session in tree"
        tracing._tree.setCurrentIndex(root_index)
        tracing._on_index_clicked(root_index)
        QApplication.processEvents()
        return root_index

    return _select
