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
        "sensitive_file,webfetch_url,expected_match,time_offset",
        [
            ("/app/.env", "https://evil.com/collect", True, 10),
            ("/secrets/api.key", "https://attacker.io/exfil", True, 10),
            ("/app/.env", "http://localhost:3000/api", False, 10),  # localhost excluded
            (
                "/app/.env",
                "http://127.0.0.1:8080/test",
                False,
                10,
            ),  # 127.0.0.1 excluded
            (
                "/app/.env",
                "https://evil.com",
                True,
                300,
            ),  # Exactly at boundary (kills <= vs < mutant)
        ],
        ids=["env-external", "key-external", "localhost", "127.0.0.1", "boundary-300s"],
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
        # Add noise events that should NOT match patterns (kills pattern key mutations)
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
            assert m.name == "exfiltration"
            assert m.description == "Exfiltration of secrets"
            assert m.score_bonus == 40
            assert m.mitre_technique == "T1048"
            assert m.session_id == "test-session"
            assert len(m.events) == 2
            # Verify matched events are the correct ones (kills pattern key mutations)
            assert m.events[0].target == sensitive_file
            assert m.events[1].target == webfetch_url
        else:
            assert len(exfil_matches) == 0
            # Verify buffer has all events (2 noise + 2 main)
            buffer = analyzer.get_session_buffer("test-session")
            assert len(buffer) == 4

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
        # Add noise BEFORE and BETWEEN events (kills pattern key mutations on ALL steps)
        noise0 = create_event(
            EventType.WRITE, "/tmp/readme.txt", timestamp=base_time - 1
        )  # Before e1
        e1 = create_event(EventType.WRITE, script_path, timestamp=base_time)
        noise1 = create_event(
            EventType.BASH, "ls -la", timestamp=base_time + 2
        )  # Between e1 and e2
        e2 = create_event(EventType.BASH, chmod_cmd, timestamp=base_time + 5)
        noise2 = create_event(
            EventType.BASH, "echo test", timestamp=base_time + 7
        )  # Between e2 and e3
        e3 = create_event(EventType.BASH, exec_cmd, timestamp=base_time + 10)

        analyzer.add_event(noise0)
        analyzer.add_event(e1)
        analyzer.add_event(noise1)
        analyzer.add_event(e2)
        analyzer.add_event(noise2)
        matches = analyzer.add_event(e3)

        script_matches = [m for m in matches if m.name == "script_execution"]
        assert len(script_matches) == 1
        m = script_matches[0]
        assert m.name == "script_execution"
        assert m.description == "Creation and execution of script"
        assert m.score_bonus == 30
        assert m.mitre_technique == "T1059"
        assert m.session_id == "test-session"
        assert len(m.events) == 3
        # Verify matched events are correct (kills pattern key mutations)
        assert m.events[0].target == script_path
        assert chmod_cmd in m.events[1].target or m.events[1].target == chmod_cmd
        assert m.events[2].target == exec_cmd
        # Verify all events buffered (3 noise + 3 main)
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
        # Use timestamps > 300s apart to kill max_window_seconds key mutations
        # (supply_chain has 600s window, default is 300s - events must span > 300s)
        noise0 = create_event(
            EventType.BASH, "pwd", timestamp=base_time - 1
        )  # Before e1
        e1 = create_event(
            EventType.BASH,
            "git clone https://github.com/malicious/repo",
            timestamp=base_time,
        )
        noise1 = create_event(
            EventType.BASH, "echo hello", timestamp=base_time + 100
        )  # Between
        e2 = create_event(EventType.BASH, install_cmd, timestamp=base_time + 200)
        noise2 = create_event(
            EventType.BASH, "ls -la", timestamp=base_time + 350
        )  # Between
        e3 = create_event(
            EventType.BASH, post_cmd, timestamp=base_time + 400
        )  # 400s from e1

        analyzer.add_event(noise0)
        analyzer.add_event(e1)
        analyzer.add_event(noise1)
        analyzer.add_event(e2)
        analyzer.add_event(noise2)
        matches = analyzer.add_event(e3)

        supply_matches = [m for m in matches if m.name == "supply_chain"]
        assert len(supply_matches) == 1
        m = supply_matches[0]
        assert m.name == "supply_chain"
        assert m.description == "Potential supply chain attack"
        assert m.score_bonus == 25
        assert m.mitre_technique == "T1195"
        assert m.session_id == "test-session"
        assert len(m.events) == 3
        # Verify matched events are correct (kills pattern key mutations)
        assert "git clone" in m.events[0].target
        assert install_cmd in m.events[1].target or m.events[1].target == install_cmd
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
        # Add noise BEFORE and BETWEEN events (kills pattern key mutations on ALL steps)
        noise0 = create_event(
            EventType.READ, "/tmp/readme.txt", timestamp=base_time - 1
        )  # Before e1
        e1 = create_event(EventType.READ, "/etc/passwd", timestamp=base_time)
        noise1 = create_event(
            EventType.READ, "/home/user/.bashrc", timestamp=base_time + 2
        )  # Between
        e2 = create_event(EventType.READ, second_file, timestamp=base_time + 5)

        analyzer.add_event(noise0)
        analyzer.add_event(e1)
        analyzer.add_event(noise1)
        matches = analyzer.add_event(e2)

        enum_matches = [m for m in matches if m.name == "system_enumeration"]
        assert len(enum_matches) == 1
        m = enum_matches[0]
        assert m.name == "system_enumeration"
        assert m.description == "System enumeration"
        assert m.score_bonus == 35
        assert m.mitre_technique == "T1087"
        assert m.session_id == "test-session"
        assert len(m.events) == 2
        # Verify matched events are correct (kills pattern key mutations)
        assert m.events[0].target == "/etc/passwd"
        assert m.events[1].target == second_file
        # All read events in buffer (2 noise + 2 main)
        assert len(analyzer.get_session_buffer("test-session")) == 4


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
            (5, 30, 5, True),  # Exactly at threshold (kills >= vs > mutant)
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
            assert match.description == "Mass deletion detected"
            assert match.score_bonus == 20
            assert match.mitre_technique == "T1070"
            assert len(match.events) >= threshold
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

    def test_mass_deletion_boundary_window(
        self, analyzer: SequenceAnalyzer, base_time: float
    ):
        """rm command exactly at window boundary should be included (kills <= vs < mutant)."""
        # 5 rm commands: 4 within window + 1 exactly at boundary
        timestamps = [
            base_time + 30,
            base_time + 35,
            base_time + 45,
            base_time + 55,
            base_time + 60,
        ]
        for i, ts in enumerate(timestamps):
            event = create_event(EventType.BASH, f"rm /tmp/file{i}", timestamp=ts)
            analyzer.add_event(event)

        # With window=30s from last event (60), events from 30+ should be included
        # Event at t=30 is exactly 30s before t=60
        match = analyzer.check_mass_deletion(
            "test-session", window_seconds=30, threshold=5
        )
        assert match is not None
        assert match.name == "mass_deletion"
        assert len(match.events) == 5


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

    def test_explicit_timestamp_preserved(self):
        """Explicitly provided timestamp should be preserved (kills or vs and mutant)."""
        explicit_ts = 1234567890.0
        event = create_event_from_audit_data(
            tool="bash",
            target="ls",
            session_id="sess-001",
            timestamp=explicit_ts,
        )
        # With 'or': explicit_ts or time.time() = explicit_ts (correct)
        # With 'and': explicit_ts and time.time() = time.time() (wrong!)
        assert event.timestamp == explicit_ts

    def test_default_risk_score_is_zero(self):
        """Default risk_score should be 0 (kills risk_score: 0 -> 1 mutant)."""
        event = create_event_from_audit_data(
            tool="bash", target="ls", session_id="sess-001"
        )
        assert event.risk_score == 0


# =====================================================
# Edge Cases (consolidated)
# =====================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_and_single_event_behavior(self, analyzer: SequenceAnalyzer):
        """Empty buffer returns empty list, single event triggers no sequences."""
        from opencode_monitor.security.sequences import SequenceMatch

        # Non-existent session
        buffer = analyzer.get_session_buffer("non-existent")
        assert buffer == []

        # SequenceMatch with empty events has empty session_id and default mitre
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
        assert m.name == "exfiltration"
        assert m.description == "Exfiltration of secrets"
        assert m.mitre_technique == "T1048"
