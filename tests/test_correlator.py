"""
Tests for EventCorrelator - Multi-event correlation.

Consolidated tests cover:
- Correlation detection (positive/negative cases)
- Session buffer management
- Edge cases
"""

import time
from typing import Any

import pytest

from opencode_monitor.security.sequences import SecurityEvent, EventType
from opencode_monitor.security.correlator import EventCorrelator


# =====================================================
# Fixtures
# =====================================================


@pytest.fixture
def correlator() -> EventCorrelator:
    """Create a fresh EventCorrelator for each test"""
    return EventCorrelator(buffer_size=200, default_window_seconds=300.0)


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
# Correlation Detection Tests (Positive Cases)
# =====================================================


class TestCorrelationDetection:
    """Tests for correlation detection - all positive cases consolidated"""

    @pytest.mark.parametrize(
        "event1_type,event1_target,event2_type,event2_target,expected_correlation,expected_mitre,expected_modifier",
        [
            # Exfiltration: read(sensitive) + webfetch(external)
            pytest.param(
                EventType.READ,
                "/home/user/.env",
                EventType.WEBFETCH,
                "https://evil.com/collect",
                "exfiltration_read_webfetch",
                "T1048",
                30,
                id="exfil_read_then_webfetch",
            ),
            # Exfiltration: webfetch(external) + read(sensitive) - reverse order
            pytest.param(
                EventType.WEBFETCH,
                "https://evil.com/check",
                EventType.READ,
                "/secrets/api.key",
                "exfiltration_read_webfetch",
                "T1048",
                30,
                id="exfil_webfetch_then_read",
            ),
            # RCE: webfetch(.sh) + bash
            pytest.param(
                EventType.WEBFETCH,
                "https://example.com/install.sh",
                EventType.BASH,
                "bash ./install.sh",
                "remote_code_execution",
                "T1059",
                35,
                id="rce_shell_script",
            ),
            # RCE: webfetch(.py) + python
            pytest.param(
                EventType.WEBFETCH,
                "https://example.com/payload.py",
                EventType.BASH,
                "python payload.py",
                "remote_code_execution",
                "T1059",
                35,
                id="rce_python_script",
            ),
            # Execution preparation: write(.sh) + chmod(+x)
            pytest.param(
                EventType.WRITE,
                "/tmp/backdoor.sh",
                EventType.BASH,
                "chmod +x /tmp/backdoor.sh",
                "execution_preparation",
                "T1222",
                25,
                id="exec_prep_chmod",
            ),
            # Git reconnaissance: read(.git/config) + webfetch(github)
            pytest.param(
                EventType.READ,
                "/project/.git/config",
                EventType.WEBFETCH,
                "https://github.com/some/repo",
                "git_reconnaissance",
                "T1592",
                20,
                id="git_recon",
            ),
        ],
    )
    def test_correlation_detected(
        self,
        correlator: EventCorrelator,
        base_time: float,
        event1_type: EventType,
        event1_target: str,
        event2_type: EventType,
        event2_target: str,
        expected_correlation: str,
        expected_mitre: str,
        expected_modifier: int,
    ):
        """Verify correlation is detected with correct metadata"""
        e1 = create_event(
            event1_type, event1_target, timestamp=base_time, risk_score=85
        )
        e2 = create_event(
            event2_type, event2_target, timestamp=base_time + 30, risk_score=50
        )

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)

        matching = [
            c for c in correlations if c.correlation_type == expected_correlation
        ]
        assert len(matching) == 1
        assert matching[0].mitre_technique == expected_mitre
        assert matching[0].score_modifier == expected_modifier

    def test_correlation_context_time_delta(
        self, correlator: EventCorrelator, base_time: float
    ):
        """Verify correlation context contains accurate time_delta_seconds"""
        e1 = create_event(EventType.READ, "/app/.env", timestamp=base_time)
        e2 = create_event(
            EventType.WEBFETCH,
            "https://evil.com/collect",
            timestamp=base_time + 30,
        )

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)

        exfil = [
            c
            for c in correlations
            if c.correlation_type == "exfiltration_read_webfetch"
        ]
        assert len(exfil) == 1
        assert exfil[0].context["time_delta_seconds"] == 30

    def test_correlation_session_id_preserved(
        self, correlator: EventCorrelator, base_time: float
    ):
        """Verify correlation preserves session_id from events"""
        e1 = create_event(
            EventType.READ, "/app/.env", session_id="my-session", timestamp=base_time
        )
        e2 = create_event(
            EventType.WEBFETCH,
            "https://evil.com",
            session_id="my-session",
            timestamp=base_time + 10,
        )

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)

        assert len(correlations) == 1
        assert correlations[0].session_id == "my-session"


# =====================================================
# No Correlation Tests (Negative Cases)
# =====================================================


class TestNoCorrelation:
    """Tests verifying correlations are NOT triggered in specific cases"""

    @pytest.mark.parametrize(
        "event1_type,event1_target,event2_type,event2_target,time_offset,reason",
        [
            # Localhost webfetch - not external
            pytest.param(
                EventType.READ,
                "/app/.env",
                EventType.WEBFETCH,
                "http://localhost:3000/api",
                10,
                "localhost_not_external",
                id="localhost_webfetch",
            ),
            # Events outside time window (600s > 300s default)
            pytest.param(
                EventType.READ,
                "/app/.env",
                EventType.WEBFETCH,
                "https://evil.com/collect",
                600,
                "outside_time_window",
                id="outside_window",
            ),
            # Same event type - no source/target pair
            pytest.param(
                EventType.READ,
                "/app/.env",
                EventType.READ,
                "/secrets/key",
                10,
                "same_type_no_pair",
                id="same_event_type",
            ),
        ],
    )
    def test_no_exfiltration_correlation(
        self,
        correlator: EventCorrelator,
        base_time: float,
        event1_type: EventType,
        event1_target: str,
        event2_type: EventType,
        event2_target: str,
        time_offset: int,
        reason: str,
    ):
        """Verify exfiltration correlation is NOT triggered"""
        e1 = create_event(event1_type, event1_target, timestamp=base_time)
        e2 = create_event(event2_type, event2_target, timestamp=base_time + time_offset)

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)

        exfil = [
            c
            for c in correlations
            if c.correlation_type == "exfiltration_read_webfetch"
        ]
        assert len(exfil) == 0

    def test_chmod_without_prior_write_no_correlation(
        self, correlator: EventCorrelator, base_time: float
    ):
        """chmod without prior write doesn't create execution_preparation"""
        e1 = create_event(
            EventType.BASH, "chmod +x /some/script.sh", timestamp=base_time
        )
        correlations = correlator.add_event(e1)

        prep = [
            c for c in correlations if c.correlation_type == "execution_preparation"
        ]
        assert len(prep) == 0

    def test_single_event_no_correlation(self, correlator: EventCorrelator):
        """Single event cannot create correlations"""
        event = create_event(EventType.READ, "/app/.env")
        correlations = correlator.add_event(event)

        assert len(correlations) == 0


# =====================================================
# Session Management Tests
# =====================================================


class TestSessionManagement:
    """Tests for session buffer management"""

    @pytest.mark.parametrize(
        "sessions_events,expected_counts",
        [
            # Two separate sessions
            pytest.param(
                [
                    ("session-1", EventType.READ, "/file1"),
                    ("session-2", EventType.WRITE, "/file2"),
                ],
                {"session-1": 1, "session-2": 1},
                id="separate_sessions",
            ),
            # Multiple events in one session
            pytest.param(
                [
                    ("session-1", EventType.READ, "/file1"),
                    ("session-1", EventType.WRITE, "/file2"),
                    ("session-2", EventType.READ, "/file3"),
                ],
                {"session-1": 2, "session-2": 1},
                id="multiple_in_one_session",
            ),
        ],
    )
    def test_session_buffer_counts(
        self,
        correlator: EventCorrelator,
        sessions_events: list[tuple[str, EventType, str]],
        expected_counts: dict[str, int],
    ):
        """Verify session buffers track events correctly"""
        for session_id, event_type, target in sessions_events:
            event = create_event(event_type, target, session_id=session_id)
            correlator.add_event(event)

        for session_id, expected_count in expected_counts.items():
            assert len(correlator.get_session_buffer(session_id)) == expected_count

    def test_clear_session_removes_data(self, correlator: EventCorrelator):
        """Clearing a session removes only that session's data"""
        e1 = create_event(EventType.READ, "/file1", session_id="s1")
        e2 = create_event(EventType.READ, "/file2", session_id="s2")

        correlator.add_event(e1)
        correlator.add_event(e2)
        correlator.clear_session("s1")

        assert len(correlator.get_session_buffer("s1")) == 0
        assert len(correlator.get_session_buffer("s2")) == 1

    def test_clear_all_removes_all_sessions(self, correlator: EventCorrelator):
        """Clearing all removes all session data"""
        e1 = create_event(EventType.READ, "/file1", session_id="s1")
        e2 = create_event(EventType.READ, "/file2", session_id="s2")

        correlator.add_event(e1)
        correlator.add_event(e2)
        correlator.clear_all()

        assert len(correlator.get_session_buffer("s1")) == 0
        assert len(correlator.get_session_buffer("s2")) == 0

    def test_empty_session_buffer_returns_empty_list(self, correlator: EventCorrelator):
        """Getting buffer for non-existent session returns empty list"""
        buffer = correlator.get_session_buffer("non-existent")
        assert buffer == []


# =====================================================
# Correlation Summary Tests
# =====================================================


class TestCorrelationSummary:
    """Tests for correlation summary functionality"""

    def test_summary_counts_by_type(
        self, correlator: EventCorrelator, base_time: float
    ):
        """get_correlation_summary returns accurate type counts"""
        # Create multiple exfiltration correlations
        e1 = create_event(EventType.READ, "/app/.env", timestamp=base_time)
        e2 = create_event(
            EventType.WEBFETCH, "https://evil.com/1", timestamp=base_time + 10
        )
        e3 = create_event(
            EventType.WEBFETCH, "https://evil.com/2", timestamp=base_time + 20
        )

        correlator.add_event(e1)
        corrs1 = correlator.add_event(e2)
        corrs2 = correlator.add_event(e3)

        all_corrs = corrs1 + corrs2
        summary = correlator.get_correlation_summary(all_corrs)

        assert summary["exfiltration_read_webfetch"] == 2


# =====================================================
# Confidence Score Tests
# =====================================================


class TestConfidenceScore:
    """Tests for correlation confidence scoring"""

    def test_close_events_high_risk_produces_high_confidence(
        self, correlator: EventCorrelator, base_time: float
    ):
        """High risk events close in time produce confidence > 0.8"""
        e1 = create_event(
            EventType.READ,
            "/secrets/.env",
            timestamp=base_time,
            risk_score=90,
        )
        e2 = create_event(
            EventType.WEBFETCH,
            "https://evil.com/exfil",
            timestamp=base_time + 1,  # Very close in time
            risk_score=80,
        )

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)

        exfil = [
            c
            for c in correlations
            if c.correlation_type == "exfiltration_read_webfetch"
        ]
        assert len(exfil) == 1
        # Confidence formula: base(0.5) + time_factor(~0.25) + risk_factor(~0.17) = ~0.92
        assert exfil[0].confidence >= 0.8

    def test_distant_events_low_risk_produces_lower_confidence(
        self, correlator: EventCorrelator, base_time: float
    ):
        """Low risk events far apart produce confidence between 0.5-0.7"""
        e1 = create_event(
            EventType.READ,
            "/app/.env",
            timestamp=base_time,
            risk_score=20,
        )
        e2 = create_event(
            EventType.WEBFETCH,
            "https://example.com",
            timestamp=base_time + 100,  # Far apart
            risk_score=10,
        )

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)

        exfil = [
            c
            for c in correlations
            if c.correlation_type == "exfiltration_read_webfetch"
        ]
        assert len(exfil) == 1
        # Lower confidence for distant, low-risk events
        assert 0.5 <= exfil[0].confidence <= 0.7
