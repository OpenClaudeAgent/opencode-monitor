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
from opencode_monitor.security.db import (
    SecurityDatabase,
    AuditedCommand,
    AuditedFileRead,
    AuditedFileWrite,
    AuditedWebFetch,
)


# =====================================================
# Fixtures
# =====================================================


@pytest.fixture
def mock_db(tmp_path: Path) -> SecurityDatabase:
    """Create a fresh test database"""
    db_path = tmp_path / "test_security.db"
    return SecurityDatabase(db_path=db_path)


@pytest.fixture
def mock_storage(tmp_path: Path):
    """Create a mock OpenCode storage directory structure"""
    storage = tmp_path / "opencode_storage"
    storage.mkdir(parents=True)
    return storage


@pytest.fixture
def sample_bash_file_content() -> dict:
    """Sample bash command file content"""
    return {
        "type": "tool",
        "tool": "bash",
        "sessionID": "sess-001",
        "state": {
            "input": {"command": "rm -rf /tmp/test"},
            "time": {"start": 1703001000000},
        },
    }


@pytest.fixture
def sample_read_file_content() -> dict:
    """Sample read tool file content"""
    return {
        "type": "tool",
        "tool": "read",
        "sessionID": "sess-002",
        "state": {
            "input": {"filePath": "/etc/passwd"},
            "time": {"start": 1703002000000},
        },
    }


@pytest.fixture
def sample_write_file_content() -> dict:
    """Sample write tool file content"""
    return {
        "type": "tool",
        "tool": "write",
        "sessionID": "sess-003",
        "state": {
            "input": {"filePath": "/home/user/.ssh/config"},
            "time": {"start": 1703003000000},
        },
    }


@pytest.fixture
def sample_edit_file_content() -> dict:
    """Sample edit tool file content"""
    return {
        "type": "tool",
        "tool": "edit",
        "sessionID": "sess-004",
        "state": {
            "input": {"filePath": "/etc/hosts"},
            "time": {"start": 1703004000000},
        },
    }


@pytest.fixture
def sample_webfetch_file_content() -> dict:
    """Sample webfetch tool file content"""
    return {
        "type": "tool",
        "tool": "webfetch",
        "sessionID": "sess-005",
        "state": {
            "input": {"url": "https://pastebin.com/raw/abc123"},
            "time": {"start": 1703005000000},
        },
    }


@pytest.fixture
def sample_non_tool_content() -> dict:
    """Sample non-tool file content (should be skipped)"""
    return {
        "type": "message",
        "content": "This is a message, not a tool",
    }


def create_prt_file(storage: Path, msg_id: str, file_id: str, content: dict) -> Path:
    """Helper to create a prt_*.json file in storage"""
    msg_dir = storage / msg_id
    msg_dir.mkdir(parents=True, exist_ok=True)
    file_path = msg_dir / f"prt_{file_id}.json"
    file_path.write_text(json.dumps(content))
    return file_path


# =====================================================
# Initialization Tests
# =====================================================


class TestSecurityAuditorInit:
    """Tests for SecurityAuditor initialization"""

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_init_creates_components(
        self, mock_reporter_cls, mock_analyzer_fn, mock_db_cls
    ):
        """Auditor initializes all required components"""
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {
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
        mock_db.get_all_scanned_ids.return_value = set()
        mock_db_cls.return_value = mock_db

        auditor = SecurityAuditor()

        assert auditor._running is False
        assert auditor._thread is None
        mock_db_cls.assert_called_once()
        mock_analyzer_fn.assert_called_once()
        mock_reporter_cls.assert_called_once()

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_init_loads_cached_stats(
        self, mock_reporter_cls, mock_analyzer_fn, mock_db_cls
    ):
        """Auditor loads cached stats from database"""
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {
            "total_scanned": 100,
            "total_commands": 50,
            "total_reads": 20,
            "total_writes": 10,
            "total_webfetches": 5,
            "critical": 3,
            "high": 10,
            "medium": 20,
            "low": 67,
        }
        mock_db.get_all_scanned_ids.return_value = {"file1", "file2", "file3"}
        mock_db_cls.return_value = mock_db

        auditor = SecurityAuditor()

        assert auditor._stats["total_scanned"] == 100
        assert auditor._stats["total_commands"] == 50
        assert auditor._stats["last_scan"] is None
        assert len(auditor._scanned_ids) == 3


# =====================================================
# Start/Stop Lifecycle Tests
# =====================================================


class TestSecurityAuditorLifecycle:
    """Tests for start/stop lifecycle"""

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_start_creates_thread(
        self, mock_reporter_cls, mock_analyzer_fn, mock_db_cls
    ):
        """start() creates and starts the background thread"""
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {"total_scanned": 0, "total_commands": 0}
        mock_db.get_all_scanned_ids.return_value = set()
        mock_db_cls.return_value = mock_db

        auditor = SecurityAuditor()

        with patch.object(auditor, "_scan_loop"):
            auditor.start()

            assert auditor._running is True
            assert auditor._thread is not None
            assert auditor._thread.daemon is True

            auditor.stop()

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_start_is_idempotent(
        self, mock_reporter_cls, mock_analyzer_fn, mock_db_cls
    ):
        """Calling start() twice doesn't create two threads"""
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {"total_scanned": 0, "total_commands": 0}
        mock_db.get_all_scanned_ids.return_value = set()
        mock_db_cls.return_value = mock_db

        auditor = SecurityAuditor()

        with patch.object(auditor, "_scan_loop"):
            auditor.start()
            first_thread = auditor._thread

            auditor.start()  # Second call

            assert auditor._thread is first_thread

            auditor.stop()

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_stop_sets_running_false(
        self, mock_reporter_cls, mock_analyzer_fn, mock_db_cls
    ):
        """stop() sets _running to False"""
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {"total_scanned": 0, "total_commands": 0}
        mock_db.get_all_scanned_ids.return_value = set()
        mock_db_cls.return_value = mock_db

        auditor = SecurityAuditor()

        with patch.object(auditor, "_scan_loop"):
            auditor.start()
            auditor.stop()

            assert auditor._running is False

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_stop_without_start(self, mock_reporter_cls, mock_analyzer_fn, mock_db_cls):
        """stop() works even if never started"""
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {"total_scanned": 0, "total_commands": 0}
        mock_db.get_all_scanned_ids.return_value = set()
        mock_db_cls.return_value = mock_db

        auditor = SecurityAuditor()
        auditor.stop()  # Should not raise

        assert auditor._running is False


# =====================================================
# File Processing Tests
# =====================================================


class TestProcessFile:
    """Tests for _process_file method"""

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_process_bash_command(
        self,
        mock_reporter_cls,
        mock_analyzer_fn,
        mock_db_cls,
        tmp_path,
        sample_bash_file_content,
    ):
        """Process a bash command file"""
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {"total_scanned": 0, "total_commands": 0}
        mock_db.get_all_scanned_ids.return_value = set()
        mock_db_cls.return_value = mock_db

        auditor = SecurityAuditor()

        prt_file = tmp_path / "prt_001.json"
        prt_file.write_text(json.dumps(sample_bash_file_content))

        result = auditor._process_file(prt_file)

        assert result is not None
        assert result["type"] == "command"
        assert result["tool"] == "bash"
        assert result["command"] == "rm -rf /tmp/test"
        assert "risk_score" in result
        assert "risk_level" in result
        assert "risk_reason" in result

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_process_read_file(
        self,
        mock_reporter_cls,
        mock_analyzer_fn,
        mock_db_cls,
        tmp_path,
        sample_read_file_content,
    ):
        """Process a read tool file"""
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {"total_scanned": 0, "total_commands": 0}
        mock_db.get_all_scanned_ids.return_value = set()
        mock_db_cls.return_value = mock_db

        mock_analyzer = MagicMock()
        mock_analyzer.analyze_file_path.return_value = RiskResult(
            score=60, level="high", reason="System passwd file"
        )
        mock_analyzer_fn.return_value = mock_analyzer

        auditor = SecurityAuditor()

        prt_file = tmp_path / "prt_002.json"
        prt_file.write_text(json.dumps(sample_read_file_content))

        result = auditor._process_file(prt_file)

        assert result is not None
        assert result["type"] == "read"
        assert result["file_path"] == "/etc/passwd"
        assert result["risk_score"] == 60
        assert result["risk_level"] == "high"

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_process_write_file(
        self,
        mock_reporter_cls,
        mock_analyzer_fn,
        mock_db_cls,
        tmp_path,
        sample_write_file_content,
    ):
        """Process a write tool file"""
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {"total_scanned": 0, "total_commands": 0}
        mock_db.get_all_scanned_ids.return_value = set()
        mock_db_cls.return_value = mock_db

        mock_analyzer = MagicMock()
        mock_analyzer.analyze_file_path.return_value = RiskResult(
            score=95, level="critical", reason="SSH directory"
        )
        mock_analyzer_fn.return_value = mock_analyzer

        auditor = SecurityAuditor()

        prt_file = tmp_path / "prt_003.json"
        prt_file.write_text(json.dumps(sample_write_file_content))

        result = auditor._process_file(prt_file)

        assert result is not None
        assert result["type"] == "write"
        assert result["file_path"] == "/home/user/.ssh/config"
        assert result["operation"] == "write"
        mock_analyzer.analyze_file_path.assert_called_with(
            "/home/user/.ssh/config", write_mode=True
        )

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_process_edit_file(
        self,
        mock_reporter_cls,
        mock_analyzer_fn,
        mock_db_cls,
        tmp_path,
        sample_edit_file_content,
    ):
        """Process an edit tool file (treated as write)"""
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {"total_scanned": 0, "total_commands": 0}
        mock_db.get_all_scanned_ids.return_value = set()
        mock_db_cls.return_value = mock_db

        mock_analyzer = MagicMock()
        mock_analyzer.analyze_file_path.return_value = RiskResult(
            score=55, level="high", reason="System config"
        )
        mock_analyzer_fn.return_value = mock_analyzer

        auditor = SecurityAuditor()

        prt_file = tmp_path / "prt_004.json"
        prt_file.write_text(json.dumps(sample_edit_file_content))

        result = auditor._process_file(prt_file)

        assert result is not None
        assert result["type"] == "write"
        assert result["operation"] == "edit"

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_process_webfetch_file(
        self,
        mock_reporter_cls,
        mock_analyzer_fn,
        mock_db_cls,
        tmp_path,
        sample_webfetch_file_content,
    ):
        """Process a webfetch tool file"""
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {"total_scanned": 0, "total_commands": 0}
        mock_db.get_all_scanned_ids.return_value = set()
        mock_db_cls.return_value = mock_db

        mock_analyzer = MagicMock()
        mock_analyzer.analyze_url.return_value = RiskResult(
            score=85, level="critical", reason="Pastebin content"
        )
        mock_analyzer_fn.return_value = mock_analyzer

        auditor = SecurityAuditor()

        prt_file = tmp_path / "prt_005.json"
        prt_file.write_text(json.dumps(sample_webfetch_file_content))

        result = auditor._process_file(prt_file)

        assert result is not None
        assert result["type"] == "webfetch"
        assert result["url"] == "https://pastebin.com/raw/abc123"
        assert result["risk_score"] == 85

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_process_non_tool_file_returns_none(
        self,
        mock_reporter_cls,
        mock_analyzer_fn,
        mock_db_cls,
        tmp_path,
        sample_non_tool_content,
    ):
        """Non-tool files return None"""
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {"total_scanned": 0, "total_commands": 0}
        mock_db.get_all_scanned_ids.return_value = set()
        mock_db_cls.return_value = mock_db

        auditor = SecurityAuditor()

        prt_file = tmp_path / "prt_006.json"
        prt_file.write_text(json.dumps(sample_non_tool_content))

        result = auditor._process_file(prt_file)

        assert result is None

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_process_bash_empty_command_returns_none(
        self, mock_reporter_cls, mock_analyzer_fn, mock_db_cls, tmp_path
    ):
        """Bash file with empty command returns None"""
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {"total_scanned": 0, "total_commands": 0}
        mock_db.get_all_scanned_ids.return_value = set()
        mock_db_cls.return_value = mock_db

        auditor = SecurityAuditor()

        content = {
            "type": "tool",
            "tool": "bash",
            "sessionID": "sess-001",
            "state": {"input": {"command": ""}, "time": {"start": 1703001000000}},
        }
        prt_file = tmp_path / "prt_empty.json"
        prt_file.write_text(json.dumps(content))

        result = auditor._process_file(prt_file)

        assert result is None

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_process_read_empty_path_returns_none(
        self, mock_reporter_cls, mock_analyzer_fn, mock_db_cls, tmp_path
    ):
        """Read file with empty path returns None"""
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {"total_scanned": 0, "total_commands": 0}
        mock_db.get_all_scanned_ids.return_value = set()
        mock_db_cls.return_value = mock_db

        auditor = SecurityAuditor()

        content = {
            "type": "tool",
            "tool": "read",
            "sessionID": "sess-001",
            "state": {"input": {"filePath": ""}, "time": {"start": 1703001000000}},
        }
        prt_file = tmp_path / "prt_empty_read.json"
        prt_file.write_text(json.dumps(content))

        result = auditor._process_file(prt_file)

        assert result is None

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_process_write_empty_path_returns_none(
        self, mock_reporter_cls, mock_analyzer_fn, mock_db_cls, tmp_path
    ):
        """Write file with empty path returns None"""
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {"total_scanned": 0, "total_commands": 0}
        mock_db.get_all_scanned_ids.return_value = set()
        mock_db_cls.return_value = mock_db

        auditor = SecurityAuditor()

        content = {
            "type": "tool",
            "tool": "write",
            "sessionID": "sess-001",
            "state": {"input": {"filePath": ""}, "time": {"start": 1703001000000}},
        }
        prt_file = tmp_path / "prt_empty_write.json"
        prt_file.write_text(json.dumps(content))

        result = auditor._process_file(prt_file)

        assert result is None

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_process_webfetch_empty_url_returns_none(
        self, mock_reporter_cls, mock_analyzer_fn, mock_db_cls, tmp_path
    ):
        """Webfetch file with empty URL returns None"""
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {"total_scanned": 0, "total_commands": 0}
        mock_db.get_all_scanned_ids.return_value = set()
        mock_db_cls.return_value = mock_db

        auditor = SecurityAuditor()

        content = {
            "type": "tool",
            "tool": "webfetch",
            "sessionID": "sess-001",
            "state": {"input": {"url": ""}, "time": {"start": 1703001000000}},
        }
        prt_file = tmp_path / "prt_empty_webfetch.json"
        prt_file.write_text(json.dumps(content))

        result = auditor._process_file(prt_file)

        assert result is None

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_process_unknown_tool_returns_none(
        self, mock_reporter_cls, mock_analyzer_fn, mock_db_cls, tmp_path
    ):
        """Unknown tool type returns None"""
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {"total_scanned": 0, "total_commands": 0}
        mock_db.get_all_scanned_ids.return_value = set()
        mock_db_cls.return_value = mock_db

        auditor = SecurityAuditor()

        content = {
            "type": "tool",
            "tool": "unknown_tool",
            "sessionID": "sess-001",
            "state": {"input": {}, "time": {"start": 1703001000000}},
        }
        prt_file = tmp_path / "prt_unknown.json"
        prt_file.write_text(json.dumps(content))

        result = auditor._process_file(prt_file)

        assert result is None

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_process_invalid_json_returns_none(
        self, mock_reporter_cls, mock_analyzer_fn, mock_db_cls, tmp_path
    ):
        """Invalid JSON file returns None (exception handled)"""
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {"total_scanned": 0, "total_commands": 0}
        mock_db.get_all_scanned_ids.return_value = set()
        mock_db_cls.return_value = mock_db

        auditor = SecurityAuditor()

        prt_file = tmp_path / "prt_invalid.json"
        prt_file.write_text("not valid json {{{")

        result = auditor._process_file(prt_file)

        assert result is None


# =====================================================
# Run Scan Tests
# =====================================================


class TestRunScan:
    """Tests for _run_scan method"""

    @patch("opencode_monitor.security.auditor.OPENCODE_STORAGE")
    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_run_scan_no_storage_dir(
        self, mock_reporter_cls, mock_analyzer_fn, mock_db_cls, mock_storage_path
    ):
        """Scan exits early if storage directory doesn't exist"""
        mock_storage_path.exists.return_value = False

        mock_db = MagicMock()
        mock_db.get_stats.return_value = {"total_scanned": 0, "total_commands": 0}
        mock_db.get_all_scanned_ids.return_value = set()
        mock_db_cls.return_value = mock_db

        auditor = SecurityAuditor()
        auditor._run_scan()

        # Should not try to iterate
        mock_storage_path.iterdir.assert_not_called()

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_run_scan_processes_new_files(
        self,
        mock_reporter_cls,
        mock_analyzer_fn,
        mock_db_cls,
        tmp_path,
        sample_bash_file_content,
    ):
        """Scan processes new files and inserts into database"""
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {
            "total_scanned": 0,
            "total_commands": 0,
            "total_reads": 0,
            "total_writes": 0,
            "total_webfetches": 0,
            "high": 0,
        }
        mock_db.get_all_scanned_ids.return_value = set()
        mock_db.insert_command.return_value = True
        mock_db_cls.return_value = mock_db

        # Create storage structure
        storage = tmp_path / "storage"
        msg_dir = storage / "msg_001"
        msg_dir.mkdir(parents=True)
        prt_file = msg_dir / "prt_001.json"
        prt_file.write_text(json.dumps(sample_bash_file_content))

        auditor = SecurityAuditor()

        with patch("opencode_monitor.security.auditor.OPENCODE_STORAGE", storage):
            auditor._run_scan()

        mock_db.insert_command.assert_called_once()
        assert "prt_001.json" in auditor._scanned_ids

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_run_scan_skips_already_scanned(
        self,
        mock_reporter_cls,
        mock_analyzer_fn,
        mock_db_cls,
        tmp_path,
        sample_bash_file_content,
    ):
        """Scan skips files that were already scanned"""
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {
            "total_scanned": 1,
            "total_commands": 1,
            "total_reads": 0,
            "total_writes": 0,
            "total_webfetches": 0,
        }
        mock_db.get_all_scanned_ids.return_value = {"prt_001.json"}  # Already scanned
        mock_db_cls.return_value = mock_db

        storage = tmp_path / "storage"
        msg_dir = storage / "msg_001"
        msg_dir.mkdir(parents=True)
        prt_file = msg_dir / "prt_001.json"
        prt_file.write_text(json.dumps(sample_bash_file_content))

        auditor = SecurityAuditor()

        with patch("opencode_monitor.security.auditor.OPENCODE_STORAGE", storage):
            auditor._run_scan()

        mock_db.insert_command.assert_not_called()

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_run_scan_skips_non_directories(
        self,
        mock_reporter_cls,
        mock_analyzer_fn,
        mock_db_cls,
        tmp_path,
    ):
        """Scan skips non-directory entries in storage"""
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

        storage = tmp_path / "storage"
        storage.mkdir(parents=True)
        # Create a file instead of directory
        (storage / "not_a_dir.txt").write_text("test")

        auditor = SecurityAuditor()

        with patch("opencode_monitor.security.auditor.OPENCODE_STORAGE", storage):
            auditor._run_scan()

        mock_db.insert_command.assert_not_called()

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_run_scan_handles_all_types(
        self,
        mock_reporter_cls,
        mock_analyzer_fn,
        mock_db_cls,
        tmp_path,
        sample_bash_file_content,
        sample_read_file_content,
        sample_write_file_content,
        sample_webfetch_file_content,
    ):
        """Scan correctly routes different tool types"""
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {
            "total_scanned": 0,
            "total_commands": 0,
            "total_reads": 0,
            "total_writes": 0,
            "total_webfetches": 0,
            "high": 0,
            "reads_high": 0,
            "writes_critical": 0,
            "webfetches_critical": 0,
        }
        mock_db.get_all_scanned_ids.return_value = set()
        mock_db.insert_command.return_value = True
        mock_db.insert_read.return_value = True
        mock_db.insert_write.return_value = True
        mock_db.insert_webfetch.return_value = True
        mock_db_cls.return_value = mock_db

        mock_analyzer = MagicMock()
        mock_analyzer.analyze_file_path.return_value = RiskResult(
            score=60, level="high", reason="Test"
        )
        mock_analyzer.analyze_url.return_value = RiskResult(
            score=85, level="critical", reason="Test"
        )
        mock_analyzer_fn.return_value = mock_analyzer

        storage = tmp_path / "storage"
        msg_dir = storage / "msg_001"
        msg_dir.mkdir(parents=True)

        (msg_dir / "prt_bash.json").write_text(json.dumps(sample_bash_file_content))
        (msg_dir / "prt_read.json").write_text(json.dumps(sample_read_file_content))
        (msg_dir / "prt_write.json").write_text(json.dumps(sample_write_file_content))
        (msg_dir / "prt_fetch.json").write_text(
            json.dumps(sample_webfetch_file_content)
        )

        auditor = SecurityAuditor()

        with patch("opencode_monitor.security.auditor.OPENCODE_STORAGE", storage):
            auditor._run_scan()

        mock_db.insert_command.assert_called()
        mock_db.insert_read.assert_called()
        mock_db.insert_write.assert_called()
        mock_db.insert_webfetch.assert_called()

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_run_scan_updates_stats(
        self,
        mock_reporter_cls,
        mock_analyzer_fn,
        mock_db_cls,
        tmp_path,
        sample_bash_file_content,
    ):
        """Scan updates statistics after processing"""
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {
            "total_scanned": 0,
            "total_commands": 0,
            "total_reads": 0,
            "total_writes": 0,
            "total_webfetches": 0,
            "high": 0,
        }
        mock_db.get_all_scanned_ids.return_value = set()
        mock_db.insert_command.return_value = True
        mock_db_cls.return_value = mock_db

        storage = tmp_path / "storage"
        msg_dir = storage / "msg_001"
        msg_dir.mkdir(parents=True)
        (msg_dir / "prt_001.json").write_text(json.dumps(sample_bash_file_content))

        auditor = SecurityAuditor()

        with patch("opencode_monitor.security.auditor.OPENCODE_STORAGE", storage):
            auditor._run_scan()

        mock_db.update_scan_stats.assert_called_once()
        assert auditor._stats["total_scanned"] == 1
        assert auditor._stats["total_commands"] == 1

    @patch("opencode_monitor.security.auditor.OPENCODE_STORAGE")
    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_run_scan_handles_exception(
        self,
        mock_reporter_cls,
        mock_analyzer_fn,
        mock_db_cls,
        mock_storage_path,
    ):
        """Scan handles exceptions gracefully"""
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

        # Mock storage that exists but raises on iterdir
        mock_storage_path.exists.return_value = True
        mock_storage_path.iterdir.side_effect = PermissionError("No access")

        auditor = SecurityAuditor()
        auditor._run_scan()  # Should not raise

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_run_scan_stops_when_not_running(
        self,
        mock_reporter_cls,
        mock_analyzer_fn,
        mock_db_cls,
        tmp_path,
        sample_bash_file_content,
    ):
        """Scan stops processing when _running becomes False"""
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

        storage = tmp_path / "storage"

        # Create multiple message directories
        for i in range(5):
            msg_dir = storage / f"msg_{i:03d}"
            msg_dir.mkdir(parents=True)
            (msg_dir / f"prt_{i:03d}.json").write_text(
                json.dumps(sample_bash_file_content)
            )

        auditor = SecurityAuditor()
        auditor._running = False  # Simulate stop signal
        auditor._thread = MagicMock()  # Pretend we have a thread

        with patch("opencode_monitor.security.auditor.OPENCODE_STORAGE", storage):
            auditor._run_scan()

        # Should have stopped early
        assert auditor._stats["total_scanned"] == 0


# =====================================================
# Update Stat Tests
# =====================================================


class TestUpdateStat:
    """Tests for _update_stat method"""

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_update_stat_increments_existing_key(
        self, mock_reporter_cls, mock_analyzer_fn, mock_db_cls
    ):
        """Update stat increments an existing key"""
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {
            "total_scanned": 0,
            "total_commands": 0,
            "high": 5,
        }
        mock_db.get_all_scanned_ids.return_value = set()
        mock_db_cls.return_value = mock_db

        auditor = SecurityAuditor()
        auditor._update_stat("high")

        assert auditor._stats["high"] == 6

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_update_stat_ignores_unknown_key(
        self, mock_reporter_cls, mock_analyzer_fn, mock_db_cls
    ):
        """Update stat ignores unknown keys"""
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {"total_scanned": 0, "total_commands": 0}
        mock_db.get_all_scanned_ids.return_value = set()
        mock_db_cls.return_value = mock_db

        auditor = SecurityAuditor()
        auditor._update_stat("unknown_key")  # Should not raise

        assert "unknown_key" not in auditor._stats


# =====================================================
# Scan Loop Tests
# =====================================================


class TestScanLoop:
    """Tests for _scan_loop method"""

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    @patch("opencode_monitor.security.auditor.time.sleep")
    def test_scan_loop_runs_initial_scan(
        self, mock_sleep, mock_reporter_cls, mock_analyzer_fn, mock_db_cls
    ):
        """Scan loop runs initial scan immediately"""
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {"total_scanned": 0, "total_commands": 0}
        mock_db.get_all_scanned_ids.return_value = set()
        mock_db_cls.return_value = mock_db

        auditor = SecurityAuditor()
        auditor._running = True

        # Stop after first sleep
        def stop_after_sleep(*args):
            auditor._running = False

        mock_sleep.side_effect = stop_after_sleep

        with patch.object(auditor, "_run_scan") as mock_run:
            auditor._scan_loop()

        # Should run scan at least once (initial)
        mock_run.assert_called()

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    @patch("opencode_monitor.security.auditor.time.sleep")
    def test_scan_loop_runs_periodic_scan(
        self, mock_sleep, mock_reporter_cls, mock_analyzer_fn, mock_db_cls
    ):
        """Scan loop runs periodic scans while running"""
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {"total_scanned": 0, "total_commands": 0}
        mock_db.get_all_scanned_ids.return_value = set()
        mock_db_cls.return_value = mock_db

        auditor = SecurityAuditor()
        auditor._running = True

        call_count = [0]

        # Stop after second sleep (allow one periodic scan)
        def stop_after_second_sleep(*args):
            call_count[0] += 1
            if call_count[0] >= 2:
                auditor._running = False

        mock_sleep.side_effect = stop_after_second_sleep

        with patch.object(auditor, "_run_scan") as mock_run:
            auditor._scan_loop()

        # Should run initial scan + 1 periodic scan
        assert mock_run.call_count >= 2


# =====================================================
# Public API Tests
# =====================================================


class TestPublicAPI:
    """Tests for public API methods"""

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_get_stats_returns_copy(
        self, mock_reporter_cls, mock_analyzer_fn, mock_db_cls
    ):
        """get_stats returns a copy of stats"""
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {
            "total_scanned": 100,
            "total_commands": 50,
        }
        mock_db.get_all_scanned_ids.return_value = set()
        mock_db_cls.return_value = mock_db

        auditor = SecurityAuditor()
        stats = auditor.get_stats()

        # Modify the returned stats
        stats["total_scanned"] = 999

        # Original should be unchanged
        assert auditor._stats["total_scanned"] == 100

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_get_critical_commands(
        self, mock_reporter_cls, mock_analyzer_fn, mock_db_cls
    ):
        """get_critical_commands delegates to database"""
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {"total_scanned": 0, "total_commands": 0}
        mock_db.get_all_scanned_ids.return_value = set()
        mock_db.get_commands_by_level.return_value = []
        mock_db_cls.return_value = mock_db

        auditor = SecurityAuditor()
        auditor.get_critical_commands(limit=10)

        mock_db.get_commands_by_level.assert_called_with(["critical", "high"], 10)

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_get_commands_by_level(
        self, mock_reporter_cls, mock_analyzer_fn, mock_db_cls
    ):
        """get_commands_by_level delegates to database"""
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {"total_scanned": 0, "total_commands": 0}
        mock_db.get_all_scanned_ids.return_value = set()
        mock_db.get_commands_by_level.return_value = []
        mock_db_cls.return_value = mock_db

        auditor = SecurityAuditor()
        auditor.get_commands_by_level("high", limit=25)

        mock_db.get_commands_by_level.assert_called_with(["high"], 25)

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_get_all_commands(self, mock_reporter_cls, mock_analyzer_fn, mock_db_cls):
        """get_all_commands delegates to database"""
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {"total_scanned": 0, "total_commands": 0}
        mock_db.get_all_scanned_ids.return_value = set()
        mock_db.get_all_commands.return_value = []
        mock_db_cls.return_value = mock_db

        auditor = SecurityAuditor()
        auditor.get_all_commands(limit=50, offset=10)

        mock_db.get_all_commands.assert_called_with(50, 10)

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_get_sensitive_reads(
        self, mock_reporter_cls, mock_analyzer_fn, mock_db_cls
    ):
        """get_sensitive_reads delegates to database"""
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {"total_scanned": 0, "total_commands": 0}
        mock_db.get_all_scanned_ids.return_value = set()
        mock_db.get_reads_by_level.return_value = []
        mock_db_cls.return_value = mock_db

        auditor = SecurityAuditor()
        auditor.get_sensitive_reads(limit=15)

        mock_db.get_reads_by_level.assert_called_with(["critical", "high"], 15)

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_get_all_reads(self, mock_reporter_cls, mock_analyzer_fn, mock_db_cls):
        """get_all_reads delegates to database"""
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {"total_scanned": 0, "total_commands": 0}
        mock_db.get_all_scanned_ids.return_value = set()
        mock_db.get_all_reads.return_value = []
        mock_db_cls.return_value = mock_db

        auditor = SecurityAuditor()
        auditor.get_all_reads(limit=500)

        mock_db.get_all_reads.assert_called_with(500)

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_get_sensitive_writes(
        self, mock_reporter_cls, mock_analyzer_fn, mock_db_cls
    ):
        """get_sensitive_writes delegates to database"""
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {"total_scanned": 0, "total_commands": 0}
        mock_db.get_all_scanned_ids.return_value = set()
        mock_db.get_writes_by_level.return_value = []
        mock_db_cls.return_value = mock_db

        auditor = SecurityAuditor()
        auditor.get_sensitive_writes(limit=15)

        mock_db.get_writes_by_level.assert_called_with(["critical", "high"], 15)

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_get_all_writes(self, mock_reporter_cls, mock_analyzer_fn, mock_db_cls):
        """get_all_writes delegates to database"""
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {"total_scanned": 0, "total_commands": 0}
        mock_db.get_all_scanned_ids.return_value = set()
        mock_db.get_all_writes.return_value = []
        mock_db_cls.return_value = mock_db

        auditor = SecurityAuditor()
        auditor.get_all_writes(limit=500)

        mock_db.get_all_writes.assert_called_with(500)

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_get_risky_webfetches(
        self, mock_reporter_cls, mock_analyzer_fn, mock_db_cls
    ):
        """get_risky_webfetches delegates to database"""
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {"total_scanned": 0, "total_commands": 0}
        mock_db.get_all_scanned_ids.return_value = set()
        mock_db.get_webfetches_by_level.return_value = []
        mock_db_cls.return_value = mock_db

        auditor = SecurityAuditor()
        auditor.get_risky_webfetches(limit=15)

        mock_db.get_webfetches_by_level.assert_called_with(["critical", "high"], 15)

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_get_all_webfetches(self, mock_reporter_cls, mock_analyzer_fn, mock_db_cls):
        """get_all_webfetches delegates to database"""
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {"total_scanned": 0, "total_commands": 0}
        mock_db.get_all_scanned_ids.return_value = set()
        mock_db.get_all_webfetches.return_value = []
        mock_db_cls.return_value = mock_db

        auditor = SecurityAuditor()
        auditor.get_all_webfetches(limit=500)

        mock_db.get_all_webfetches.assert_called_with(500)

    @patch("opencode_monitor.security.auditor.SecurityDatabase")
    @patch("opencode_monitor.security.auditor.get_risk_analyzer")
    @patch("opencode_monitor.security.auditor.SecurityReporter")
    def test_generate_report(self, mock_reporter_cls, mock_analyzer_fn, mock_db_cls):
        """generate_report uses reporter with correct data"""
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {"total_scanned": 100, "total_commands": 50}
        mock_db.get_all_scanned_ids.return_value = set()
        mock_db.get_commands_by_level.return_value = []
        mock_db.get_reads_by_level.return_value = []
        mock_db.get_writes_by_level.return_value = []
        mock_db.get_webfetches_by_level.return_value = []
        mock_db_cls.return_value = mock_db

        mock_reporter = MagicMock()
        mock_reporter.generate_summary_report.return_value = "Test Report"
        mock_reporter_cls.return_value = mock_reporter

        auditor = SecurityAuditor()
        result = auditor.generate_report()

        assert result == "Test Report"
        mock_reporter.generate_summary_report.assert_called_once()


# =====================================================
# Global Functions Tests
# =====================================================


class TestGlobalFunctions:
    """Tests for global singleton functions"""

    def test_get_auditor_creates_singleton(self):
        """get_auditor creates a singleton instance"""
        import opencode_monitor.security.auditor as auditor_module

        # Reset global state
        auditor_module._auditor = None

        with patch.object(auditor_module, "SecurityAuditor") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            result1 = get_auditor()
            result2 = get_auditor()

            mock_cls.assert_called_once()
            assert result1 is result2

        # Clean up
        auditor_module._auditor = None

    def test_get_auditor_returns_existing(self):
        """get_auditor returns existing instance"""
        import opencode_monitor.security.auditor as auditor_module

        mock_auditor = MagicMock()
        auditor_module._auditor = mock_auditor

        result = get_auditor()

        assert result is mock_auditor

        # Clean up
        auditor_module._auditor = None

    def test_start_auditor_calls_start(self):
        """start_auditor starts the auditor"""
        import opencode_monitor.security.auditor as auditor_module

        mock_auditor = MagicMock()
        auditor_module._auditor = mock_auditor

        start_auditor()

        mock_auditor.start.assert_called_once()

        # Clean up
        auditor_module._auditor = None

    def test_stop_auditor_stops_and_clears(self):
        """stop_auditor stops the auditor and clears the singleton"""
        import opencode_monitor.security.auditor as auditor_module

        mock_auditor = MagicMock()
        auditor_module._auditor = mock_auditor

        stop_auditor()

        mock_auditor.stop.assert_called_once()
        assert auditor_module._auditor is None

    def test_stop_auditor_when_none(self):
        """stop_auditor handles None auditor gracefully"""
        import opencode_monitor.security.auditor as auditor_module

        auditor_module._auditor = None

        stop_auditor()  # Should not raise

        assert auditor_module._auditor is None
