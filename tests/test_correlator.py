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


# =====================================================
# Phase 3 - New Correlation Pattern Tests (Plan 43)
# =====================================================


class TestConfigPoisoningCorrelation:
    """Tests for config_poisoning correlation pattern."""

    @pytest.mark.parametrize(
        "config_file,bash_cmd,expected_match",
        [
            (".bashrc", "ls -la", True),
            ("~/.zshrc", "echo hello", True),
            ("/home/user/.profile", "pwd", True),
            ("/tmp/random.txt", "ls", False),  # Not a config file
        ],
        ids=["bashrc-ls", "zshrc-echo", "profile-pwd", "no-config"],
    )
    def test_config_poisoning_detection(
        self,
        correlator: EventCorrelator,
        base_time: float,
        config_file: str,
        bash_cmd: str,
        expected_match: bool,
    ):
        """write(shell_config) -> bash(any) triggers config poisoning."""
        e1 = create_event(EventType.WRITE, config_file, timestamp=base_time)
        e2 = create_event(EventType.BASH, bash_cmd, timestamp=base_time + 10)

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)

        poisoning = [
            c for c in correlations if c.correlation_type == "config_poisoning"
        ]

        if expected_match:
            assert len(poisoning) == 1
            assert poisoning[0].score_modifier == 25
            assert poisoning[0].mitre_technique == "T1546"
        else:
            assert len(poisoning) == 0

    def test_config_poisoning_outside_window(
        self, correlator: EventCorrelator, base_time: float
    ):
        """Config poisoning outside 60s window doesn't trigger."""
        e1 = create_event(EventType.WRITE, ".bashrc", timestamp=base_time)
        e2 = create_event(
            EventType.BASH,
            "ls",
            timestamp=base_time + 120,  # 2 minutes later
        )

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)

        poisoning = [
            c for c in correlations if c.correlation_type == "config_poisoning"
        ]
        assert len(poisoning) == 0


class TestDependencyConfusionCorrelation:
    """Tests for dependency_confusion correlation pattern."""

    @pytest.mark.parametrize(
        "fetch_url,package_file,expected_match",
        [
            ("https://registry.npmjs.org/malicious", "package.json", True),
            ("https://pypi.org/simple/evil-pkg", "setup.py", True),
            ("https://rubygems.org/gems/backdoor", "Gemfile", True),
            (
                "https://example.com/data.json",
                "config.json",
                False,
            ),  # Not package registry
        ],
        ids=["npm-package", "pypi-setup", "rubygems-gemfile", "no-registry"],
    )
    def test_dependency_confusion_detection(
        self,
        correlator: EventCorrelator,
        base_time: float,
        fetch_url: str,
        package_file: str,
        expected_match: bool,
    ):
        """webfetch(registry) -> write(package_file) triggers dependency confusion."""
        e1 = create_event(EventType.WEBFETCH, fetch_url, timestamp=base_time)
        e2 = create_event(EventType.WRITE, package_file, timestamp=base_time + 30)

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)

        confusion = [
            c for c in correlations if c.correlation_type == "dependency_confusion"
        ]

        if expected_match:
            assert len(confusion) == 1
            assert confusion[0].score_modifier == 30
            assert confusion[0].mitre_technique == "T1195"
        else:
            assert len(confusion) == 0


class TestSecretLoggingCorrelation:
    """Tests for secret_logging correlation pattern."""

    @pytest.mark.parametrize(
        "secret_file,log_file,expected_match",
        [
            ("/app/.env", "/var/log/app.log", True),
            ("/secrets/credentials.json", "output.log", True),
            ("~/.ssh/id_rsa.pem", "logs/debug.log", True),
            ("/app/config.yml", "/var/log/app.log", False),  # Not a secrets file
        ],
        ids=["env-varlog", "creds-outputlog", "pem-debuglog", "no-secrets"],
    )
    def test_secret_logging_detection(
        self,
        correlator: EventCorrelator,
        base_time: float,
        secret_file: str,
        log_file: str,
        expected_match: bool,
    ):
        """read(secrets) -> write(log) triggers secret logging."""
        e1 = create_event(EventType.READ, secret_file, timestamp=base_time)
        e2 = create_event(EventType.WRITE, log_file, timestamp=base_time + 30)

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)

        logging_corr = [
            c for c in correlations if c.correlation_type == "secret_logging"
        ]

        if expected_match:
            assert len(logging_corr) == 1
            assert logging_corr[0].score_modifier == 35
            assert logging_corr[0].mitre_technique == "T1074"
        else:
            assert len(logging_corr) == 0


class TestTunnelEstablishmentCorrelation:
    """Tests for tunnel_establishment correlation pattern."""

    @pytest.mark.parametrize(
        "ssh_cmd,webfetch_url,expected_match",
        [
            ("ssh -L 8080:remote:80 user@host", "https://evil.com/data", True),
            ("ssh -R 9000:localhost:22 attacker@box", "https://external.io/api", True),
            ("ssh user@server", "https://example.com", False),  # No tunnel flags
            (
                "ssh -L 8080:remote:80 user@host",
                "http://localhost:3000",
                False,
            ),  # localhost
        ],
        ids=["local-tunnel", "remote-tunnel", "no-tunnel", "localhost-excluded"],
    )
    def test_tunnel_establishment_detection(
        self,
        correlator: EventCorrelator,
        base_time: float,
        ssh_cmd: str,
        webfetch_url: str,
        expected_match: bool,
    ):
        """bash(ssh -L/-R) -> webfetch(external) triggers tunnel establishment."""
        e1 = create_event(EventType.BASH, ssh_cmd, timestamp=base_time)
        e2 = create_event(EventType.WEBFETCH, webfetch_url, timestamp=base_time + 60)

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)

        tunnel = [
            c for c in correlations if c.correlation_type == "tunnel_establishment"
        ]

        if expected_match:
            assert len(tunnel) == 1
            assert tunnel[0].score_modifier == 30
            assert tunnel[0].mitre_technique == "T1572"
        else:
            assert len(tunnel) == 0


class TestCleanupAfterAttackCorrelation:
    """Tests for cleanup_after_attack correlation pattern."""

    @pytest.mark.parametrize(
        "destructive_cmd,cleanup_cmd,expected_match",
        [
            ("rm -rf /tmp/evidence", "history -c", True),
            ("shred -u /var/log/auth.log", "rm ~/.bash_history", True),
            ("rm -rf /data/traces", "unset HISTFILE", True),
            ("ls -la", "history -c", False),  # Not destructive
        ],
        ids=["rm-history-c", "shred-rm-history", "rm-unset-histfile", "no-destructive"],
    )
    def test_cleanup_after_attack_detection(
        self,
        correlator: EventCorrelator,
        base_time: float,
        destructive_cmd: str,
        cleanup_cmd: str,
        expected_match: bool,
    ):
        """bash(rm -rf/shred) -> bash(history clear) triggers cleanup detection."""
        e1 = create_event(EventType.BASH, destructive_cmd, timestamp=base_time)
        e2 = create_event(EventType.BASH, cleanup_cmd, timestamp=base_time + 30)

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)

        cleanup = [
            c for c in correlations if c.correlation_type == "cleanup_after_attack"
        ]

        if expected_match:
            assert len(cleanup) == 1
            assert cleanup[0].score_modifier == 40
            assert cleanup[0].mitre_technique == "T1070"
        else:
            assert len(cleanup) == 0

    def test_cleanup_outside_window(
        self, correlator: EventCorrelator, base_time: float
    ):
        """Cleanup correlation outside 3min window doesn't trigger."""
        e1 = create_event(EventType.BASH, "rm -rf /tmp/data", timestamp=base_time)
        e2 = create_event(
            EventType.BASH,
            "history -c",
            timestamp=base_time + 300,  # 5 minutes later
        )

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)

        cleanup = [
            c for c in correlations if c.correlation_type == "cleanup_after_attack"
        ]
        assert len(cleanup) == 0


class TestNewCorrelationMetadata:
    """Tests for metadata correctness on new correlations."""

    def test_config_poisoning_context_includes_time_delta(
        self, correlator: EventCorrelator, base_time: float
    ):
        """Config poisoning correlation context includes accurate time_delta."""
        e1 = create_event(EventType.WRITE, ".bashrc", timestamp=base_time)
        e2 = create_event(EventType.BASH, "ls", timestamp=base_time + 15)

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)

        poisoning = [
            c for c in correlations if c.correlation_type == "config_poisoning"
        ]
        assert len(poisoning) == 1
        assert poisoning[0].context["time_delta_seconds"] == 15

    def test_cleanup_correlation_preserves_session_id(
        self, correlator: EventCorrelator, base_time: float
    ):
        """Cleanup correlation preserves session_id from events."""
        e1 = create_event(
            EventType.BASH,
            "rm -rf /tmp/data",
            session_id="attack-session",
            timestamp=base_time,
        )
        e2 = create_event(
            EventType.BASH,
            "history -c",
            session_id="attack-session",
            timestamp=base_time + 10,
        )

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)

        cleanup = [
            c for c in correlations if c.correlation_type == "cleanup_after_attack"
        ]
        assert len(cleanup) == 1
        assert cleanup[0].session_id == "attack-session"
