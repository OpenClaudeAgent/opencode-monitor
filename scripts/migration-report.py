#!/usr/bin/env python3
"""
Test Migration Progress Report

Tracks migration progress from old test style to new test structure.
"""

import subprocess
import sys
from pathlib import Path


def count_tests(path: str) -> int:
    try:
        result = subprocess.run(
            ["pytest", "--collect-only", "-q", path],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )

        for line in result.stdout.split("\n"):
            if "test" in line.lower() and "selected" not in line:
                continue
            if line.strip().endswith("selected"):
                parts = line.split()
                if parts and parts[0].isdigit():
                    return int(parts[0])
        return 0
    except Exception as e:
        print(f"Error counting tests in {path}: {e}", file=sys.stderr)
        return 0


def main():
    unit_tests = count_tests("tests/unit/")
    integration_tests = count_tests("tests/integration/")
    e2e_tests = count_tests("tests/e2e/")

    new_tests = unit_tests + integration_tests + e2e_tests
    all_tests = count_tests("tests/")
    old_tests = all_tests - new_tests

    total = all_tests
    migrated_pct = (new_tests / total * 100) if total > 0 else 0

    print("=" * 60)
    print("Test Migration Progress Report")
    print("=" * 60)
    print()
    print(f"Unit Tests:        {unit_tests:4d}")
    print(f"Integration Tests: {integration_tests:4d}")
    print(f"E2E Tests:         {e2e_tests:4d}")
    print(f"{'─' * 30}")
    print(f"New Structure:     {new_tests:4d} ({migrated_pct:.1f}%)")
    print(f"Old Structure:     {old_tests:4d}")
    print(f"{'─' * 30}")
    print(f"Total:             {total:4d}")
    print()
    print("=" * 60)

    if migrated_pct >= 60:
        print("✅ Migration target reached (60%+)")
    else:
        print(f"⏳ Migration in progress (target: 60%, current: {migrated_pct:.1f}%)")

    print("=" * 60)


if __name__ == "__main__":
    main()
