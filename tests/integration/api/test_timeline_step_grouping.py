import pytest
import json
from datetime import datetime
from opencode_monitor.analytics.ingestion.processor import IngestionProcessor
from tests.factories import OpenCodeFactory


def test_timeline_groups_tools_by_step(flask_app_real, analytics_db_real, temp_storage):
    """Test that tools are grouped by step in the timeline summary."""

    factory = OpenCodeFactory(temp_storage)
    session = factory.create_session(title="Step Grouping Test")
    session_id = session["id"]

    message = factory.create_message(session_id=session_id, content="Run two commands")
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

    part_tool1 = factory.create_part(
        session_id=session_id,
        message_id=message_assistant["id"],
        part_type="tool",
        tool_name="bash",
        tool_args={"command": "echo 1"},
        created_at=datetime.now().timestamp() * 1000,
    )
    processor.process_part(temp_storage / "part" / f"{part_tool1['id']}.json")

    part_step1 = factory.create_part(
        session_id=session_id,
        message_id=message_assistant["id"],
        part_type="step-finish",
        content="step 1 complete",
        created_at=(datetime.now().timestamp() + 1) * 1000,
    )
    processor.process_part(temp_storage / "part" / f"{part_step1['id']}.json")

    part_tool2 = factory.create_part(
        session_id=session_id,
        message_id=message_assistant["id"],
        part_type="tool",
        tool_name="read",
        tool_args={"path": "file.txt"},
        created_at=(datetime.now().timestamp() + 2) * 1000,
    )
    processor.process_part(temp_storage / "part" / f"{part_tool2['id']}.json")

    part_step2 = factory.create_part(
        session_id=session_id,
        message_id=message_assistant["id"],
        part_type="step-finish",
        content="step 2 complete",
        created_at=(datetime.now().timestamp() + 3) * 1000,
    )
    processor.process_part(temp_storage / "part" / f"{part_step2['id']}.json")

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

    step_events = [e for e in timeline if e["type"] == "step_finish"]
    assert len(step_events) == 2

    print(f"\nStep 1 Summary: {step_events[0].get('summary')}")
    print(f"Step 2 Summary: {step_events[1].get('summary')}")

    assert step_events[0]["summary"] == "Executed bash"
    assert step_events[1]["summary"] == "Executed read"


def test_timeline_groups_multiple_tools_in_one_step(
    flask_app_real, analytics_db_real, temp_storage
):
    """Test that multiple tools in one step are grouped correctly."""

    factory = OpenCodeFactory(temp_storage)
    session = factory.create_session(title="Multi Tool Step Test")
    session_id = session["id"]

    message = factory.create_message(
        session_id=session_id, content="Run multiple commands"
    )
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

    part_tool1 = factory.create_part(
        session_id=session_id,
        message_id=message_assistant["id"],
        part_type="tool",
        tool_name="ls",
        tool_args={"path": "."},
        created_at=datetime.now().timestamp() * 1000,
    )
    processor.process_part(temp_storage / "part" / f"{part_tool1['id']}.json")

    part_tool2 = factory.create_part(
        session_id=session_id,
        message_id=message_assistant["id"],
        part_type="tool",
        tool_name="grep",
        tool_args={"pattern": "test"},
        created_at=(datetime.now().timestamp() + 1) * 1000,
    )
    processor.process_part(temp_storage / "part" / f"{part_tool2['id']}.json")

    part_step = factory.create_part(
        session_id=session_id,
        message_id=message_assistant["id"],
        part_type="step-finish",
        content="step complete",
        created_at=(datetime.now().timestamp() + 2) * 1000,
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

    step_events = [e for e in timeline if e["type"] == "step_finish"]
    assert len(step_events) == 1

    print(f"\nStep Summary: {step_events[0].get('summary')}")
    assert "Executed 2 tools" in step_events[0]["summary"]
    assert "ls" in step_events[0]["summary"]
    assert "grep" in step_events[0]["summary"]
