import pytest
import json
from datetime import datetime
from opencode_monitor.analytics.ingestion.processor import IngestionProcessor
from tests.factories import OpenCodeFactory


def test_timeline_api_returns_enriched_steps(
    flask_app_real, analytics_db_real, temp_storage, caplog
):
    """Test that the timeline API returns enriched step summaries."""

    factory = OpenCodeFactory(temp_storage)
    session = factory.create_session(title="API Enrichment Test")
    session_id = session["id"]

    message = factory.create_message(session_id=session_id, content="Run command")
    message_id = message["id"]
    processor = IngestionProcessor(analytics_db_real)
    processor.process_session(temp_storage / "session" / f"{session_id}.json")
    processor.process_message(temp_storage / "message" / f"{message_id}.json")

    message_assistant = factory.create_message(
        session_id=session_id, role="assistant", content="Done", parent_id=message_id
    )
    processor.process_message(
        temp_storage / "message" / f"{message_assistant['id']}.json"
    )

    part_tool = factory.create_part(
        session_id=session_id,
        message_id=message_assistant["id"],
        part_type="tool",
        tool_name="bash",
        tool_args={"command": "echo hello"},
        content="hello",
    )
    processor.process_part(temp_storage / "part" / f"{part_tool['id']}.json")

    part_step = factory.create_part(
        session_id=session_id,
        message_id=message_assistant["id"],
        part_type="step-finish",
        content="step complete",
    )
    processor.process_part(temp_storage / "part" / f"{part_step['id']}.json")

    conn = analytics_db_real.connect()

    conn.execute(
        """
        INSERT OR IGNORE INTO agent_traces (trace_id, session_id, title, created_at, subagent_type, prompt_input, started_at)
        SELECT id, id, title, created_at, 'root', 'Test Prompt', created_at FROM sessions WHERE id = ?
    """,
        [session_id],
    )

    from opencode_monitor.analytics.materialization import MaterializedTableManager

    manager = MaterializedTableManager(analytics_db_real)
    manager.refresh_exchanges(incremental=False)
    manager.refresh_exchange_traces()

    client = flask_app_real.test_client()
    response = client.get(f"/api/session/{session_id}/timeline/full?stream=false")

    assert response.status_code == 200
    data = response.json["data"]
    timeline = data["timeline"]

    step_event = next((e for e in timeline if e["type"] == "step_finish"), None)
    assert step_event is not None, "Step finish event not found in timeline"

    assert "summary" in step_event
    assert step_event["summary"] == "Executed bash"
