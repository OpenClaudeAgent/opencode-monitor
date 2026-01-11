#!/usr/bin/env python3
"""
Bulk backfill script for OpenCode Monitor.

Loads all historical data into the analytics database.
Must be run when the app is NOT running (DB must not be locked).

Usage:
    make backfill
    # or
    uv run python scripts/backfill.py
"""

import sys
import time
from pathlib import Path

# Add src to path for opencode_monitor imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
# Add scripts to path for local bulk_loader import
sys.path.insert(0, str(Path(__file__).parent))

from opencode_monitor.analytics.db import AnalyticsDB
from opencode_monitor.analytics.indexer.sync_state import SyncState
from opencode_monitor.analytics.indexer.trace_builder import TraceBuilder
from bulk_loader import BulkLoader


OPENCODE_STORAGE = Path.home() / ".local" / "share" / "opencode" / "storage"


def check_db_lock(db_path: Path) -> bool:
    """Return True if DB is available, False if locked."""
    import duckdb

    try:
        conn = duckdb.connect(str(db_path))
        conn.execute("SELECT 1")
        conn.close()
        return True
    except duckdb.IOException:
        return False


def run_backfill() -> int:
    print("=" * 60)
    print("OpenCode Monitor - Bulk Backfill")
    print("=" * 60)

    db_path = Path.home() / ".config" / "opencode-monitor" / "analytics.duckdb"

    if not check_db_lock(db_path):
        print()
        print("ERROR: Database is locked!")
        print()
        print("The app is probably running. Stop it first:")
        print("  pkill -f opencode_monitor")
        print()
        print("Then run backfill again:")
        print("  make backfill")
        print()
        return 1

    if not OPENCODE_STORAGE.exists():
        print(f"ERROR: Storage path not found: {OPENCODE_STORAGE}")
        return 1

    print(f"Storage: {OPENCODE_STORAGE}")
    print(f"Database: {db_path}")
    print()

    db = AnalyticsDB(db_path)
    db.connect()

    sync_state = SyncState(db)
    bulk_loader = BulkLoader(db, OPENCODE_STORAGE, sync_state)
    trace_builder = TraceBuilder(db)

    start_time = time.time()
    cutoff_time = time.time()

    counts = bulk_loader.count_files()
    total = sum(counts.values())
    print(
        f"Files to load: {total:,} ({counts['session']:,} sessions, {counts['message']:,} messages, {counts['part']:,} parts)"
    )
    print("-" * 40)

    print("Loading sessions...", flush=True)
    results = {"session": bulk_loader.load_sessions()}
    print(
        f"  Sessions: {results['session'].files_loaded:,} in {results['session'].duration_seconds:.1f}s"
    )

    print("Loading messages...", flush=True)
    results["message"] = bulk_loader.load_messages()
    print(
        f"  Messages: {results['message'].files_loaded:,} in {results['message'].duration_seconds:.1f}s"
    )

    print("Loading parts (this may take a while)...", flush=True)
    results["part"] = bulk_loader.load_parts()
    print(
        f"  Parts: {results['part'].files_loaded:,} in {results['part'].duration_seconds:.1f}s"
    )

    total_loaded = sum(r.files_loaded for r in results.values())
    total_time = sum(r.duration_seconds for r in results.values())

    print("-" * 40)
    print(f"Bulk load complete: {total_loaded:,} files in {total_time:.1f}s")
    print()

    print("Post-processing...")
    print("-" * 40)

    updated_agents = trace_builder.update_root_trace_agents()
    if updated_agents > 0:
        print(f"  Updated {updated_agents} root trace agents")

    resolved = trace_builder.resolve_parent_traces()
    if resolved > 0:
        print(f"  Resolved {resolved} parent traces")

    backfilled = trace_builder.backfill_missing_tokens()
    if backfilled > 0:
        print(f"  Backfilled tokens for {backfilled} traces")

    try:
        stats = trace_builder.build_all()
        exchanges = stats.get("exchanges", 0)
        exchange_traces = stats.get("exchange_traces", 0)
        session_traces = stats.get("session_traces", 0)
        if exchanges > 0 or exchange_traces > 0 or session_traces > 0:
            print(
                f"  Built trace tables: {exchanges} exchanges, "
                f"{exchange_traces} events, {session_traces} sessions"
            )
    except Exception as e:
        print(f"  Warning: Failed to build trace tables: {e}")

    print("-" * 40)

    db.close()

    total_elapsed = time.time() - start_time
    print()
    print(f"Backfill complete in {total_elapsed:.1f}s")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(run_backfill())
