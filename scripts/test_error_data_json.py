"""
Test script for DQ-005: error_data JSON migration.

Tests:
1. Schema migration (column exists and is JSON type)
2. JSON data insertion via parser
3. JSON query functionality
4. Validation of structured error data
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from opencode_monitor.analytics.db import AnalyticsDB, get_db_path
from opencode_monitor.analytics.indexer.parsers import FileParser


def test_schema_migration():
    """Test that error_data column exists and is JSON type."""
    print("\n" + "=" * 60)
    print("TEST 1: Schema Migration")
    print("=" * 60)

    db_path = get_db_path()
    if not db_path.exists():
        print("❌ Database not found. Run indexer first.")
        return False

    with AnalyticsDB(read_only=True) as db:
        conn = db.connect()

        # Check column exists
        result = conn.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns 
            WHERE table_name = 'parts' AND column_name = 'error_data'
        """).fetchone()

        if not result:
            print("❌ error_data column does not exist")
            return False

        col_name, col_type = result
        print(f"✓ Column exists: {col_name}")
        print(f"✓ Column type: {col_type}")

        if "JSON" not in col_type.upper():
            print(f"❌ Expected JSON type, got {col_type}")
            return False

        print("✓ Schema migration successful")
        return True


def test_json_insertion():
    """Test inserting structured error data via parser."""
    print("\n" + "=" * 60)
    print("TEST 2: JSON Data Insertion")
    print("=" * 60)

    # Create mock error part data
    mock_part = {
        "id": "test_error_part_001",
        "sessionID": "test_session",
        "messageID": "test_message",
        "type": "tool",
        "tool": "bash",
        "callID": "call_123",
        "state": {
            "status": "error",
            "error": "Command timed out after 30 seconds",
            "time": {
                "start": int(datetime.now().timestamp() * 1000),
                "end": int((datetime.now().timestamp() + 30) * 1000),
            },
        },
        "time": {},
    }

    # Parse the part
    parsed = FileParser.parse_part(mock_part)

    if not parsed:
        print("❌ Failed to parse mock part")
        return False

    print(f"✓ Parsed part ID: {parsed.id}")
    print(f"✓ Error message: {parsed.error_message}")

    if not parsed.error_data:
        print("❌ error_data is None - parser did not structure error")
        return False

    # Validate JSON structure
    try:
        error_data = json.loads(parsed.error_data)
        print(f"✓ error_data is valid JSON")

        # Check required fields
        required_fields = ["error_type", "error_message", "timestamp"]
        for field in required_fields:
            if field not in error_data:
                print(f"❌ Missing required field: {field}")
                return False
            print(f"  - {field}: {error_data[field]}")

        # Check error_type detection
        if error_data["error_type"] != "timeout":
            print(f"❌ Expected error_type='timeout', got '{error_data['error_type']}'")
            return False

        print("✓ Structured error data is valid")
        return True

    except json.JSONDecodeError as e:
        print(f"❌ error_data is not valid JSON: {e}")
        return False


def test_json_queries():
    """Test JSON query functionality."""
    print("\n" + "=" * 60)
    print("TEST 3: JSON Query Functionality")
    print("=" * 60)

    db_path = get_db_path()
    if not db_path.exists():
        print("❌ Database not found")
        return False

    with AnalyticsDB(read_only=True) as db:
        conn = db.connect()

        # Count parts with error_data
        count = conn.execute(
            "SELECT COUNT(*) FROM parts WHERE error_data IS NOT NULL"
        ).fetchone()[0]

        print(f"Found {count} parts with error_data")

        if count == 0:
            print("⚠️  No error_data records to test (run indexer with errors)")
            return True

        # Test JSON extraction
        try:
            results = conn.execute("""
                SELECT 
                    id,
                    error_data->>'error_type' as error_type,
                    error_data->>'error_message' as error_message,
                    error_data->>'error_code' as error_code
                FROM parts
                WHERE error_data IS NOT NULL
                LIMIT 5
            """).fetchall()

            print(f"✓ JSON query executed successfully")
            print(f"✓ Retrieved {len(results)} records:")

            for row in results:
                print(f"  - ID: {row[0]}")
                print(f"    Type: {row[1]}")
                print(
                    f"    Message: {row[2][:50]}..."
                    if row[2]
                    else f"    Message: {row[2]}"
                )
                print(f"    Code: {row[3]}")

            return True

        except Exception as e:
            print(f"❌ JSON query failed: {e}")
            return False


def test_error_type_detection():
    """Test error type detection logic."""
    print("\n" + "=" * 60)
    print("TEST 4: Error Type Detection")
    print("=" * 60)

    test_cases = [
        ("Connection timeout", "timeout", 408),
        ("Authentication failed", "auth", 403),
        ("Permission denied", "auth", 403),
        ("Network error occurred", "network", 500),
        ("Syntax error in JSON", "syntax", 400),
        ("File not found", "not_found", 404),
        ("Unknown error", "unknown", None),
    ]

    passed = 0
    failed = 0

    for error_msg, expected_type, expected_code in test_cases:
        mock_part = {
            "id": f"test_{passed + failed}",
            "type": "tool",
            "tool": "test",
            "state": {
                "status": "error",
                "error": error_msg,
                "time": {"start": 0, "end": 1000},
            },
            "time": {},
        }

        parsed = FileParser.parse_part(mock_part)
        if parsed and parsed.error_data:
            error_data = json.loads(parsed.error_data)
            actual_type = error_data.get("error_type")
            actual_code = error_data.get("error_code")

            if actual_type == expected_type and actual_code == expected_code:
                print(f"✓ '{error_msg}' → {actual_type} (code: {actual_code})")
                passed += 1
            else:
                print(
                    f"❌ '{error_msg}' → Expected {expected_type}/{expected_code}, got {actual_type}/{actual_code}"
                )
                failed += 1
        else:
            print(f"❌ Failed to parse: {error_msg}")
            failed += 1

    print(f"\nPassed: {passed}/{len(test_cases)}")
    return failed == 0


def run_all_tests():
    """Run all tests and report results."""
    print("\n" + "=" * 60)
    print("DQ-005: error_data JSON Migration Tests")
    print("=" * 60)

    tests = [
        ("Schema Migration", test_schema_migration),
        ("JSON Insertion", test_json_insertion),
        ("JSON Queries", test_json_queries),
        ("Error Type Detection", test_error_type_detection),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ {test_name} crashed: {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:10} {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n❌ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
