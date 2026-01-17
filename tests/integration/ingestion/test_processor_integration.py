from opencode_monitor.analytics.db import AnalyticsDB
from opencode_monitor.analytics.ingestion.processor import IngestionProcessor
from tests.factories import OpenCodeFactory


def test_processor_ingestion(temp_env):
    storage_path, db_path = temp_env

    factory = OpenCodeFactory(storage_path)

    session = factory.create_session(title="Processor Test Session")
    session_id = session["id"]

    message = factory.create_message(session_id=session_id, content="Processor Message")
    message_id = message["id"]

    part = factory.create_part(
        session_id=session_id, message_id=message_id, content="Processor Part"
    )
    part_path = storage_path / "part" / f"{part['id']}.json"

    db = AnalyticsDB(db_path)
    db.connect()

    processor = IngestionProcessor(db)

    processor.process_session(storage_path / "session" / f"{session_id}.json")
    processor.process_message(storage_path / "message" / f"{message_id}.json")
    processor.process_part(part_path)

    conn = db.connect()

    row_session = conn.execute(
        "SELECT id, title FROM sessions WHERE id = ?", [session_id]
    ).fetchone()
    assert row_session is not None
    assert row_session[1] == "Processor Test Session"

    row_message = conn.execute(
        "SELECT id FROM messages WHERE id = ?", [message_id]
    ).fetchone()
    assert row_message is not None

    count_parts = conn.execute(
        "SELECT COUNT(*) FROM parts WHERE session_id = ?", [session_id]
    ).fetchone()[0]
    assert count_parts == 1
