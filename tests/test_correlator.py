"""
Tests for EventCorrelator - Multi-event correlation.

Tests cover:
- Event correlation detection
- Path-based correlation
- Time window filtering
- Confidence scoring
- MITRE technique tagging
"""

import time

import pytest

from opencode_monitor.security.sequences import SecurityEvent, EventType
from opencode_monitor.security.correlator import (
    EventCorrelator,
    Correlation,
    CORRELATION_PATTERNS,
)


# =====================================================
# Fixtures (base_time is provided by conftest.py)
# =====================================================


@pytest.fixture
def correlator() -> EventCorrelator:
    """Create a fresh EventCorrelator for each test"""
    return EventCorrelator(buffer_size=200, default_window_seconds=300.0)


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
# Exfiltration Correlation Tests
# =====================================================


class TestExfiltrationCorrelation:
    """Tests for read + webfetch exfiltration correlation"""

    def test_sensitive_read_then_webfetch_correlates(
        self, correlator: EventCorrelator, base_time: float
    ):
        """read(sensitive) + webfetch(external) creates correlation"""
        e1 = create_event(
            EventType.READ,
            "/home/user/.env",
            timestamp=base_time,
            risk_score=85,
        )
        e2 = create_event(
            EventType.WEBFETCH,
            "https://evil.com/collect",
            timestamp=base_time + 30,
            risk_score=50,
        )

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)

        assert len(correlations) >= 1
        exfil = [
            c
            for c in correlations
            if c.correlation_type == "exfiltration_read_webfetch"
        ]
        assert len(exfil) == 1
        assert exfil[0].mitre_technique == "T1048"
        assert exfil[0].score_modifier == 30

    def test_webfetch_then_sensitive_read_correlates(
        self, correlator: EventCorrelator, base_time: float
    ):
        """webfetch(external) + read(sensitive) also correlates"""
        e1 = create_event(
            EventType.WEBFETCH,
            "https://evil.com/check",
            timestamp=base_time,
        )
        e2 = create_event(
            EventType.READ,
            "/secrets/api.key",
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

    def test_localhost_webfetch_no_correlation(
        self, correlator: EventCorrelator, base_time: float
    ):
        """read(sensitive) + webfetch(localhost) does NOT correlate"""
        e1 = create_event(EventType.READ, "/app/.env", timestamp=base_time)
        e2 = create_event(
            EventType.WEBFETCH,
            "http://localhost:3000/api",
            timestamp=base_time + 10,
        )

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)

        exfil = [
            c
            for c in correlations
            if c.correlation_type == "exfiltration_read_webfetch"
        ]
        assert len(exfil) == 0


# =====================================================
# Remote Code Execution Correlation Tests
# =====================================================


class TestRemoteCodeExecutionCorrelation:
    """Tests for webfetch(script) + bash correlation"""

    def test_script_download_then_bash_correlates(
        self, correlator: EventCorrelator, base_time: float
    ):
        """webfetch(.sh) + bash triggers RCE correlation"""
        e1 = create_event(
            EventType.WEBFETCH,
            "https://example.com/install.sh",
            timestamp=base_time,
        )
        e2 = create_event(
            EventType.BASH,
            "bash ./install.sh",
            timestamp=base_time + 30,
        )

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)

        rce = [c for c in correlations if c.correlation_type == "remote_code_execution"]
        assert len(rce) == 1
        assert rce[0].mitre_technique == "T1059"

    def test_python_download_then_python_correlates(
        self, correlator: EventCorrelator, base_time: float
    ):
        """webfetch(.py) + python triggers RCE correlation"""
        e1 = create_event(
            EventType.WEBFETCH,
            "https://example.com/payload.py",
            timestamp=base_time,
        )
        e2 = create_event(
            EventType.BASH,
            "python payload.py",
            timestamp=base_time + 30,
        )

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)

        rce = [c for c in correlations if c.correlation_type == "remote_code_execution"]
        assert len(rce) == 1


# =====================================================
# Execution Preparation Correlation Tests
# =====================================================


class TestExecutionPreparationCorrelation:
    """Tests for write + chmod correlation"""

    def test_write_script_then_chmod_correlates(
        self, correlator: EventCorrelator, base_time: float
    ):
        """write(.sh) + chmod(+x) triggers execution preparation"""
        e1 = create_event(
            EventType.WRITE,
            "/tmp/backdoor.sh",
            timestamp=base_time,
        )
        e2 = create_event(
            EventType.BASH,
            "chmod +x /tmp/backdoor.sh",
            timestamp=base_time + 5,
        )

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)

        prep = [
            c for c in correlations if c.correlation_type == "execution_preparation"
        ]
        assert len(prep) == 1
        assert prep[0].mitre_technique == "T1222"

    def test_chmod_without_write_no_correlation(
        self, correlator: EventCorrelator, base_time: float
    ):
        """chmod without prior write doesn't correlate"""
        e1 = create_event(
            EventType.BASH,
            "chmod +x /some/script.sh",
            timestamp=base_time,
        )

        correlations = correlator.add_event(e1)

        prep = [
            c for c in correlations if c.correlation_type == "execution_preparation"
        ]
        assert len(prep) == 0


# =====================================================
# Git Reconnaissance Correlation Tests
# =====================================================


class TestGitReconnaissanceCorrelation:
    """Tests for git config read + webfetch correlation"""

    def test_git_config_then_github_webfetch_correlates(
        self, correlator: EventCorrelator, base_time: float
    ):
        """read(.git/config) + webfetch(github) triggers reconnaissance"""
        e1 = create_event(
            EventType.READ,
            "/project/.git/config",
            timestamp=base_time,
        )
        e2 = create_event(
            EventType.WEBFETCH,
            "https://github.com/some/repo",
            timestamp=base_time + 60,
        )

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)

        recon = [c for c in correlations if c.correlation_type == "git_reconnaissance"]
        assert len(recon) == 1
        assert recon[0].mitre_technique == "T1592"


# =====================================================
# Time Window Tests
# =====================================================


class TestTimeWindow:
    """Tests for time window filtering"""

    def test_events_outside_window_no_correlation(
        self, correlator: EventCorrelator, base_time: float
    ):
        """Events outside time window don't correlate"""
        e1 = create_event(EventType.READ, "/app/.env", timestamp=base_time)
        # 10 minutes later (outside 5 minute window)
        e2 = create_event(
            EventType.WEBFETCH,
            "https://evil.com/collect",
            timestamp=base_time + 600,
        )

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)

        exfil = [
            c
            for c in correlations
            if c.correlation_type == "exfiltration_read_webfetch"
        ]
        assert len(exfil) == 0


# =====================================================
# Confidence Score Tests
# =====================================================


class TestConfidenceScore:
    """Tests for correlation confidence scoring"""

    def test_high_risk_events_higher_confidence(
        self, correlator: EventCorrelator, base_time: float
    ):
        """High risk events produce higher confidence"""
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
        assert exfil[0].confidence > 0.5

    def test_confidence_between_0_and_1(
        self, correlator: EventCorrelator, base_time: float
    ):
        """Confidence is always between 0 and 1"""
        e1 = create_event(EventType.READ, "/app/.env", timestamp=base_time)
        e2 = create_event(
            EventType.WEBFETCH,
            "https://example.com",
            timestamp=base_time + 100,
        )

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)

        for corr in correlations:
            assert 0.0 <= corr.confidence <= 1.0


# =====================================================
# Session Management Tests
# =====================================================


class TestSessionManagement:
    """Tests for session buffer management"""

    def test_separate_session_buffers(self, correlator: EventCorrelator):
        """Different sessions have separate buffers"""
        e1 = create_event(EventType.READ, "/file1", session_id="session-1")
        e2 = create_event(EventType.WRITE, "/file2", session_id="session-2")

        correlator.add_event(e1)
        correlator.add_event(e2)

        assert len(correlator.get_session_buffer("session-1")) == 1
        assert len(correlator.get_session_buffer("session-2")) == 1

    def test_clear_session(self, correlator: EventCorrelator):
        """Clearing a session removes its data"""
        event = create_event(EventType.READ, "/file1")
        correlator.add_event(event)

        correlator.clear_session("test-session")

        assert len(correlator.get_session_buffer("test-session")) == 0

    def test_clear_all(self, correlator: EventCorrelator):
        """Clearing all removes all session data"""
        e1 = create_event(EventType.READ, "/file1", session_id="s1")
        e2 = create_event(EventType.READ, "/file2", session_id="s2")

        correlator.add_event(e1)
        correlator.add_event(e2)
        correlator.clear_all()

        assert len(correlator.get_session_buffer("s1")) == 0
        assert len(correlator.get_session_buffer("s2")) == 0


# =====================================================
# Correlation Summary Tests
# =====================================================


class TestCorrelationSummary:
    """Tests for correlation summary functionality"""

    def test_get_correlation_summary(
        self, correlator: EventCorrelator, base_time: float
    ):
        """get_correlation_summary returns type counts"""
        # Create multiple correlations
        e1 = create_event(EventType.READ, "/app/.env", timestamp=base_time)
        e2 = create_event(
            EventType.WEBFETCH,
            "https://evil.com/1",
            timestamp=base_time + 10,
        )
        e3 = create_event(
            EventType.WEBFETCH,
            "https://evil.com/2",
            timestamp=base_time + 20,
        )

        correlator.add_event(e1)
        corrs1 = correlator.add_event(e2)
        corrs2 = correlator.add_event(e3)

        all_corrs = corrs1 + corrs2
        summary = correlator.get_correlation_summary(all_corrs)

        assert isinstance(summary, dict)


# =====================================================
# Context Information Tests
# =====================================================


class TestContextInformation:
    """Tests for correlation context information"""

    def test_correlation_has_context(
        self, correlator: EventCorrelator, base_time: float
    ):
        """Correlation includes context information"""
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
        assert "time_delta_seconds" in exfil[0].context
        assert exfil[0].context["time_delta_seconds"] == 30

    def test_correlation_has_session_id(
        self, correlator: EventCorrelator, base_time: float
    ):
        """Correlation has correct session_id property"""
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

        if correlations:
            assert correlations[0].session_id == "my-session"


# =====================================================
# Edge Cases
# =====================================================


class TestEdgeCases:
    """Tests for edge cases"""

    def test_empty_session_buffer(self, correlator: EventCorrelator):
        """Getting buffer for non-existent session returns empty list"""
        buffer = correlator.get_session_buffer("non-existent")
        assert buffer == []

    def test_single_event_no_correlation(self, correlator: EventCorrelator):
        """Single event doesn't create correlations"""
        event = create_event(EventType.READ, "/app/.env")
        correlations = correlator.add_event(event)

        assert len(correlations) == 0

    def test_same_event_type_no_correlation(
        self, correlator: EventCorrelator, base_time: float
    ):
        """Two events of same type don't correlate (need source/target pair)"""
        e1 = create_event(EventType.READ, "/app/.env", timestamp=base_time)
        e2 = create_event(EventType.READ, "/secrets/key", timestamp=base_time + 10)

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)

        # Should not have exfiltration (needs READ + WEBFETCH)
        exfil = [
            c
            for c in correlations
            if c.correlation_type == "exfiltration_read_webfetch"
        ]
        assert len(exfil) == 0
