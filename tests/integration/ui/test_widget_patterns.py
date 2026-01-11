import pytest
from PyQt6.QtWidgets import QWidget, QLabel, QPushButton, QVBoxLayout
from PyQt6.QtCore import pyqtSignal, QObject, Qt


class DataProvider(QObject):
    data_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._data = ""

    def set_data(self, value: str):
        self._data = value
        self.data_changed.emit(value)

    def get_data(self) -> str:
        return self._data


class SimpleWidget(QWidget):
    def __init__(self, data_provider: DataProvider):
        super().__init__()
        self.data_provider = data_provider

        self.label = QLabel("No data")
        self.button = QPushButton("Update")

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.button)
        self.setLayout(layout)

        self.data_provider.data_changed.connect(self._on_data_changed)
        self.button.clicked.connect(lambda: self.data_provider.set_data("Updated"))

    def _on_data_changed(self, value: str):
        self.label.setText(value)


class TestWidgetWithDependencyInjection:
    def test_widget_receives_injected_dependency(self, qtbot):
        provider = DataProvider()
        widget = SimpleWidget(data_provider=provider)
        qtbot.addWidget(widget)

        assert widget.data_provider is provider

    def test_widget_updates_when_data_changes(self, qtbot):
        provider = DataProvider()
        widget = SimpleWidget(data_provider=provider)
        qtbot.addWidget(widget)

        provider.set_data("New value")

        qtbot.waitUntil(lambda: widget.label.text() == "New value")
        assert widget.label.text() == "New value"

    def test_button_click_triggers_data_update(self, qtbot):
        provider = DataProvider()
        widget = SimpleWidget(data_provider=provider)
        qtbot.addWidget(widget)

        qtbot.mouseClick(widget.button, Qt.MouseButton.LeftButton)

        qtbot.waitUntil(lambda: provider.get_data() == "Updated")
        assert widget.label.text() == "Updated"

    def test_signal_emission_via_waitSignal(self, qtbot):
        provider = DataProvider()
        widget = SimpleWidget(data_provider=provider)
        qtbot.addWidget(widget)

        with qtbot.waitSignal(provider.data_changed, timeout=1000) as blocker:
            provider.set_data("Signal test")

        assert blocker.signal_triggered
        assert blocker.args == ["Signal test"]


class TestWidgetLifecycle:
    def test_widget_initialization(self, qtbot):
        provider = DataProvider()
        widget = SimpleWidget(data_provider=provider)
        qtbot.addWidget(widget)

        assert widget.isVisible() is False
        widget.show()
        assert widget.isVisible()

    def test_widget_remains_functional_after_show(self, qtbot):
        provider = DataProvider()
        widget = SimpleWidget(data_provider=provider)
        qtbot.addWidget(widget)

        widget.show()
        qtbot.waitExposed(widget)

        provider.set_data("After show")
        qtbot.waitUntil(lambda: widget.label.text() == "After show")
        assert widget.label.text() == "After show"


class TestWidgetWithAssertions:
    def test_wait_until_with_assertion(self, qtbot):
        provider = DataProvider()
        widget = SimpleWidget(data_provider=provider)
        qtbot.addWidget(widget)

        provider.set_data("Test value")

        def check_label():
            assert widget.label.text() == "Test value"

        qtbot.waitUntil(check_label, timeout=1000)

    def test_multiple_updates_reflected(self, qtbot):
        provider = DataProvider()
        widget = SimpleWidget(data_provider=provider)
        qtbot.addWidget(widget)

        values = ["First", "Second", "Third"]
        for value in values:
            provider.set_data(value)
            qtbot.waitUntil(lambda v=value: widget.label.text() == v)

        assert widget.label.text() == "Third"
