"""
Tests for SecurityAuditor - Background scanner for OpenCode command history.

Consolidated test suite covering:
- Initialization with cached stats
- Start/stop lifecycle
- File processing for all tool types
- Scan loop and run_scan behavior
- Public API delegation
- Global singleton functions
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from opencode_monitor.security.auditor import (
    SecurityAuditor,
    get_auditor,
    start_auditor,
    stop_auditor,
)
from opencode_monitor.security.analyzer import RiskResult


# =====================================================
# Local Helpers
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


def make_default_stats(
    total_scanned=0, total_commands=0, total_reads=0, total_writes=0, total_webfetches=0
):
    """Create stats dict with defaults."""
    return {
        "total_scanned": total_scanned,
        "total_commands": total_commands,
        "total_reads": total_reads,
        "total_writes": total_writes,
        "total_webfetches": total_webfetches,
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
    }


# =====================================================
# Shared Fixtures
# =====================================================


@pytest.fixture
def mock_db():
    """Standard mock database with common stats."""
    db = MagicMock()
    db.get_stats.return_value = make_default_stats()
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
    """Container for auditor and its mocked dependencies."""

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
        return getattr(self._auditor, name)

    def __setattr__(self, name, value):
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


# =====================================================
# Initialization Tests
# =====================================================


class TestSecurityAuditorInit:
    """Tests for SecurityAuditor initialization and cached stats loading."""

    @pytest.mark.parametrize(
        "cached_stats,scanned_ids,expected_scanned,expected_commands,expected_ids_count",
        [
            # Fresh start - no cached data
            (make_default_stats(), set(), 0, 0, 0),
            # Restored from cache with existing IDs
            (
                {
                    **make_default_stats(100, 50, 20, 10, 5),
                    "critical": 3,
                    "high": 10,
                    "medium": 20,
                    "low": 67,
                },
                {"f1", "f2", "f3"},
                100,
                50,
                3,
            ),
        ],
        ids=["fresh_start", "restored_from_cache"],
    )
    def test_init_creates_components_and_loads_stats(
        self,
        cached_stats,
        scanned_ids,
        expected_scanned,
        expected_commands,
        expected_ids_count,
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
            mock_db.get_all_scanned_ids.return_value = scanned_ids
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
# Lifecycle Tests - Start/Stop
# =====================================================


class TestSecurityAuditorLifecycle:
    """Tests for start/stop lifecycle management."""

    @pytest.mark.parametrize(
        "scenario,actions,expected_running,expected_thread_is_first",
        [
            # Start creates thread, second start is idempotent, stop cleans up
            (
                "full_lifecycle",
                ["start", "start", "stop"],
                False,
                True,
            ),
            # Stop without start is safe
            (
                "stop_only",
                ["stop"],
                False,
                None,
            ),
        ],
        ids=["full_lifecycle", "stop_without_start"],
    )
    def test_lifecycle_scenarios(
        self,
        auditor_with_mocks,
        scenario,
        actions,
        expected_running,
        expected_thread_is_first,
    ):
        """Test various lifecycle scenarios."""
        ctx = auditor_with_mocks
        first_thread = None

        with patch.object(ctx._auditor, "_scan_loop"):
            for action in actions:
                if action == "start":
                    ctx.start()
                    if first_thread is None:
                        first_thread = ctx._thread
                        assert ctx._running is True
                        assert ctx._thread is not None
                        assert ctx._thread.daemon is True
                elif action == "stop":
                    ctx.stop()

            assert ctx._running == expected_running

            if expected_thread_is_first is True:
                # Verify second start didn't create new thread
                assert ctx._thread is first_thread


# =====================================================
# File Processing Tests
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

        assert result["type"] == expected_type
        assert result[expected_field] == expected_value
        assert "risk_score" in result
        assert "risk_level" in result

    @pytest.mark.parametrize(
        "scenario,content_factory,expected_none",
        [
            # Empty inputs
            ("bash_empty", lambda: create_tool_content("bash", command=""), True),
            ("read_empty", lambda: create_tool_content("read", filePath=""), True),
            ("write_empty", lambda: create_tool_content("write", filePath=""), True),
            ("webfetch_empty", lambda: create_tool_content("webfetch", url=""), True),
            # Non-tool and unknown tool
            (
                "non_tool",
                lambda: {"type": "message", "content": "Not a tool"},
                True,
            ),
            (
                "unknown_tool",
                lambda: {
                    "type": "tool",
                    "tool": "unknown_tool",
                    "sessionID": "s1",
                    "state": {"input": {}, "time": {"start": 1}},
                },
                True,
            ),
            # Invalid JSON (special case)
            ("invalid_json", lambda: "INVALID_JSON_MARKER", True),
        ],
        ids=[
            "bash_empty",
            "read_empty",
            "write_empty",
            "webfetch_empty",
            "non_tool",
            "unknown_tool",
            "invalid_json",
        ],
    )
    def test_process_returns_none_for_invalid_content(
        self, auditor_with_mocks, tmp_path, scenario, content_factory, expected_none
    ):
        """Various invalid contents return None."""
        auditor = auditor_with_mocks

        prt_file = tmp_path / f"prt_{scenario}.json"
        content = content_factory()

        if content == "INVALID_JSON_MARKER":
            prt_file.write_text("not valid json {{{")
        else:
            prt_file.write_text(json.dumps(content))

        result = auditor._process_file(prt_file)
        assert result is None


# =====================================================
# Run Scan Tests - Consolidated
# =====================================================


class TestRunScan:
    """Tests for _run_scan method - consolidated scenarios."""

    @pytest.mark.parametrize(
        "scenario,storage_exists,already_scanned,running,expect_insert",
        [
            # Normal: processes new files
            ("process_new", True, set(), True, True),
            # Skip already scanned
            ("skip_scanned", True, {"prt_001.json"}, True, False),
            # No storage dir
            ("no_storage", False, set(), True, False),
        ],
        ids=["process_new_files", "skip_already_scanned", "no_storage_dir"],
    )
    def test_run_scan_scenarios(
        self,
        tmp_path,
        scenario,
        storage_exists,
        already_scanned,
        running,
        expect_insert,
    ):
        """Run scan handles various scenarios correctly."""
        with (
            patch("opencode_monitor.security.auditor.SecurityDatabase") as mock_db_cls,
            patch(
                "opencode_monitor.security.auditor.get_risk_analyzer"
            ) as mock_analyzer_fn,
            patch("opencode_monitor.security.auditor.SecurityReporter"),
            patch(
                "opencode_monitor.security.auditor.OPENCODE_STORAGE"
            ) as mock_storage_path,
        ):
            mock_db = MagicMock()
            mock_db.get_stats.return_value = make_default_stats()
            mock_db.get_all_scanned_ids.return_value = already_scanned
            mock_db_cls.return_value = mock_db

            mock_analyzer = MagicMock()
            mock_analyzer.analyze_file_path.return_value = RiskResult(
                score=60, level="high", reason="Test"
            )
            mock_analyzer_fn.return_value = mock_analyzer

            # Setup storage
            storage = tmp_path / "storage"
            if storage_exists:
                msg_dir = storage / "msg_001"
                msg_dir.mkdir(parents=True)
                content = create_tool_content("bash", command="ls -la")
                (msg_dir / "prt_001.json").write_text(json.dumps(content))
                mock_storage_path.exists.return_value = True
                mock_storage_path.iterdir.return_value = [msg_dir]
            else:
                mock_storage_path.exists.return_value = False

            auditor = SecurityAuditor()
            auditor._running = running
            if running:
                auditor._thread = MagicMock()

            # Use real storage path for existing scenarios
            if storage_exists:
                with patch(
                    "opencode_monitor.security.auditor.OPENCODE_STORAGE", storage
                ):
                    auditor._run_scan()
            else:
                auditor._run_scan()

            if expect_insert:
                mock_db.insert_command.assert_called_once()
                assert auditor._stats["total_scanned"] == 1
            else:
                if scenario == "skip_scanned":
                    mock_db.insert_command.assert_not_called()
                elif scenario == "no_storage":
                    mock_storage_path.iterdir.assert_not_called()

    def test_run_scan_routes_all_tool_types(self, auditor_with_mocks, tmp_path):
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

        # All insert methods called
        auditor.mock_db.insert_command.assert_called()
        auditor.mock_db.insert_read.assert_called()
        auditor.mock_db.insert_write.assert_called()
        auditor.mock_db.insert_webfetch.assert_called()

    @pytest.mark.parametrize(
        "scenario,setup_exception,running_state",
        [
            ("exception", PermissionError("No access"), True),
            ("not_running", None, False),
        ],
        ids=["handles_exception", "stops_when_not_running"],
    )
    def test_run_scan_edge_cases(
        self, tmp_path, scenario, setup_exception, running_state
    ):
        """Scan handles exceptions gracefully and stops when not running."""
        with (
            patch("opencode_monitor.security.auditor.OPENCODE_STORAGE") as mock_storage,
            patch("opencode_monitor.security.auditor.SecurityDatabase") as mock_db_cls,
            patch("opencode_monitor.security.auditor.get_risk_analyzer"),
            patch("opencode_monitor.security.auditor.SecurityReporter"),
        ):
            mock_db = MagicMock()
            mock_db.get_stats.return_value = make_default_stats()
            mock_db.get_all_scanned_ids.return_value = set()
            mock_db_cls.return_value = mock_db

            if setup_exception:
                mock_storage.exists.return_value = True
                mock_storage.iterdir.side_effect = setup_exception
            else:
                # Setup storage with files for not_running test
                storage = tmp_path / "storage"
                for i in range(5):
                    msg_dir = storage / f"msg_{i:03d}"
                    msg_dir.mkdir(parents=True)
                    content = create_tool_content("bash", command="ls")
                    (msg_dir / f"prt_{i:03d}.json").write_text(json.dumps(content))

            auditor = SecurityAuditor()
            auditor._running = running_state
            if not running_state:
                auditor._thread = MagicMock()

            if setup_exception:
                auditor._run_scan()  # Should not raise
            else:
                with patch(
                    "opencode_monitor.security.auditor.OPENCODE_STORAGE", storage
                ):
                    auditor._run_scan()
                assert auditor._stats["total_scanned"] == 0


# =====================================================
# Scan Loop and Stats Tests
# =====================================================


class TestScanLoopAndStats:
    """Tests for _scan_loop and _update_stat methods."""

    def test_scan_loop_runs_periodically_and_update_stat_works(
        self, auditor_with_mocks
    ):
        """Scan loop runs periodic scans; update_stat increments correctly."""
        ctx = auditor_with_mocks
        ctx._running = True
        ctx._stats["high"] = 5

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

        # Scan loop ran multiple times
        assert mock_run.call_count >= 2

        # Test update_stat behavior
        ctx._update_stat("high")
        assert ctx._stats["high"] == 6

        # Unknown key ignored
        ctx._update_stat("unknown_key")
        assert "unknown_key" not in ctx._stats


# =====================================================
# Public API Tests
# =====================================================


class TestPublicAPI:
    """Tests for public API methods."""

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
            "critical_commands",
            "commands_by_level",
            "all_commands",
            "sensitive_reads",
            "all_reads",
            "sensitive_writes",
            "all_writes",
            "risky_webfetches",
            "all_webfetches",
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

    def test_get_stats_returns_copy_and_generate_report_works(self, auditor_with_mocks):
        """get_stats returns defensive copy; generate_report uses reporter."""
        auditor = auditor_with_mocks
        auditor._stats["total_scanned"] = 100

        # get_stats returns copy
        stats = auditor.get_stats()
        stats["total_scanned"] = 999
        assert auditor._stats["total_scanned"] == 100

        # generate_report delegates to reporter
        with patch.object(auditor._auditor, "_reporter") as mock_reporter:
            mock_reporter.generate_summary_report.return_value = "Test Report"
            result = auditor.generate_report()
            assert result == "Test Report"


# =====================================================
# Global Singleton Functions Tests
# =====================================================


class TestGlobalFunctions:
    """Tests for global singleton functions."""

    @pytest.mark.parametrize(
        "test_stop_when_none",
        [False, True],
        ids=["full_lifecycle", "stop_when_none"],
    )
    def test_singleton_functions(self, test_stop_when_none):
        """Singleton lifecycle: get creates, start starts, stop clears."""
        import opencode_monitor.security.auditor as auditor_module

        auditor_module._auditor = None

        if test_stop_when_none:
            # Just test stop when None
            stop_auditor()  # Should not raise
            assert auditor_module._auditor is None
        else:
            # Full lifecycle test
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

            auditor_module._auditor = None
