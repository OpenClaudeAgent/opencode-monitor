#!/usr/bin/env python3
"""
Backfill script for root trace tokens (DQ-001).

This script updates all root traces with tokens_in=0 and tokens_out=0
by aggregating token counts from their child session messages.

Usage:
    python scripts/backfill_root_trace_tokens.py [--dry-run] [--limit N]

Options:
    --dry-run: Show what would be updated without making changes
    --limit N: Limit to N traces (for testing)
    --verbose: Show detailed progress

Example:
    # Dry run to see what would be updated
    python scripts/backfill_root_trace_tokens.py --dry-run

    # Update first 10 traces
    python scripts/backfill_root_trace_tokens.py --limit 10

    # Update all traces
    python scripts/backfill_root_trace_tokens.py
"""

import argparse
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from opencode_monitor.analytics.db import AnalyticsDB
from opencode_monitor.analytics.indexer.trace_builder.builder import TraceBuilder


def main():
    parser = argparse.ArgumentParser(
        description="Backfill root trace tokens from messages"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without making changes",
    )
    parser.add_argument("--limit", type=int, help="Limit to N traces (for testing)")
    parser.add_argument("--verbose", action="store_true", help="Show detailed progress")
    parser.add_argument(
        "--db-path",
        type=Path,
        help="Path to database file (default: ~/.opencode/analytics.duckdb)",
    )

    args = parser.parse_args()

    # Connect to database
    db_path = args.db_path or Path.home() / ".opencode" / "analytics.duckdb"
    print(f"[Backfill] Using database: {db_path}")

    if not db_path.exists():
        print(f"[Backfill] ERROR: Database not found at {db_path}")
        print("[Backfill] Run the indexer first to create the database")
        return 1

    db = AnalyticsDB(db_path=db_path)
    conn = db.connect()

    # Count root traces that need updating
    query = """
        SELECT COUNT(*) FROM agent_traces t
        WHERE t.trace_id LIKE 'root_%'
          AND t.child_session_id IS NOT NULL
          AND (t.tokens_in IS NULL OR t.tokens_in = 0)
          AND (t.tokens_out IS NULL OR t.tokens_out = 0)
          AND EXISTS (
              SELECT 1 FROM messages m
              WHERE m.session_id = t.child_session_id
              GROUP BY m.session_id
              HAVING SUM(m.tokens_input) > 0 OR SUM(m.tokens_output) > 0
          )
    """

    if args.limit:
        print(f"[Backfill] Limiting to {args.limit} traces")

    result = conn.execute(query).fetchone()
    traces_to_update = result[0] if result else 0

    print(f"[Backfill] Found {traces_to_update:,} root traces with zero tokens")

    if traces_to_update == 0:
        print("[Backfill] ✅ No traces need updating - all tokens are already set!")
        return 0

    if args.dry_run:
        print("[Backfill] DRY RUN - showing what would be updated:")
        print()

        # Show sample traces that would be updated
        sample_query = """
            SELECT 
                t.trace_id,
                t.child_session_id,
                t.tokens_in as current_in,
                t.tokens_out as current_out,
                COALESCE(SUM(m.tokens_input), 0) as new_in,
                COALESCE(SUM(m.tokens_output), 0) as new_out
            FROM agent_traces t
            LEFT JOIN messages m ON m.session_id = t.child_session_id
            WHERE t.trace_id LIKE 'root_%'
              AND t.child_session_id IS NOT NULL
              AND (t.tokens_in IS NULL OR t.tokens_in = 0)
              AND (t.tokens_out IS NULL OR t.tokens_out = 0)
            GROUP BY t.trace_id, t.child_session_id, t.tokens_in, t.tokens_out
            HAVING SUM(m.tokens_input) > 0 OR SUM(m.tokens_output) > 0
            LIMIT 10
        """

        samples = conn.execute(sample_query).fetchall()

        for trace_id, session_id, curr_in, curr_out, new_in, new_out in samples:
            print(
                f"  {trace_id[:30]:<30} | "
                f"tokens_in: {curr_in:>6} -> {new_in:>6} | "
                f"tokens_out: {curr_out:>6} -> {new_out:>6}"
            )

        print()
        print(f"[Backfill] Would update {traces_to_update:,} traces total")
        print("[Backfill] Run without --dry-run to apply changes")
        return 0

    # Perform actual backfill
    print(f"[Backfill] Updating {traces_to_update:,} traces...")

    trace_builder = TraceBuilder(db)

    # If limit is set, we need to update in batches
    if args.limit:
        print(f"[Backfill] Processing in batches of {args.limit}...")

        batch_query = """
            SELECT trace_id FROM agent_traces t
            WHERE t.trace_id LIKE 'root_%'
              AND t.child_session_id IS NOT NULL
              AND (t.tokens_in IS NULL OR t.tokens_in = 0)
              AND (t.tokens_out IS NULL OR t.tokens_out = 0)
              AND EXISTS (
                  SELECT 1 FROM messages m
                  WHERE m.session_id = t.child_session_id
                  GROUP BY m.session_id
                  HAVING SUM(m.tokens_input) > 0 OR SUM(m.tokens_output) > 0
              )
            LIMIT ?
        """

        trace_ids = [
            row[0] for row in conn.execute(batch_query, [args.limit]).fetchall()
        ]

        # Update each trace individually (for progress tracking)
        for i, trace_id in enumerate(trace_ids, 1):
            # Get child_session_id
            result = conn.execute(
                "SELECT child_session_id FROM agent_traces WHERE trace_id = ?",
                [trace_id],
            ).fetchone()

            if result and result[0]:
                trace_builder.update_trace_tokens(result[0])

            if args.verbose and i % 10 == 0:
                print(f"[Backfill] Progress: {i}/{len(trace_ids)}")

        updated_count = len(trace_ids)

    else:
        # Bulk update using backfill_missing_tokens
        updated_count = trace_builder.backfill_missing_tokens()

    print(f"[Backfill] ✅ Updated {updated_count:,} root traces")

    # Show statistics
    stats_query = """
        SELECT 
            COUNT(*) as total_root_traces,
            COUNT(CASE WHEN tokens_in > 0 OR tokens_out > 0 THEN 1 END) as with_tokens,
            SUM(tokens_in) as total_input,
            SUM(tokens_out) as total_output
        FROM agent_traces
        WHERE trace_id LIKE 'root_%'
    """

    stats = conn.execute(stats_query).fetchone()
    if stats:
        total, with_tokens, total_in, total_out = stats
        print()
        print("[Backfill] Statistics:")
        print(f"  Total root traces: {total:,}")
        print(f"  With tokens: {with_tokens:,} ({with_tokens / total * 100:.1f}%)")
        print(f"  Total input tokens: {total_in:,}")
        print(f"  Total output tokens: {total_out:,}")
        print(f"  Total tokens: {total_in + total_out:,}")

    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
