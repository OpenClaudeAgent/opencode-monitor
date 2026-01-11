#!/usr/bin/env python3
"""
API Performance Profiler

Runs load tests against API endpoints and measures performance.
Generates reports on response times, payload sizes, and bottlenecks.

Usage:
    python tools/profile_api.py [--endpoint ENDPOINT] [--requests NUM]
"""

import sys
import time
import requests
import statistics
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class APIProfiler:
    def __init__(self, base_url: str = "http://localhost:5050"):
        self.base_url = base_url
        self.results: List[Dict[str, Any]] = []

    def test_endpoint(
        self, path: str, params: Dict[str, Any] | None = None, num_requests: int = 10
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        durations = []
        sizes = []
        errors = []

        print(f"\nTesting {path} ({num_requests} requests)...")

        for i in range(num_requests):
            start = time.perf_counter()
            try:
                response = requests.get(url, params=params, timeout=30)
                duration_ms = (time.perf_counter() - start) * 1000

                if response.status_code == 200:
                    durations.append(duration_ms)
                    sizes.append(len(response.content) / 1024)
                else:
                    errors.append(f"HTTP {response.status_code}")
            except Exception as e:
                duration_ms = (time.perf_counter() - start) * 1000
                errors.append(str(e))

            if (i + 1) % 10 == 0:
                print(f"  Progress: {i + 1}/{num_requests}")

        if not durations:
            return {
                "endpoint": path,
                "errors": errors,
                "success": False,
            }

        durations_sorted = sorted(durations)
        sizes_sorted = sorted(sizes)

        result = {
            "endpoint": path,
            "requests": num_requests,
            "success": len(durations),
            "errors": len(errors),
            "duration_ms": {
                "min": min(durations),
                "max": max(durations),
                "avg": statistics.mean(durations),
                "median": statistics.median(durations),
                "p95": durations_sorted[int(len(durations_sorted) * 0.95)],
                "p99": durations_sorted[int(len(durations_sorted) * 0.99)],
            },
            "size_kb": {
                "min": min(sizes),
                "max": max(sizes),
                "avg": statistics.mean(sizes),
                "median": statistics.median(sizes),
            },
        }

        self.results.append(result)
        return result

    def print_result(self, result: Dict) -> None:
        print(f"\n{result['endpoint']}:")
        print(f"  Success: {result.get('success', 0)}/{result['requests']}")

        if result.get("success"):
            dur = result["duration_ms"]
            size = result["size_kb"]
            print(f"  Duration (ms):")
            print(f"    Min:    {dur['min']:>8.1f}")
            print(f"    Avg:    {dur['avg']:>8.1f}")
            print(f"    Median: {dur['median']:>8.1f}")
            print(f"    P95:    {dur['p95']:>8.1f}")
            print(f"    P99:    {dur['p99']:>8.1f}")
            print(f"    Max:    {dur['max']:>8.1f}")
            print(f"  Size (KB):")
            print(f"    Min:    {size['min']:>8.1f}")
            print(f"    Avg:    {size['avg']:>8.1f}")
            print(f"    Max:    {size['max']:>8.1f}")

        if result.get("errors"):
            print(f"  Errors: {result.get('errors')}")

    def run_suite(self, num_requests: int = 10) -> None:
        print("=" * 80)
        print("API PERFORMANCE TEST SUITE")
        print("=" * 80)

        endpoints = [
            ("/api/health", {}),
            ("/api/stats", {}),
            ("/api/global-stats", {"days": 7}),
            ("/api/sessions", {"days": 7, "limit": 100}),
            ("/api/tracing/tree", {"days": 7, "include_tools": "false"}),
            ("/api/security", {"row_limit": 100}),
        ]

        for path, params in endpoints:
            result = self.test_endpoint(path, params, num_requests)
            self.print_result(result)

        self.print_summary()

    def print_summary(self) -> None:
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)

        critical_endpoints = []
        slow_endpoints = []
        large_endpoints = []

        for result in self.results:
            if not result.get("success"):
                continue

            endpoint = result["endpoint"]
            avg_ms = result["duration_ms"]["avg"]
            avg_kb = result["size_kb"]["avg"]
            p95_ms = result["duration_ms"]["p95"]

            if p95_ms > 5000:
                critical_endpoints.append((endpoint, p95_ms))
            elif avg_ms > 1000:
                slow_endpoints.append((endpoint, avg_ms))

            if avg_kb > 1024:
                large_endpoints.append((endpoint, avg_kb))

        if critical_endpoints:
            print("\n⚠️  CRITICAL (P95 > 5s):")
            for endpoint, p95 in critical_endpoints:
                print(f"  {endpoint}: {p95:.0f}ms")

        if slow_endpoints:
            print("\n⏱️  SLOW (avg > 1s):")
            for endpoint, avg in slow_endpoints:
                print(f"  {endpoint}: {avg:.0f}ms")

        if large_endpoints:
            print("\n📦 LARGE PAYLOADS (avg > 1MB):")
            for endpoint, size in large_endpoints:
                print(f"  {endpoint}: {size / 1024:.1f}MB")

        if not (critical_endpoints or slow_endpoints or large_endpoints):
            print("\n✅ All endpoints performing well")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Profile API performance")
    parser.add_argument("--endpoint", type=str, help="Specific endpoint to test")
    parser.add_argument(
        "--requests", type=int, default=10, help="Number of requests per endpoint"
    )
    parser.add_argument(
        "--url", type=str, default="http://localhost:5050", help="API base URL"
    )

    args = parser.parse_args()

    profiler = APIProfiler(base_url=args.url)

    try:
        if args.endpoint:
            result = profiler.test_endpoint(args.endpoint, num_requests=args.requests)
            profiler.print_result(result)
        else:
            profiler.run_suite(num_requests=args.requests)
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Could not connect to API server")
        print(f"   Make sure the server is running at {args.url}")
        sys.exit(1)


if __name__ == "__main__":
    main()
