"""
Tests for SequenceAnalyzer - Kill Chain Detection.

Consolidated tests covering event buffering, kill chain patterns,
mass deletion detection, time window filtering, and event factory.
"""

import time
import pytest
from opencode_monitor.security.sequences import (
    SequenceAnalyzer,
    SecurityEvent,
    EventType,
    SequenceMatch,
    create_event_from_audit_data,
)


# =====================================================
# Fixtures & Helpers
# =====================================================


@pytest.fixture
def analyzer() -> SequenceAnalyzer:
    """Create a fresh SequenceAnalyzer for each test."""
    return SequenceAnalyzer(buffer_size=100, default_window_seconds=300.0)


def create_event(
    event_type: EventType,
    target: str,
    session_id: str = "test-session",
    timestamp: float = 0.0,
    risk_score: int = 0,
) -> SecurityEvent:
    """Helper to create security events."""
    ts = timestamp if timestamp > 0 else time.time()
    return SecurityEvent(
        event_type=event_type,
        target=target,
        session_id=session_id,
        timestamp=ts,
        risk_score=risk_score,
    )


def assert_match(
    m: SequenceMatch, name: str, desc: str, bonus: int, mitre: str, n_events: int
):
    """Assert SequenceMatch has expected properties."""
    assert m.name == name
    assert m.description == desc
    assert m.score_bonus == bonus
    assert m.mitre_technique == mitre
    assert len(m.events) == n_events


# =====================================================
# Event Buffering Tests
# =====================================================


class TestEventBuffering:
    """Tests for event buffering functionality."""

    def test_session_buffer_operations(
        self, analyzer: SequenceAnalyzer, base_time: float
    ):
        """Session buffers: creation, ordering, max size, clearing."""
        e1 = create_event(EventType.READ, "/file1", timestamp=base_time)
        e2 = create_event(EventType.WRITE, "/file2", timestamp=base_time + 1)
        e3 = create_event(EventType.BASH, "ls", timestamp=base_time + 2)

        analyzer.add_event(e1)
        analyzer.add_event(e2)
        analyzer.add_event(e3)

        sessions = analyzer.get_active_sessions()
        buffer = analyzer.get_session_buffer("test-session")
        assert sessions == ["test-session"]
        assert len(buffer) == 3
        assert [b.target for b in buffer] == ["/file1", "/file2", "ls"]

        analyzer.clear_session("test-session")
        assert analyzer.get_active_sessions() == []
        assert analyzer.get_session_buffer("test-session") == []

    def test_buffer_max_size_and_multiple_sessions(self, base_time: float):
        """Buffer respects max size and sessions are isolated."""
        small_analyzer = SequenceAnalyzer(buffer_size=5)

        for i in range(10):
            event = create_event(EventType.BASH, f"cmd{i}", timestamp=base_time + i)
            small_analyzer.add_event(event)

        e_other = create_event(EventType.READ, "/other", session_id="other-session")
        small_analyzer.add_event(e_other)

        buffer = small_analyzer.get_session_buffer("test-session")
        assert len(buffer) == 5
        assert buffer[0].target == "cmd5"
        assert buffer[4].target == "cmd9"

        sessions = small_analyzer.get_active_sessions()
        assert len(sessions) == 2
        assert len(small_analyzer.get_session_buffer("other-session")) == 1

        small_analyzer.clear_all()
        assert small_analyzer.get_active_sessions() == []


# =====================================================
# Kill Chain Detection Tests
# =====================================================


class TestKillChainDetection:
    """Consolidated tests for all kill chain patterns."""

    @pytest.mark.parametrize(
        "sensitive_file,webfetch_url,expected_match,time_offset",
        [
            ("/app/.env", "https://evil.com/collect", True, 10),
            ("/secrets/api.key", "https://attacker.io/exfil", True, 10),
            ("/app/.env", "http://localhost:3000/api", False, 10),
            ("/app/.env", "http://127.0.0.1:8080/test", False, 10),
            ("/app/.env", "https://evil.com", True, 300),  # Boundary (kills <= vs <)
            ("/app/.env", "https://evil.com/collect", False, 600),  # Outside window
        ],
        ids=[
            "env-external",
            "key-external",
            "localhost",
            "127.0.0.1",
            "boundary-300s",
            "outside-window",
        ],
    )
    def test_exfiltration_detection(
        self,
        analyzer: SequenceAnalyzer,
        base_time: float,
        sensitive_file: str,
        webfetch_url: str,
        expected_match: bool,
        time_offset: int,
    ):
        """read(sensitive) -> webfetch(external) triggers exfiltration detection."""
        noise1 = create_event(
            EventType.READ, "/normal/file.txt", timestamp=base_time - 2
        )
        noise2 = create_event(
            EventType.WEBFETCH, "http://localhost/api", timestamp=base_time - 1
        )
        e1 = create_event(EventType.READ, sensitive_file, timestamp=base_time)
        e2 = create_event(
            EventType.WEBFETCH, webfetch_url, timestamp=base_time + time_offset
        )

        analyzer.add_event(noise1)
        analyzer.add_event(noise2)
        analyzer.add_event(e1)
        matches = analyzer.add_event(e2)

        exfil_matches = [m for m in matches if m.name == "exfiltration"]

        if expected_match:
            assert len(exfil_matches) == 1
            m = exfil_matches[0]
            assert_match(m, "exfiltration", "Exfiltration of secrets", 40, "T1048", 2)
            assert m.session_id == "test-session"
            assert m.events[0].target == sensitive_file
            assert m.events[1].target == webfetch_url
        else:
            assert len(exfil_matches) == 0

    @pytest.mark.parametrize(
        "chmod_cmd,exec_cmd",
        [
            ("chmod +x /tmp/malware.sh", "bash /tmp/malware.sh"),
            ("chmod 755 /tmp/script.bash", "/tmp/script.bash"),
        ],
        ids=["chmod-plus-x", "chmod-755"],
    )
    def test_script_execution_detection(
        self,
        analyzer: SequenceAnalyzer,
        base_time: float,
        chmod_cmd: str,
        exec_cmd: str,
    ):
        """write(.sh) -> chmod(+x) -> bash(.sh) triggers script execution."""
        script_path = chmod_cmd.split()[-1]
        noise0 = create_event(
            EventType.WRITE, "/tmp/readme.txt", timestamp=base_time - 1
        )
        e1 = create_event(EventType.WRITE, script_path, timestamp=base_time)
        noise1 = create_event(EventType.BASH, "ls -la", timestamp=base_time + 2)
        e2 = create_event(EventType.BASH, chmod_cmd, timestamp=base_time + 5)
        noise2 = create_event(EventType.BASH, "echo test", timestamp=base_time + 7)
        e3 = create_event(EventType.BASH, exec_cmd, timestamp=base_time + 10)

        for ev in [noise0, e1, noise1, e2, noise2, e3]:
            analyzer.add_event(ev)
        matches = [
            m
            for m in analyzer._check_patterns("test-session")
            if m.name == "script_execution"
        ]

        assert len(matches) == 1
        m = matches[0]
        assert_match(
            m, "script_execution", "Creation and execution of script", 30, "T1059", 3
        )
        assert m.events[0].target == script_path
        assert m.events[2].target == exec_cmd
        assert len(analyzer.get_session_buffer("test-session")) == 6

    @pytest.mark.parametrize(
        "install_cmd,post_cmd",
        [
            ("npm install", "bash ./node_modules/.bin/postinstall.sh"),
            ("pip install -r requirements.txt", "python setup.py"),
            ("yarn install", "node scripts/postinstall.js"),
        ],
        ids=["npm", "pip", "yarn"],
    )
    def test_supply_chain_detection(
        self,
        analyzer: SequenceAnalyzer,
        base_time: float,
        install_cmd: str,
        post_cmd: str,
    ):
        """git clone -> package install -> execution triggers supply chain detection."""
        noise0 = create_event(EventType.BASH, "pwd", timestamp=base_time - 1)
        e1 = create_event(
            EventType.BASH,
            "git clone https://github.com/malicious/repo",
            timestamp=base_time,
        )
        noise1 = create_event(EventType.BASH, "echo hello", timestamp=base_time + 100)
        e2 = create_event(EventType.BASH, install_cmd, timestamp=base_time + 200)
        noise2 = create_event(EventType.BASH, "ls -la", timestamp=base_time + 350)
        e3 = create_event(EventType.BASH, post_cmd, timestamp=base_time + 400)

        for ev in [noise0, e1, noise1, e2, noise2, e3]:
            analyzer.add_event(ev)
        matches = [
            m
            for m in analyzer._check_patterns("test-session")
            if m.name == "supply_chain"
        ]

        assert len(matches) == 1
        m = matches[0]
        assert_match(m, "supply_chain", "Potential supply chain attack", 25, "T1195", 3)
        assert "git clone" in m.events[0].target
        assert m.events[2].target == post_cmd

    @pytest.mark.parametrize(
        "second_file",
        ["/etc/shadow", "/etc/group", "/etc/sudoers"],
        ids=["shadow", "group", "sudoers"],
    )
    def test_system_enumeration_detection(
        self,
        analyzer: SequenceAnalyzer,
        base_time: float,
        second_file: str,
    ):
        """read(/etc/passwd) -> read(system file) triggers enumeration."""
        noise0 = create_event(
            EventType.READ, "/tmp/readme.txt", timestamp=base_time - 1
        )
        e1 = create_event(EventType.READ, "/etc/passwd", timestamp=base_time)
        noise1 = create_event(
            EventType.READ, "/home/user/.bashrc", timestamp=base_time + 2
        )
        e2 = create_event(EventType.READ, second_file, timestamp=base_time + 5)

        for ev in [noise0, e1, noise1, e2]:
            analyzer.add_event(ev)
        matches = [
            m
            for m in analyzer._check_patterns("test-session")
            if m.name == "system_enumeration"
        ]

        assert len(matches) == 1
        m = matches[0]
        assert_match(m, "system_enumeration", "System enumeration", 35, "T1087", 2)
        assert m.events[0].target == "/etc/passwd"
        assert m.events[1].target == second_file
        assert len(analyzer.get_session_buffer("test-session")) == 4


# =====================================================
# Mass Deletion Tests
# =====================================================


class TestMassDeletion:
    """Tests for mass deletion detection."""

    @pytest.mark.parametrize(
        "rm_count,window_seconds,threshold,expected_match",
        [
            (6, 30, 5, True),
            (3, 30, 5, False),
            (10, 60, 5, True),
            (5, 30, 5, True),  # Exact threshold (kills >= vs >)
        ],
        ids=["above-threshold", "below-threshold", "many-deletions", "exact-threshold"],
    )
    def test_mass_deletion_threshold(
        self,
        analyzer: SequenceAnalyzer,
        base_time: float,
        rm_count: int,
        window_seconds: int,
        threshold: int,
        expected_match: bool,
    ):
        """Mass deletion detected based on rm count and time window."""
        for i in range(rm_count):
            event = create_event(
                EventType.BASH, f"rm -rf /tmp/dir{i}", timestamp=base_time + i * 3
            )
            analyzer.add_event(event)

        match = analyzer.check_mass_deletion(
            "test-session", window_seconds=window_seconds, threshold=threshold
        )

        if expected_match:
            assert match is not None
            assert match.name == "mass_deletion"
            assert match.description == "Mass deletion detected"
            assert match.score_bonus == 20
            assert match.mitre_technique == "T1070"
            assert len(match.events) >= threshold
        else:
            assert match is None

    @pytest.mark.parametrize(
        "timestamps,window,threshold,expect_match,reason",
        [
            # First 5 rm in 0-4s, 6th at 60s => only 1 in last 30s window
            ([0, 1, 2, 3, 4, 60], 30, 5, False, "outside-window"),
            # 5 rm at t=30,35,45,55,60 => t=30 exactly at boundary from t=60
            ([30, 35, 45, 55, 60], 30, 5, True, "boundary-included"),
        ],
        ids=["outside-window", "boundary-window"],
    )
    def test_mass_deletion_window_edge_cases(
        self,
        analyzer: SequenceAnalyzer,
        base_time: float,
        timestamps: list,
        window: int,
        threshold: int,
        expect_match: bool,
        reason: str,
    ):
        """Edge cases: events outside window don't count, boundary events included."""
        for i, ts in enumerate(timestamps):
            event = create_event(
                EventType.BASH, f"rm /tmp/file{i}", timestamp=base_time + ts
            )
            analyzer.add_event(event)

        match = analyzer.check_mass_deletion(
            "test-session", window_seconds=window, threshold=threshold
        )

        if expect_match:
            assert match is not None
            assert match.name == "mass_deletion"
            assert len(match.events) == len(timestamps)
        else:
            assert match is None


# =====================================================
# Event Factory Tests
# =====================================================


class TestEventFactory:
    """Tests for create_event_from_audit_data factory."""

    @pytest.mark.parametrize(
        "tool,expected_type",
        [
            ("bash", EventType.BASH),
            ("read", EventType.READ),
            ("write", EventType.WRITE),
            ("edit", EventType.WRITE),
            ("webfetch", EventType.WEBFETCH),
            ("mystery_tool", EventType.UNKNOWN),
            ("glob", EventType.UNKNOWN),
        ],
        ids=["bash", "read", "write", "edit->write", "webfetch", "unknown", "glob"],
    )
    def test_tool_to_event_type_mapping(self, tool: str, expected_type: EventType):
        """Tool names map correctly to EventType."""
        event = create_event_from_audit_data(
            tool=tool, target="test-target", session_id="sess-001", risk_score=10
        )
        assert event.event_type == expected_type
        assert event.target == "test-target"
        assert event.session_id == "sess-001"
        assert event.risk_score == 10

    def test_timestamp_handling(self):
        """Default timestamp is now; explicit timestamp preserved (kills or vs and)."""
        before = time.time()
        event_default = create_event_from_audit_data(
            tool="bash", target="ls", session_id="sess-001"
        )
        after = time.time()
        assert before <= event_default.timestamp <= after

        explicit_ts = 1234567890.0
        event_explicit = create_event_from_audit_data(
            tool="bash", target="ls", session_id="sess-001", timestamp=explicit_ts
        )
        assert event_explicit.timestamp == explicit_ts

    def test_default_risk_score_is_zero(self):
        """Default risk_score is 0 (kills risk_score: 0 -> 1 mutant)."""
        event = create_event_from_audit_data(
            tool="bash", target="ls", session_id="sess-001"
        )
        assert event.risk_score == 0


# =====================================================
# Edge Cases
# =====================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_buffer_single_event_and_match_properties(
        self, analyzer: SequenceAnalyzer
    ):
        """Empty buffer, single event, and SequenceMatch edge cases."""
        # Non-existent session returns empty
        assert analyzer.get_session_buffer("non-existent") == []

        # SequenceMatch with empty events
        empty_match = SequenceMatch(
            name="test", description="test", events=[], score_bonus=0
        )
        assert empty_match.session_id == ""
        assert empty_match.mitre_technique == ""

        # Single event doesn't trigger sequences
        event = create_event(EventType.READ, "/app/.env")
        matches = analyzer.add_event(event)
        assert len(matches) == 0

    def test_sequence_match_contains_session_id(
        self, analyzer: SequenceAnalyzer, base_time: float
    ):
        """SequenceMatch includes correct session_id from triggering events."""
        e1 = create_event(
            EventType.READ,
            "/app/.env",
            session_id="custom-session",
            timestamp=base_time,
        )
        e2 = create_event(
            EventType.WEBFETCH,
            "https://evil.com",
            session_id="custom-session",
            timestamp=base_time + 10,
        )

        analyzer.add_event(e1)
        matches = analyzer.add_event(e2)

        assert len(matches) == 1
        m = matches[0]
        assert m.session_id == "custom-session"
        assert_match(m, "exfiltration", "Exfiltration of secrets", 40, "T1048", 2)
