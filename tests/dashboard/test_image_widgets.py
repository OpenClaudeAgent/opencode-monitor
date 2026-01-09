"""Tests for image-related widgets and cache."""

import pytest
import base64
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import Qt


# Minimal valid 1x1 red PNG for testing
MINIMAL_PNG_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
VALID_PNG_DATA_URL = f"data:image/png;base64,{MINIMAL_PNG_BASE64}"
INVALID_DATA_URL = "not-a-data-url"


class TestImageThumbnail:
    """Tests for ImageThumbnail widget."""

    def test_valid_image_shows_widget(self, qtbot):
        """Widget should be visible when valid image is set."""
        from opencode_monitor.dashboard.sections.tracing.image_widgets import (
            ImageThumbnail,
        )

        thumb = ImageThumbnail()
        qtbot.addWidget(thumb)
        thumb.set_image_url(VALID_PNG_DATA_URL)

        assert thumb.isVisible()
        assert thumb.pixmap() is not None

    def test_invalid_url_hides_widget(self, qtbot):
        """Widget should be hidden for invalid URL."""
        from opencode_monitor.dashboard.sections.tracing.image_widgets import (
            ImageThumbnail,
        )

        thumb = ImageThumbnail()
        qtbot.addWidget(thumb)
        thumb.set_image_url(INVALID_DATA_URL)

        assert not thumb.isVisible()

    def test_empty_url_hides_widget(self, qtbot):
        """Widget should be hidden for empty URL."""
        from opencode_monitor.dashboard.sections.tracing.image_widgets import (
            ImageThumbnail,
        )

        thumb = ImageThumbnail()
        qtbot.addWidget(thumb)
        thumb.set_image_url("")

        assert not thumb.isVisible()

    def test_none_url_hides_widget(self, qtbot):
        """Widget should be hidden for None URL."""
        from opencode_monitor.dashboard.sections.tracing.image_widgets import (
            ImageThumbnail,
        )

        thumb = ImageThumbnail()
        qtbot.addWidget(thumb)
        thumb.set_image_url(None)

        assert not thumb.isVisible()

    def test_data_url_property(self, qtbot):
        """Should return the stored data URL."""
        from opencode_monitor.dashboard.sections.tracing.image_widgets import (
            ImageThumbnail,
        )

        thumb = ImageThumbnail()
        qtbot.addWidget(thumb)
        thumb.set_image_url(VALID_PNG_DATA_URL)

        assert thumb.data_url() == VALID_PNG_DATA_URL

    def test_click_emits_signal(self, qtbot):
        """Click should emit signal with data URL."""
        from opencode_monitor.dashboard.sections.tracing.image_widgets import (
            ImageThumbnail,
        )

        thumb = ImageThumbnail()
        qtbot.addWidget(thumb)
        thumb.set_image_url(VALID_PNG_DATA_URL)

        with qtbot.waitSignal(thumb.clicked, timeout=1000) as blocker:
            qtbot.mouseClick(thumb, Qt.MouseButton.LeftButton)

        assert blocker.args[0] == VALID_PNG_DATA_URL

    def test_tooltip_shows_image_info(self, qtbot):
        """Tooltip should show image dimensions."""
        from opencode_monitor.dashboard.sections.tracing.image_widgets import (
            ImageThumbnail,
        )

        thumb = ImageThumbnail()
        qtbot.addWidget(thumb)
        thumb.set_image_url(VALID_PNG_DATA_URL)

        tooltip = thumb.toolTip()
        assert "Image:" in tooltip or "1x1" in tooltip

    def test_custom_size(self, qtbot):
        """Should respect custom size parameter."""
        from opencode_monitor.dashboard.sections.tracing.image_widgets import (
            ImageThumbnail,
        )

        custom_size = (64, 64)
        thumb = ImageThumbnail(size=custom_size)
        qtbot.addWidget(thumb)

        assert thumb.width() == custom_size[0]
        assert thumb.height() == custom_size[1]


class TestThumbnailCache:
    """Tests for ThumbnailCache."""

    def test_get_thumbnail_returns_none_for_uncached(self):
        """Should return None for uncached images."""
        from opencode_monitor.dashboard.sections.tracing.image_cache import (
            ThumbnailCache,
        )

        cache = ThumbnailCache()
        result = cache.get_thumbnail(VALID_PNG_DATA_URL)
        assert result is None

    def test_cache_stores_thumbnail(self):
        """Should store and retrieve thumbnails."""
        from opencode_monitor.dashboard.sections.tracing.image_cache import (
            ThumbnailCache,
        )
        from PyQt6.QtGui import QPixmap

        cache = ThumbnailCache()
        pixmap = QPixmap(10, 10)
        cache_key = cache._make_key(VALID_PNG_DATA_URL, (48, 48))

        cache._cache[cache_key] = pixmap
        result = cache.get_thumbnail(VALID_PNG_DATA_URL)

        assert result is not None

    def test_make_key_includes_size(self):
        """Cache key should include size for different resolutions."""
        from opencode_monitor.dashboard.sections.tracing.image_cache import (
            ThumbnailCache,
        )

        cache = ThumbnailCache()
        key1 = cache._make_key(VALID_PNG_DATA_URL, (48, 48))
        key2 = cache._make_key(VALID_PNG_DATA_URL, (128, 128))

        assert key1 != key2

    def test_clear_empties_cache(self):
        """Clear should remove all cached items."""
        from opencode_monitor.dashboard.sections.tracing.image_cache import (
            ThumbnailCache,
        )
        from PyQt6.QtGui import QPixmap

        cache = ThumbnailCache()
        cache._cache["test_key"] = QPixmap(10, 10)
        cache.clear()

        assert len(cache._cache) == 0


class TestImagePreviewDialog:
    """Tests for ImagePreviewDialog."""

    def test_dialog_creates_with_valid_image(self, qtbot):
        """Dialog should create successfully with valid image."""
        from opencode_monitor.dashboard.sections.tracing.image_widgets import (
            ImagePreviewDialog,
        )

        dialog = ImagePreviewDialog(VALID_PNG_DATA_URL)
        qtbot.addWidget(dialog)

        assert dialog is not None

    def test_escape_closes_dialog(self, qtbot):
        """ESC key should close the dialog."""
        from opencode_monitor.dashboard.sections.tracing.image_widgets import (
            ImagePreviewDialog,
        )
        from PyQt6.QtCore import Qt

        dialog = ImagePreviewDialog(VALID_PNG_DATA_URL)
        qtbot.addWidget(dialog)
        dialog.show()

        qtbot.keyClick(dialog, Qt.Key.Key_Escape)

        # Dialog should be closed (or closing)
        assert not dialog.isVisible()
