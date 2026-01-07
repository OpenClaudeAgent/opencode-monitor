"""Tests for EventCorrelator - Multi-event correlation."""

import time
import pytest
from opencode_monitor.security.sequences import SecurityEvent, EventType
from opencode_monitor.security.correlator import EventCorrelator


@pytest.fixture
def correlator() -> EventCorrelator:
    """Create a fresh EventCorrelator for each test."""
    return EventCorrelator(buffer_size=200, default_window_seconds=300.0)


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


class TestCorrelationDetection:
    """Tests for correlation detection - positive and negative cases."""

    POSITIVE_CASES = [
        pytest.param(
            EventType.READ,
            "/home/user/.env",
            EventType.WEBFETCH,
            "https://evil.com/collect",
            "exfiltration_read_webfetch",
            "T1048",
            30,
            id="exfil_read_webfetch",
        ),
        pytest.param(
            EventType.WEBFETCH,
            "https://evil.com/check",
            EventType.READ,
            "/secrets/api.key",
            "exfiltration_read_webfetch",
            "T1048",
            30,
            id="exfil_webfetch_read",
        ),
        pytest.param(
            EventType.WEBFETCH,
            "https://example.com/install.sh",
            EventType.BASH,
            "bash ./install.sh",
            "remote_code_execution",
            "T1059",
            35,
            id="rce_shell",
        ),
        pytest.param(
            EventType.WEBFETCH,
            "https://example.com/payload.py",
            EventType.BASH,
            "python payload.py",
            "remote_code_execution",
            "T1059",
            35,
            id="rce_python",
        ),
        pytest.param(
            EventType.WRITE,
            "/tmp/backdoor.sh",
            EventType.BASH,
            "chmod +x /tmp/backdoor.sh",
            "execution_preparation",
            "T1222",
            25,
            id="exec_prep",
        ),
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
    ]

    @pytest.mark.parametrize(
        "e1_type,e1_target,e2_type,e2_target,corr_type,mitre,modifier", POSITIVE_CASES
    )
    def test_correlation_detected(
        self,
        correlator,
        base_time,
        e1_type,
        e1_target,
        e2_type,
        e2_target,
        corr_type,
        mitre,
        modifier,
    ):
        """Verify correlation is detected with correct metadata."""
        e1 = create_event(e1_type, e1_target, timestamp=base_time, risk_score=85)
        e2 = create_event(e2_type, e2_target, timestamp=base_time + 30, risk_score=50)

        corrs1 = correlator.add_event(e1)
        corrs2 = correlator.add_event(e2)

        # First event no correlations
        assert isinstance(corrs1, list)
        assert len(corrs1) == 0
        # Second event triggers correlation
        matching = [c for c in corrs2 if c.correlation_type == corr_type]
        assert len(matching) == 1
        assert matching[0].mitre_technique == mitre
        assert matching[0].score_modifier == modifier
        assert matching[0].confidence >= 0.0

    def test_correlation_context_time_delta(self, correlator, base_time):
        """Verify correlation context contains accurate time_delta_seconds."""
        e1 = create_event(EventType.READ, "/app/.env", timestamp=base_time)
        e2 = create_event(
            EventType.WEBFETCH, "https://evil.com/collect", timestamp=base_time + 30
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
        assert isinstance(exfil[0].context, dict)
        assert "time_delta_seconds" in exfil[0].context

    def test_correlation_session_id_preserved(self, correlator, base_time):
        """Verify correlation preserves session_id from events."""
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
        assert isinstance(correlations[0].session_id, str)
        assert correlations[0].session_id != ""


class TestNoCorrelation:
    """Tests verifying correlations are NOT triggered in specific cases."""

    NEGATIVE_CASES = [
        pytest.param(
            EventType.READ,
            "/app/.env",
            EventType.WEBFETCH,
            "http://localhost:3000/api",
            10,
            id="localhost",
        ),
        pytest.param(
            EventType.READ,
            "/app/.env",
            EventType.WEBFETCH,
            "https://evil.com/collect",
            600,
            id="outside_window",
        ),
        pytest.param(
            EventType.READ,
            "/app/.env",
            EventType.READ,
            "/secrets/key",
            10,
            id="same_type",
        ),
    ]

    @pytest.mark.parametrize(
        "e1_type,e1_target,e2_type,e2_target,offset", NEGATIVE_CASES
    )
    def test_no_exfiltration_correlation(
        self, correlator, base_time, e1_type, e1_target, e2_type, e2_target, offset
    ):
        """Verify exfiltration correlation is NOT triggered."""
        e1 = create_event(e1_type, e1_target, timestamp=base_time)
        e2 = create_event(e2_type, e2_target, timestamp=base_time + offset)

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)
        exfil = [
            c
            for c in correlations
            if c.correlation_type == "exfiltration_read_webfetch"
        ]

        assert len(exfil) == 0
        assert isinstance(correlations, list)
        # Correlator still works
        assert correlator is not None

    def test_chmod_without_prior_write_no_correlation(self, correlator, base_time):
        """chmod without prior write doesn't create execution_preparation."""
        e1 = create_event(
            EventType.BASH, "chmod +x /some/script.sh", timestamp=base_time
        )
        correlations = correlator.add_event(e1)
        prep = [
            c for c in correlations if c.correlation_type == "execution_preparation"
        ]

        assert len(prep) == 0
        assert isinstance(correlations, list)
        assert len(correlator.get_session_buffer("test-session")) == 1
        assert correlations is not None

    def test_single_event_no_correlation(self, correlator):
        """Single event cannot create correlations."""
        event = create_event(EventType.READ, "/app/.env")
        correlations = correlator.add_event(event)

        assert len(correlations) == 0
        assert isinstance(correlations, list)
        assert len(correlator.get_session_buffer("test-session")) == 1
        assert event.event_type == EventType.READ


class TestSessionManagement:
    """Tests for session buffer management."""

    SESSION_CASES = [
        pytest.param(
            [("s1", EventType.READ, "/f1"), ("s2", EventType.WRITE, "/f2")],
            {"s1": 1, "s2": 1},
            id="separate",
        ),
        pytest.param(
            [
                ("s1", EventType.READ, "/f1"),
                ("s1", EventType.WRITE, "/f2"),
                ("s2", EventType.READ, "/f3"),
            ],
            {"s1": 2, "s2": 1},
            id="multiple_in_one",
        ),
    ]

    @pytest.mark.parametrize("events,expected", SESSION_CASES)
    def test_session_buffer_counts(self, correlator, events, expected):
        """Verify session buffers track events correctly."""
        for session_id, event_type, target in events:
            event = create_event(event_type, target, session_id=session_id)
            correlator.add_event(event)

        for session_id, count in expected.items():
            buffer = correlator.get_session_buffer(session_id)
            assert len(buffer) == count
            assert isinstance(buffer, list)

    def test_clear_session_removes_only_target(self, correlator):
        """Clearing a session removes only that session's data."""
        e1 = create_event(EventType.READ, "/file1", session_id="s1")
        e2 = create_event(EventType.READ, "/file2", session_id="s2")

        correlator.add_event(e1)
        correlator.add_event(e2)
        correlator.clear_session("s1")

        assert len(correlator.get_session_buffer("s1")) == 0
        assert len(correlator.get_session_buffer("s2")) == 1
        assert isinstance(correlator.get_session_buffer("s1"), list)
        assert isinstance(correlator.get_session_buffer("s2"), list)

    def test_clear_all_removes_all_sessions(self, correlator):
        """Clearing all removes all session data."""
        e1 = create_event(EventType.READ, "/file1", session_id="s1")
        e2 = create_event(EventType.READ, "/file2", session_id="s2")

        correlator.add_event(e1)
        correlator.add_event(e2)
        correlator.clear_all()

        assert len(correlator.get_session_buffer("s1")) == 0
        assert len(correlator.get_session_buffer("s2")) == 0
        assert correlator.get_session_buffer("s1") == []
        assert correlator.get_session_buffer("s2") == []

    def test_empty_session_buffer_returns_empty_list(self, correlator):
        """Getting buffer for non-existent session returns empty list."""
        buffer = correlator.get_session_buffer("non-existent")

        assert buffer == []
        assert isinstance(buffer, list)
        assert len(buffer) == 0
        assert buffer is not None
        assert not buffer  # Falsy check


class TestCorrelationMetrics:
    """Tests for correlation summary and confidence scoring."""

    def test_summary_counts_by_type(self, correlator, base_time):
        """get_correlation_summary returns accurate type counts."""
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
        assert isinstance(summary, dict)
        assert len(all_corrs) == 2
        assert all(
            c.correlation_type == "exfiltration_read_webfetch" for c in all_corrs
        )

    def test_high_risk_close_events_high_confidence(self, correlator, base_time):
        """High risk events close in time produce confidence > 0.8."""
        e1 = create_event(
            EventType.READ, "/secrets/.env", timestamp=base_time, risk_score=90
        )
        e2 = create_event(
            EventType.WEBFETCH,
            "https://evil.com/exfil",
            timestamp=base_time + 1,
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
        assert exfil[0].confidence >= 0.8
        assert isinstance(exfil[0].confidence, float)
        assert exfil[0].confidence <= 1.0

    def test_low_risk_distant_events_lower_confidence(self, correlator, base_time):
        """Low risk events far apart produce confidence between 0.5-0.7."""
        e1 = create_event(
            EventType.READ, "/app/.env", timestamp=base_time, risk_score=20
        )
        e2 = create_event(
            EventType.WEBFETCH,
            "https://example.com",
            timestamp=base_time + 100,
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
        assert 0.5 <= exfil[0].confidence <= 0.7
        assert isinstance(exfil[0].confidence, float)
        assert exfil[0].confidence >= 0.0
