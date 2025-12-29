"""
Tests for settings management module.
"""

import json
import pytest
from unittest.mock import patch, mock_open, MagicMock

from opencode_monitor.utils import settings
from opencode_monitor.utils.settings import Settings, get_settings, save_settings


class TestSettings:
    """Tests for Settings dataclass"""

    def test_default_values(self):
        """Settings should have correct default values"""
        s = Settings()
        assert s.usage_refresh_interval == 60

    def test_custom_values(self):
        """Settings can be initialized with custom values"""
        s = Settings(usage_refresh_interval=120)
        assert s.usage_refresh_interval == 120


class TestSettingsSave:
    """Tests for Settings.save() method"""

    def test_save_creates_directory_and_writes_file(self, tmp_path):
        """save() should create config directory and write JSON file"""
        config_dir = tmp_path / "config"
        config_file = config_dir / "settings.json"

        with (
            patch.object(settings, "CONFIG_DIR", str(config_dir)),
            patch.object(settings, "CONFIG_FILE", str(config_file)),
        ):
            s = Settings(usage_refresh_interval=90)
            s.save()

            # Verify directory was created
            assert config_dir.exists()

            # Verify file was written with correct content
            assert config_file.exists()
            with open(config_file) as f:
                data = json.load(f)
            assert data == {"usage_refresh_interval": 90}

    def test_save_overwrites_existing_file(self, tmp_path):
        """save() should overwrite existing config file"""
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "settings.json"
        config_file.write_text('{"usage_refresh_interval": 30}')

        with (
            patch.object(settings, "CONFIG_DIR", str(config_dir)),
            patch.object(settings, "CONFIG_FILE", str(config_file)),
        ):
            s = Settings(usage_refresh_interval=120)
            s.save()

            with open(config_file) as f:
                data = json.load(f)
            assert data == {"usage_refresh_interval": 120}


class TestSettingsLoad:
    """Tests for Settings.load() class method"""

    def test_load_returns_defaults_when_file_missing(self, tmp_path):
        """load() should return default settings when config file doesn't exist"""
        config_file = tmp_path / "nonexistent" / "settings.json"

        with patch.object(settings, "CONFIG_FILE", str(config_file)):
            s = Settings.load()
            assert s.usage_refresh_interval == 60

    def test_load_reads_existing_file(self, tmp_path):
        """load() should read and parse existing config file"""
        config_file = tmp_path / "settings.json"
        config_file.write_text('{"usage_refresh_interval": 45}')

        with patch.object(settings, "CONFIG_FILE", str(config_file)):
            s = Settings.load()
            assert s.usage_refresh_interval == 45

    def test_load_filters_obsolete_fields(self, tmp_path):
        """load() should ignore unknown/obsolete fields in config file"""
        config_file = tmp_path / "settings.json"
        config_file.write_text(
            json.dumps(
                {
                    "usage_refresh_interval": 30,
                    "obsolete_field": "should be ignored",
                    "another_old_setting": 999,
                }
            )
        )

        with patch.object(settings, "CONFIG_FILE", str(config_file)):
            s = Settings.load()
            assert s.usage_refresh_interval == 30
            assert not hasattr(s, "obsolete_field")
            assert not hasattr(s, "another_old_setting")

    def test_load_returns_defaults_on_invalid_json(self, tmp_path):
        """load() should return defaults when config file contains invalid JSON"""
        config_file = tmp_path / "settings.json"
        config_file.write_text("not valid json {{{")

        with patch.object(settings, "CONFIG_FILE", str(config_file)):
            s = Settings.load()
            assert s.usage_refresh_interval == 60

    def test_load_returns_defaults_on_read_error(self, tmp_path):
        """load() should return defaults when file read fails"""
        config_file = tmp_path / "settings.json"
        config_file.write_text('{"usage_refresh_interval": 45}')

        with (
            patch.object(settings, "CONFIG_FILE", str(config_file)),
            patch("builtins.open", side_effect=PermissionError("Access denied")),
        ):
            s = Settings.load()
            assert s.usage_refresh_interval == 60


class TestGetSettings:
    """Tests for get_settings() function"""

    def setup_method(self):
        """Reset global settings before each test"""
        settings._settings = None

    def teardown_method(self):
        """Clean up global settings after each test"""
        settings._settings = None

    def test_get_settings_lazy_loads(self, tmp_path):
        """get_settings() should lazy load settings on first call"""
        config_file = tmp_path / "settings.json"
        config_file.write_text('{"usage_refresh_interval": 75}')

        with patch.object(settings, "CONFIG_FILE", str(config_file)):
            assert settings._settings is None
            s = get_settings()
            assert s.usage_refresh_interval == 75
            assert settings._settings is not None

    def test_get_settings_returns_cached_instance(self, tmp_path):
        """get_settings() should return same instance on subsequent calls"""
        config_file = tmp_path / "settings.json"
        config_file.write_text('{"usage_refresh_interval": 75}')

        with patch.object(settings, "CONFIG_FILE", str(config_file)):
            s1 = get_settings()
            s2 = get_settings()
            assert s1 is s2


class TestSaveSettings:
    """Tests for save_settings() function"""

    def setup_method(self):
        """Reset global settings before each test"""
        settings._settings = None

    def teardown_method(self):
        """Clean up global settings after each test"""
        settings._settings = None

    def test_save_settings_does_nothing_when_not_loaded(self):
        """save_settings() should do nothing if settings were never loaded"""
        with patch.object(Settings, "save") as mock_save:
            save_settings()
            mock_save.assert_not_called()

    def test_save_settings_saves_loaded_settings(self, tmp_path):
        """save_settings() should save when settings were loaded"""
        config_dir = tmp_path / "config"
        config_file = config_dir / "settings.json"

        with (
            patch.object(settings, "CONFIG_DIR", str(config_dir)),
            patch.object(settings, "CONFIG_FILE", str(config_file)),
        ):
            # First load settings (creates _settings)
            s = get_settings()
            s.usage_refresh_interval = 200

            # Then save
            save_settings()

            # Verify file was written
            assert config_file.exists()
            with open(config_file) as f:
                data = json.load(f)
            assert data["usage_refresh_interval"] == 200
