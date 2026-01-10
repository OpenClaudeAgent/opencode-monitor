#!/usr/bin/env python3
"""
Dashboard Profiler - Identify performance bottlenecks.

Usage: uv run python scripts/profile_dashboard.py
"""

import time
import sys
import json
from collections import defaultdict

# Add src to path
sys.path.insert(0, "src")


def profile_api_response():
    """Profile API response time and data size."""
    print("\n" + "=" * 60)
    print("1. API RESPONSE PROFILING")
    print("=" * 60)

    from opencode_monitor.api import get_api_client

    client = get_api_client()

    if not client.is_available:
        print("❌ API not available - is menubar running?")
        return None

    # Profile tracing tree endpoint
    print("\n📡 GET /api/tracing/tree (30 days)...")
    start = time.perf_counter()
    tree_data = client.get_tracing_tree(days=30)
    elapsed = time.perf_counter() - start

    if tree_data:
        # Count nodes recursively
        def count_nodes(nodes):
            total = len(nodes)
            for node in nodes:
                total += count_nodes(node.get("children", []))
            return total

        total_nodes = count_nodes(tree_data)
        json_size = len(json.dumps(tree_data))

        print(f"   ⏱️  Time: {elapsed * 1000:.1f} ms")
        print(f"   📊 Root sessions: {len(tree_data)}")
        print(f"   🌳 Total nodes: {total_nodes}")
        print(f"   📦 JSON size: {json_size / 1024:.1f} KB")

        # Analyze tree depth and breadth
        def analyze_tree(nodes, depth=0):
            stats = {"max_depth": depth, "nodes_by_depth": defaultdict(int)}
            for node in nodes:
                stats["nodes_by_depth"][depth] += 1
                children = node.get("children", [])
                if children:
                    child_stats = analyze_tree(children, depth + 1)
                    stats["max_depth"] = max(
                        stats["max_depth"], child_stats["max_depth"]
                    )
                    for d, c in child_stats["nodes_by_depth"].items():
                        stats["nodes_by_depth"][d] += c
            return stats

        tree_stats = analyze_tree(tree_data)
        print(f"   📏 Max depth: {tree_stats['max_depth']}")
        print(f"   📊 Nodes by depth:")
        for depth, count in sorted(tree_stats["nodes_by_depth"].items()):
            print(f"      Depth {depth}: {count} nodes")

        return tree_data
    else:
        print("   ⚠️  No data returned")
        return None


def profile_tree_building(tree_data):
    """Profile Qt tree widget building."""
    print("\n" + "=" * 60)
    print("2. QT TREE BUILDING PROFILING")
    print("=" * 60)

    if not tree_data:
        print("❌ No tree data to profile")
        return

    # Import Qt (headless)
    import os

    os.environ["QT_QPA_PLATFORM"] = "offscreen"

    from PyQt6.QtWidgets import QApplication, QTreeWidget
    from PyQt6.QtCore import Qt

    app = QApplication.instance()
    if not app:
        app = QApplication([])

    # Create tree widget
    tree = QTreeWidget()
    tree.setHeaderLabels(["Type / Name", "Time", "Duration", "In", "Out", ""])

    # Profile tree building
    from opencode_monitor.dashboard.sections.tracing.tree_builder import (
        build_session_tree,
    )

    print("\n🌲 Building tree widget...")
    start = time.perf_counter()
    build_session_tree(tree, tree_data)
    elapsed = time.perf_counter() - start

    # Count items
    def count_items(parent_item=None):
        if parent_item is None:
            count = tree.topLevelItemCount()
            total = count
            for i in range(count):
                total += count_items(tree.topLevelItem(i))
            return total
        else:
            count = parent_item.childCount()
            total = count
            for i in range(count):
                total += count_items(parent_item.child(i))
            return total

    total_items = count_items()

    print(f"   ⏱️  Build time: {elapsed * 1000:.1f} ms")
    print(f"   📊 Tree items created: {total_items}")
    print(f"   ⚡ Items/sec: {total_items / elapsed:.0f}")


def profile_db_queries():
    """Profile database query times."""
    print("\n" + "=" * 60)
    print("3. DATABASE QUERY PROFILING")
    print("=" * 60)

    from datetime import datetime, timedelta
    from opencode_monitor.analytics import AnalyticsDB

    # Use read_only mode to avoid lock conflicts with menubar
    db = AnalyticsDB(read_only=True)
    conn = db.connect()
    start_date = datetime.now() - timedelta(days=30)

    queries = [
        ("sessions count", "SELECT count(*) FROM sessions"),
        ("messages count", "SELECT count(*) FROM messages"),
        ("parts count", "SELECT count(*) FROM parts"),
        ("agent_traces count", "SELECT count(*) FROM agent_traces"),
        (
            "root traces (30d)",
            f"""
            SELECT count(*) FROM agent_traces
            WHERE parent_trace_id IS NULL
            AND (trigger_type = 'main_session' OR trigger_type IS NULL)
            AND started_at >= '{start_date.isoformat()}'
            """,
        ),
        (
            "child traces (30d)",
            f"""
            SELECT count(*) FROM agent_traces
            WHERE parent_trace_id IS NOT NULL
            AND started_at >= '{start_date.isoformat()}'
            """,
        ),
        (
            "messages with parts join",
            """
            SELECT count(*)
            FROM messages m
            LEFT JOIN parts p ON p.message_id = m.id
            WHERE m.role = 'assistant'
            """,
        ),
    ]

    print("\n📊 Query benchmarks:")
    for name, query in queries:
        start = time.perf_counter()
        try:
            result = conn.execute(query).fetchone()
            elapsed = time.perf_counter() - start
            print(f"   {name}: {result[0]:,} rows ({elapsed * 1000:.1f} ms)")
        except Exception as e:
            print(f"   {name}: ERROR - {e}")

    # Profile the heavy join query used by tracing endpoint
    print("\n📊 Heavy query profiling:")

    heavy_query = f"""
    SELECT
        at.trace_id,
        at.session_id,
        at.parent_trace_id,
        at.agent_type,
        at.subagent_type,
        at.started_at,
        at.duration_ms,
        at.tokens_in,
        at.tokens_out,
        at.status,
        at.trigger_type,
        at.prompt_input,
        at.prompt_output,
        s.title,
        s.directory
    FROM agent_traces at
    LEFT JOIN sessions s ON s.id = at.session_id
    WHERE at.parent_trace_id IS NULL
      AND (at.trigger_type = 'main_session' OR at.trigger_type IS NULL)
      AND at.started_at >= '{start_date.isoformat()}'
    ORDER BY at.started_at DESC
    """

    start = time.perf_counter()
    rows = conn.execute(heavy_query).fetchall()
    elapsed = time.perf_counter() - start
    print(f"   Root traces query: {len(rows)} rows ({elapsed * 1000:.1f} ms)")

    # Check for large JSON fields
    print("\n📊 Large data field analysis:")

    large_prompts_query = """
    SELECT
        count(*) as total,
        count(CASE WHEN length(prompt_input) > 10000 THEN 1 END) as large_input,
        count(CASE WHEN length(prompt_output) > 10000 THEN 1 END) as large_output,
        max(length(prompt_input)) as max_input_len,
        max(length(prompt_output)) as max_output_len,
        avg(length(prompt_input)) as avg_input_len,
        avg(length(prompt_output)) as avg_output_len
    FROM agent_traces
    """

    result = conn.execute(large_prompts_query).fetchone()
    print(f"   Total traces: {result[0]:,}")
    print(f"   Large inputs (>10KB): {result[1]:,}")
    print(f"   Large outputs (>10KB): {result[2]:,}")
    print(f"   Max input size: {result[3] or 0:,} chars")
    print(f"   Max output size: {result[4] or 0:,} chars")
    print(f"   Avg input size: {result[5] or 0:,.0f} chars")
    print(f"   Avg output size: {result[6] or 0:,.0f} chars")


def profile_memory():
    """Profile memory usage of tree data."""
    print("\n" + "=" * 60)
    print("4. MEMORY PROFILING")
    print("=" * 60)

    import tracemalloc

    tracemalloc.start()

    from opencode_monitor.api import get_api_client

    client = get_api_client()
    if client.is_available:
        tree_data = client.get_tracing_tree(days=30)

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        print(f"\n📊 Memory usage:")
        print(f"   Current: {current / 1024 / 1024:.1f} MB")
        print(f"   Peak: {peak / 1024 / 1024:.1f} MB")
    else:
        print("❌ API not available")


def main():
    print("🔍 DASHBOARD PERFORMANCE PROFILER")
    print("=" * 60)

    # 1. Profile API
    tree_data = profile_api_response()

    # 2. Profile DB queries
    profile_db_queries()

    # 3. Profile tree building
    profile_tree_building(tree_data)

    # 4. Profile memory
    profile_memory()

    print("\n" + "=" * 60)
    print("PROFILING COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
