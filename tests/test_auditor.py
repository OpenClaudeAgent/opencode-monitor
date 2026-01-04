"""
Tests for SecurityAuditor - Background scanner for OpenCode command history.

Tests cover:
- Initialization and component wiring
- Start/stop lifecycle
- File processing for different tool types
- Scan loop logic
- Public API methods
- Global singleton functions
"""

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch, PropertyMock

import pytest

from opencode_monitor.security.auditor import (
    SecurityAuditor,
    get_auditor,
    start_auditor,
    stop_auditor,
    OPENCODE_STORAGE,
    SCAN_INTERVAL,
)
from opencode_monitor.security.analyzer import RiskLevel, RiskResult


# =====================================================
# Local Helpers (factorized patterns)
# =====================================================


def create_tool_content(tool: str, session_id: str = "sess-001", **input_args) -> dict:
    """Factory to create tool file content."""
    return {
        "type": "tool",
        "tool": tool,
        "sessionID": session_id,
        "state": {
            "input": input_args,
            "time": {"start": 1703001000000},
        },
    }


def create_prt_file(storage: Path, msg_id: str, file_id: str, content: dict) -> Path:
    """Helper to create a prt_*.json file in storage."""
    msg_dir = storage / msg_id
    msg_dir.mkdir(parents=True, exist_ok=True)
    file_path = msg_dir / f"prt_{file_id}.json"
    file_path.write_text(json.dumps(content))
    return file_path


# =====================================================
# Shared Fixtures - Reduce mock duplication
# =====================================================


@pytest.fixture
def mock_db():
    """Standard mock database with common stats."""
    db = MagicMock()
    db.get_stats.return_value = {
        "total_scanned": 0,
        "total_commands": 0,
        "total_reads": 0,
        "total_writes": 0,
        "total_webfetches": 0,
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
    }
    db.get_all_scanned_ids.return_value = set()
    db.insert_command.return_value = True
    db.insert_read.return_value = True
    db.insert_write.return_value = True
    db.insert_webfetch.return_value = True
    return db


@pytest.fixture
def mock_analyzer():
    """Standard mock analyzer."""
    analyzer = MagicMock()
    analyzer.analyze_file_path.return_value = RiskResult(
        score=60, level="high", reason="Test"
    )
    analyzer.analyze_url.return_value = RiskResult(
        score=85, level="critical", reason="Test"
    )
    return analyzer


class AuditorTestContext:
    """Container for auditor and its mocked dependencies.

    Provides transparent access to auditor methods/attributes while
    also exposing mock_db and mock_analyzer for test assertions.
    """

    __slots__ = ("_auditor", "_mock_db", "_mock_analyzer")

    def __init__(self, auditor, mock_db, mock_analyzer):
        object.__setattr__(self, "_auditor", auditor)
        object.__setattr__(self, "_mock_db", mock_db)
        object.__setattr__(self, "_mock_analyzer", mock_analyzer)

    @property
    def mock_db(self):
        return self._mock_db

    @property
    def mock_analyzer(self):
        return self._mock_analyzer

    def __getattr__(self, name):
        """Delegate attribute access to underlying auditor."""
        return getattr(self._auditor, name)

    def __setattr__(self, name, value):
        """Delegate attribute assignment to underlying auditor."""
        if name in ("_auditor", "_mock_db", "_mock_analyzer"):
            object.__setattr__(self, name, value)
        else:
            setattr(self._auditor, name, value)


@pytest.fixture
def auditor_with_mocks(mock_db, mock_analyzer):
    """Create auditor with all dependencies mocked. Returns AuditorTestContext."""
    with (
        patch("opencode_monitor.security.auditor.SecurityDatabase") as mock_db_cls,
        patch(
            "opencode_monitor.security.auditor.get_risk_analyzer"
        ) as mock_analyzer_fn,
        patch("opencode_monitor.security.auditor.SecurityReporter"),
    ):
        mock_db_cls.return_value = mock_db
        mock_analyzer_fn.return_value = mock_analyzer
        auditor = SecurityAuditor()
        yield AuditorTestContext(auditor, mock_db, mock_analyzer)


@pytest.fixture
def mock_storage(tmp_path):
    """Create a mock OpenCode storage directory structure."""
    storage = tmp_path / "opencode_storage"
    storage.mkdir(parents=True)
    return storage


# =====================================================
# Parametrized Tool Content Data
# =====================================================

TOOL_CONTENT_DATA = [
    ("bash", {"command": "rm -rf /tmp/test"}, "sess-001"),
    ("read", {"filePath": "/etc/passwd"}, "sess-002"),
    ("write", {"filePath": "/home/user/.ssh/config"}, "sess-003"),
    ("edit", {"filePath": "/etc/hosts"}, "sess-004"),
    ("webfetch", {"url": "https://pastebin.com/raw/abc123"}, "sess-005"),
]


# =====================================================
# Initialization Tests
# =====================================================


class TestSecurityAuditorInit:
    """Tests for SecurityAuditor initialization and cached stats loading."""

    @pytest.mark.parametrize(
        "cached_stats,expected_scanned,expected_commands,expected_ids_count",
        [
            # Fresh start - no cached data
            (
                {
                    "total_scanned": 0,
                    "total_commands": 0,
                    "total_reads": 0,
                    "total_writes": 0,
                    "total_webfetches": 0,
                    "critical": 0,
                    "high": 0,
                    "medium": 0,
                    "low": 0,
                },
                0,
                0,
                0,
            ),
            # Restored from cache
            (
                {
                    "total_scanned": 100,
                    "total_commands": 50,
                    "total_reads": 20,
                    "total_writes": 10,
                    "total_webfetches": 5,
                    "critical": 3,
                    "high": 10,
                    "medium": 20,
                    "low": 67,
                },
                100,
                50,
                3,
            ),
        ],
        ids=["fresh_start", "restored_from_cache"],
    )
    def test_init_creates_components_and_loads_stats(
        self, cached_stats, expected_scanned, expected_commands, expected_ids_count
    ):
        """Auditor initializes components and loads cached stats from database."""
        with (
            patch("opencode_monitor.security.auditor.SecurityDatabase") as mock_db_cls,
            patch(
                "opencode_monitor.security.auditor.get_risk_analyzer"
            ) as mock_analyzer_fn,
            patch(
                "opencode_monitor.security.auditor.SecurityReporter"
            ) as mock_reporter_cls,
        ):
            mock_db = MagicMock()
            mock_db.get_stats.return_value = cached_stats
            ids_list = ["f1", "f2", "f3"][:expected_ids_count]
            mock_db.get_all_scanned_ids.return_value = set(ids_list)
            mock_db_cls.return_value = mock_db

            auditor = SecurityAuditor()

            # Component creation verified
            assert auditor._running is False
            assert auditor._thread is None
            mock_db_cls.assert_called_once()
            mock_analyzer_fn.assert_called_once()
            mock_reporter_cls.assert_called_once()

            # Stats loaded correctly
            assert auditor._stats["total_scanned"] == expected_scanned
            assert auditor._stats["total_commands"] == expected_commands
            assert auditor._stats["last_scan"] is None
            assert len(auditor._scanned_ids) == expected_ids_count


# =====================================================
# Start/Stop Lifecycle Tests
# =====================================================


class TestSecurityAuditorLifecycle:
    """Tests for start/stop lifecycle management."""

    def test_start_creates_thread_and_stop_cleans_up(self, auditor_with_mocks):
        """Start creates daemon thread, stop sets running=False."""
        ctx = auditor_with_mocks

        with patch.object(ctx._auditor, "_scan_loop"):
            # Start should create thread
            ctx.start()
            assert ctx._running is True
            assert ctx._thread is not None
            assert ctx._thread.daemon is True

            first_thread = ctx._thread

            # Second start is idempotent
            ctx.start()
            assert ctx._thread is first_thread

            # Stop cleans up
            ctx.stop()
            assert ctx._running is False

    def test_stop_without_start_is_safe(self, auditor_with_mocks):
        """Stop works even if never started."""
        auditor = auditor_with_mocks
        auditor.stop()  # Should not raise
        assert auditor._running is False


# =====================================================
# File Processing Tests - Consolidated with Parametrize
# =====================================================


class TestProcessFile:
    """Tests for _process_file method with all tool types."""

    @pytest.mark.parametrize(
        "tool,input_args,expected_type,expected_field,expected_value",
        [
            (
                "bash",
                {"command": "rm -rf /tmp/test"},
                "command",
                "command",
                "rm -rf /tmp/test",
            ),
            ("read", {"filePath": "/etc/passwd"}, "read", "file_path", "/etc/passwd"),
            (
                "write",
                {"filePath": "/home/user/.ssh/config"},
                "write",
                "file_path",
                "/home/user/.ssh/config",
            ),
            ("edit", {"filePath": "/etc/hosts"}, "write", "file_path", "/etc/hosts"),
            (
                "webfetch",
                {"url": "https://pastebin.com/raw/abc123"},
                "webfetch",
                "url",
                "https://pastebin.com/raw/abc123",
            ),
        ],
        ids=["bash", "read", "write", "edit_as_write", "webfetch"],
    )
    def test_process_tool_file_types(
        self,
        auditor_with_mocks,
        tmp_path,
        tool,
        input_args,
        expected_type,
        expected_field,
        expected_value,
    ):
        """Process all supported tool types with correct extraction."""
        auditor = auditor_with_mocks
        content = create_tool_content(tool, **input_args)

        prt_file = tmp_path / f"prt_{tool}.json"
        prt_file.write_text(json.dumps(content))

        result = auditor._process_file(prt_file)

        assert result is not None
        assert result["type"] == expected_type
        assert result[expected_field] == expected_value
        assert "risk_score" in result
        assert "risk_level" in result
        assert "risk_reason" in result

    @pytest.mark.parametrize(
        "tool,empty_field,content_override",
        [
            ("bash", "command", {"command": ""}),
            ("read", "filePath", {"filePath": ""}),
            ("write", "filePath", {"filePath": ""}),
            ("webfetch", "url", {"url": ""}),
        ],
        ids=[
            "bash_empty_cmd",
            "read_empty_path",
            "write_empty_path",
            "webfetch_empty_url",
        ],
    )
    def test_process_empty_input_returns_none(
        self, auditor_with_mocks, tmp_path, tool, empty_field, content_override
    ):
        """Tool files with empty required fields return None."""
        auditor = auditor_with_mocks
        content = create_tool_content(tool, **content_override)

        prt_file = tmp_path / f"prt_empty_{tool}.json"
        prt_file.write_text(json.dumps(content))

        result = auditor._process_file(prt_file)
        assert result is None

    @pytest.mark.parametrize(
        "content,description",
        [
            ({"type": "message", "content": "Not a tool"}, "non_tool_type"),
            (
                {
                    "type": "tool",
                    "tool": "unknown_tool",
                    "sessionID": "s1",
                    "state": {"input": {}, "time": {"start": 1}},
                },
                "unknown_tool",
            ),
        ],
        ids=["non_tool", "unknown_tool"],
    )
    def test_process_skipped_content_returns_none(
        self, auditor_with_mocks, tmp_path, content, description
    ):
        """Non-tool and unknown tool files return None."""
        auditor = auditor_with_mocks

        prt_file = tmp_path / f"prt_{description}.json"
        prt_file.write_text(json.dumps(content))

        result = auditor._process_file(prt_file)
        assert result is None

    def test_process_invalid_json_returns_none(self, auditor_with_mocks, tmp_path):
        """Invalid JSON file returns None (exception handled)."""
        auditor = auditor_with_mocks

        prt_file = tmp_path / "prt_invalid.json"
        prt_file.write_text("not valid json {{{")

        result = auditor._process_file(prt_file)
        assert result is None


# =====================================================
# Run Scan Tests
# =====================================================


class TestRunScan:
    """Tests for _run_scan method."""

    def test_run_scan_no_storage_dir(self):
        """Scan exits early if storage directory doesn't exist."""
        with (
            patch(
                "opencode_monitor.security.auditor.OPENCODE_STORAGE"
            ) as mock_storage_path,
            patch("opencode_monitor.security.auditor.SecurityDatabase") as mock_db_cls,
            patch("opencode_monitor.security.auditor.get_risk_analyzer"),
            patch("opencode_monitor.security.auditor.SecurityReporter"),
        ):
            mock_storage_path.exists.return_value = False
            mock_db = MagicMock()
            mock_db.get_stats.return_value = {"total_scanned": 0, "total_commands": 0}
            mock_db.get_all_scanned_ids.return_value = set()
            mock_db_cls.return_value = mock_db

            auditor = SecurityAuditor()
            auditor._run_scan()

            mock_storage_path.iterdir.assert_not_called()

    def test_run_scan_processes_new_files_and_updates_stats(
        self, auditor_with_mocks, tmp_path
    ):
        """Scan processes new files, inserts into database, and updates stats."""
        auditor = auditor_with_mocks
        content = create_tool_content("bash", command="ls -la")

        storage = tmp_path / "storage"
        msg_dir = storage / "msg_001"
        msg_dir.mkdir(parents=True)
        (msg_dir / "prt_001.json").write_text(json.dumps(content))

        with patch("opencode_monitor.security.auditor.OPENCODE_STORAGE", storage):
            auditor._run_scan()

        auditor.mock_db.insert_command.assert_called_once()
        assert "prt_001.json" in auditor._scanned_ids
        auditor.mock_db.update_scan_stats.assert_called_once()
        assert auditor._stats["total_scanned"] == 1
        assert auditor._stats["total_commands"] == 1

    def test_run_scan_skips_already_scanned_files(self, tmp_path):
        """Scan skips files that were already scanned."""
        with (
            patch("opencode_monitor.security.auditor.SecurityDatabase") as mock_db_cls,
            patch("opencode_monitor.security.auditor.get_risk_analyzer"),
            patch("opencode_monitor.security.auditor.SecurityReporter"),
        ):
            mock_db = MagicMock()
            mock_db.get_stats.return_value = {
                "total_scanned": 1,
                "total_commands": 1,
                "total_reads": 0,
                "total_writes": 0,
                "total_webfetches": 0,
            }
            mock_db.get_all_scanned_ids.return_value = {
                "prt_001.json"
            }  # Already scanned
            mock_db_cls.return_value = mock_db

            content = create_tool_content("bash", command="ls")
            storage = tmp_path / "storage"
            msg_dir = storage / "msg_001"
            msg_dir.mkdir(parents=True)
            (msg_dir / "prt_001.json").write_text(json.dumps(content))

            auditor = SecurityAuditor()

            with patch("opencode_monitor.security.auditor.OPENCODE_STORAGE", storage):
                auditor._run_scan()

            mock_db.insert_command.assert_not_called()

    def test_run_scan_handles_all_tool_types(self, auditor_with_mocks, tmp_path):
        """Scan correctly routes different tool types to appropriate insert methods."""
        auditor = auditor_with_mocks

        storage = tmp_path / "storage"
        msg_dir = storage / "msg_001"
        msg_dir.mkdir(parents=True)

        # Create files for all tool types
        (msg_dir / "prt_bash.json").write_text(
            json.dumps(create_tool_content("bash", command="ls"))
        )
        (msg_dir / "prt_read.json").write_text(
            json.dumps(create_tool_content("read", filePath="/etc/passwd"))
        )
        (msg_dir / "prt_write.json").write_text(
            json.dumps(create_tool_content("write", filePath="/tmp/out"))
        )
        (msg_dir / "prt_fetch.json").write_text(
            json.dumps(create_tool_content("webfetch", url="https://example.com"))
        )

        with patch("opencode_monitor.security.auditor.OPENCODE_STORAGE", storage):
            auditor._run_scan()

        auditor.mock_db.insert_command.assert_called()
        auditor.mock_db.insert_read.assert_called()
        auditor.mock_db.insert_write.assert_called()
        auditor.mock_db.insert_webfetch.assert_called()

    def test_run_scan_handles_exception_gracefully(self):
        """Scan handles exceptions gracefully without crashing."""
        with (
            patch(
                "opencode_monitor.security.auditor.OPENCODE_STORAGE"
            ) as mock_storage_path,
            patch("opencode_monitor.security.auditor.SecurityDatabase") as mock_db_cls,
            patch("opencode_monitor.security.auditor.get_risk_analyzer"),
            patch("opencode_monitor.security.auditor.SecurityReporter"),
        ):
            mock_db = MagicMock()
            mock_db.get_stats.return_value = {
                "total_scanned": 0,
                "total_commands": 0,
                "total_reads": 0,
                "total_writes": 0,
                "total_webfetches": 0,
            }
            mock_db.get_all_scanned_ids.return_value = set()
            mock_db_cls.return_value = mock_db

            mock_storage_path.exists.return_value = True
            mock_storage_path.iterdir.side_effect = PermissionError("No access")

            auditor = SecurityAuditor()
            auditor._run_scan()  # Should not raise

    def test_run_scan_stops_when_not_running(self, tmp_path):
        """Scan stops processing when _running becomes False."""
        with (
            patch("opencode_monitor.security.auditor.SecurityDatabase") as mock_db_cls,
            patch("opencode_monitor.security.auditor.get_risk_analyzer"),
            patch("opencode_monitor.security.auditor.SecurityReporter"),
        ):
            mock_db = MagicMock()
            mock_db.get_stats.return_value = {
                "total_scanned": 0,
                "total_commands": 0,
                "total_reads": 0,
                "total_writes": 0,
                "total_webfetches": 0,
            }
            mock_db.get_all_scanned_ids.return_value = set()
            mock_db_cls.return_value = mock_db

            content = create_tool_content("bash", command="ls")
            storage = tmp_path / "storage"

            for i in range(5):
                msg_dir = storage / f"msg_{i:03d}"
                msg_dir.mkdir(parents=True)
                (msg_dir / f"prt_{i:03d}.json").write_text(json.dumps(content))

            auditor = SecurityAuditor()
            auditor._running = False
            auditor._thread = MagicMock()

            with patch("opencode_monitor.security.auditor.OPENCODE_STORAGE", storage):
                auditor._run_scan()

            assert auditor._stats["total_scanned"] == 0


# =====================================================
# Update Stat Tests
# =====================================================


class TestUpdateStat:
    """Tests for _update_stat method."""

    def test_update_stat_behavior(self, auditor_with_mocks):
        """Update stat increments existing keys and ignores unknown ones."""
        auditor = auditor_with_mocks
        auditor._stats["high"] = 5

        # Increments existing key
        auditor._update_stat("high")
        assert auditor._stats["high"] == 6

        # Ignores unknown key (no error)
        auditor._update_stat("unknown_key")
        assert "unknown_key" not in auditor._stats


# =====================================================
# Scan Loop Tests
# =====================================================


class TestScanLoop:
    """Tests for _scan_loop method."""

    def test_scan_loop_runs_scans_periodically(self, auditor_with_mocks):
        """Scan loop runs initial and periodic scans while running."""
        ctx = auditor_with_mocks
        ctx._running = True

        call_count = [0]

        def stop_after_second_sleep(*args):
            call_count[0] += 1
            if call_count[0] >= 2:
                ctx._running = False

        with (
            patch.object(ctx._auditor, "_run_scan") as mock_run,
            patch(
                "opencode_monitor.security.auditor.time.sleep",
                side_effect=stop_after_second_sleep,
            ),
        ):
            ctx._scan_loop()

        # Should run initial scan + at least 1 periodic scan
        assert mock_run.call_count >= 2


# =====================================================
# Public API Tests - Consolidated with Parametrize
# =====================================================


class TestPublicAPI:
    """Tests for public API methods."""

    def test_get_stats_returns_copy(self, auditor_with_mocks):
        """get_stats returns a defensive copy of stats."""
        auditor = auditor_with_mocks
        auditor._stats["total_scanned"] = 100

        stats = auditor.get_stats()
        stats["total_scanned"] = 999

        # Original unchanged
        assert auditor._stats["total_scanned"] == 100

    @pytest.mark.parametrize(
        "method_name,method_args,db_method,db_args",
        [
            (
                "get_critical_commands",
                {"limit": 10},
                "get_commands_by_level",
                (["critical", "high"], 10),
            ),
            (
                "get_commands_by_level",
                {"level": "high", "limit": 25},
                "get_commands_by_level",
                (["high"], 25),
            ),
            (
                "get_all_commands",
                {"limit": 50, "offset": 10},
                "get_all_commands",
                (50, 10),
            ),
            (
                "get_sensitive_reads",
                {"limit": 15},
                "get_reads_by_level",
                (["critical", "high"], 15),
            ),
            ("get_all_reads", {"limit": 500}, "get_all_reads", (500,)),
            (
                "get_sensitive_writes",
                {"limit": 15},
                "get_writes_by_level",
                (["critical", "high"], 15),
            ),
            ("get_all_writes", {"limit": 500}, "get_all_writes", (500,)),
            (
                "get_risky_webfetches",
                {"limit": 15},
                "get_webfetches_by_level",
                (["critical", "high"], 15),
            ),
            ("get_all_webfetches", {"limit": 500}, "get_all_webfetches", (500,)),
        ],
        ids=[
            "get_critical_commands",
            "get_commands_by_level",
            "get_all_commands",
            "get_sensitive_reads",
            "get_all_reads",
            "get_sensitive_writes",
            "get_all_writes",
            "get_risky_webfetches",
            "get_all_webfetches",
        ],
    )
    def test_api_methods_delegate_to_database(
        self, auditor_with_mocks, method_name, method_args, db_method, db_args
    ):
        """API methods correctly delegate to database with proper arguments."""
        auditor = auditor_with_mocks
        getattr(auditor.mock_db, db_method).return_value = []

        method = getattr(auditor, method_name)
        method(**method_args)

        getattr(auditor.mock_db, db_method).assert_called_with(*db_args)

    def test_generate_report_uses_reporter(self, auditor_with_mocks):
        """generate_report uses reporter with correct data."""
        auditor = auditor_with_mocks

        with patch.object(auditor._auditor, "_reporter") as mock_reporter:
            mock_reporter.generate_summary_report.return_value = "Test Report"

            result = auditor.generate_report()

            assert result == "Test Report"
            mock_reporter.generate_summary_report.assert_called_once()


# =====================================================
# Global Functions Tests
# =====================================================


class TestGlobalFunctions:
    """Tests for global singleton functions."""

    def test_singleton_lifecycle(self):
        """get_auditor creates singleton, start_auditor starts it, stop_auditor clears it."""
        import opencode_monitor.security.auditor as auditor_module

        # Reset state
        auditor_module._auditor = None

        with patch.object(auditor_module, "SecurityAuditor") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            # get_auditor creates singleton
            result1 = get_auditor()
            result2 = get_auditor()

            mock_cls.assert_called_once()
            assert result1 is result2

            # start_auditor calls start
            start_auditor()
            mock_instance.start.assert_called_once()

            # stop_auditor stops and clears
            stop_auditor()
            mock_instance.stop.assert_called_once()
            assert auditor_module._auditor is None

        # Clean up
        auditor_module._auditor = None

    def test_stop_auditor_when_none(self):
        """stop_auditor handles None auditor gracefully."""
        import opencode_monitor.security.auditor as auditor_module

        auditor_module._auditor = None
        stop_auditor()  # Should not raise
        assert auditor_module._auditor is None
