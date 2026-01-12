"""
Tests for bulk_enrichment.py - Bulk security enrichment for backfill.

Tests the bulk_enrich() function which:
1. Processes all unenriched parts in large batches
2. Runs synchronously (no background thread)
3. Returns enrichment statistics
4. Stops when no more unenriched parts found
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))
from bulk_enrichment import bulk_enrich


@pytest.fixture
def enrichment_db(analytics_db):
    """Create database with parts table including risk columns."""
    conn = analytics_db.connect()

    conn.execute("DROP TABLE IF EXISTS parts")
    conn.execute("""
        CREATE TABLE parts (
            id VARCHAR PRIMARY KEY,
            session_id VARCHAR,
            message_id VARCHAR,
            part_type VARCHAR,
            tool_name VARCHAR,
            tool_status VARCHAR,
            arguments VARCHAR,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            risk_score INTEGER,
            risk_level VARCHAR,
            risk_reason VARCHAR,
            mitre_techniques VARCHAR,
            security_enriched_at TIMESTAMP,
            scope_verdict VARCHAR,
            scope_resolved_path VARCHAR
        )
    """)

    conn.execute("DROP TABLE IF EXISTS sessions")
    conn.execute("""
        CREATE TABLE sessions (
            id VARCHAR PRIMARY KEY,
            directory VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    return analytics_db


@pytest.fixture
def unenriched_parts(enrichment_db):
    """Insert unenriched parts that need bulk enrichment."""
    conn = enrichment_db.connect()
    now = datetime.now()

    parts = []
    for i in range(50):
        parts.append(
            (
                f"prt_{i:03d}",
                "ses_001",
                f"msg_{i:03d}",
                "tool",
                "bash",
                "completed",
                json.dumps({"command": f"echo test_{i}"}),
            )
        )

    conn.executemany(
        """
        INSERT INTO parts (id, session_id, message_id, part_type, tool_name, tool_status, arguments)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        parts,
    )

    return enrichment_db


class TestBulkEnrich:
    """Tests for bulk_enrich() function."""

    def test_enriches_all_unenriched_parts(self, unenriched_parts):
        """Should enrich all unenriched parts in the database."""
        result = bulk_enrich(unenriched_parts, batch_size=10)

        assert result["enriched"] == 50
        assert result["duration_seconds"] > 0
        assert result["rate"] > 0

        conn = unenriched_parts.connect()
        enriched_count = conn.execute(
            "SELECT COUNT(*) FROM parts WHERE security_enriched_at IS NOT NULL"
        ).fetchone()[0]
        assert enriched_count == 50

    def test_returns_zero_when_all_already_enriched(self, enrichment_db):
        """Should return 0 enriched when all parts are already enriched."""
        conn = enrichment_db.connect()

        conn.execute(
            """
            INSERT INTO parts (id, session_id, message_id, part_type, tool_name, 
                              tool_status, arguments, security_enriched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                "prt_001",
                "ses_001",
                "msg_001",
                "tool",
                "bash",
                "completed",
                json.dumps({"command": "echo test"}),
                datetime.now(),
            ),
        )

        result = bulk_enrich(enrichment_db, batch_size=10)

        assert result["enriched"] == 0
        assert result["duration_seconds"] >= 0

    def test_processes_in_batches(self, unenriched_parts):
        """Should process parts in configurable batches."""
        result = bulk_enrich(unenriched_parts, batch_size=5)

        assert result["enriched"] == 50

        conn = unenriched_parts.connect()
        enriched = conn.execute(
            "SELECT COUNT(*) FROM parts WHERE security_enriched_at IS NOT NULL"
        ).fetchone()[0]
        assert enriched == 50

    def test_enriches_only_security_relevant_tools(self, enrichment_db):
        """Should only enrich parts with security-relevant tool names."""
        conn = enrichment_db.connect()
        now = datetime.now()

        parts = [
            (
                "prt_bash",
                "ses_001",
                "msg_001",
                "tool",
                "bash",
                "completed",
                json.dumps({"command": "echo"}),
            ),
            (
                "prt_read",
                "ses_001",
                "msg_002",
                "tool",
                "read",
                "completed",
                json.dumps({"filePath": "/tmp/test"}),
            ),
            ("prt_text", "ses_001", "msg_003", "text", None, None, None),
        ]

        conn.executemany(
            """
            INSERT INTO parts (id, session_id, message_id, part_type, tool_name, tool_status, arguments)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            parts,
        )

        result = bulk_enrich(enrichment_db, batch_size=10)

        assert result["enriched"] == 2

    def test_enrichment_sets_all_security_fields(self, enrichment_db):
        """Should set risk_score, risk_level, risk_reason, mitre_techniques."""
        conn = enrichment_db.connect()

        conn.execute(
            """
            INSERT INTO parts (id, session_id, message_id, part_type, tool_name, tool_status, arguments)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                "prt_001",
                "ses_001",
                "msg_001",
                "tool",
                "bash",
                "completed",
                json.dumps({"command": "rm -rf /"}),
            ),
        )

        bulk_enrich(enrichment_db, batch_size=10)

        result = conn.execute(
            """
            SELECT risk_score, risk_level, risk_reason, mitre_techniques, security_enriched_at
            FROM parts WHERE id = 'prt_001'
        """
        ).fetchone()

        assert result[0] is not None
        assert result[1] is not None
        assert result[2] is not None
        assert result[3] is not None
        assert result[4] is not None

    def test_idempotent_multiple_runs(self, unenriched_parts):
        """Running bulk_enrich multiple times should not re-enrich same parts."""
        result1 = bulk_enrich(unenriched_parts, batch_size=10)
        assert result1["enriched"] == 50

        result2 = bulk_enrich(unenriched_parts, batch_size=10)
        assert result2["enriched"] == 0

    def test_resumes_after_partial_enrichment(self, enrichment_db):
        """Should resume enrichment from where it left off."""
        conn = enrichment_db.connect()
        now = datetime.now()

        parts = []
        for i in range(20):
            parts.append(
                (
                    f"prt_{i:03d}",
                    "ses_001",
                    f"msg_{i:03d}",
                    "tool",
                    "bash",
                    "completed",
                    json.dumps({"command": f"echo {i}"}),
                    now if i < 10 else None,
                )
            )

        conn.executemany(
            """
            INSERT INTO parts (id, session_id, message_id, part_type, tool_name, 
                              tool_status, arguments, security_enriched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            parts,
        )

        result = bulk_enrich(enrichment_db, batch_size=5)

        assert result["enriched"] == 10

        enriched = conn.execute(
            "SELECT COUNT(*) FROM parts WHERE security_enriched_at IS NOT NULL"
        ).fetchone()[0]
        assert enriched == 20

    def test_calculates_correct_statistics(self, unenriched_parts):
        """Should return accurate enrichment statistics."""
        result = bulk_enrich(unenriched_parts, batch_size=10)

        assert "enriched" in result
        assert "duration_seconds" in result
        assert "rate" in result

        assert result["enriched"] == 50
        assert result["duration_seconds"] > 0
        assert result["rate"] == result["enriched"] / result["duration_seconds"]

    @patch("bulk_enrichment.info")
    def test_logs_progress(self, mock_info, unenriched_parts):
        """Should log progress messages during enrichment."""
        bulk_enrich(unenriched_parts, batch_size=10)

        assert mock_info.called
        log_messages = [call[0][0] for call in mock_info.call_args_list]

        start_messages = [msg for msg in log_messages if "Starting" in msg]
        complete_messages = [msg for msg in log_messages if "Complete" in msg]

        assert len(start_messages) > 0
        assert len(complete_messages) > 0


class TestBulkEnrichmentEdgeCases:
    """Edge case tests for bulk enrichment."""

    def test_handles_empty_database(self, enrichment_db):
        """Should handle database with no parts gracefully."""
        result = bulk_enrich(enrichment_db, batch_size=10)

        assert result["enriched"] == 0
        assert result["duration_seconds"] >= 0

    def test_handles_invalid_json_arguments(self, enrichment_db):
        """Should handle parts with invalid JSON in arguments."""
        conn = enrichment_db.connect()

        conn.execute(
            """
            INSERT INTO parts (id, session_id, message_id, part_type, tool_name, tool_status, arguments)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                "prt_001",
                "ses_001",
                "msg_001",
                "tool",
                "bash",
                "completed",
                "{invalid json",
            ),
        )

        result = bulk_enrich(enrichment_db, batch_size=10)

        assert result["enriched"] == 1

        enriched = conn.execute(
            "SELECT security_enriched_at FROM parts WHERE id = 'prt_001'"
        ).fetchone()[0]
        assert enriched is not None

    def test_custom_batch_size(self, unenriched_parts):
        """Should respect custom batch_size parameter."""
        result = bulk_enrich(unenriched_parts, batch_size=3)

        assert result["enriched"] == 50

    def test_large_dataset_performance(self, enrichment_db):
        """Should handle large datasets efficiently."""
        conn = enrichment_db.connect()

        parts = []
        for i in range(1000):
            parts.append(
                (
                    f"prt_{i:04d}",
                    "ses_001",
                    f"msg_{i:04d}",
                    "tool",
                    "bash",
                    "completed",
                    json.dumps({"command": f"echo {i}"}),
                )
            )

        conn.executemany(
            """
            INSERT INTO parts (id, session_id, message_id, part_type, tool_name, tool_status, arguments)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            parts,
        )

        result = bulk_enrich(enrichment_db, batch_size=100)

        assert result["enriched"] == 1000
        assert result["rate"] > 50
