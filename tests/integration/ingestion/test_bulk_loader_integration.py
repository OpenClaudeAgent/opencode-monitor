from opencode_monitor.analytics.db import AnalyticsDB
from opencode_monitor.analytics.ingestion.bulk_loader import BulkLoader
from tests.factories import OpenCodeFactory


def test_bulk_loader_ingestion(temp_env):
    """Test full ingestion flow: generate data -> bulk load -> query DB."""
    storage_path, db_path = temp_env

    # Arrange
    factory = OpenCodeFactory(storage_path)

    session = factory.create_session(title="Integration Test Session")
    session_id = session["id"]

    message = factory.create_message(
        session_id=session_id, role="user", content="Test Message"
    )
    message_id = message["id"]

    factory.create_part(
        session_id=session_id,
        message_id=message_id,
        part_type="text",
        content="Hello world",
    )

    factory.create_part(
        session_id=session_id,
        message_id=message_id,
        part_type="tool",
        tool_name="write",
        tool_args={"filePath": "/tmp/test.py", "content": "print('hi')"},
    )

    # Act
    db = AnalyticsDB(db_path)
    db.connect()

    loader = BulkLoader(db, storage_path)
    loader.load_all()

    # Assert
    conn = db.connect()

    row_session = conn.execute(
        "SELECT id, title FROM sessions WHERE id = ?", [session_id]
    ).fetchone()
    assert row_session is not None
    assert row_session[0] == session_id
    assert row_session[1] == "Integration Test Session"

    row_message = conn.execute(
        "SELECT id, role FROM messages WHERE id = ?", [message_id]
    ).fetchone()
    assert row_message is not None
    assert row_message[0] == message_id
    assert row_message[1] == "user"

    count_parts = conn.execute(
        "SELECT COUNT(*) FROM parts WHERE session_id = ?", [session_id]
    ).fetchone()[0]
    assert count_parts == 2

    count_ops = conn.execute(
        "SELECT COUNT(*) FROM file_operations WHERE session_id = ?", [session_id]
    ).fetchone()[0]
    assert count_ops == 1

    op_row = conn.execute(
        "SELECT operation, file_path FROM file_operations WHERE session_id = ?",
        [session_id],
    ).fetchone()
    assert op_row[0] == "write"
    assert op_row[1] == "/tmp/test.py"
