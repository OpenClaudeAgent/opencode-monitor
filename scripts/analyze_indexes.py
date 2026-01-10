#!/usr/bin/env python3
"""
Analyze current database indexes and benchmark queries.
Part of DQ-004: Add Missing Database Indexes
"""

import sys
import time
from pathlib import Path

try:
    import duckdb
except ImportError:
    print("Error: duckdb package not installed. Run: pip install duckdb")
    sys.exit(1)


def get_db_path():
    """Get path to analytics database."""
    return Path.home() / ".config" / "opencode-monitor" / "analytics.duckdb"


def check_current_indexes(conn):
    """Check what indexes currently exist on each table."""
    print("=" * 80)
    print("CURRENT INDEXES")
    print("=" * 80)

    tables = [
        "sessions",
        "messages",
        "parts",
        "file_operations",
        "exchange_traces",
        "agent_traces",
    ]

    for table in tables:
        print(f"\n{table}:")
        try:
            indexes = conn.execute(f"""
                SELECT index_name 
                FROM duckdb_indexes() 
                WHERE table_name = '{table}'
            """).fetchall()

            if indexes:
                for idx in indexes:
                    print(f"  - {idx[0]}")
            else:
                print(f"  (no indexes)")
        except Exception as e:
            print(f"  Error: {e}")


def check_table_columns(conn):
    """Check what columns exist in key tables."""
    print("\n" + "=" * 80)
    print("TABLE COLUMNS")
    print("=" * 80)

    tables = ["sessions", "messages", "parts", "file_operations"]

    for table in tables:
        print(f"\n{table}:")
        try:
            columns = conn.execute(f"""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = '{table}'
                ORDER BY ordinal_position
            """).fetchall()

            for col_name, col_type in columns:
                print(f"  - {col_name} ({col_type})")
        except Exception as e:
            print(f"  Error: {e}")


def benchmark_queries_before(conn):
    """Benchmark queries BEFORE adding new indexes."""
    print("\n" + "=" * 80)
    print("BENCHMARK - BEFORE INDEXES")
    print("=" * 80)

    # Get sample data for queries
    session_sample = conn.execute("""
        SELECT id, project_name 
        FROM sessions 
        WHERE project_name IS NOT NULL 
        LIMIT 1
    """).fetchone()

    if not session_sample:
        print("No session data to benchmark")
        return {}

    session_id = session_sample[0]
    project_name = session_sample[1] if len(session_sample) > 1 else None

    message_sample = conn.execute(f"""
        SELECT id FROM messages WHERE session_id = '{session_id}' LIMIT 1
    """).fetchone()
    message_id = message_sample[0] if message_sample else None

    queries = {}

    # Query 1: Project filtering with time sort
    if project_name:
        query = f"""
            SELECT * FROM sessions 
            WHERE project_name = '{project_name}' 
            ORDER BY created_at DESC 
            LIMIT 10
        """
        start = time.perf_counter()
        conn.execute(query).fetchall()
        elapsed = (time.perf_counter() - start) * 1000
        queries["sessions_project_time"] = elapsed
        print(f"\nQuery 1 - sessions(project_name, created_at):")
        print(f"  Time: {elapsed:.2f}ms")

    # Query 2: Message ordering by session
    query = f"""
        SELECT * FROM messages 
        WHERE session_id = '{session_id}' 
        ORDER BY created_at
    """
    start = time.perf_counter()
    conn.execute(query).fetchall()
    elapsed = (time.perf_counter() - start) * 1000
    queries["messages_session_order"] = elapsed
    print(f"\nQuery 2 - messages(session_id, created_at):")
    print(f"  Time: {elapsed:.2f}ms")

    # Query 3: Parts by message
    if message_id:
        query = f"""
            SELECT * FROM parts 
            WHERE message_id = '{message_id}' 
            ORDER BY created_at
        """
        start = time.perf_counter()
        conn.execute(query).fetchall()
        elapsed = (time.perf_counter() - start) * 1000
        queries["parts_message_order"] = elapsed
        print(f"\nQuery 3 - parts(message_id, created_at):")
        print(f"  Time: {elapsed:.2f}ms")

    # Query 4: Parts by tool name
    if message_id:
        query = f"""
            SELECT * FROM parts 
            WHERE message_id = '{message_id}' AND tool_name IS NOT NULL
        """
        start = time.perf_counter()
        conn.execute(query).fetchall()
        elapsed = (time.perf_counter() - start) * 1000
        queries["parts_message_tool"] = elapsed
        print(f"\nQuery 4 - parts(message_id, tool_name):")
        print(f"  Time: {elapsed:.2f}ms")

    # Query 5: File operations by session and type
    query = f"""
        SELECT * FROM file_operations 
        WHERE session_id = '{session_id}'
        ORDER BY operation
    """
    start = time.perf_counter()
    conn.execute(query).fetchall()
    elapsed = (time.perf_counter() - start) * 1000
    queries["file_ops_session_type"] = elapsed
    print(f"\nQuery 5 - file_operations(session_id, operation):")
    print(f"  Time: {elapsed:.2f}ms")

    # Query 6: Messages by root_path (Sprint 1 prep)
    query = """
        SELECT * FROM messages 
        WHERE root_path IS NOT NULL
        LIMIT 100
    """
    start = time.perf_counter()
    conn.execute(query).fetchall()
    elapsed = (time.perf_counter() - start) * 1000
    queries["messages_root_path"] = elapsed
    print(f"\nQuery 6 - messages(root_path):")
    print(f"  Time: {elapsed:.2f}ms")

    # Query 7: Parts by error
    query = """
        SELECT * FROM parts 
        WHERE error_message IS NOT NULL
        LIMIT 100
    """
    start = time.perf_counter()
    conn.execute(query).fetchall()
    elapsed = (time.perf_counter() - start) * 1000
    queries["parts_error"] = elapsed
    print(f"\nQuery 7 - parts(error_message):")
    print(f"  Time: {elapsed:.2f}ms")

    # Query 8: Exchange traces
    exchange_sample = conn.execute("""
        SELECT exchange_id FROM exchange_traces LIMIT 1
    """).fetchone()

    if exchange_sample:
        exchange_id = exchange_sample[0]
        query = f"""
            SELECT * FROM exchange_traces 
            WHERE exchange_id = '{exchange_id}'
            ORDER BY event_order
        """
        start = time.perf_counter()
        conn.execute(query).fetchall()
        elapsed = (time.perf_counter() - start) * 1000
        queries["exchange_traces_order"] = elapsed
        print(f"\nQuery 8 - exchange_traces(exchange_id, event_order):")
        print(f"  Time: {elapsed:.2f}ms")

    return queries


def main():
    """Main analysis function."""
    print("DQ-004: Database Index Analysis")
    print("=" * 80)

    db_path = get_db_path()
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    conn = duckdb.connect(str(db_path), read_only=True)

    try:
        check_current_indexes(conn)
        check_table_columns(conn)
        results = benchmark_queries_before(conn)
    finally:
        conn.close()

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print(f"\nTotal queries benchmarked: {len(results)}")
    if results:
        avg_time = sum(results.values()) / len(results)
        print(f"Average query time: {avg_time:.2f}ms")

    return results


if __name__ == "__main__":
    main()
