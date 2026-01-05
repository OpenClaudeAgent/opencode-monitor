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
        "state": {"input": input_args, "time": {"start": 1703001000000}},
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
        yield AuditorTestContext(SecurityAuditor(), mock_db, mock_analyzer)


# =====================================================
# Initialization and Lifecycle Tests
# =====================================================


class TestSecurityAuditorInitAndLifecycle:
    """Tests for SecurityAuditor initialization and lifecycle."""

    @pytest.mark.parametrize(
        "cached_stats,scanned_ids,expected_scanned,expected_commands,expected_ids_count,actions,expected_running",
        [
            # Init fresh start, no lifecycle actions
            (make_default_stats(), set(), 0, 0, 0, [], None),
            # Init restored from cache, no lifecycle actions
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
                [],
                None,
            ),
            # Full lifecycle: start, start (idempotent), stop
            (make_default_stats(), set(), 0, 0, 0, ["start", "start", "stop"], False),
            # Stop without start
            (make_default_stats(), set(), 0, 0, 0, ["stop"], False),
        ],
        ids=["init_fresh", "init_cached", "lifecycle_full", "lifecycle_stop_only"],
    )
    def test_init_and_lifecycle(
        self,
        cached_stats,
        scanned_ids,
        expected_scanned,
        expected_commands,
        expected_ids_count,
        actions,
        expected_running,
    ):
        """Test initialization loads stats and lifecycle works correctly."""
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

            # Verify init
            assert auditor._running is False
            assert auditor._thread is None
            mock_db_cls.assert_called_once()
            mock_analyzer_fn.assert_called_once()
            mock_reporter_cls.assert_called_once()
            assert auditor._stats["total_scanned"] == expected_scanned
            assert auditor._stats["total_commands"] == expected_commands
            assert auditor._stats["last_scan"] is None
            assert len(auditor._scanned_ids) == expected_ids_count

            # Execute lifecycle actions if any
            if actions:
                first_thread = None
                with patch.object(auditor, "_scan_loop"):
                    for action in actions:
                        if action == "start":
                            auditor.start()
                            if first_thread is None:
                                first_thread = auditor._thread
                                assert auditor._running is True
                                assert auditor._thread is not None
                                assert auditor._thread.daemon is True
                        elif action == "stop":
                            auditor.stop()

                assert auditor._running == expected_running
                if first_thread and "start" in actions:
                    assert auditor._thread is first_thread


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
    def test_process_tool_types(
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
        prt_file = tmp_path / f"prt_{tool}.json"
        prt_file.write_text(json.dumps(create_tool_content(tool, **input_args)))
        result = auditor_with_mocks._process_file(prt_file)

        assert result["type"] == expected_type
        assert result[expected_field] == expected_value
        assert "risk_score" in result
        assert "risk_level" in result

    @pytest.mark.parametrize(
        "scenario,content_factory",
        [
            ("bash_empty", lambda: create_tool_content("bash", command="")),
            ("read_empty", lambda: create_tool_content("read", filePath="")),
            ("write_empty", lambda: create_tool_content("write", filePath="")),
            ("webfetch_empty", lambda: create_tool_content("webfetch", url="")),
            ("non_tool", lambda: {"type": "message", "content": "Not a tool"}),
            (
                "unknown_tool",
                lambda: {
                    "type": "tool",
                    "tool": "unknown",
                    "sessionID": "s1",
                    "state": {"input": {}, "time": {"start": 1}},
                },
            ),
            ("invalid_json", lambda: "INVALID_JSON_MARKER"),
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
    def test_process_returns_none_for_invalid(
        self, auditor_with_mocks, tmp_path, scenario, content_factory
    ):
        """Invalid contents return None."""
        prt_file = tmp_path / f"prt_{scenario}.json"
        content = content_factory()
        prt_file.write_text(
            "not valid json {{{"
            if content == "INVALID_JSON_MARKER"
            else json.dumps(content)
        )
        assert auditor_with_mocks._process_file(prt_file) is None


# =====================================================
# Run Scan Tests
# =====================================================


class TestRunScan:
    """Tests for _run_scan method."""

    @pytest.mark.parametrize(
        "scenario,storage_exists,already_scanned,running,expect_insert,setup_exception",
        [
            ("process_new", True, set(), True, True, None),
            ("skip_scanned", True, {"prt_001.json"}, True, False, None),
            ("no_storage", False, set(), True, False, None),
            ("exception", True, set(), True, False, PermissionError("No access")),
            ("not_running", True, set(), False, False, None),
        ],
        ids=["process_new", "skip_scanned", "no_storage", "exception", "not_running"],
    )
    def test_run_scan_scenarios(
        self,
        tmp_path,
        scenario,
        storage_exists,
        already_scanned,
        running,
        expect_insert,
        setup_exception,
    ):
        """Run scan handles all scenarios correctly."""
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

            storage = tmp_path / "storage"
            if storage_exists:
                if scenario == "not_running":
                    for i in range(5):
                        msg_dir = storage / f"msg_{i:03d}"
                        msg_dir.mkdir(parents=True)
                        (msg_dir / f"prt_{i:03d}.json").write_text(
                            json.dumps(create_tool_content("bash", command="ls"))
                        )
                else:
                    msg_dir = storage / "msg_001"
                    msg_dir.mkdir(parents=True)
                    (msg_dir / "prt_001.json").write_text(
                        json.dumps(create_tool_content("bash", command="ls -la"))
                    )

                if setup_exception:
                    mock_storage_path.exists.return_value = True
                    mock_storage_path.iterdir.side_effect = setup_exception
                else:
                    mock_storage_path.exists.return_value = True
                    mock_storage_path.iterdir.return_value = [msg_dir]
            else:
                mock_storage_path.exists.return_value = False

            auditor = SecurityAuditor()
            auditor._running = running
            if not running:
                auditor._thread = MagicMock()
            elif running:
                auditor._thread = MagicMock()

            if storage_exists and not setup_exception:
                with patch(
                    "opencode_monitor.security.auditor.OPENCODE_STORAGE", storage
                ):
                    auditor._run_scan()
            else:
                auditor._run_scan()

            if expect_insert:
                mock_db.insert_command.assert_called_once()
                assert auditor._stats["total_scanned"] == 1
            elif scenario == "skip_scanned":
                mock_db.insert_command.assert_not_called()
            elif scenario == "no_storage":
                mock_storage_path.iterdir.assert_not_called()
            elif scenario == "not_running":
                assert auditor._stats["total_scanned"] == 0

    def test_routes_all_tools_and_scan_loop_works(self, auditor_with_mocks, tmp_path):
        """Scan routes tools correctly; loop runs periodically; update_stat works."""
        auditor = auditor_with_mocks

        # Test tool routing
        storage = tmp_path / "storage"
        msg_dir = storage / "msg_001"
        msg_dir.mkdir(parents=True)
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

        # Test scan loop
        auditor._running = True
        auditor._stats["high"] = 5
        call_count = [0]

        def stop_after_second(*args):
            call_count[0] += 1
            if call_count[0] >= 2:
                auditor._running = False

        with (
            patch.object(auditor._auditor, "_run_scan") as mock_run,
            patch(
                "opencode_monitor.security.auditor.time.sleep",
                side_effect=stop_after_second,
            ),
        ):
            auditor._scan_loop()
        assert mock_run.call_count >= 2

        # Test update_stat
        auditor._update_stat("high")
        assert auditor._stats["high"] == 6
        auditor._update_stat("unknown")
        assert "unknown" not in auditor._stats


# =====================================================
# Public API and Global Functions Tests
# =====================================================


class TestPublicAPIAndGlobals:
    """Tests for public API methods and global singleton functions."""

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
            ("get_stats", {}, None, None),
            ("generate_report", {}, None, None),
        ],
        ids=[
            "critical_cmds",
            "cmds_by_level",
            "all_cmds",
            "sensitive_reads",
            "all_reads",
            "sensitive_writes",
            "all_writes",
            "risky_fetches",
            "all_fetches",
            "get_stats",
            "report",
        ],
    )
    def test_api_methods(
        self, auditor_with_mocks, method_name, method_args, db_method, db_args
    ):
        """API methods delegate correctly to database."""
        auditor = auditor_with_mocks

        if method_name == "get_stats":
            auditor._stats["total_scanned"] = 100
            stats = auditor.get_stats()
            stats["total_scanned"] = 999
            assert auditor._stats["total_scanned"] == 100
        elif method_name == "generate_report":
            with patch.object(auditor._auditor, "_reporter") as mock_rep:
                mock_rep.generate_summary_report.return_value = "Report"
                assert auditor.generate_report() == "Report"
        else:
            getattr(auditor.mock_db, db_method).return_value = []
            getattr(auditor, method_name)(**method_args)
            getattr(auditor.mock_db, db_method).assert_called_with(*db_args)

    @pytest.mark.parametrize(
        "stop_when_none", [False, True], ids=["full_lifecycle", "stop_when_none"]
    )
    def test_singleton_functions(self, stop_when_none):
        """Global singleton lifecycle works correctly."""
        import opencode_monitor.security.auditor as mod

        mod._auditor = None

        if stop_when_none:
            stop_auditor()
            assert mod._auditor is None
        else:
            with patch.object(mod, "SecurityAuditor") as mock_cls:
                mock_inst = MagicMock()
                mock_cls.return_value = mock_inst

                r1 = get_auditor()
                r2 = get_auditor()
                mock_cls.assert_called_once()
                assert r1 is r2

                start_auditor()
                mock_inst.start.assert_called_once()

                stop_auditor()
                mock_inst.stop.assert_called_once()
                assert mod._auditor is None

            mod._auditor = None
