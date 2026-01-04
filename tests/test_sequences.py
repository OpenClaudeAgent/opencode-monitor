"""
Tests for SequenceAnalyzer - Kill Chain Detection.

Consolidated tests covering:
- Event buffering per session
- Kill chain pattern detection (exfiltration, script, supply chain, enumeration)
- Mass deletion detection
- Time window filtering
- Event factory function
"""

import time

import pytest

from opencode_monitor.security.sequences import (
    SequenceAnalyzer,
    SecurityEvent,
    EventType,
    create_event_from_audit_data,
)


# =====================================================
# Fixtures
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


# =====================================================
# Event Buffering Tests (consolidated)
# =====================================================


class TestEventBuffering:
    """Tests for event buffering functionality."""

    def test_session_buffer_operations(
        self, analyzer: SequenceAnalyzer, base_time: float
    ):
        """Session buffers: creation, ordering, max size, clearing."""
        # Create events in order
        e1 = create_event(EventType.READ, "/file1", timestamp=base_time)
        e2 = create_event(EventType.WRITE, "/file2", timestamp=base_time + 1)
        e3 = create_event(EventType.BASH, "ls", timestamp=base_time + 2)

        analyzer.add_event(e1)
        analyzer.add_event(e2)
        analyzer.add_event(e3)

        # Verify session created and events ordered
        sessions = analyzer.get_active_sessions()
        buffer = analyzer.get_session_buffer("test-session")
        assert sessions == ["test-session"]
        assert len(buffer) == 3
        assert buffer[0].target == "/file1"
        assert buffer[1].target == "/file2"
        assert buffer[2].target == "ls"

        # Clear and verify
        analyzer.clear_session("test-session")
        assert analyzer.get_active_sessions() == []
        assert analyzer.get_session_buffer("test-session") == []

    def test_buffer_max_size_and_multiple_sessions(self, base_time: float):
        """Buffer respects max size and sessions are isolated."""
        small_analyzer = SequenceAnalyzer(buffer_size=5)

        # Overflow buffer with 10 events
        for i in range(10):
            event = create_event(EventType.BASH, f"cmd{i}", timestamp=base_time + i)
            small_analyzer.add_event(event)

        # Add event to different session
        e_other = create_event(EventType.READ, "/other", session_id="other-session")
        small_analyzer.add_event(e_other)

        # Verify buffer size and session isolation
        buffer = small_analyzer.get_session_buffer("test-session")
        assert len(buffer) == 5
        assert buffer[0].target == "cmd5"  # First 5 dropped
        assert buffer[4].target == "cmd9"

        sessions = small_analyzer.get_active_sessions()
        assert len(sessions) == 2
        assert len(small_analyzer.get_session_buffer("other-session")) == 1

        # clear_all works
        small_analyzer.clear_all()
        assert small_analyzer.get_active_sessions() == []


# =====================================================
# Kill Chain Detection Tests (consolidated)
# =====================================================


class TestKillChainDetection:
    """Consolidated tests for all kill chain patterns."""

    @pytest.mark.parametrize(
        "sensitive_file,webfetch_url,expected_match",
        [
            ("/app/.env", "https://evil.com/collect", True),
            ("/secrets/api.key", "https://attacker.io/exfil", True),
            ("/app/.env", "http://localhost:3000/api", False),  # localhost excluded
            ("/app/.env", "http://127.0.0.1:8080/test", False),  # 127.0.0.1 excluded
        ],
        ids=["env-external", "key-external", "localhost", "127.0.0.1"],
    )
    def test_exfiltration_detection(
        self,
        analyzer: SequenceAnalyzer,
        base_time: float,
        sensitive_file: str,
        webfetch_url: str,
        expected_match: bool,
    ):
        """read(sensitive) -> webfetch(external) triggers exfiltration detection."""
        e1 = create_event(EventType.READ, sensitive_file, timestamp=base_time)
        e2 = create_event(EventType.WEBFETCH, webfetch_url, timestamp=base_time + 10)

        analyzer.add_event(e1)
        matches = analyzer.add_event(e2)

        exfil_matches = [m for m in matches if m.name == "exfiltration"]

        if expected_match:
            assert len(exfil_matches) == 1
            assert exfil_matches[0].name == "exfiltration"
            assert exfil_matches[0].score_bonus == 40
            assert exfil_matches[0].mitre_technique == "T1048"
            assert exfil_matches[0].session_id == "test-session"
        else:
            assert len(exfil_matches) == 0
            # Verify buffer still has both events
            buffer = analyzer.get_session_buffer("test-session")
            assert len(buffer) == 2

    def test_exfiltration_outside_window(
        self, analyzer: SequenceAnalyzer, base_time: float
    ):
        """Events outside 5-minute window don't trigger detection."""
        e1 = create_event(EventType.READ, "/app/.env", timestamp=base_time)
        e2 = create_event(
            EventType.WEBFETCH,
            "https://evil.com/collect",
            timestamp=base_time + 600,  # 10 minutes later
        )

        analyzer.add_event(e1)
        matches = analyzer.add_event(e2)

        exfil_matches = [m for m in matches if m.name == "exfiltration"]
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
        e1 = create_event(EventType.WRITE, script_path, timestamp=base_time)
        e2 = create_event(EventType.BASH, chmod_cmd, timestamp=base_time + 5)
        e3 = create_event(EventType.BASH, exec_cmd, timestamp=base_time + 10)

        analyzer.add_event(e1)
        analyzer.add_event(e2)
        matches = analyzer.add_event(e3)

        script_matches = [m for m in matches if m.name == "script_execution"]
        assert len(script_matches) == 1
        assert script_matches[0].name == "script_execution"
        assert script_matches[0].score_bonus == 30
        assert script_matches[0].mitre_technique == "T1059"
        assert script_matches[0].session_id == "test-session"
        # Verify all 3 events buffered
        assert len(analyzer.get_session_buffer("test-session")) == 3

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
        e1 = create_event(
            EventType.BASH,
            "git clone https://github.com/malicious/repo",
            timestamp=base_time,
        )
        e2 = create_event(EventType.BASH, install_cmd, timestamp=base_time + 60)
        e3 = create_event(EventType.BASH, post_cmd, timestamp=base_time + 120)

        analyzer.add_event(e1)
        analyzer.add_event(e2)
        matches = analyzer.add_event(e3)

        supply_matches = [m for m in matches if m.name == "supply_chain"]
        assert len(supply_matches) == 1
        assert supply_matches[0].name == "supply_chain"
        assert supply_matches[0].mitre_technique == "T1195"
        assert supply_matches[0].session_id == "test-session"
        assert supply_matches[0].score_bonus > 0

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
        e1 = create_event(EventType.READ, "/etc/passwd", timestamp=base_time)
        e2 = create_event(EventType.READ, second_file, timestamp=base_time + 5)

        analyzer.add_event(e1)
        matches = analyzer.add_event(e2)

        enum_matches = [m for m in matches if m.name == "system_enumeration"]
        assert len(enum_matches) == 1
        assert enum_matches[0].name == "system_enumeration"
        assert enum_matches[0].mitre_technique == "T1087"
        assert enum_matches[0].session_id == "test-session"
        assert enum_matches[0].score_bonus > 0
        # Both read events in buffer
        assert len(analyzer.get_session_buffer("test-session")) == 2


# =====================================================
# Mass Deletion Tests (consolidated)
# =====================================================


class TestMassDeletion:
    """Tests for mass deletion detection."""

    @pytest.mark.parametrize(
        "rm_count,window_seconds,threshold,expected_match",
        [
            (6, 30, 5, True),  # 6 rm in 30s, threshold 5 -> match
            (3, 30, 5, False),  # 3 rm in 30s, threshold 5 -> no match
            (10, 60, 5, True),  # 10 rm in 60s, threshold 5 -> match
        ],
        ids=["above-threshold", "below-threshold", "many-deletions"],
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
                EventType.BASH,
                f"rm -rf /tmp/dir{i}",
                timestamp=base_time + i * 3,  # 3s apart
            )
            analyzer.add_event(event)

        match = analyzer.check_mass_deletion(
            "test-session",
            window_seconds=window_seconds,
            threshold=threshold,
        )

        if expected_match:
            assert match.name == "mass_deletion"
            assert match.score_bonus == 20
            assert match.mitre_technique == "T1070"
        else:
            assert match is None

    def test_mass_deletion_outside_window(
        self, analyzer: SequenceAnalyzer, base_time: float
    ):
        """rm commands outside window don't count together."""
        # First 5 rm commands
        for i in range(5):
            event = create_event(
                EventType.BASH, f"rm /tmp/file{i}", timestamp=base_time + i
            )
            analyzer.add_event(event)

        # 6th rm command 60 seconds later (outside 30s window)
        event = create_event(EventType.BASH, "rm /tmp/last", timestamp=base_time + 60)
        analyzer.add_event(event)

        # Only 1 rm in the last 30s window
        match = analyzer.check_mass_deletion(
            "test-session", window_seconds=30, threshold=5
        )
        assert match is None


# =====================================================
# Event Factory Tests (consolidated)
# =====================================================


class TestEventFactory:
    """Tests for create_event_from_audit_data factory."""

    @pytest.mark.parametrize(
        "tool,expected_type",
        [
            ("bash", EventType.BASH),
            ("read", EventType.READ),
            ("write", EventType.WRITE),
            ("edit", EventType.WRITE),  # edit maps to WRITE
            ("webfetch", EventType.WEBFETCH),
            ("mystery_tool", EventType.UNKNOWN),
            ("glob", EventType.UNKNOWN),
        ],
        ids=["bash", "read", "write", "edit->write", "webfetch", "unknown", "glob"],
    )
    def test_tool_to_event_type_mapping(self, tool: str, expected_type: EventType):
        """Tool names map correctly to EventType."""
        event = create_event_from_audit_data(
            tool=tool,
            target="test-target",
            session_id="sess-001",
            risk_score=10,
        )

        assert event.event_type == expected_type
        assert event.target == "test-target"
        assert event.session_id == "sess-001"
        assert event.risk_score == 10

    def test_default_timestamp_set(self):
        """Default timestamp is set to current time if not provided."""
        before = time.time()
        event = create_event_from_audit_data(
            tool="bash", target="ls", session_id="sess-001"
        )
        after = time.time()

        assert before <= event.timestamp <= after


# =====================================================
# Edge Cases (consolidated)
# =====================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_and_single_event_behavior(self, analyzer: SequenceAnalyzer):
        """Empty buffer returns empty list, single event triggers no sequences."""
        # Non-existent session
        buffer = analyzer.get_session_buffer("non-existent")
        assert buffer == []

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
        assert matches[0].session_id == "custom-session"
        assert matches[0].name == "exfiltration"
