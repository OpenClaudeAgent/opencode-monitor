from pathlib import Path

import pytest
from opencode_monitor.analytics.db import AnalyticsDB
from opencode_monitor.analytics.indexer.handlers import (
    SessionHandler,
    MessageHandler,
    PartHandler,
)
from opencode_monitor.analytics.indexer.parsers import FileParser
from opencode_monitor.analytics.indexer.trace_builder import TraceBuilder
from tests.factories import OpenCodeFactory
import json


def test_handlers_ingestion(temp_env):
    """Test ingestion via Handlers (File Watcher flow)."""
    storage_path, db_path = temp_env

    # Arrange
    factory = OpenCodeFactory(storage_path)

    session = factory.create_session(title="Handler Test Session")
    session_id = session["id"]

    message = factory.create_message(session_id=session_id, content="Handler Message")
    message_id = message["id"]

    part = factory.create_part(
        session_id=session_id, message_id=message_id, content="Handler Part"
    )
    part_path = storage_path / "part" / f"{part['id']}.json"

    # Act
    db = AnalyticsDB(db_path)
    db.connect()
    conn = db.connect()

    parser = FileParser()
    trace_builder = TraceBuilder(db)

    session_handler = SessionHandler()
    with open(storage_path / "session" / f"{session_id}.json") as f:
        raw_session = json.load(f)
    session_handler.process(
        storage_path / "session" / f"{session_id}.json",
        raw_session,
        conn,
        parser,
        trace_builder,
    )

    message_handler = MessageHandler()
    with open(storage_path / "message" / f"{message_id}.json") as f:
        raw_message = json.load(f)
    message_handler.process(
        storage_path / "message" / f"{message_id}.json",
        raw_message,
        conn,
        parser,
        trace_builder,
    )

    part_handler = PartHandler()
    with open(part_path) as f:
        raw_part = json.load(f)
    part_handler.process(part_path, raw_part, conn, parser, trace_builder)

    # Assert
    row_session = conn.execute(
        "SELECT id, title FROM sessions WHERE id = ?", [session_id]
    ).fetchone()
    assert row_session is not None
    assert row_session[1] == "Handler Test Session"

    row_message = conn.execute(
        "SELECT id FROM messages WHERE id = ?", [message_id]
    ).fetchone()
    assert row_message is not None

    count_parts = conn.execute(
        "SELECT COUNT(*) FROM parts WHERE session_id = ?", [session_id]
    ).fetchone()[0]
    assert count_parts == 1
