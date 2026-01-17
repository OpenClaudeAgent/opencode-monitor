from opencode_monitor.analytics.db import AnalyticsDB
from opencode_monitor.analytics.ingestion.bulk_loader import BulkLoader
from tests.factories import OpenCodeFactory


def test_complex_agent_workflow_ingestion(temp_env):
    storage_path, db_path = temp_env
    factory = OpenCodeFactory(storage_path)

    session = factory.create_session(
        title="Complex Refactoring Mission", session_id="ses_complex_1"
    )

    message_user = factory.create_message(
        session_id="ses_complex_1",
        role="user",
        content="Refactor the database layer and add git support",
        message_id="msg_user_1",
    )

    factory.create_part(
        session_id="ses_complex_1",
        message_id="msg_user_1",
        part_type="reasoning",
        content="I need to check the current database schema first.",
    )

    factory.create_part(
        session_id="ses_complex_1",
        message_id="msg_user_1",
        part_type="tool",
        tool_name="bash",
        tool_args={"command": "ls -R src/db"},
        content="src/db/schema.sql",
    )

    factory.create_part(
        session_id="ses_complex_1",
        message_id="msg_user_1",
        part_type="tool",
        tool_name="edit",
        tool_args={
            "filePath": "/abs/src/db/schema.sql",
            "oldString": "CREATE TABLE users",
            "newString": "CREATE TABLE users_v2",
        },
    )

    factory.create_part(
        session_id="ses_complex_1",
        message_id="msg_user_1",
        part_type="patch",
        git_hash="a1b2c3d",
        git_files=["src/db/schema.sql"],
    )

    # 2. User Request
    message_user = factory.create_message(
        session_id="ses_complex_1",
        role="user",
        content="Refactor the database layer and add git support",
        message_id="msg_user_1",
    )

    # 3. Agent Thought (Reasoning)
    factory.create_part(
        session_id="ses_complex_1",
        message_id="msg_user_1",
        part_type="reasoning",
        content="I need to check the current database schema first.",
    )

    # 4. Agent Action: List files (Tool)
    factory.create_part(
        session_id="ses_complex_1",
        message_id="msg_user_1",
        part_type="tool",
        tool_name="bash",
        tool_args={"command": "ls -R src/db"},
        content="src/db/schema.sql",
    )

    # 5. Agent Action: Edit File (File Operation)
    factory.create_part(
        session_id="ses_complex_1",
        message_id="msg_user_1",
        part_type="tool",
        tool_name="edit",
        tool_args={
            "filePath": "/abs/src/db/schema.sql",
            "oldString": "CREATE TABLE users",
            "newString": "CREATE TABLE users_v2",
        },
    )

    # 6. Agent Action: Git Commit (Patch)
    factory.create_part(
        session_id="ses_complex_1",
        message_id="msg_user_1",
        part_type="patch",
        git_hash="a1b2c3d",
        git_files=["src/db/schema.sql"],
    )

    factory.create_part(
        session_id="ses_complex_1",
        message_id="msg_user_1",
        part_type="tool",
        tool_name="bash",
        tool_args={"command": "invalid_command"},
        tool_status="error",
        error_message="command not found: invalid_command",
    )

    db = AnalyticsDB(db_path)
    db.connect()

    loader = BulkLoader(db, storage_path)
    loader.load_all()

    conn = db.connect()

    res_session = conn.execute(
        "SELECT title, files_changed FROM sessions WHERE id = 'ses_complex_1'"
    ).fetchone()
    assert res_session[0] == "Complex Refactoring Mission"
    assert res_session[1] == 2

    res_msg = conn.execute(
        "SELECT role FROM messages WHERE id = 'msg_user_1'"
    ).fetchone()
    assert res_msg[0] == "user"

    res_reasoning = conn.execute(
        "SELECT content FROM parts WHERE session_id = 'ses_complex_1' AND part_type = 'reasoning'"
    ).fetchone()
    assert "check the current database schema" in res_reasoning[0]

    res_file_op = conn.execute(
        "SELECT operation, file_path FROM file_operations WHERE session_id = 'ses_complex_1'"
    ).fetchone()
    assert res_file_op[0] == "edit"
    assert res_file_op[1] == "/abs/src/db/schema.sql"

    res_patch = conn.execute(
        "SELECT git_hash, files FROM patches WHERE session_id = 'ses_complex_1'"
    ).fetchone()
    assert res_patch[0] == "a1b2c3d"
    assert "src/db/schema.sql" in res_patch[1]

    res_error = conn.execute(
        "SELECT tool_status, error_message FROM parts WHERE tool_name = 'bash' AND tool_status = 'error'"
    ).fetchone()
    assert res_error[0] == "error"
    assert res_error[1] == "command not found: invalid_command"
