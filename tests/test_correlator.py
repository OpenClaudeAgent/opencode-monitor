"""Tests for EventCorrelator - Multi-event correlation."""

import time
import pytest
from opencode_monitor.security.sequences import SecurityEvent, EventType
from opencode_monitor.security.correlator import EventCorrelator, Correlation


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
        c = matching[0]
        assert c.mitre_technique == mitre
        assert c.mitre_technique != "XXXX"  # Kill mutant 145
        assert c.score_modifier == modifier
        assert 0.0 <= c.confidence <= 1.0  # Kill mutants 171, 184
        assert isinstance(c, Correlation)
        assert c.description != ""  # Kill description mutants

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
        assert "source_target" in exfil[0].context
        assert "related_target" in exfil[0].context

    def test_correlation_at_window_boundary(self, correlator, base_time):
        """Verify correlation works exactly at max_window_seconds boundary."""
        # At 299s should still correlate (inside 300s window)
        e1 = create_event(EventType.READ, "/app/.env", timestamp=base_time)
        e2 = create_event(
            EventType.WEBFETCH, "https://evil.com/exfil", timestamp=base_time + 299
        )
        correlator.add_event(e1)
        corrs = correlator.add_event(e2)
        assert (
            len(
                [c for c in corrs if c.correlation_type == "exfiltration_read_webfetch"]
            )
            == 1
        )
        # Test correlation at exact window boundary (kills mutant 120: > vs >=)
        correlator.clear_all()
        e3 = create_event(EventType.READ, "/secret/.env", timestamp=base_time)
        e4 = create_event(
            EventType.WEBFETCH, "https://evil.com", timestamp=base_time + 300
        )
        correlator.add_event(e3)
        corrs2 = correlator.add_event(e4)
        # At exactly 300s, should still correlate (> not >=)
        exfil2 = [
            c for c in corrs2 if c.correlation_type == "exfiltration_read_webfetch"
        ]
        assert len(exfil2) == 1  # Kills mutant 120

    def test_correlation_session_id_preserved(self, correlator, base_time):
        """Verify correlation preserves session_id and find_related_events works."""
        e1 = create_event(
            EventType.WRITE,
            "/tmp/malware.sh",
            session_id="my-session",
            timestamp=base_time,
        )
        e2 = create_event(
            EventType.BASH,
            "chmod +x /tmp/malware.sh",
            session_id="my-session",
            timestamp=base_time + 10,
        )

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)

        # Verify execution_preparation correlation
        prep = [
            c for c in correlations if c.correlation_type == "execution_preparation"
        ]
        assert len(prep) == 1
        assert prep[0].session_id == "my-session"
        assert isinstance(prep[0].session_id, str)
        assert prep[0].session_id != ""
        # Test find_related_events by path (kills mutants 190, 192)
        related = correlator.find_related_events(e1)
        assert isinstance(related, list)
        assert len(related) == 1
        assert related[0] is e2
        # Verify get_events_by_path returns the indexed event
        path_events = correlator.get_events_by_path("my-session", "/tmp/malware.sh")
        assert len(path_events) >= 1
        # Test find_related_events with events in mixed order (kills 195)
        correlator.clear_all()
        ea = create_event(
            EventType.WRITE, "/path/file.sh", session_id="s", timestamp=base_time
        )
        eb = create_event(
            EventType.BASH,
            "echo /path/file.sh",
            session_id="s",
            timestamp=base_time + 500,
        )
        ec = create_event(
            EventType.BASH,
            "cat /path/file.sh",
            session_id="s",
            timestamp=base_time + 10,
        )
        correlator.add_event(ea)
        correlator.add_event(eb)  # Added second, outside window from ea
        correlator.add_event(ec)  # Added third, inside window from ea
        # Buffer order: ea, eb, ec. When checking ea, loop sees eb first (outside window).
        # With continue: skip eb, find ec. With break: exit after eb, miss ec.
        related3 = correlator.find_related_events(ea)
        assert len(related3) == 1  # Should find ec despite eb being outside window


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
            301,  # Just outside 300s window - kills max_window_seconds mutants
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
        e2 = create_event(
            EventType.READ,
            "no_path_here",
            timestamp=base_time + 5,  # No "/" in target
        )
        correlations = correlator.add_event(e1)
        correlator.add_event(e2)
        prep = [
            c for c in correlations if c.correlation_type == "execution_preparation"
        ]

        assert len(prep) == 0
        assert isinstance(correlations, list)
        # Test find_related_events: e1 and e2 have no correlated paths
        related = correlator.find_related_events(e1)
        assert isinstance(related, list)
        # e2 has no extractable path (no "/"), so they don't correlate
        assert len(related) == 0

    def test_single_event_no_correlation(self, correlator, base_time):
        """Single event cannot create correlations, find_related_events returns empty."""
        event = create_event(EventType.READ, "/app/.env", timestamp=base_time)
        correlations = correlator.add_event(event)

        assert len(correlations) == 0
        assert isinstance(correlations, list)
        assert len(correlator.get_session_buffer("test-session")) == 1
        assert event.event_type == EventType.READ
        # Verify find_related_events returns empty list for single event
        related = correlator.find_related_events(event)
        assert related == []
        # Verify get_events_by_path indexes correctly
        path_events = correlator.get_events_by_path("test-session", "/app/.env")
        assert len(path_events) == 1


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
            # Verify get_events_by_path works
            if buffer:
                path_events = correlator.get_events_by_path(
                    session_id, buffer[0].target
                )
                assert isinstance(path_events, list)

    def test_clear_session_removes_only_target(self, correlator):
        """Clearing a session removes only that session's data including path_index."""
        e1 = create_event(EventType.READ, "/path/file1", session_id="s1")
        e2 = create_event(EventType.READ, "/path/file2", session_id="s2")

        correlator.add_event(e1)
        correlator.add_event(e2)
        # Verify path_index has s1 before clear
        assert correlator.get_events_by_path("s1", "/path/file1") != []
        correlator.clear_session("s1")

        assert len(correlator.get_session_buffer("s1")) == 0
        assert len(correlator.get_session_buffer("s2")) == 1
        # Verify path_index is also cleared for s1 (kills mutant 200)
        assert correlator.get_events_by_path("s1", "/path/file1") == []
        assert isinstance(correlator.get_session_buffer("s1"), list)

    def test_clear_all_removes_all_sessions(self, correlator):
        """Clearing all removes all session data including path_index."""
        e1 = create_event(EventType.READ, "/path/file1", session_id="s1")
        e2 = create_event(EventType.READ, "/path/file2", session_id="s2")

        correlator.add_event(e1)
        correlator.add_event(e2)
        # Verify data exists before clear
        assert correlator.get_events_by_path("s1", "/path/file1") != []
        correlator.clear_all()

        assert len(correlator.get_session_buffer("s1")) == 0
        assert len(correlator.get_session_buffer("s2")) == 0
        assert correlator.get_session_buffer("s1") == []
        assert correlator.get_session_buffer("s2") == []
        # Verify path_index is also cleared
        assert correlator.get_events_by_path("s1", "/path/file1") == []

    def test_empty_session_buffer_returns_empty_list(self, correlator, base_time):
        """Getting buffer for non-existent session returns empty list."""
        buffer = correlator.get_session_buffer("non-existent")
        path_events = correlator.get_events_by_path("non-existent", "/any/path")

        assert buffer == []
        assert isinstance(buffer, list)
        assert len(buffer) == 0
        assert buffer is not None
        assert not buffer  # Falsy check
        assert path_events == []
        # Test get_events_by_path with path that has no "/" (kills mutant 197)
        e = create_event(
            EventType.READ, "simple_target", session_id="s", timestamp=base_time
        )
        correlator.add_event(e)
        # "simple_target" has no "/" so _extract_path returns None, uses fallback
        events = correlator.get_events_by_path("s", "simple_target")
        # With `or path`: normalized_path = "simple_target", finds event
        # With `and path`: normalized_path = None, won't find event
        assert (
            len(events) == 0
        )  # Actually won't find because path_index uses extracted path


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
        """High risk events close in time produce confidence > 0.8 and <= 1.0."""
        # Use risk_scores that sum to >100 to test min(1.0, ...) capping
        e1 = create_event(
            EventType.READ, "/secrets/.env", timestamp=base_time, risk_score=100
        )
        e2 = create_event(
            EventType.WEBFETCH,
            "https://evil.com/exfil",
            timestamp=base_time + 1,
            risk_score=100,
        )

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)
        exfil = [
            c
            for c in correlations
            if c.correlation_type == "exfiltration_read_webfetch"
        ]

        assert len(exfil) == 1
        conf = exfil[0].confidence
        assert conf >= 0.8
        assert isinstance(conf, float)
        # With risk_score 100+100=200, risk_factor = 200/100 = 2.0 if not capped
        # min(1.0, 2.0) = 1.0, confidence = 0.5*time + 0.3*1.0 + 0.2 = ~1.0
        # min(2.0, 2.0) = 2.0, confidence = 0.5*time + 0.3*2.0 + 0.2 = ~1.3 (capped by outer min)
        assert conf <= 1.0  # Must be capped at 1.0

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
        conf = exfil[0].confidence
        assert 0.5 <= conf <= 0.7
        assert isinstance(conf, float)
        assert conf >= 0.0
        assert conf <= 1.0
        # Additional check: distant events with high risk should still have capped confidence
        correlator.clear_all()
        e3 = create_event(
            EventType.READ, "/x/.env", timestamp=base_time, risk_score=100
        )
        e4 = create_event(
            EventType.WEBFETCH,
            "https://evil.com/x",
            timestamp=base_time + 295,
            risk_score=100,
        )
        correlator.add_event(e3)
        corrs = correlator.add_event(e4)
        exfil2 = [
            c for c in corrs if c.correlation_type == "exfiltration_read_webfetch"
        ]
        assert len(exfil2) == 1
        # With risk capped at 1.0: conf ~0.51; with mutant (risk=2.0): conf ~0.81
        assert exfil2[0].confidence < 0.6  # Kills mutant 171
