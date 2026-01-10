"""
Migration 001: Add error_data JSON column to parts table.

This migration:
1. Backs up existing error_message data
2. Adds error_data column as JSON type
3. Migrates error_message to structured JSON format
4. Provides rollback procedure

Usage:
    python -m opencode_monitor.analytics.migrations.001_add_error_data_json
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import duckdb


def get_db_path() -> Path:
    """Get the path to the analytics database."""
    config_dir = Path.home() / ".config" / "opencode-monitor"
    return config_dir / "analytics.duckdb"


def backup_error_data(conn: duckdb.DuckDBPyConnection) -> int:
    """Backup existing error_message data before migration.

    Returns:
        Number of records with error_message
    """
    print("[Backup] Checking for existing error_message data...")

    # Create backup table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS parts_error_backup AS
        SELECT id, error_message, created_at
        FROM parts
        WHERE error_message IS NOT NULL
    """)

    count = conn.execute(
        "SELECT COUNT(*) FROM parts WHERE error_message IS NOT NULL"
    ).fetchone()[0]

    print(f"[Backup] Backed up {count} records with error_message")
    return count


def add_error_data_column(conn: duckdb.DuckDBPyConnection) -> None:
    """Add error_data column as JSON type."""
    print("[Migration] Adding error_data column as JSON type...")

    # Check if column already exists
    try:
        result = conn.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'parts' AND column_name = 'error_data'
        """).fetchone()

        if result:
            print("[Migration] error_data column already exists, skipping...")
            return
    except Exception as e:
        print(f"[Warning] Could not check column existence: {e}")

    # Add the column
    try:
        conn.execute("ALTER TABLE parts ADD COLUMN error_data JSON")
        print("[Migration] Successfully added error_data column")
    except Exception as e:
        print(f"[Error] Failed to add error_data column: {e}")
        raise


def migrate_error_messages(conn: duckdb.DuckDBPyConnection) -> int:
    """Migrate existing error_message to structured JSON format.

    Returns:
        Number of records migrated
    """
    print("[Migration] Migrating error_message to error_data JSON...")

    # Get all parts with error_message
    parts_with_errors = conn.execute("""
        SELECT id, error_message, tool_name, tool_status, created_at
        FROM parts
        WHERE error_message IS NOT NULL
    """).fetchall()

    migrated = 0
    for part_id, error_msg, tool_name, tool_status, created_at in parts_with_errors:
        # Structure error data as JSON
        error_data = {
            "error_type": "unknown",  # Cannot determine from error_message alone
            "error_message": error_msg,
            "tool_name": tool_name,
            "tool_status": tool_status,
            "timestamp": created_at.isoformat() if created_at else None,
        }

        # Update the record
        try:
            conn.execute(
                "UPDATE parts SET error_data = ? WHERE id = ?",
                [json.dumps(error_data), part_id],
            )
            migrated += 1
        except Exception as e:
            print(f"[Warning] Failed to migrate part {part_id}: {e}")

    print(f"[Migration] Migrated {migrated} records")
    return migrated


def verify_migration(conn: duckdb.DuckDBPyConnection) -> bool:
    """Verify migration completed successfully.

    Returns:
        True if verification passed
    """
    print("[Verify] Checking migration results...")

    # Check that error_data column exists
    try:
        result = conn.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns 
            WHERE table_name = 'parts' AND column_name = 'error_data'
        """).fetchone()

        if not result:
            print("[Verify] FAILED - error_data column not found")
            return False

        print(f"[Verify] error_data column exists with type: {result[1]}")
    except Exception as e:
        print(f"[Verify] FAILED - Could not verify column: {e}")
        return False

    # Check that data was migrated
    try:
        error_msg_count = conn.execute(
            "SELECT COUNT(*) FROM parts WHERE error_message IS NOT NULL"
        ).fetchone()[0]

        error_data_count = conn.execute(
            "SELECT COUNT(*) FROM parts WHERE error_data IS NOT NULL"
        ).fetchone()[0]

        print(f"[Verify] Records with error_message: {error_msg_count}")
        print(f"[Verify] Records with error_data: {error_data_count}")

        if error_msg_count > 0 and error_data_count == 0:
            print("[Verify] WARNING - error_message exists but error_data is empty")
            return False

    except Exception as e:
        print(f"[Verify] WARNING - Could not verify data: {e}")

    # Test JSON query functionality
    try:
        test_result = conn.execute("""
            SELECT error_data->>'error_type' as error_type
            FROM parts
            WHERE error_data IS NOT NULL
            LIMIT 1
        """).fetchone()

        if test_result:
            print(f"[Verify] JSON query test passed: {test_result}")
        else:
            print("[Verify] No error_data records to test JSON queries")
    except Exception as e:
        print(f"[Verify] FAILED - JSON query test failed: {e}")
        return False

    print("[Verify] ✓ Migration verification passed")
    return True


def rollback_migration(conn: duckdb.DuckDBPyConnection) -> None:
    """Rollback the migration (remove error_data column).

    WARNING: This will delete all error_data!
    """
    print("[Rollback] Rolling back migration...")

    try:
        # Drop the error_data column
        conn.execute("ALTER TABLE parts DROP COLUMN error_data")
        print("[Rollback] Removed error_data column")

        # Drop backup table
        conn.execute("DROP TABLE IF EXISTS parts_error_backup")
        print("[Rollback] Removed backup table")

        print("[Rollback] ✓ Rollback completed")
    except Exception as e:
        print(f"[Rollback] FAILED: {e}")
        raise


def run_migration(rollback: bool = False) -> None:
    """Run the migration or rollback.

    Args:
        rollback: If True, rollback the migration instead
    """
    db_path = get_db_path()

    if not db_path.exists():
        print(f"Database not found at {db_path}")
        print("Run the indexer first to create the database")
        return

    print(f"Connecting to database: {db_path}")
    conn = duckdb.connect(str(db_path))

    try:
        if rollback:
            rollback_migration(conn)
        else:
            # Run migration
            print("\n" + "=" * 60)
            print("Migration 001: Add error_data JSON column")
            print("=" * 60 + "\n")

            backup_count = backup_error_data(conn)
            add_error_data_column(conn)
            migrated_count = migrate_error_messages(conn)

            print("\n" + "-" * 60)
            if verify_migration(conn):
                print("\n✓ Migration completed successfully")
                print(f"  - Backed up: {backup_count} records")
                print(f"  - Migrated: {migrated_count} records")
            else:
                print("\n✗ Migration verification failed")
                print("  Consider running rollback")
    finally:
        conn.close()


if __name__ == "__main__":
    import sys

    rollback = "--rollback" in sys.argv
    run_migration(rollback=rollback)
