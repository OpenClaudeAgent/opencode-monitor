import pytest

from ..fixtures import process_qt_events
from ..conftest import SECTION_TRACING, SECTION_MONITORING
from ..fixtures import MockAPIResponses

pytestmark = [
    pytest.mark.integration,
    pytest.mark.xdist_group(name="qt_tracing"),
]


class TestTracingDataPersistence:
    def test_data_persists_after_navigation(self, dashboard_window, qtbot, click_nav):
        click_nav(dashboard_window, SECTION_TRACING)

        tracing = dashboard_window._tracing
        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.waitUntil(lambda: tracing._model.rowCount() > 0, timeout=3000)

        initial_count = tracing._model.rowCount()

        click_nav(dashboard_window, SECTION_MONITORING)
        click_nav(dashboard_window, SECTION_TRACING)

        assert tracing._model.rowCount() == initial_count


class TestTracingSignals:
    def test_double_click_emits_open_terminal_signal(
        self, dashboard_window, qtbot, click_nav
    ):
        click_nav(dashboard_window, SECTION_TRACING)

        tracing = dashboard_window._tracing

        signals_received = []
        tracing.open_terminal_requested.connect(
            lambda sid: signals_received.append(sid)
        )

        data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.waitUntil(lambda: tracing._model.rowCount() > 0, timeout=3000)

        index = tracing._model.index(0, 0)
        assert index.isValid()

        tracing._on_index_double_clicked(index)
        process_qt_events()

        assert len(signals_received) == 1
        assert signals_received[0] == "sess-root-001"


class TestTracingPagination:
    def test_can_fetch_more_when_has_more(self, dashboard_window, qtbot, click_nav):
        click_nav(dashboard_window, SECTION_TRACING)

        tracing = dashboard_window._tracing
        model = tracing._model

        data = MockAPIResponses.realistic_tracing()
        data["meta"] = {"has_more": True}
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.waitUntil(lambda: model.rowCount() > 0, timeout=3000)

        from PyQt6.QtCore import QModelIndex

        assert model.canFetchMore(QModelIndex()) == True

    def test_cannot_fetch_more_when_no_more(self, dashboard_window, qtbot, click_nav):
        click_nav(dashboard_window, SECTION_TRACING)

        tracing = dashboard_window._tracing
        model = tracing._model

        data = MockAPIResponses.realistic_tracing()
        data["meta"] = {"has_more": False}
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.waitUntil(lambda: model.rowCount() > 0, timeout=3000)

        from PyQt6.QtCore import QModelIndex

        assert model.canFetchMore(QModelIndex()) == False

    def test_append_data_increases_row_count(self, dashboard_window, qtbot, click_nav):
        click_nav(dashboard_window, SECTION_TRACING)

        tracing = dashboard_window._tracing

        initial_data = MockAPIResponses.realistic_tracing()
        dashboard_window._signals.tracing_updated.emit(initial_data)
        qtbot.waitUntil(lambda: tracing._model.rowCount() > 0, timeout=3000)

        append_data = {
            "session_hierarchy": [
                {
                    "node_type": "session",
                    "session_id": "sess-append-001",
                    "directory": "/test/append",
                    "children": [],
                }
            ],
            "meta": {"has_more": False, "limit": 50, "offset": 1, "count": 1},
            "is_append": True,
        }
        dashboard_window._signals.tracing_updated.emit(append_data)
        qtbot.waitUntil(lambda: tracing._model.rowCount() == 2, timeout=3000)

    def test_fetch_more_emits_signal(self, dashboard_window, qtbot, click_nav):
        click_nav(dashboard_window, SECTION_TRACING)

        tracing = dashboard_window._tracing
        model = tracing._model

        signals_received = []
        tracing.load_more_requested.connect(
            lambda offset, limit: signals_received.append((offset, limit))
        )

        data = MockAPIResponses.realistic_tracing()
        data["meta"] = {"has_more": True}
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.waitUntil(lambda: model.rowCount() > 0, timeout=3000)

        from PyQt6.QtCore import QModelIndex

        model.fetchMore(QModelIndex())
        process_qt_events()

        assert len(signals_received) == 1
        assert signals_received[0][0] == 1  # offset = total_loaded
        assert signals_received[0][1] == 80  # page_size

    def test_scroll_to_bottom_triggers_fetch_more(
        self, dashboard_window, qtbot, click_nav
    ):
        click_nav(dashboard_window, SECTION_TRACING)

        tracing = dashboard_window._tracing
        model = tracing._model
        tree = tracing._tree

        signals_received = []
        tracing.load_more_requested.connect(
            lambda offset, limit: signals_received.append((offset, limit))
        )

        data = MockAPIResponses.realistic_tracing()
        data["meta"] = {"has_more": True}
        dashboard_window._signals.tracing_updated.emit(data)
        qtbot.waitUntil(lambda: model.rowCount() > 0, timeout=3000)

        last_index = model.index(model.rowCount() - 1, 0)
        tree.scrollTo(last_index)
        process_qt_events()

        qtbot.waitUntil(lambda: len(signals_received) > 0, timeout=2000)

        assert len(signals_received) >= 1
        assert signals_received[0][0] == 1  # offset = total_loaded
        assert signals_received[0][1] == 80  # page_size
