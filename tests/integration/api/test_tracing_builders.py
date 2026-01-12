"""Integration tests for tracing API builders with error data."""

from datetime import datetime

import pytest

from opencode_monitor.analytics.db import AnalyticsDB


class TestBuildToolsBySession:
    def test_build_tools_returns_error_field(self, analytics_db_real: AnalyticsDB):
        from opencode_monitor.api.routes.tracing.builders import build_tools_by_session

        conn = analytics_db_real.connect()
        now = datetime.now()

        conn.execute(
            """
            INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ["sess-001", "proj-001", "/dir", "Test Session", now, now],
        )

        conn.execute(
            """
            INSERT INTO parts (id, session_id, message_id, part_type, tool_name, tool_status, 
                              arguments, created_at, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "prt-001",
                "sess-001",
                "msg-001",
                "tool",
                "bash",
                "error",
                '{"command": "ls"}',
                now,
                "Tool execution aborted",
            ],
        )

        result = build_tools_by_session(conn, {"sess-001"}, include_tools=True)

        assert "sess-001" in result
        tools = result["sess-001"]
        assert len(tools) == 1
        assert tools[0]["tool_name"] == "bash"
        assert tools[0]["status"] == "error"
        assert tools[0]["error"] == "Tool execution aborted"

    def test_build_tools_success_has_null_error(self, analytics_db_real: AnalyticsDB):
        from opencode_monitor.api.routes.tracing.builders import build_tools_by_session

        conn = analytics_db_real.connect()
        now = datetime.now()

        conn.execute(
            """
            INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ["sess-001", "proj-001", "/dir", "Test Session", now, now],
        )

        conn.execute(
            """
            INSERT INTO parts (id, session_id, message_id, part_type, tool_name, tool_status, 
                              arguments, created_at, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "prt-001",
                "sess-001",
                "msg-001",
                "tool",
                "bash",
                "success",
                '{"command": "ls"}',
                now,
                None,
            ],
        )

        result = build_tools_by_session(conn, {"sess-001"}, include_tools=True)

        tools = result["sess-001"]
        assert tools[0]["error"] is None

    def test_build_tools_multiple_errors(self, analytics_db_real: AnalyticsDB):
        from opencode_monitor.api.routes.tracing.builders import build_tools_by_session

        conn = analytics_db_real.connect()
        now = datetime.now()

        conn.execute(
            """
            INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ["sess-001", "proj-001", "/dir", "Test Session", now, now],
        )

        error_parts = [
            ("prt-001", "bash", "Tool execution aborted"),
            ("prt-002", "webfetch", "Error: Request failed with status code: 403"),
            ("prt-003", "read", "File not found: /path/to/file"),
        ]

        for part_id, tool, error in error_parts:
            conn.execute(
                """
                INSERT INTO parts (id, session_id, message_id, part_type, tool_name, tool_status, 
                                  arguments, created_at, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    part_id,
                    "sess-001",
                    "msg-001",
                    "tool",
                    tool,
                    "error",
                    "{}",
                    now,
                    error,
                ],
            )

        result = build_tools_by_session(conn, {"sess-001"}, include_tools=True)

        tools = result["sess-001"]
        assert len(tools) == 3

        errors = {t["tool_name"]: t["error"] for t in tools}
        assert errors["bash"] == "Tool execution aborted"
        assert errors["webfetch"] == "Error: Request failed with status code: 403"
        assert errors["read"] == "File not found: /path/to/file"


class TestBuildToolsByMessage:
    def test_build_tools_by_message_returns_error_field(
        self, analytics_db_real: AnalyticsDB
    ):
        from opencode_monitor.api.routes.tracing.builders import build_tools_by_message

        conn = analytics_db_real.connect()
        now = datetime.now()

        conn.execute(
            """
            INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ["sess-001", "proj-001", "/dir", "Test Session", now, now],
        )

        conn.execute(
            """
            INSERT INTO messages (id, session_id, role, created_at)
            VALUES (?, ?, ?, ?)
            """,
            ["msg-001", "sess-001", "assistant", now],
        )

        conn.execute(
            """
            INSERT INTO parts (id, session_id, message_id, part_type, tool_name, tool_status, 
                              arguments, created_at, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "prt-001",
                "sess-001",
                "msg-001",
                "tool",
                "edit",
                "error",
                '{"filePath": "/test.py"}',
                now,
                "Error: oldString not found in content",
            ],
        )

        result = build_tools_by_message(conn, {"sess-001"}, include_tools=True)

        assert "msg-001" in result
        tools = result["msg-001"]
        assert len(tools) == 1
        assert tools[0]["error"] == "Error: oldString not found in content"


class TestErrorMessagePreservation:
    def test_long_error_message_preserved(self, analytics_db_real: AnalyticsDB):
        from opencode_monitor.api.routes.tracing.builders import build_tools_by_session

        conn = analytics_db_real.connect()
        now = datetime.now()

        conn.execute(
            """
            INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ["sess-001", "proj-001", "/dir", "Test Session", now, now],
        )

        long_error = 'Error: The user has specified a rule which prevents you from using this specific tool call. Here are some of the relevant rules [{"permission":"*","pattern":"*","action":"allow"},{"permission":"todowrite","pattern":"*","action":"deny"}]'

        conn.execute(
            """
            INSERT INTO parts (id, session_id, message_id, part_type, tool_name, tool_status, 
                              arguments, created_at, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "prt-001",
                "sess-001",
                "msg-001",
                "tool",
                "todowrite",
                "error",
                "{}",
                now,
                long_error,
            ],
        )

        result = build_tools_by_session(conn, {"sess-001"}, include_tools=True)

        tools = result["sess-001"]
        assert tools[0]["error"] == long_error
        assert len(tools[0]["error"]) == len(long_error)

    @pytest.mark.parametrize(
        "error_message",
        [
            "Tool execution aborted",
            "Error: Request failed with status code: 403",
            "Error: unknown certificate verification error",
            "Error: The user rejected permission to use this specific tool call.",
            "File not found: /path/to/missing/file.py",
            "",
            None,
        ],
    )
    def test_various_error_messages(
        self, analytics_db_real: AnalyticsDB, error_message
    ):
        from opencode_monitor.api.routes.tracing.builders import build_tools_by_session

        conn = analytics_db_real.connect()
        now = datetime.now()

        conn.execute(
            """
            INSERT INTO sessions (id, project_id, directory, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ["sess-001", "proj-001", "/dir", "Test Session", now, now],
        )

        conn.execute(
            """
            INSERT INTO parts (id, session_id, message_id, part_type, tool_name, tool_status, 
                              arguments, created_at, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "prt-001",
                "sess-001",
                "msg-001",
                "tool",
                "bash",
                "error",
                "{}",
                now,
                error_message,
            ],
        )

        result = build_tools_by_session(conn, {"sess-001"}, include_tools=True)

        tools = result["sess-001"]
        assert tools[0]["error"] == error_message
