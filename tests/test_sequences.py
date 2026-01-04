"""
Tests for SequenceAnalyzer - Kill Chain Detection.

Tests cover:
- Event buffering per session
- Kill chain pattern detection
- Mass deletion detection
- Time window filtering
- MITRE technique tagging
"""

import time

import pytest

from opencode_monitor.security.sequences import (
    SequenceAnalyzer,
    SecurityEvent,
    EventType,
    SequenceMatch,
    create_event_from_audit_data,
    KILL_CHAIN_PATTERNS,
)


# =====================================================
# Fixtures (base_time is provided by conftest.py)
# =====================================================


@pytest.fixture
def sequence_analyzer() -> SequenceAnalyzer:
    """Create a fresh SequenceAnalyzer for each test.

    Named 'sequence_analyzer' to avoid confusion with 'risk_analyzer' in conftest.
    """
    return SequenceAnalyzer(buffer_size=100, default_window_seconds=300.0)


# Alias for backward compatibility
@pytest.fixture
def analyzer(sequence_analyzer: SequenceAnalyzer) -> SequenceAnalyzer:
    """Alias for sequence_analyzer."""
    return sequence_analyzer


# Note: 'base_time' fixture is now provided by conftest.py


def create_event(
    event_type: EventType,
    target: str,
    session_id: str = "test-session",
    timestamp: float = 0.0,
    risk_score: int = 0,
) -> SecurityEvent:
    """Helper to create security events"""
    ts = timestamp if timestamp > 0 else time.time()
    return SecurityEvent(
        event_type=event_type,
        target=target,
        session_id=session_id,
        timestamp=ts,
        risk_score=risk_score,
    )


# =====================================================
# Basic Event Buffering Tests
# =====================================================


class TestEventBuffering:
    """Tests for event buffering functionality"""

    def test_add_event_creates_session_buffer(self, analyzer: SequenceAnalyzer):
        """Adding an event creates a session buffer"""
        event = create_event(EventType.READ, "/home/user/.env")
        analyzer.add_event(event)

        assert "test-session" in analyzer.get_active_sessions()

    def test_events_stored_in_order(self, analyzer: SequenceAnalyzer, base_time: float):
        """Events are stored in chronological order"""
        e1 = create_event(EventType.READ, "/file1", timestamp=base_time)
        e2 = create_event(EventType.WRITE, "/file2", timestamp=base_time + 1)
        e3 = create_event(EventType.BASH, "ls", timestamp=base_time + 2)

        analyzer.add_event(e1)
        analyzer.add_event(e2)
        analyzer.add_event(e3)

        buffer = analyzer.get_session_buffer("test-session")
        assert len(buffer) == 3
        assert buffer[0].target == "/file1"
        assert buffer[2].target == "ls"

    def test_buffer_respects_max_size(self, base_time: float):
        """Buffer doesn't exceed max size"""
        analyzer = SequenceAnalyzer(buffer_size=5)

        for i in range(10):
            event = create_event(EventType.BASH, f"cmd{i}", timestamp=base_time + i)
            analyzer.add_event(event)

        buffer = analyzer.get_session_buffer("test-session")
        assert len(buffer) == 5
        assert buffer[0].target == "cmd5"  # First 5 dropped

    def test_separate_session_buffers(self, analyzer: SequenceAnalyzer):
        """Different sessions have separate buffers"""
        e1 = create_event(EventType.READ, "/file1", session_id="session-1")
        e2 = create_event(EventType.WRITE, "/file2", session_id="session-2")

        analyzer.add_event(e1)
        analyzer.add_event(e2)

        assert len(analyzer.get_active_sessions()) == 2
        assert len(analyzer.get_session_buffer("session-1")) == 1
        assert len(analyzer.get_session_buffer("session-2")) == 1

    def test_clear_session(self, analyzer: SequenceAnalyzer):
        """Clearing a session removes its buffer"""
        event = create_event(EventType.READ, "/file1")
        analyzer.add_event(event)

        analyzer.clear_session("test-session")

        assert "test-session" not in analyzer.get_active_sessions()
        assert len(analyzer.get_session_buffer("test-session")) == 0

    def test_clear_all(self, analyzer: SequenceAnalyzer):
        """Clearing all removes all buffers"""
        e1 = create_event(EventType.READ, "/file1", session_id="s1")
        e2 = create_event(EventType.READ, "/file2", session_id="s2")

        analyzer.add_event(e1)
        analyzer.add_event(e2)
        analyzer.clear_all()

        assert len(analyzer.get_active_sessions()) == 0


# =====================================================
# Exfiltration Sequence Tests
# =====================================================


class TestExfiltrationSequence:
    """Tests for exfiltration kill chain detection"""

    def test_env_read_then_webfetch_detected(
        self, analyzer: SequenceAnalyzer, base_time: float
    ):
        """read(.env) -> webfetch(external) triggers exfiltration detection"""
        e1 = create_event(EventType.READ, "/app/.env", timestamp=base_time)
        e2 = create_event(
            EventType.WEBFETCH,
            "https://evil.com/collect",
            timestamp=base_time + 10,
        )

        analyzer.add_event(e1)
        matches = analyzer.add_event(e2)

        assert len(matches) == 1
        assert matches[0].name == "exfiltration"
        assert matches[0].score_bonus == 40
        assert matches[0].mitre_technique == "T1048"

    def test_key_read_then_webfetch_detected(
        self, analyzer: SequenceAnalyzer, base_time: float
    ):
        """read(.key) -> webfetch(external) triggers exfiltration"""
        e1 = create_event(EventType.READ, "/secrets/api.key", timestamp=base_time)
        e2 = create_event(
            EventType.WEBFETCH,
            "https://attacker.io/exfil",
            timestamp=base_time + 30,
        )

        analyzer.add_event(e1)
        matches = analyzer.add_event(e2)

        assert len(matches) == 1
        assert matches[0].name == "exfiltration"

    def test_localhost_webfetch_not_exfiltration(
        self, analyzer: SequenceAnalyzer, base_time: float
    ):
        """read(.env) -> webfetch(localhost) does NOT trigger exfiltration"""
        e1 = create_event(EventType.READ, "/app/.env", timestamp=base_time)
        e2 = create_event(
            EventType.WEBFETCH,
            "http://localhost:3000/api",
            timestamp=base_time + 10,
        )

        analyzer.add_event(e1)
        matches = analyzer.add_event(e2)

        # Should not match because localhost is excluded
        exfil_matches = [m for m in matches if m.name == "exfiltration"]
        assert len(exfil_matches) == 0

    def test_exfiltration_outside_window_not_detected(
        self, analyzer: SequenceAnalyzer, base_time: float
    ):
        """Events outside time window don't trigger detection"""
        e1 = create_event(EventType.READ, "/app/.env", timestamp=base_time)
        # 10 minutes later (beyond 5 minute window)
        e2 = create_event(
            EventType.WEBFETCH,
            "https://evil.com/collect",
            timestamp=base_time + 600,
        )

        analyzer.add_event(e1)
        matches = analyzer.add_event(e2)

        exfil_matches = [m for m in matches if m.name == "exfiltration"]
        assert len(exfil_matches) == 0


# =====================================================
# Script Execution Sequence Tests
# =====================================================


class TestScriptExecutionSequence:
    """Tests for script creation and execution kill chain"""

    def test_write_chmod_bash_detected(
        self, analyzer: SequenceAnalyzer, base_time: float
    ):
        """write(.sh) -> chmod(+x) -> bash(.sh) triggers script execution"""
        e1 = create_event(EventType.WRITE, "/tmp/malware.sh", timestamp=base_time)
        e2 = create_event(
            EventType.BASH,
            "chmod +x /tmp/malware.sh",
            timestamp=base_time + 5,
        )
        e3 = create_event(
            EventType.BASH,
            "bash /tmp/malware.sh",
            timestamp=base_time + 10,
        )

        analyzer.add_event(e1)
        analyzer.add_event(e2)
        matches = analyzer.add_event(e3)

        assert len(matches) == 1
        assert matches[0].name == "script_execution"
        assert matches[0].score_bonus == 30
        assert matches[0].mitre_technique == "T1059"

    def test_chmod_numeric_detected(self, analyzer: SequenceAnalyzer, base_time: float):
        """chmod 755 also triggers the pattern"""
        e1 = create_event(EventType.WRITE, "/tmp/script.bash", timestamp=base_time)
        e2 = create_event(
            EventType.BASH,
            "chmod 755 /tmp/script.bash",
            timestamp=base_time + 5,
        )
        e3 = create_event(
            EventType.BASH,
            "/tmp/script.bash",
            timestamp=base_time + 10,
        )

        analyzer.add_event(e1)
        analyzer.add_event(e2)
        matches = analyzer.add_event(e3)

        script_matches = [m for m in matches if m.name == "script_execution"]
        assert len(script_matches) == 1


# =====================================================
# Supply Chain Sequence Tests
# =====================================================


class TestSupplyChainSequence:
    """Tests for supply chain attack detection"""

    def test_git_clone_npm_install_bash_detected(
        self, analyzer: SequenceAnalyzer, base_time: float
    ):
        """git clone -> npm install -> bash triggers supply chain detection"""
        e1 = create_event(
            EventType.BASH,
            "git clone https://github.com/malicious/repo",
            timestamp=base_time,
        )
        e2 = create_event(
            EventType.BASH,
            "npm install",
            timestamp=base_time + 60,
        )
        e3 = create_event(
            EventType.BASH,
            "bash ./node_modules/.bin/postinstall.sh",
            timestamp=base_time + 120,
        )

        analyzer.add_event(e1)
        analyzer.add_event(e2)
        matches = analyzer.add_event(e3)

        supply_matches = [m for m in matches if m.name == "supply_chain"]
        assert len(supply_matches) == 1
        assert supply_matches[0].mitre_technique == "T1195"

    def test_pip_install_also_matches(
        self, analyzer: SequenceAnalyzer, base_time: float
    ):
        """pip install also triggers the pattern"""
        e1 = create_event(
            EventType.BASH,
            "git clone https://github.com/user/repo",
            timestamp=base_time,
        )
        e2 = create_event(
            EventType.BASH,
            "pip install -r requirements.txt",
            timestamp=base_time + 30,
        )
        e3 = create_event(
            EventType.BASH,
            "python setup.py",
            timestamp=base_time + 60,
        )

        analyzer.add_event(e1)
        analyzer.add_event(e2)
        matches = analyzer.add_event(e3)

        supply_matches = [m for m in matches if m.name == "supply_chain"]
        assert len(supply_matches) == 1


# =====================================================
# System Enumeration Tests
# =====================================================


class TestSystemEnumeration:
    """Tests for system enumeration detection"""

    def test_passwd_shadow_detected(self, analyzer: SequenceAnalyzer, base_time: float):
        """read(/etc/passwd) -> read(/etc/shadow) triggers enumeration"""
        e1 = create_event(EventType.READ, "/etc/passwd", timestamp=base_time)
        e2 = create_event(EventType.READ, "/etc/shadow", timestamp=base_time + 5)

        analyzer.add_event(e1)
        matches = analyzer.add_event(e2)

        enum_matches = [m for m in matches if m.name == "system_enumeration"]
        assert len(enum_matches) == 1
        assert enum_matches[0].mitre_technique == "T1087"

    def test_passwd_group_detected(self, analyzer: SequenceAnalyzer, base_time: float):
        """/etc/passwd -> /etc/group also triggers"""
        e1 = create_event(EventType.READ, "/etc/passwd", timestamp=base_time)
        e2 = create_event(EventType.READ, "/etc/group", timestamp=base_time + 5)

        analyzer.add_event(e1)
        matches = analyzer.add_event(e2)

        enum_matches = [m for m in matches if m.name == "system_enumeration"]
        assert len(enum_matches) == 1


# =====================================================
# Mass Deletion Tests
# =====================================================


class TestMassDeletion:
    """Tests for mass deletion detection"""

    def test_multiple_rm_in_short_time_detected(
        self, analyzer: SequenceAnalyzer, base_time: float
    ):
        """5+ rm commands in 30s triggers mass deletion"""
        for i in range(6):
            event = create_event(
                EventType.BASH,
                f"rm -rf /tmp/dir{i}",
                timestamp=base_time + i * 5,
            )
            analyzer.add_event(event)

        match = analyzer.check_mass_deletion(
            "test-session", window_seconds=30, threshold=5
        )

        assert match is not None
        assert match.name == "mass_deletion"
        assert match.score_bonus == 20
        assert match.mitre_technique == "T1070"

    def test_few_rm_not_detected(self, analyzer: SequenceAnalyzer, base_time: float):
        """Less than threshold rm commands don't trigger"""
        for i in range(3):
            event = create_event(
                EventType.BASH,
                f"rm /tmp/file{i}",
                timestamp=base_time + i,
            )
            analyzer.add_event(event)

        match = analyzer.check_mass_deletion("test-session", threshold=5)

        assert match is None

    def test_rm_outside_window_not_detected(
        self, analyzer: SequenceAnalyzer, base_time: float
    ):
        """rm commands outside window don't count"""
        # First 5 rm commands
        for i in range(5):
            event = create_event(
                EventType.BASH,
                f"rm /tmp/file{i}",
                timestamp=base_time + i,
            )
            analyzer.add_event(event)

        # 6th rm command 60 seconds later (outside 30s window)
        event = create_event(
            EventType.BASH,
            "rm /tmp/last",
            timestamp=base_time + 60,
        )
        analyzer.add_event(event)

        match = analyzer.check_mass_deletion(
            "test-session", window_seconds=30, threshold=5
        )

        assert match is None  # Only 1 rm in the last 30s


# =====================================================
# Factory Function Tests
# =====================================================


class TestCreateEventFromAuditData:
    """Tests for create_event_from_audit_data factory"""

    def test_bash_event(self):
        """Creates bash event correctly"""
        event = create_event_from_audit_data(
            tool="bash",
            target="ls -la",
            session_id="sess-001",
            risk_score=10,
        )

        assert event.event_type == EventType.BASH
        assert event.target == "ls -la"
        assert event.session_id == "sess-001"
        assert event.risk_score == 10

    def test_read_event(self):
        """Creates read event correctly"""
        event = create_event_from_audit_data(
            tool="read",
            target="/etc/passwd",
            session_id="sess-001",
        )

        assert event.event_type == EventType.READ
        assert event.target == "/etc/passwd"

    def test_write_event(self):
        """Creates write event correctly"""
        event = create_event_from_audit_data(
            tool="write",
            target="/tmp/file.txt",
            session_id="sess-001",
        )

        assert event.event_type == EventType.WRITE

    def test_edit_maps_to_write(self):
        """edit tool maps to WRITE event type"""
        event = create_event_from_audit_data(
            tool="edit",
            target="/tmp/file.txt",
            session_id="sess-001",
        )

        assert event.event_type == EventType.WRITE

    def test_webfetch_event(self):
        """Creates webfetch event correctly"""
        event = create_event_from_audit_data(
            tool="webfetch",
            target="https://example.com",
            session_id="sess-001",
        )

        assert event.event_type == EventType.WEBFETCH

    def test_unknown_tool_maps_to_unknown(self):
        """Unknown tool maps to UNKNOWN event type"""
        event = create_event_from_audit_data(
            tool="mystery_tool",
            target="something",
            session_id="sess-001",
        )

        assert event.event_type == EventType.UNKNOWN

    def test_default_timestamp(self):
        """Default timestamp is set if not provided"""
        before = time.time()
        event = create_event_from_audit_data(
            tool="bash",
            target="ls",
            session_id="sess-001",
        )
        after = time.time()

        assert before <= event.timestamp <= after


# =====================================================
# Edge Cases
# =====================================================


class TestEdgeCases:
    """Tests for edge cases"""

    def test_empty_session_buffer(self, analyzer: SequenceAnalyzer):
        """Getting buffer for non-existent session returns empty list"""
        buffer = analyzer.get_session_buffer("non-existent")
        assert buffer == []

    def test_no_matches_for_single_event(self, analyzer: SequenceAnalyzer):
        """Single event doesn't trigger any sequences"""
        event = create_event(EventType.READ, "/app/.env")
        matches = analyzer.add_event(event)

        assert len(matches) == 0

    def test_sequence_match_session_id(
        self, analyzer: SequenceAnalyzer, base_time: float
    ):
        """SequenceMatch has correct session_id"""
        e1 = create_event(
            EventType.READ, "/app/.env", session_id="my-session", timestamp=base_time
        )
        e2 = create_event(
            EventType.WEBFETCH,
            "https://evil.com",
            session_id="my-session",
            timestamp=base_time + 10,
        )

        analyzer.add_event(e1)
        matches = analyzer.add_event(e2)

        assert matches[0].session_id == "my-session"
