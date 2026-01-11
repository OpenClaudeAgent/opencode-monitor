"""Tests for FilesListWidget and ClickableLabel components."""

import pytest
from unittest.mock import MagicMock

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel


class TestClickableLabel:
    """Tests for ClickableLabel widget."""

    def test_emits_clicked_signal_on_mouse_press(self, qtbot):
        """Should emit clicked signal when mouse is pressed."""
        from opencode_monitor.dashboard.widgets.controls import ClickableLabel

        label = ClickableLabel("Test")
        qtbot.addWidget(label)

        with qtbot.waitSignal(label.clicked, timeout=1000):
            qtbot.mouseClick(label, Qt.MouseButton.LeftButton)

    def test_inherits_qlabel_functionality(self, qtbot):
        """Should support all QLabel methods."""
        from opencode_monitor.dashboard.widgets.controls import ClickableLabel

        label = ClickableLabel("Initial")
        qtbot.addWidget(label)

        assert label.text() == "Initial"
        label.setText("Updated")
        assert label.text() == "Updated"

    def test_can_connect_slot_to_clicked(self, qtbot):
        """Should allow connecting slots to clicked signal."""
        from opencode_monitor.dashboard.widgets.controls import ClickableLabel

        label = ClickableLabel("Click me")
        qtbot.addWidget(label)

        callback = MagicMock()
        label.clicked.connect(callback)

        qtbot.mouseClick(label, Qt.MouseButton.LeftButton)
        callback.assert_called_once()


class TestFilesListWidget:
    """Tests for FilesListWidget expand/collapse functionality."""

    def test_starts_collapsed_by_default(self, qtbot):
        """Widget should start in collapsed state."""
        from opencode_monitor.dashboard.sections.tracing.detail_panel.components.session_overview import (
            FilesListWidget,
        )

        widget = FilesListWidget()
        qtbot.addWidget(widget)

        assert widget._is_expanded is False

    def test_header_shows_chevron_down_when_collapsed(self, qtbot):
        """Header should show down chevron when collapsed."""
        from opencode_monitor.dashboard.sections.tracing.detail_panel.components.session_overview import (
            FilesListWidget,
        )

        widget = FilesListWidget()
        qtbot.addWidget(widget)

        files = {"edit": ["file1.py", "file2.py"]}
        widget.load_files(files)

        assert "▼" in widget._header.text()
        assert "▲" not in widget._header.text()

    def test_header_shows_chevron_up_when_expanded(self, qtbot):
        """Header should show up chevron when expanded."""
        from opencode_monitor.dashboard.sections.tracing.detail_panel.components.session_overview import (
            FilesListWidget,
        )

        widget = FilesListWidget()
        qtbot.addWidget(widget)

        files = {"edit": ["file1.py", "file2.py"]}
        widget.load_files(files)
        widget._toggle_expand()

        assert "▲" in widget._header.text()
        assert "▼" not in widget._header.text()

    def test_collapsed_shows_max_8_files(self, qtbot):
        """Collapsed state should show max 8 files."""
        from opencode_monitor.dashboard.sections.tracing.detail_panel.components.session_overview import (
            FilesListWidget,
        )

        widget = FilesListWidget()
        qtbot.addWidget(widget)

        files = {"edit": [f"file{i}.py" for i in range(15)]}
        widget.load_files(files)

        visible_labels = []
        for i in range(widget._container_layout.count()):
            w = widget._container_layout.itemAt(i).widget()
            if isinstance(w, QLabel) and w.text().startswith("✏️"):
                visible_labels.append(w)
        assert len(visible_labels) == 8

    def test_expanded_shows_all_files(self, qtbot):
        """Expanded state should show all files."""
        from opencode_monitor.dashboard.sections.tracing.detail_panel.components.session_overview import (
            FilesListWidget,
        )

        widget = FilesListWidget()
        qtbot.addWidget(widget)

        files = {"edit": [f"file{i}.py" for i in range(15)]}
        widget.load_files(files)
        widget._toggle_expand()

        visible_labels = []
        for i in range(widget._container_layout.count()):
            w = widget._container_layout.itemAt(i).widget()
            if isinstance(w, QLabel) and w.text().startswith("✏️"):
                visible_labels.append(w)
        assert len(visible_labels) == 15

    def test_collapsed_shows_more_indicator(self, qtbot):
        """Collapsed state should show '+N more...' when truncated."""
        from opencode_monitor.dashboard.sections.tracing.detail_panel.components.session_overview import (
            FilesListWidget,
        )

        widget = FilesListWidget()
        qtbot.addWidget(widget)

        files = {"edit": [f"file{i}.py" for i in range(15)]}
        widget.load_files(files)

        more_labels = []
        for i in range(widget._container_layout.count()):
            w = widget._container_layout.itemAt(i).widget()
            if isinstance(w, QLabel) and "more..." in w.text():
                more_labels.append(w)
        assert len(more_labels) == 1
        assert "+7 more..." in more_labels[0].text()

    def test_expanded_hides_more_indicator(self, qtbot):
        """Expanded state should not show '+N more...'."""
        from opencode_monitor.dashboard.sections.tracing.detail_panel.components.session_overview import (
            FilesListWidget,
        )

        widget = FilesListWidget()
        qtbot.addWidget(widget)

        files = {"edit": [f"file{i}.py" for i in range(15)]}
        widget.load_files(files)
        widget._toggle_expand()

        more_labels = []
        for i in range(widget._container_layout.count()):
            w = widget._container_layout.itemAt(i).widget()
            if isinstance(w, QLabel) and "more..." in w.text():
                more_labels.append(w)
        assert len(more_labels) == 0

    def test_toggle_changes_state(self, qtbot):
        """Toggle should flip expanded state."""
        from opencode_monitor.dashboard.sections.tracing.detail_panel.components.session_overview import (
            FilesListWidget,
        )

        widget = FilesListWidget()
        qtbot.addWidget(widget)

        files = {"edit": ["file1.py"]}
        widget.load_files(files)

        assert widget._is_expanded is False
        widget._toggle_expand()
        assert widget._is_expanded is True
        widget._toggle_expand()
        assert widget._is_expanded is False

    def test_header_shows_file_count(self, qtbot):
        """Header should display total file count."""
        from opencode_monitor.dashboard.sections.tracing.detail_panel.components.session_overview import (
            FilesListWidget,
        )

        widget = FilesListWidget()
        qtbot.addWidget(widget)

        files = {"edit": ["a.py", "b.py"], "read": ["c.py"]}
        widget.load_files(files)

        assert "(3)" in widget._header.text()

    def test_empty_files_shows_no_files_message(self, qtbot):
        """Empty files dict should show 'No files accessed'."""
        from opencode_monitor.dashboard.sections.tracing.detail_panel.components.session_overview import (
            FilesListWidget,
        )

        widget = FilesListWidget()
        qtbot.addWidget(widget)

        widget.load_files({})

        labels = []
        for i in range(widget._container_layout.count()):
            w = widget._container_layout.itemAt(i).widget()
            if isinstance(w, QLabel) and "No files accessed" in w.text():
                labels.append(w)
        assert len(labels) == 1

    def test_header_clickable_triggers_toggle(self, qtbot):
        """Clicking header should toggle expand/collapse."""
        from opencode_monitor.dashboard.sections.tracing.detail_panel.components.session_overview import (
            FilesListWidget,
        )

        widget = FilesListWidget()
        qtbot.addWidget(widget)

        files = {"edit": ["file1.py"]}
        widget.load_files(files)

        assert widget._is_expanded is False
        qtbot.mouseClick(widget._header, Qt.MouseButton.LeftButton)
        assert widget._is_expanded is True

    def test_prioritizes_edit_over_read(self, qtbot):
        """Should show edit files before read files."""
        from opencode_monitor.dashboard.sections.tracing.detail_panel.components.session_overview import (
            FilesListWidget,
        )

        widget = FilesListWidget()
        qtbot.addWidget(widget)

        files = {"read": ["read.py"], "edit": ["edit.py"]}
        widget.load_files(files)

        labels: list[str] = []
        for i in range(widget._container_layout.count()):
            w = widget._container_layout.itemAt(i).widget()
            if isinstance(w, QLabel):
                text = w.text()
                if text.startswith("✏️") or text.startswith("📖"):
                    labels.append(text)

        assert labels[0].startswith("✏️")
        assert labels[1].startswith("📖")
