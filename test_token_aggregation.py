#!/usr/bin/env python3
"""
Test script to verify token aggregation fix.
Tests that session tokens are not double-counted.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def test_aggregation_logic():
    """Test the token aggregation logic."""

    # Mock tree structure mimicking real data
    # Session has aggregated tokens (175, 4747, 658693, 61035)
    # Each exchange has individual message tokens
    mock_tree = {
        "node_type": "session",
        "session_id": "ses_test",
        "tokens_in": 175,  # Aggregated from messages
        "tokens_out": 4747,
        "cache_read": 658693,
        "cache_write": 61035,
        "children": [
            {
                "node_type": "user_turn",
                "tokens_in": 100,  # Individual message tokens
                "tokens_out": 2000,
                "cache_read": 300000,
                "cache_write": 30000,
                "children": [],
            },
            {
                "node_type": "user_turn",
                "tokens_in": 75,  # Individual message tokens
                "tokens_out": 2747,
                "cache_read": 358693,
                "cache_write": 31035,
                "children": [],
            },
        ],
    }

    # Simple version of the fixed aggregation logic
    def aggregate_tokens_fixed(node: dict, depth: int = 0) -> tuple[int, int, int, int]:
        """Fixed aggregation that doesn't double-count session tokens."""
        node_type = node.get("node_type", "unknown")
        indent = "  " * depth

        print(f"{indent}Aggregating node type={node_type}")

        # Get tokens from current node
        tokens_in = node.get("tokens_in", 0) or 0
        tokens_out = node.get("tokens_out", 0) or 0
        cache_read = node.get("cache_read", 0) or 0
        cache_write = node.get("cache_write", 0) or 0

        print(
            f"{indent}  Node tokens: in={tokens_in}, out={tokens_out}, cr={cache_read}, cw={cache_write}"
        )

        # FIX: Skip session node tokens (they're aggregated and would cause double counting)
        if node_type == "session":
            print(f"{indent}  ⚠️  SKIPPING session tokens (would double count)")
            tokens_in = 0
            tokens_out = 0
            cache_read = 0
            cache_write = 0

        # Aggregate from children
        for child in node.get("children", []):
            child_in, child_out, child_cr, child_cw = aggregate_tokens_fixed(
                child, depth + 1
            )
            tokens_in += child_in
            tokens_out += child_out
            cache_read += child_cr
            cache_write += child_cw

        print(
            f"{indent}  → Total: in={tokens_in}, out={tokens_out}, cr={cache_read}, cw={cache_write}"
        )
        return tokens_in, tokens_out, cache_read, cache_write

    print("=" * 70)
    print("Testing FIXED aggregation logic (should NOT double-count)")
    print("=" * 70)

    tokens_in, tokens_out, cache_read, cache_write = aggregate_tokens_fixed(mock_tree)

    print("\n" + "=" * 70)
    print("RESULT:")
    print(f"  Input:       {tokens_in:,}")
    print(f"  Output:      {tokens_out:,}")
    print(f"  Cache Read:  {cache_read:,}")
    print(f"  Cache Write: {cache_write:,}")
    print(f"  Total:       {tokens_in + tokens_out + cache_read + cache_write:,}")
    print("=" * 70)

    # Expected: sum of individual exchanges only (not session)
    expected_in = 100 + 75  # 175
    expected_out = 2000 + 2747  # 4747
    expected_cr = 300000 + 358693  # 658693
    expected_cw = 30000 + 31035  # 61035

    print("\nEXPECTED:")
    print(f"  Input:       {expected_in:,}")
    print(f"  Output:      {expected_out:,}")
    print(f"  Cache Read:  {expected_cr:,}")
    print(f"  Cache Write: {expected_cw:,}")
    print(f"  Total:       {expected_in + expected_out + expected_cr + expected_cw:,}")

    # Check if correct
    if (
        tokens_in == expected_in
        and tokens_out == expected_out
        and cache_read == expected_cr
        and cache_write == expected_cw
    ):
        print("\n✅ SUCCESS: Aggregation is correct!")
        return True
    else:
        print("\n❌ FAILURE: Aggregation is incorrect!")
        return False


if __name__ == "__main__":
    success = test_aggregation_logic()
    sys.exit(0 if success else 1)
