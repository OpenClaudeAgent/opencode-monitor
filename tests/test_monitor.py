"""
Tests for opencode_monitor.core.monitor module.

Covers:
- find_opencode_ports() - subprocess mocking for netstat
- get_tty_for_port() - subprocess mocking for lsof/ps
- extract_tools_from_messages() - message parsing
- count_todos() - todo counting logic
- fetch_instance() - async instance fetching
- fetch_all_instances() - async state building
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from opencode_monitor.core.monitor import (
    find_opencode_ports,
    get_tty_for_port,
    extract_tools_from_messages,
    count_todos,
    fetch_instance,
    fetch_all_instances,
)
from opencode_monitor.core.models import (
    Instance,
    Agent,
    Tool,
    SessionStatus,
    State,
    Todos,
    AgentTodos,
)


# ===========================================================================
# Tests for find_opencode_ports()
# ===========================================================================


class TestFindOpencodePorts:
    """Tests for find_opencode_ports() function"""

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_netstat_fails(self):
        """When subprocess raises exception, return empty list"""
        with patch("opencode_monitor.core.monitor.ports.subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Command failed")
            result = await find_opencode_ports()
            assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_listening_ports(self):
        """When netstat has no LISTEN lines, return empty list"""
        mock_result = MagicMock()
        mock_result.stdout = "Active connections\nProto  Local Address\n"

        with patch("opencode_monitor.core.monitor.ports.subprocess.run") as mock_run:
            mock_run.return_value = mock_result
            result = await find_opencode_ports()
            assert result == []

    @pytest.mark.asyncio
    async def test_parses_netstat_output_and_filters_ports(self):
        """Parse netstat output and verify ports with check_opencode_port"""
        netstat_output = """Active Internet connections
Proto Recv-Q Send-Q  Local Address          Foreign Address        (state)
tcp4       0      0  127.0.0.1.8080         *.*                    LISTEN
tcp4       0      0  127.0.0.1.3000         *.*                    LISTEN
tcp4       0      0  192.168.1.1.80         *.*                    LISTEN
tcp4       0      0  127.0.0.1.500          *.*                    LISTEN
"""
        mock_result = MagicMock()
        mock_result.stdout = netstat_output

        async def mock_check(port):
            # Only port 8080 is an opencode instance
            return port == 8080

        with patch("opencode_monitor.core.monitor.ports.subprocess.run") as mock_run:
            with patch(
                "opencode_monitor.core.monitor.ports.check_opencode_port",
                side_effect=mock_check,
            ):
                mock_run.return_value = mock_result
                result = await find_opencode_ports()
                assert result == [8080]

    @pytest.mark.asyncio
    async def test_handles_invalid_port_numbers(self):
        """Ignore lines with invalid port numbers"""
        netstat_output = """Active Internet connections
tcp4       0      0  127.0.0.1.abc          *.*                    LISTEN
tcp4       0      0  127.0.0.1.8080         *.*                    LISTEN
"""
        mock_result = MagicMock()
        mock_result.stdout = netstat_output

        async def mock_check(port):
            return True

        with patch("opencode_monitor.core.monitor.ports.subprocess.run") as mock_run:
            with patch(
                "opencode_monitor.core.monitor.ports.check_opencode_port",
                side_effect=mock_check,
            ):
                mock_run.return_value = mock_result
                result = await find_opencode_ports()
                assert 8080 in result

    @pytest.mark.asyncio
    async def test_filters_ports_outside_valid_range(self):
        """Only include ports between 1024 and 65535"""
        netstat_output = """Active Internet connections
tcp4       0      0  127.0.0.1.80           *.*                    LISTEN
tcp4       0      0  127.0.0.1.1024         *.*                    LISTEN
tcp4       0      0  127.0.0.1.65536        *.*                    LISTEN
tcp4       0      0  127.0.0.1.8080         *.*                    LISTEN
"""
        mock_result = MagicMock()
        mock_result.stdout = netstat_output

        async def mock_check(port):
            return True

        with patch("opencode_monitor.core.monitor.ports.subprocess.run") as mock_run:
            with patch(
                "opencode_monitor.core.monitor.ports.check_opencode_port",
                side_effect=mock_check,
            ):
                mock_run.return_value = mock_result
                result = await find_opencode_ports()
                # Only 8080 is in valid range (1024 < port < 65535)
                assert 8080 in result
                assert 80 not in result
                assert 1024 not in result

    @pytest.mark.asyncio
    async def test_multiple_opencode_instances(self):
        """Return multiple ports when several opencode instances exist"""
        netstat_output = """Active Internet connections
tcp4       0      0  127.0.0.1.8080         *.*                    LISTEN
tcp4       0      0  127.0.0.1.8081         *.*                    LISTEN
tcp4       0      0  127.0.0.1.9000         *.*                    LISTEN
"""
        mock_result = MagicMock()
        mock_result.stdout = netstat_output

        async def mock_check(port):
            return port in [8080, 9000]

        with patch("opencode_monitor.core.monitor.ports.subprocess.run") as mock_run:
            with patch(
                "opencode_monitor.core.monitor.ports.check_opencode_port",
                side_effect=mock_check,
            ):
                mock_run.return_value = mock_result
                result = await find_opencode_ports()
                assert sorted(result) == [8080, 9000]


# ===========================================================================
# Tests for get_tty_for_port()
# ===========================================================================


class TestGetTtyForPort:
    """Tests for get_tty_for_port() function"""

    def test_returns_empty_string_when_lsof_fails(self):
        """When lsof raises exception, return empty string"""
        with patch("opencode_monitor.core.monitor.ports.subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Command failed")
            result = get_tty_for_port(8080)
            assert result == ""

    def test_returns_empty_string_when_no_opencode_process(self):
        """When no opencode process found, return empty string"""
        mock_result = MagicMock()
        mock_result.stdout = "COMMAND     PID   USER\nnode      1234   user"

        with patch("opencode_monitor.core.monitor.ports.subprocess.run") as mock_run:
            mock_run.return_value = mock_result
            result = get_tty_for_port(8080)
            assert result == ""

    def test_returns_tty_when_found(self):
        """Return TTY when opencode process found with valid TTY"""
        lsof_output = """COMMAND     PID   USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME
opencode  12345   user    5u  IPv4 0xabc123      0t0  TCP 127.0.0.1:8080 (LISTEN)
"""
        ps_output = "ttys001"

        mock_lsof = MagicMock()
        mock_lsof.stdout = lsof_output

        mock_ps = MagicMock()
        mock_ps.stdout = ps_output

        with patch("opencode_monitor.core.monitor.ports.subprocess.run") as mock_run:
            mock_run.side_effect = [mock_lsof, mock_ps]
            result = get_tty_for_port(8080)
            assert result == "ttys001"

    def test_returns_empty_string_when_tty_is_unknown(self):
        """Return empty string when TTY is ??"""
        lsof_output = """COMMAND     PID   USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME
opencode  12345   user    5u  IPv4 0xabc123      0t0  TCP 127.0.0.1:8080 (LISTEN)
"""
        ps_output = "??"

        mock_lsof = MagicMock()
        mock_lsof.stdout = lsof_output

        mock_ps = MagicMock()
        mock_ps.stdout = ps_output

        with patch("opencode_monitor.core.monitor.ports.subprocess.run") as mock_run:
            mock_run.side_effect = [mock_lsof, mock_ps]
            result = get_tty_for_port(8080)
            assert result == ""

    def test_returns_empty_string_when_tty_is_empty(self):
        """Return empty string when TTY is empty"""
        lsof_output = """COMMAND     PID   USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME
opencode  12345   user    5u  IPv4 0xabc123      0t0  TCP 127.0.0.1:8080 (LISTEN)
"""
        mock_lsof = MagicMock()
        mock_lsof.stdout = lsof_output

        mock_ps = MagicMock()
        mock_ps.stdout = ""

        with patch("opencode_monitor.core.monitor.ports.subprocess.run") as mock_run:
            mock_run.side_effect = [mock_lsof, mock_ps]
            result = get_tty_for_port(8080)
            assert result == ""

    def test_handles_line_without_listen(self):
        """Ignore lines without LISTEN"""
        lsof_output = """COMMAND     PID   USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME
opencode  12345   user    5u  IPv4 0xabc123      0t0  TCP 127.0.0.1:8080 (ESTABLISHED)
"""
        mock_lsof = MagicMock()
        mock_lsof.stdout = lsof_output

        with patch("opencode_monitor.core.monitor.ports.subprocess.run") as mock_run:
            mock_run.return_value = mock_lsof
            result = get_tty_for_port(8080)
            assert result == ""

    def test_handles_line_with_insufficient_parts(self):
        """Handle lines with fewer than 2 parts"""
        lsof_output = """LISTEN
"""
        mock_lsof = MagicMock()
        mock_lsof.stdout = lsof_output

        with patch("opencode_monitor.core.monitor.ports.subprocess.run") as mock_run:
            mock_run.return_value = mock_lsof
            result = get_tty_for_port(8080)
            assert result == ""

    def test_handles_ps_exception(self):
        """Handle exception when running ps command"""
        lsof_output = """COMMAND     PID   USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME
opencode  12345   user    5u  IPv4 0xabc123      0t0  TCP 127.0.0.1:8080 (LISTEN)
"""
        mock_lsof = MagicMock()
        mock_lsof.stdout = lsof_output

        with patch("opencode_monitor.core.monitor.ports.subprocess.run") as mock_run:
            # First call (lsof) succeeds, second call (ps) raises exception
            mock_run.side_effect = [mock_lsof, Exception("ps failed")]
            result = get_tty_for_port(8080)
            assert result == ""


# ===========================================================================
# Tests for extract_tools_from_messages()
# ===========================================================================


class TestExtractToolsFromMessages:
    """Tests for extract_tools_from_messages() function"""

    def test_returns_empty_list_for_none(self):
        """Return empty list when messages is None"""
        result = extract_tools_from_messages(None)
        assert result == []

    def test_returns_empty_list_for_non_list(self):
        """Return empty list when messages is not a list"""
        result = extract_tools_from_messages("not a list")
        assert result == []

    def test_returns_empty_list_for_empty_list(self):
        """Return empty list when messages is empty"""
        result = extract_tools_from_messages([])
        assert result == []

    def test_returns_empty_list_when_no_parts(self):
        """Return empty list when first message has no parts"""
        messages = [{"content": "Hello"}]
        result = extract_tools_from_messages(messages)
        assert result == []

    def test_returns_empty_list_when_no_tool_parts(self):
        """Return empty list when parts contain no tools"""
        messages = [{"parts": [{"type": "text", "content": "Hello"}]}]
        result = extract_tools_from_messages(messages)
        assert result == []

    def test_ignores_non_running_tools(self):
        """Ignore tools that are not in running state"""
        messages = [
            {
                "parts": [
                    {
                        "type": "tool",
                        "tool": "bash",
                        "state": {"status": "completed", "input": {"command": "ls"}},
                    }
                ]
            }
        ]
        result = extract_tools_from_messages(messages)
        assert result == []

    def test_extracts_running_tool_with_command(self):
        """Extract running tool with command argument"""
        messages = [
            {
                "parts": [
                    {
                        "type": "tool",
                        "tool": "bash",
                        "state": {
                            "status": "running",
                            "input": {"command": "npm test"},
                        },
                    }
                ]
            }
        ]
        result = extract_tools_from_messages(messages)
        assert len(result) == 1
        assert result[0].name == "bash"
        assert result[0].arg == "npm test"

    def test_extracts_running_tool_with_filepath(self):
        """Extract running tool with filePath argument"""
        messages = [
            {
                "parts": [
                    {
                        "type": "tool",
                        "tool": "read",
                        "state": {
                            "status": "running",
                            "input": {"filePath": "/path/to/file.py"},
                        },
                    }
                ]
            }
        ]
        result = extract_tools_from_messages(messages)
        assert len(result) == 1
        assert result[0].name == "read"
        assert result[0].arg == "/path/to/file.py"

    def test_extracts_running_tool_with_title(self):
        """Extract running tool with title in state"""
        messages = [
            {
                "parts": [
                    {
                        "type": "tool",
                        "tool": "webfetch",
                        "state": {
                            "status": "running",
                            "title": "Fetching documentation",
                            "input": {},
                        },
                    }
                ]
            }
        ]
        result = extract_tools_from_messages(messages)
        assert len(result) == 1
        assert result[0].name == "webfetch"
        assert result[0].arg == "Fetching documentation"

    def test_extracts_running_tool_with_description(self):
        """Extract running tool with description argument"""
        messages = [
            {
                "parts": [
                    {
                        "type": "tool",
                        "tool": "bash",
                        "state": {
                            "status": "running",
                            "input": {"description": "Running tests"},
                        },
                    }
                ]
            }
        ]
        result = extract_tools_from_messages(messages)
        assert len(result) == 1
        assert result[0].arg == "Running tests"

    def test_extracts_running_tool_with_pattern(self):
        """Extract running tool with pattern argument"""
        messages = [
            {
                "parts": [
                    {
                        "type": "tool",
                        "tool": "glob",
                        "state": {
                            "status": "running",
                            "input": {"pattern": "**/*.py"},
                        },
                    }
                ]
            }
        ]
        result = extract_tools_from_messages(messages)
        assert len(result) == 1
        assert result[0].arg == "**/*.py"

    def test_extracts_running_tool_with_prompt_truncated(self):
        """Extract running tool with prompt (truncated to 50 chars)"""
        long_prompt = "A" * 100
        messages = [
            {
                "parts": [
                    {
                        "type": "tool",
                        "tool": "ask",
                        "state": {
                            "status": "running",
                            "input": {"prompt": long_prompt},
                        },
                    }
                ]
            }
        ]
        result = extract_tools_from_messages(messages)
        assert len(result) == 1
        assert result[0].arg == "A" * 50

    def test_extracts_multiple_running_tools(self):
        """Extract multiple running tools from parts"""
        messages = [
            {
                "parts": [
                    {
                        "type": "tool",
                        "tool": "bash",
                        "state": {"status": "running", "input": {"command": "ls"}},
                    },
                    {
                        "type": "tool",
                        "tool": "read",
                        "state": {
                            "status": "running",
                            "input": {"filePath": "/file.py"},
                        },
                    },
                    {
                        "type": "tool",
                        "tool": "write",
                        "state": {"status": "completed", "input": {}},
                    },
                ]
            }
        ]
        result = extract_tools_from_messages(messages)
        assert len(result) == 2
        assert result[0].name == "bash"
        assert result[1].name == "read"

    def test_handles_none_input(self):
        """Handle case where input is None"""
        messages = [
            {
                "parts": [
                    {
                        "type": "tool",
                        "tool": "unknown",
                        "state": {"status": "running", "input": None},
                    }
                ]
            }
        ]
        result = extract_tools_from_messages(messages)
        assert len(result) == 1
        assert result[0].name == "unknown"
        assert result[0].arg == ""

    def test_handles_empty_state(self):
        """Handle case where state is empty"""
        messages = [
            {
                "parts": [
                    {
                        "type": "tool",
                        "tool": "test",
                        "state": {},
                    }
                ]
            }
        ]
        result = extract_tools_from_messages(messages)
        # Status is not "running", so no tool extracted
        assert result == []

    def test_calculates_elapsed_ms_from_start_time(self):
        """Calculate elapsed_ms from state.time.start"""
        import time

        # Use a start time 3 seconds in the past
        start_time_ms = int((time.time() - 3) * 1000)
        messages = [
            {
                "parts": [
                    {
                        "type": "tool",
                        "tool": "bash",
                        "state": {
                            "status": "running",
                            "input": {"command": "sleep 10"},
                            "time": {"start": start_time_ms},
                        },
                    }
                ]
            }
        ]
        result = extract_tools_from_messages(messages)
        assert len(result) == 1
        # elapsed_ms should be approximately 3000 (3 seconds)
        # Allow 500ms tolerance for test execution time
        assert 2500 <= result[0].elapsed_ms <= 4000

    def test_elapsed_ms_is_zero_when_no_time_field(self):
        """elapsed_ms is 0 when state has no time field"""
        messages = [
            {
                "parts": [
                    {
                        "type": "tool",
                        "tool": "bash",
                        "state": {
                            "status": "running",
                            "input": {"command": "ls"},
                        },
                    }
                ]
            }
        ]
        result = extract_tools_from_messages(messages)
        assert len(result) == 1
        assert result[0].elapsed_ms == 0

    def test_elapsed_ms_is_zero_when_start_time_none(self):
        """elapsed_ms is 0 when time.start is None"""
        messages = [
            {
                "parts": [
                    {
                        "type": "tool",
                        "tool": "bash",
                        "state": {
                            "status": "running",
                            "input": {"command": "ls"},
                            "time": {"start": None},
                        },
                    }
                ]
            }
        ]
        result = extract_tools_from_messages(messages)
        assert len(result) == 1
        assert result[0].elapsed_ms == 0

    def test_elapsed_ms_clamped_to_non_negative(self):
        """elapsed_ms is clamped to 0 if start time is in the future"""
        import time

        # Use a start time 10 seconds in the future (should not happen, but defensive)
        future_start_ms = int((time.time() + 10) * 1000)
        messages = [
            {
                "parts": [
                    {
                        "type": "tool",
                        "tool": "bash",
                        "state": {
                            "status": "running",
                            "input": {"command": "ls"},
                            "time": {"start": future_start_ms},
                        },
                    }
                ]
            }
        ]
        result = extract_tools_from_messages(messages)
        assert len(result) == 1
        assert result[0].elapsed_ms == 0


# ===========================================================================
# Tests for count_todos()
# ===========================================================================


class TestCountTodos:
    """Tests for count_todos() function"""

    def test_returns_zeros_for_none(self):
        """Return zeros when todos is None"""
        pending, in_progress, current, next_label = count_todos(None)
        assert pending == 0
        assert in_progress == 0
        assert current == ""
        assert next_label == ""

    def test_returns_zeros_for_non_list(self):
        """Return zeros when todos is not a list"""
        pending, in_progress, current, next_label = count_todos("not a list")
        assert pending == 0
        assert in_progress == 0
        assert current == ""
        assert next_label == ""

    def test_returns_zeros_for_empty_list(self):
        """Return zeros when todos is empty"""
        pending, in_progress, current, next_label = count_todos([])
        assert pending == 0
        assert in_progress == 0
        assert current == ""
        assert next_label == ""

    def test_counts_pending_todos(self):
        """Count pending todos correctly"""
        todos = [
            {"status": "pending", "content": "Task 1"},
            {"status": "pending", "content": "Task 2"},
            {"status": "completed", "content": "Task 3"},
        ]
        pending, in_progress, current, next_label = count_todos(todos)
        assert pending == 2
        assert in_progress == 0

    def test_counts_in_progress_todos(self):
        """Count in_progress todos correctly"""
        todos = [
            {"status": "in_progress", "content": "Task 1"},
            {"status": "in_progress", "content": "Task 2"},
        ]
        pending, in_progress, current, next_label = count_todos(todos)
        assert pending == 0
        assert in_progress == 2

    def test_extracts_first_pending_label(self):
        """Extract label of first pending todo"""
        todos = [
            {"status": "pending", "content": "First pending"},
            {"status": "pending", "content": "Second pending"},
        ]
        pending, in_progress, current, next_label = count_todos(todos)
        assert next_label == "First pending"

    def test_extracts_first_in_progress_label(self):
        """Extract label of first in_progress todo"""
        todos = [
            {"status": "in_progress", "content": "First in progress"},
            {"status": "in_progress", "content": "Second in progress"},
        ]
        pending, in_progress, current, next_label = count_todos(todos)
        assert current == "First in progress"

    def test_handles_mixed_statuses(self):
        """Handle todos with mixed statuses"""
        todos = [
            {"status": "completed", "content": "Done task"},
            {"status": "in_progress", "content": "Working on this"},
            {"status": "pending", "content": "Next task"},
            {"status": "pending", "content": "After that"},
        ]
        pending, in_progress, current, next_label = count_todos(todos)
        assert pending == 2
        assert in_progress == 1
        assert current == "Working on this"
        assert next_label == "Next task"

    def test_handles_todos_without_content(self):
        """Handle todos missing content field"""
        todos = [
            {"status": "pending"},
            {"status": "in_progress"},
        ]
        pending, in_progress, current, next_label = count_todos(todos)
        assert pending == 1
        assert in_progress == 1
        assert current == ""
        assert next_label == ""

    def test_handles_todos_without_status(self):
        """Handle todos missing status field"""
        todos = [
            {"content": "Task without status"},
        ]
        pending, in_progress, current, next_label = count_todos(todos)
        assert pending == 0
        assert in_progress == 0


# ===========================================================================
# Tests for fetch_instance()
# ===========================================================================


class TestFetchInstance:
    """Tests for fetch_instance() async function"""

    @pytest.mark.asyncio
    async def test_returns_instance_with_no_agents_when_no_busy_sessions(self):
        """Return instance with empty agents when no busy sessions"""
        mock_client = AsyncMock()
        mock_client.get_status.return_value = {}
        mock_client.get_all_sessions.return_value = []

        with patch(
            "opencode_monitor.core.monitor.fetcher.OpenCodeClient", return_value=mock_client
        ):
            with patch(
                "opencode_monitor.core.monitor.fetcher.get_tty_for_port", return_value="ttys001"
            ):
                (
                    instance,
                    pending,
                    in_progress,
                    idle_candidates,
                    busy_ids,
                ) = await fetch_instance(8080)

                assert instance is not None
                assert instance.port == 8080
                assert instance.tty == "ttys001"
                assert instance.agents == []
                assert pending == 0
                assert in_progress == 0
                assert idle_candidates == []
                assert busy_ids == set()

    @pytest.mark.asyncio
    async def test_returns_instance_with_no_agents_when_status_is_none(self):
        """Return instance with empty agents when status returns None"""
        mock_client = AsyncMock()
        mock_client.get_status.return_value = None
        mock_client.get_all_sessions.return_value = []

        with patch(
            "opencode_monitor.core.monitor.fetcher.OpenCodeClient", return_value=mock_client
        ):
            with patch(
                "opencode_monitor.core.monitor.fetcher.get_tty_for_port", return_value=""
            ):
                instance, pending, in_progress, _, _ = await fetch_instance(8080)

                assert instance is not None
                assert instance.port == 8080
                assert instance.agents == []

    @pytest.mark.asyncio
    async def test_fetches_busy_session_data(self):
        """Fetch and process data for busy sessions"""
        mock_client = AsyncMock()
        mock_client.get_status.return_value = {
            "ses_123": {"type": "busy"},
        }
        mock_client.get_all_sessions.return_value = [{"id": "ses_123"}]
        mock_client.fetch_session_data.return_value = {
            "info": {"title": "Test Session", "directory": "/home/user/project"},
            "messages": [],
            "todos": [{"status": "pending", "content": "Task 1"}],
        }

        with patch(
            "opencode_monitor.core.monitor.fetcher.OpenCodeClient", return_value=mock_client
        ):
            with patch(
                "opencode_monitor.core.monitor.fetcher.get_tty_for_port", return_value="ttys001"
            ):
                instance, pending, in_progress, _, busy_ids = await fetch_instance(8080)

                assert instance is not None
                assert len(instance.agents) == 1
                assert instance.agents[0].id == "ses_123"
                assert instance.agents[0].title == "Test Session"
                assert instance.agents[0].dir == "project"
                assert instance.agents[0].status == SessionStatus.BUSY
                assert pending == 1
                assert in_progress == 0
                assert "ses_123" in busy_ids

    @pytest.mark.asyncio
    async def test_handles_idle_session_status_type(self):
        """Handle session with idle status type - idle sessions no longer in busy_status"""
        mock_client = AsyncMock()
        # Idle sessions are not in get_status (only busy sessions are)
        mock_client.get_status.return_value = {}
        mock_client.get_all_sessions.return_value = [
            {"id": "ses_123", "title": "Idle Session", "directory": ""}
        ]

        with patch(
            "opencode_monitor.core.monitor.fetcher.OpenCodeClient", return_value=mock_client
        ):
            with patch(
                "opencode_monitor.core.monitor.fetcher.get_tty_for_port", return_value=""
            ):
                (
                    instance,
                    pending,
                    in_progress,
                    idle_candidates,
                    _,
                ) = await fetch_instance(8080)

                # Idle sessions are returned as candidates for post-processing
                assert len(idle_candidates) == 1
                assert idle_candidates[0]["id"] == "ses_123"

    @pytest.mark.asyncio
    async def test_extracts_tools_from_messages(self):
        """Extract running tools from session messages"""
        mock_client = AsyncMock()
        mock_client.get_status.return_value = {
            "ses_123": {"type": "busy"},
        }
        mock_client.get_all_sessions.return_value = [{"id": "ses_123"}]
        mock_client.fetch_session_data.return_value = {
            "info": {"title": "Test", "directory": "/project"},
            "messages": [
                {
                    "parts": [
                        {
                            "type": "tool",
                            "tool": "bash",
                            "state": {
                                "status": "running",
                                "input": {"command": "npm test"},
                            },
                        }
                    ]
                }
            ],
            "todos": [],
        }

        with patch(
            "opencode_monitor.core.monitor.fetcher.OpenCodeClient", return_value=mock_client
        ):
            with patch(
                "opencode_monitor.core.monitor.fetcher.get_tty_for_port", return_value=""
            ):
                instance, pending, in_progress, _, _ = await fetch_instance(8080)

                assert len(instance.agents[0].tools) == 1
                assert instance.agents[0].tools[0].name == "bash"
                assert instance.agents[0].tools[0].arg == "npm test"

    @pytest.mark.asyncio
    async def test_handles_session_without_title(self):
        """Handle session with missing title"""
        mock_client = AsyncMock()
        mock_client.get_status.return_value = {
            "ses_123": {"type": "busy"},
        }
        mock_client.get_all_sessions.return_value = [{"id": "ses_123"}]
        mock_client.fetch_session_data.return_value = {
            "info": {"directory": "/project"},
            "messages": [],
            "todos": [],
        }

        with patch(
            "opencode_monitor.core.monitor.fetcher.OpenCodeClient", return_value=mock_client
        ):
            with patch(
                "opencode_monitor.core.monitor.fetcher.get_tty_for_port", return_value=""
            ):
                instance, pending, in_progress, _, _ = await fetch_instance(8080)

                assert instance.agents[0].title == "Sans titre"

    @pytest.mark.asyncio
    async def test_handles_empty_directory(self):
        """Handle session with empty directory"""
        mock_client = AsyncMock()
        mock_client.get_status.return_value = {
            "ses_123": {"type": "busy"},
        }
        mock_client.get_all_sessions.return_value = [{"id": "ses_123"}]
        mock_client.fetch_session_data.return_value = {
            "info": {"title": "Test", "directory": ""},
            "messages": [],
            "todos": [],
        }

        with patch(
            "opencode_monitor.core.monitor.fetcher.OpenCodeClient", return_value=mock_client
        ):
            with patch(
                "opencode_monitor.core.monitor.fetcher.get_tty_for_port", return_value=""
            ):
                instance, pending, in_progress, _, _ = await fetch_instance(8080)

                assert instance.agents[0].dir == "global"

    @pytest.mark.asyncio
    async def test_handles_none_info(self):
        """Handle session with None info"""
        mock_client = AsyncMock()
        mock_client.get_status.return_value = {
            "ses_123": {"type": "busy"},
        }
        mock_client.get_all_sessions.return_value = [{"id": "ses_123"}]
        mock_client.fetch_session_data.return_value = {
            "info": None,
            "messages": None,
            "todos": None,
        }

        with patch(
            "opencode_monitor.core.monitor.fetcher.OpenCodeClient", return_value=mock_client
        ):
            with patch(
                "opencode_monitor.core.monitor.fetcher.get_tty_for_port", return_value=""
            ):
                instance, pending, in_progress, _, _ = await fetch_instance(8080)

                assert instance.agents[0].title == "Sans titre"
                assert instance.agents[0].dir == "global"

    @pytest.mark.asyncio
    async def test_handles_subagent_with_parent_id(self):
        """Handle sub-agent with parentID"""
        mock_client = AsyncMock()
        mock_client.get_status.return_value = {
            "ses_123": {"type": "busy"},
        }
        mock_client.get_all_sessions.return_value = [{"id": "ses_123"}]
        mock_client.fetch_session_data.return_value = {
            "info": {
                "title": "Sub-agent",
                "directory": "/project",
                "parentID": "ses_parent",
            },
            "messages": [],
            "todos": [],
        }

        with patch(
            "opencode_monitor.core.monitor.fetcher.OpenCodeClient", return_value=mock_client
        ):
            with patch(
                "opencode_monitor.core.monitor.fetcher.get_tty_for_port", return_value=""
            ):
                instance, pending, in_progress, _, _ = await fetch_instance(8080)

                assert instance.agents[0].parent_id == "ses_parent"
                assert instance.agents[0].is_subagent

    @pytest.mark.asyncio
    async def test_multiple_sessions(self):
        """Handle multiple busy sessions"""
        mock_client = AsyncMock()
        mock_client.get_status.return_value = {
            "ses_1": {"type": "busy"},
            "ses_2": {"type": "busy"},
        }
        mock_client.get_all_sessions.return_value = [{"id": "ses_1"}, {"id": "ses_2"}]
        mock_client.fetch_session_data.side_effect = [
            {
                "info": {"title": "Session 1", "directory": "/proj1"},
                "messages": [],
                "todos": [{"status": "pending", "content": "Task"}],
            },
            {
                "info": {"title": "Session 2", "directory": "/proj2"},
                "messages": [],
                "todos": [{"status": "in_progress", "content": "Working"}],
            },
        ]

        with patch(
            "opencode_monitor.core.monitor.fetcher.OpenCodeClient", return_value=mock_client
        ):
            with patch(
                "opencode_monitor.core.monitor.fetcher.get_tty_for_port", return_value=""
            ):
                instance, pending, in_progress, _, busy_ids = await fetch_instance(8080)

                assert len(instance.agents) == 2
                assert pending == 1
                assert in_progress == 1
                assert "ses_1" in busy_ids
                assert "ses_2" in busy_ids


# ===========================================================================
# Tests for fetch_all_instances()
# ===========================================================================


class TestFetchAllInstances:
    """Tests for fetch_all_instances() async function"""

    @pytest.mark.asyncio
    async def test_returns_disconnected_state_when_no_ports(self):
        """Return disconnected state when no OpenCode ports found"""
        with patch(
            "opencode_monitor.core.monitor.fetcher.find_opencode_ports", return_value=[]
        ):
            state = await fetch_all_instances()

            assert state.connected is False
            assert state.instances == []

    @pytest.mark.asyncio
    async def test_returns_state_with_instances(self):
        """Return state with instances when ports found"""
        mock_instance = Instance(
            port=8080,
            tty="ttys001",
            agents=[
                Agent(
                    id="ses_1",
                    title="Test",
                    dir="project",
                    full_dir="/home/user/project",
                    status=SessionStatus.BUSY,
                    tools=[],
                    todos=AgentTodos(pending=1, in_progress=0),
                )
            ],
        )

        async def mock_find():
            return [8080]

        async def mock_fetch(port):
            # Returns (instance, pending, in_progress, idle_candidates, busy_session_ids)
            return (mock_instance, 1, 0, [], {"ses_1"})

        with patch(
            "opencode_monitor.core.monitor.fetcher.find_opencode_ports",
            side_effect=mock_find,
        ):
            with patch(
                "opencode_monitor.core.monitor.fetcher.fetch_instance",
                side_effect=mock_fetch,
            ):
                state = await fetch_all_instances()

                assert state.connected is True
                assert len(state.instances) == 1
                assert state.instances[0].port == 8080
                assert state.todos.pending == 1
                assert state.todos.in_progress == 0

    @pytest.mark.asyncio
    async def test_aggregates_todos_across_instances(self):
        """Aggregate todos from all instances"""
        instance1 = Instance(port=8080, tty="", agents=[])
        instance2 = Instance(port=9000, tty="", agents=[])

        async def mock_find():
            return [8080, 9000]

        call_count = [0]

        async def mock_fetch(port):
            call_count[0] += 1
            if port == 8080:
                # Returns (instance, pending, in_progress, idle_candidates, busy_session_ids)
                return (instance1, 2, 1, [], set())
            else:
                return (instance2, 3, 2, [], set())

        with patch(
            "opencode_monitor.core.monitor.fetcher.find_opencode_ports",
            side_effect=mock_find,
        ):
            with patch(
                "opencode_monitor.core.monitor.fetcher.fetch_instance",
                side_effect=mock_fetch,
            ):
                state = await fetch_all_instances()

                assert state.todos.pending == 5  # 2 + 3
                assert state.todos.in_progress == 3  # 1 + 2

    @pytest.mark.asyncio
    async def test_handles_none_instance_from_fetch(self):
        """Handle None instance returned from fetch_instance"""
        valid_instance = Instance(port=8080, tty="", agents=[])

        async def mock_find():
            return [8080, 9000]

        async def mock_fetch(port):
            # Returns (instance, pending, in_progress, idle_candidates, busy_session_ids)
            if port == 8080:
                return (valid_instance, 1, 0, [], set())
            else:
                return (None, 0, 0, [], set())

        with patch(
            "opencode_monitor.core.monitor.fetcher.find_opencode_ports",
            side_effect=mock_find,
        ):
            with patch(
                "opencode_monitor.core.monitor.fetcher.fetch_instance",
                side_effect=mock_fetch,
            ):
                state = await fetch_all_instances()

                assert state.connected is True
                assert len(state.instances) == 1

    @pytest.mark.asyncio
    async def test_returns_disconnected_when_all_instances_none(self):
        """Return disconnected state when all instances are None"""

        async def mock_find():
            return [8080, 9000]

        async def mock_fetch(port):
            # Returns (instance, pending, in_progress, idle_candidates, busy_session_ids)
            return (None, 0, 0, [], set())

        with patch(
            "opencode_monitor.core.monitor.fetcher.find_opencode_ports",
            side_effect=mock_find,
        ):
            with patch(
                "opencode_monitor.core.monitor.fetcher.fetch_instance",
                side_effect=mock_fetch,
            ):
                state = await fetch_all_instances()

                assert state.connected is False
                assert state.instances == []

    @pytest.mark.asyncio
    async def test_fetches_all_ports_in_parallel(self):
        """Verify all ports are fetched"""
        instance1 = Instance(port=8080, tty="", agents=[])
        instance2 = Instance(port=9000, tty="", agents=[])
        instance3 = Instance(port=9001, tty="", agents=[])

        async def mock_find():
            return [8080, 9000, 9001]

        async def mock_fetch(port):
            # Returns (instance, pending, in_progress, idle_candidates, busy_session_ids)
            if port == 8080:
                return (instance1, 0, 0, [], set())
            elif port == 9000:
                return (instance2, 0, 0, [], set())
            else:
                return (instance3, 0, 0, [], set())

        with patch(
            "opencode_monitor.core.monitor.fetcher.find_opencode_ports",
            side_effect=mock_find,
        ):
            with patch(
                "opencode_monitor.core.monitor.fetcher.fetch_instance",
                side_effect=mock_fetch,
            ):
                state = await fetch_all_instances()

                assert len(state.instances) == 3
                ports = [i.port for i in state.instances]
                assert 8080 in ports
                assert 9000 in ports
                assert 9001 in ports

    @pytest.mark.asyncio
    async def test_filters_zombie_sessions_with_known_active_sessions(self):
        """Filter out sessions that were never seen as BUSY when cache is provided"""
        instance = Instance(port=8080, tty="", agents=[])

        # Create an idle session that will be found via idle_candidates
        idle_session = {"id": "zombie_session", "title": "Zombie", "directory": ""}

        async def mock_find():
            return [8080]

        async def mock_fetch(port):
            # Return instance with no agents but one idle candidate
            return (instance, 0, 0, [idle_session], set())

        # Mock disk check to say there's a pending ask_user
        def mock_check_pending(session_id, storage_path=None):
            from opencode_monitor.core.monitor import AskUserResult

            return AskUserResult(has_pending=True, title="Test question")

        with patch(
            "opencode_monitor.core.monitor.fetcher.find_opencode_ports",
            side_effect=mock_find,
        ):
            with patch(
                "opencode_monitor.core.monitor.fetcher.fetch_instance",
                side_effect=mock_fetch,
            ):
                with patch(
                    "opencode_monitor.core.monitor.fetcher.check_pending_ask_user_from_disk",
                    side_effect=mock_check_pending,
                ):
                    # With known_active_sessions that doesn't include zombie_session
                    state = await fetch_all_instances(
                        known_active_sessions={"other_session"}
                    )

                    # zombie_session should be filtered out because it's not in known_active_sessions
                    assert state.connected is True
                    assert len(state.instances) == 1
                    assert len(state.instances[0].agents) == 0

    @pytest.mark.asyncio
    async def test_includes_idle_session_with_pending_ask_user_when_in_cache(self):
        """Include idle sessions with pending ask_user when they are in the cache"""
        instance = Instance(port=8080, tty="", agents=[])

        # Create an idle session that will be found via idle_candidates
        idle_session = {
            "id": "known_session",
            "title": "Known Session",
            "directory": "/project",
        }

        async def mock_find():
            return [8080]

        async def mock_fetch(port):
            # Return instance with no agents but one idle candidate
            return (instance, 0, 0, [idle_session], set())

        # Mock disk check to say there's a pending ask_user
        def mock_check_pending(session_id, storage_path=None):
            from opencode_monitor.core.monitor import AskUserResult

            return AskUserResult(has_pending=True, title="User input needed")

        with patch(
            "opencode_monitor.core.monitor.fetcher.find_opencode_ports",
            side_effect=mock_find,
        ):
            with patch(
                "opencode_monitor.core.monitor.fetcher.fetch_instance",
                side_effect=mock_fetch,
            ):
                with patch(
                    "opencode_monitor.core.monitor.fetcher.check_pending_ask_user_from_disk",
                    side_effect=mock_check_pending,
                ):
                    # With known_active_sessions that includes known_session
                    state = await fetch_all_instances(
                        known_active_sessions={"known_session"}
                    )

                    # known_session should be included because it's in the cache
                    assert state.connected is True
                    assert len(state.instances) == 1
                    assert len(state.instances[0].agents) == 1
                    agent = state.instances[0].agents[0]
                    assert agent.id == "known_session"
                    assert agent.has_pending_ask_user is True
                    assert agent.ask_user_title == "User input needed"
                    assert agent.status == SessionStatus.IDLE

    @pytest.mark.asyncio
    async def test_includes_all_idle_sessions_when_no_cache_provided(self):
        """Include all idle sessions with pending ask_user when no cache is provided"""
        instance = Instance(port=8080, tty="", agents=[])

        # Create an idle session that will be found via idle_candidates
        idle_session = {
            "id": "any_session",
            "title": "Any Session",
            "directory": "/project",
        }

        async def mock_find():
            return [8080]

        async def mock_fetch(port):
            # Return instance with no agents but one idle candidate
            return (instance, 0, 0, [idle_session], set())

        # Mock disk check to say there's a pending ask_user
        def mock_check_pending(session_id, storage_path=None):
            from opencode_monitor.core.monitor import AskUserResult

            return AskUserResult(has_pending=True, title="Question")

        with patch(
            "opencode_monitor.core.monitor.fetcher.find_opencode_ports",
            side_effect=mock_find,
        ):
            with patch(
                "opencode_monitor.core.monitor.fetcher.fetch_instance",
                side_effect=mock_fetch,
            ):
                with patch(
                    "opencode_monitor.core.monitor.fetcher.check_pending_ask_user_from_disk",
                    side_effect=mock_check_pending,
                ):
                    # Without known_active_sessions (None)
                    state = await fetch_all_instances(known_active_sessions=None)

                    # any_session should be included because no cache filtering
                    assert state.connected is True
                    assert len(state.instances) == 1
                    assert len(state.instances[0].agents) == 1

    @pytest.mark.asyncio
    async def test_deduplicates_agents_across_processing(self):
        """Ensure agents are not duplicated when processing"""
        busy_agent = Agent(
            id="ses_1",
            title="Busy Agent",
            dir="project",
            full_dir="/project",
            status=SessionStatus.BUSY,
            tools=[],
        )
        instance = Instance(port=8080, tty="", agents=[busy_agent])

        # Create an idle candidate with the same ID as the busy agent
        idle_session = {"id": "ses_1", "title": "Same Session", "directory": "/project"}

        async def mock_find():
            return [8080]

        async def mock_fetch(port):
            # Return instance with busy agent and same session as idle candidate
            return (instance, 0, 0, [idle_session], {"ses_1"})

        with patch(
            "opencode_monitor.core.monitor.fetcher.find_opencode_ports",
            side_effect=mock_find,
        ):
            with patch(
                "opencode_monitor.core.monitor.fetcher.fetch_instance",
                side_effect=mock_fetch,
            ):
                state = await fetch_all_instances()

                # Should only have one agent, not duplicated
                assert len(state.instances[0].agents) == 1
                assert state.instances[0].agents[0].id == "ses_1"


# ===========================================================================
# Tests for AskUserResult dataclass
# ===========================================================================


class TestAskUserResult:
    """Tests for AskUserResult dataclass"""

    def test_default_values(self):
        """Test default values for AskUserResult"""
        from opencode_monitor.core.monitor import AskUserResult

        result = AskUserResult(has_pending=False)
        assert result.has_pending is False
        assert result.title == ""

    def test_with_title(self):
        """Test AskUserResult with custom title"""
        from opencode_monitor.core.monitor import AskUserResult

        result = AskUserResult(has_pending=True, title="User input needed")
        assert result.has_pending is True
        assert result.title == "User input needed"


# ===========================================================================
# Tests for _find_latest_notify_ask_user()
# ===========================================================================


class TestFindLatestNotifyAskUser:
    """Tests for _find_latest_notify_ask_user() internal function"""

    def test_returns_empty_when_no_message_files(self, tmp_path):
        """Return empty results when message directory has no files"""
        from opencode_monitor.core.monitor import _find_latest_notify_ask_user

        message_dir = tmp_path / "message" / "session_1"
        message_dir.mkdir(parents=True)
        part_dir = tmp_path / "part"
        part_dir.mkdir(parents=True)

        timestamp, notify_input, messages = _find_latest_notify_ask_user(
            message_dir, part_dir, cutoff_time=0
        )

        assert timestamp == 0
        assert notify_input == {}
        assert messages == []

    def test_skips_files_older_than_cutoff(self, tmp_path):
        """Skip message files older than cutoff time"""
        from opencode_monitor.core.monitor import _find_latest_notify_ask_user
        import time
        import os

        message_dir = tmp_path / "message" / "session_1"
        message_dir.mkdir(parents=True)
        part_dir = tmp_path / "part"
        part_dir.mkdir(parents=True)

        # Create a message file
        msg_file = message_dir / "msg_001.json"
        msg_file.write_text(
            '{"id": "msg_001", "time": {"created": 1000}, "role": "assistant"}'
        )

        # Set file modification time to the past
        old_time = time.time() - 7200  # 2 hours ago
        os.utime(msg_file, (old_time, old_time))

        # Use cutoff time of 1 hour ago
        cutoff_time = time.time() - 3600

        timestamp, notify_input, messages = _find_latest_notify_ask_user(
            message_dir, part_dir, cutoff_time
        )

        # Should skip the old file
        assert timestamp == 0
        assert messages == []

    def test_parses_recent_message_files(self, tmp_path):
        """Parse message files newer than cutoff time"""
        from opencode_monitor.core.monitor import _find_latest_notify_ask_user
        import time

        message_dir = tmp_path / "message" / "session_1"
        message_dir.mkdir(parents=True)
        part_dir = tmp_path / "part"
        part_dir.mkdir(parents=True)

        # Create a recent message file
        msg_file = message_dir / "msg_001.json"
        msg_file.write_text(
            '{"id": "msg_001", "time": {"created": 1000}, "role": "assistant"}'
        )

        # Use cutoff time in the past
        cutoff_time = time.time() - 3600

        timestamp, notify_input, messages = _find_latest_notify_ask_user(
            message_dir, part_dir, cutoff_time
        )

        # Should include the message
        assert len(messages) == 1
        assert messages[0] == (1000, "msg_001", "assistant")

    def test_handles_malformed_json(self, tmp_path):
        """Handle malformed JSON files gracefully"""
        from opencode_monitor.core.monitor import _find_latest_notify_ask_user
        import time

        message_dir = tmp_path / "message" / "session_1"
        message_dir.mkdir(parents=True)
        part_dir = tmp_path / "part"
        part_dir.mkdir(parents=True)

        # Create a malformed message file
        msg_file = message_dir / "msg_001.json"
        msg_file.write_text("not valid json {{{")

        # Create a valid message file
        msg_file2 = message_dir / "msg_002.json"
        msg_file2.write_text(
            '{"id": "msg_002", "time": {"created": 2000}, "role": "user"}'
        )

        cutoff_time = time.time() - 3600

        timestamp, notify_input, messages = _find_latest_notify_ask_user(
            message_dir, part_dir, cutoff_time
        )

        # Should only include the valid message
        assert len(messages) == 1
        assert messages[0] == (2000, "msg_002", "user")

    def test_finds_notify_ask_user_in_part_files(self, tmp_path):
        """Find notify_ask_user tool calls in part files"""
        from opencode_monitor.core.monitor import _find_latest_notify_ask_user
        import time
        import json

        message_dir = tmp_path / "message" / "session_1"
        message_dir.mkdir(parents=True)
        part_dir = tmp_path / "part"
        part_dir.mkdir(parents=True)

        # Create message file
        msg_file = message_dir / "msg_001.json"
        msg_file.write_text(
            '{"id": "msg_001", "time": {"created": 1000}, "role": "assistant"}'
        )

        # Create part directory and file with notify_ask_user
        msg_part_dir = part_dir / "msg_001"
        msg_part_dir.mkdir(parents=True)

        part_data = {
            "type": "tool",
            "tool": "notify_ask_user",
            "state": {
                "status": "completed",
                "time": {"start": 1500},
                "input": {"title": "Need user input"},
            },
        }
        part_file = msg_part_dir / "prt_001.json"
        part_file.write_text(json.dumps(part_data))

        cutoff_time = time.time() - 3600

        timestamp, notify_input, messages = _find_latest_notify_ask_user(
            message_dir, part_dir, cutoff_time
        )

        assert timestamp == 1500
        assert notify_input.get("title") == "Need user input"

    def test_finds_latest_notify_when_multiple_exist(self, tmp_path):
        """Find the most recent notify_ask_user when multiple exist"""
        from opencode_monitor.core.monitor import _find_latest_notify_ask_user
        import time
        import json

        message_dir = tmp_path / "message" / "session_1"
        message_dir.mkdir(parents=True)
        part_dir = tmp_path / "part"
        part_dir.mkdir(parents=True)

        # Create message files
        for i, created in [(1, 1000), (2, 2000)]:
            msg_file = message_dir / f"msg_00{i}.json"
            msg_file.write_text(
                json.dumps(
                    {
                        "id": f"msg_00{i}",
                        "time": {"created": created},
                        "role": "assistant",
                    }
                )
            )

            msg_part_dir = part_dir / f"msg_00{i}"
            msg_part_dir.mkdir(parents=True)

            part_data = {
                "type": "tool",
                "tool": "notify_ask_user",
                "state": {
                    "status": "completed",
                    "time": {"start": created + 100},
                    "input": {"title": f"Question {i}"},
                },
            }
            part_file = msg_part_dir / f"prt_00{i}.json"
            part_file.write_text(json.dumps(part_data))

        cutoff_time = time.time() - 3600

        timestamp, notify_input, messages = _find_latest_notify_ask_user(
            message_dir, part_dir, cutoff_time
        )

        # Should find the most recent one
        assert timestamp == 2100  # 2000 + 100
        assert notify_input.get("title") == "Question 2"

    def test_ignores_non_completed_notify(self, tmp_path):
        """Ignore notify_ask_user that is not in completed status"""
        from opencode_monitor.core.monitor import _find_latest_notify_ask_user
        import time
        import json

        message_dir = tmp_path / "message" / "session_1"
        message_dir.mkdir(parents=True)
        part_dir = tmp_path / "part"
        part_dir.mkdir(parents=True)

        # Create message file
        msg_file = message_dir / "msg_001.json"
        msg_file.write_text(
            '{"id": "msg_001", "time": {"created": 1000}, "role": "assistant"}'
        )

        # Create part with running status (not completed)
        msg_part_dir = part_dir / "msg_001"
        msg_part_dir.mkdir(parents=True)

        part_data = {
            "type": "tool",
            "tool": "notify_ask_user",
            "state": {
                "status": "running",  # Not completed
                "time": {"start": 1500},
                "input": {"title": "Should be ignored"},
            },
        }
        part_file = msg_part_dir / "prt_001.json"
        part_file.write_text(json.dumps(part_data))

        cutoff_time = time.time() - 3600

        timestamp, notify_input, messages = _find_latest_notify_ask_user(
            message_dir, part_dir, cutoff_time
        )

        assert timestamp == 0  # Not found
        assert notify_input == {}

    def test_ignores_other_tool_types(self, tmp_path):
        """Ignore tool calls that are not notify_ask_user"""
        from opencode_monitor.core.monitor import _find_latest_notify_ask_user
        import time
        import json

        message_dir = tmp_path / "message" / "session_1"
        message_dir.mkdir(parents=True)
        part_dir = tmp_path / "part"
        part_dir.mkdir(parents=True)

        # Create message file
        msg_file = message_dir / "msg_001.json"
        msg_file.write_text(
            '{"id": "msg_001", "time": {"created": 1000}, "role": "assistant"}'
        )

        # Create part with different tool
        msg_part_dir = part_dir / "msg_001"
        msg_part_dir.mkdir(parents=True)

        part_data = {
            "type": "tool",
            "tool": "bash",  # Not notify_ask_user
            "state": {
                "status": "completed",
                "time": {"start": 1500},
                "input": {"command": "ls"},
            },
        }
        part_file = msg_part_dir / "prt_001.json"
        part_file.write_text(json.dumps(part_data))

        cutoff_time = time.time() - 3600

        timestamp, notify_input, messages = _find_latest_notify_ask_user(
            message_dir, part_dir, cutoff_time
        )

        assert timestamp == 0
        assert notify_input == {}


# ===========================================================================
# Tests for _has_activity_after_notify()
# ===========================================================================


class TestHasActivityAfterNotify:
    """Tests for _has_activity_after_notify() internal function"""

    def test_returns_false_when_no_messages_after_notify(self, tmp_path):
        """Return False when no messages exist after notify timestamp"""
        from opencode_monitor.core.monitor import _has_activity_after_notify

        part_dir = tmp_path / "part"
        part_dir.mkdir(parents=True)

        # Messages are all before the notify timestamp
        recent_messages = [
            (1000, "msg_001", "assistant"),
            (1100, "msg_002", "assistant"),
        ]

        result = _has_activity_after_notify(
            notify_timestamp=2000,
            recent_messages=recent_messages,
            part_dir=part_dir,
        )

        assert result is False

    def test_returns_true_when_user_message_after_notify(self, tmp_path):
        """Return True when user message exists after notify timestamp"""
        from opencode_monitor.core.monitor import _has_activity_after_notify

        part_dir = tmp_path / "part"
        part_dir.mkdir(parents=True)

        # User message after the notify
        recent_messages = [
            (1000, "msg_001", "assistant"),
            (2500, "msg_002", "user"),  # After notify_timestamp=2000
        ]

        result = _has_activity_after_notify(
            notify_timestamp=2000,
            recent_messages=recent_messages,
            part_dir=part_dir,
        )

        assert result is True

    def test_returns_true_when_other_tool_call_after_notify(self, tmp_path):
        """Return True when non-notify tool call exists after notify timestamp"""
        from opencode_monitor.core.monitor import _has_activity_after_notify
        import json

        part_dir = tmp_path / "part"
        part_dir.mkdir(parents=True)

        # Assistant message after notify with a different tool call
        recent_messages = [
            (1000, "msg_001", "assistant"),
            (2500, "msg_002", "assistant"),  # After notify_timestamp=2000
        ]

        # Create part file for msg_002 with a different tool
        msg_part_dir = part_dir / "msg_002"
        msg_part_dir.mkdir(parents=True)
        part_data = {
            "type": "tool",
            "tool": "bash",  # Different tool, indicates agent resumed
            "state": {"status": "completed"},
        }
        part_file = msg_part_dir / "prt_001.json"
        part_file.write_text(json.dumps(part_data))

        result = _has_activity_after_notify(
            notify_timestamp=2000,
            recent_messages=recent_messages,
            part_dir=part_dir,
        )

        assert result is True

    def test_ignores_notify_ask_user_tool_as_activity(self, tmp_path):
        """Ignore notify_ask_user calls when checking for activity"""
        from opencode_monitor.core.monitor import _has_activity_after_notify
        import json

        part_dir = tmp_path / "part"
        part_dir.mkdir(parents=True)

        # Assistant message after notify
        recent_messages = [
            (2500, "msg_002", "assistant"),  # After notify_timestamp=2000
        ]

        # Create part file for msg_002 with notify_ask_user (should be ignored)
        msg_part_dir = part_dir / "msg_002"
        msg_part_dir.mkdir(parents=True)
        part_data = {
            "type": "tool",
            "tool": "notify_ask_user",  # Same tool, should be ignored
            "state": {"status": "completed"},
        }
        part_file = msg_part_dir / "prt_001.json"
        part_file.write_text(json.dumps(part_data))

        result = _has_activity_after_notify(
            notify_timestamp=2000,
            recent_messages=recent_messages,
            part_dir=part_dir,
        )

        assert result is False  # No real activity detected

    def test_handles_missing_part_directory(self, tmp_path):
        """Handle case when part directory for message doesn't exist"""
        from opencode_monitor.core.monitor import _has_activity_after_notify

        part_dir = tmp_path / "part"
        part_dir.mkdir(parents=True)

        # Assistant message after notify but no part directory
        recent_messages = [
            (2500, "msg_002", "assistant"),  # After notify_timestamp=2000
        ]
        # Don't create msg_002 part directory

        result = _has_activity_after_notify(
            notify_timestamp=2000,
            recent_messages=recent_messages,
            part_dir=part_dir,
        )

        assert result is False

    def test_handles_malformed_part_json(self, tmp_path):
        """Handle malformed JSON in part files gracefully"""
        from opencode_monitor.core.monitor import _has_activity_after_notify

        part_dir = tmp_path / "part"
        part_dir.mkdir(parents=True)

        recent_messages = [
            (2500, "msg_002", "assistant"),
        ]

        # Create malformed part file
        msg_part_dir = part_dir / "msg_002"
        msg_part_dir.mkdir(parents=True)
        part_file = msg_part_dir / "prt_001.json"
        part_file.write_text("not valid json")

        result = _has_activity_after_notify(
            notify_timestamp=2000,
            recent_messages=recent_messages,
            part_dir=part_dir,
        )

        assert result is False  # Gracefully handled


# ===========================================================================
# Tests for check_pending_ask_user_from_disk()
# ===========================================================================


class TestCheckPendingAskUserFromDisk:
    """Tests for check_pending_ask_user_from_disk() function"""

    def test_returns_false_when_message_directory_missing(self, tmp_path):
        """Return has_pending=False when message directory doesn't exist"""
        from opencode_monitor.core.monitor import check_pending_ask_user_from_disk

        # Don't create the message directory
        result = check_pending_ask_user_from_disk(
            session_id="nonexistent_session",
            storage_path=tmp_path,
        )

        assert result.has_pending is False
        assert result.title == ""

    def test_returns_false_when_no_recent_notify(self, tmp_path):
        """Return has_pending=False when no recent notify_ask_user found"""
        from opencode_monitor.core.monitor import check_pending_ask_user_from_disk

        # Create empty message directory
        message_dir = tmp_path / "message" / "session_1"
        message_dir.mkdir(parents=True)
        part_dir = tmp_path / "part"
        part_dir.mkdir(parents=True)

        result = check_pending_ask_user_from_disk(
            session_id="session_1",
            storage_path=tmp_path,
        )

        assert result.has_pending is False

    def test_returns_true_when_pending_notify_found(self, tmp_path):
        """Return has_pending=True when pending notify_ask_user found"""
        from opencode_monitor.core.monitor import check_pending_ask_user_from_disk
        import json
        import time

        # Create message directory and file
        message_dir = tmp_path / "message" / "session_1"
        message_dir.mkdir(parents=True)
        msg_file = message_dir / "msg_001.json"
        msg_file.write_text(
            json.dumps(
                {
                    "id": "msg_001",
                    "time": {"created": int(time.time() * 1000)},  # Recent timestamp
                    "role": "assistant",
                }
            )
        )

        # Create part with notify_ask_user
        part_dir = tmp_path / "part"
        part_dir.mkdir(parents=True)
        msg_part_dir = part_dir / "msg_001"
        msg_part_dir.mkdir(parents=True)
        part_data = {
            "type": "tool",
            "tool": "notify_ask_user",
            "state": {
                "status": "completed",
                "time": {"start": int(time.time() * 1000)},
                "input": {"title": "Waiting for user"},
            },
        }
        part_file = msg_part_dir / "prt_001.json"
        part_file.write_text(json.dumps(part_data))

        result = check_pending_ask_user_from_disk(
            session_id="session_1",
            storage_path=tmp_path,
        )

        assert result.has_pending is True
        assert result.title == "Waiting for user"

    def test_returns_false_when_user_responded_after_notify(self, tmp_path):
        """Return has_pending=False when user responded after notify"""
        from opencode_monitor.core.monitor import check_pending_ask_user_from_disk
        import json
        import time

        current_time = int(time.time() * 1000)

        # Create message directory
        message_dir = tmp_path / "message" / "session_1"
        message_dir.mkdir(parents=True)

        # Create assistant message with notify_ask_user
        msg_file = message_dir / "msg_001.json"
        msg_file.write_text(
            json.dumps(
                {
                    "id": "msg_001",
                    "time": {"created": current_time - 5000},  # 5 seconds ago
                    "role": "assistant",
                }
            )
        )

        # Create user response message (after the notify)
        msg_file2 = message_dir / "msg_002.json"
        msg_file2.write_text(
            json.dumps(
                {
                    "id": "msg_002",
                    "time": {
                        "created": current_time - 2000
                    },  # 2 seconds ago (after notify)
                    "role": "user",
                }
            )
        )

        # Create part with notify_ask_user
        part_dir = tmp_path / "part"
        part_dir.mkdir(parents=True)
        msg_part_dir = part_dir / "msg_001"
        msg_part_dir.mkdir(parents=True)
        part_data = {
            "type": "tool",
            "tool": "notify_ask_user",
            "state": {
                "status": "completed",
                "time": {"start": current_time - 4000},  # 4 seconds ago
                "input": {"title": "Question"},
            },
        }
        part_file = msg_part_dir / "prt_001.json"
        part_file.write_text(json.dumps(part_data))

        result = check_pending_ask_user_from_disk(
            session_id="session_1",
            storage_path=tmp_path,
        )

        # User responded, so not pending
        assert result.has_pending is False

    def test_respects_timeout_setting(self, tmp_path):
        """Notifications older than timeout are ignored"""
        from opencode_monitor.core.monitor import check_pending_ask_user_from_disk
        from unittest.mock import patch, MagicMock
        import json
        import time
        import os

        # Create message directory
        message_dir = tmp_path / "message" / "session_1"
        message_dir.mkdir(parents=True)

        # Create a notification from 45 minutes ago
        forty_five_min_ago = time.time() - (45 * 60)
        forty_five_min_ago_ms = int(forty_five_min_ago * 1000)

        # Create message file
        msg_file = message_dir / "msg_001.json"
        msg_file.write_text(
            json.dumps(
                {
                    "id": "msg_001",
                    "time": {"created": forty_five_min_ago_ms},
                    "role": "assistant",
                }
            )
        )
        os.utime(msg_file, (forty_five_min_ago, forty_five_min_ago))

        # Create part with notify_ask_user
        part_dir = tmp_path / "part"
        part_dir.mkdir(parents=True)
        msg_part_dir = part_dir / "msg_001"
        msg_part_dir.mkdir(parents=True)
        part_data = {
            "type": "tool",
            "tool": "notify_ask_user",
            "state": {
                "status": "completed",
                "time": {"start": forty_five_min_ago_ms},
                "input": {"title": "Old question"},
            },
        }
        part_file = msg_part_dir / "prt_001.json"
        part_file.write_text(json.dumps(part_data))
        os.utime(part_file, (forty_five_min_ago, forty_five_min_ago))

        # With default timeout of 30 minutes, 45-minute-old notification should be ignored
        mock_settings = MagicMock()
        mock_settings.ask_user_timeout = 30 * 60  # 30 minutes

        with patch(
            "opencode_monitor.core.monitor.ask_user.get_settings", return_value=mock_settings
        ):
            result = check_pending_ask_user_from_disk(
                session_id="session_1",
                storage_path=tmp_path,
            )

        # 45 minutes ago is older than 30 minute timeout
        assert result.has_pending is False

        # With 1 hour timeout, should find it
        mock_settings.ask_user_timeout = 60 * 60  # 1 hour

        with patch(
            "opencode_monitor.core.monitor.ask_user.get_settings", return_value=mock_settings
        ):
            result = check_pending_ask_user_from_disk(
                session_id="session_1",
                storage_path=tmp_path,
            )

        # 45 minutes ago is within 1 hour timeout
        assert result.has_pending is True

    def test_handles_exception_gracefully(self, tmp_path):
        """Handle exceptions during file scanning gracefully"""
        from opencode_monitor.core.monitor import check_pending_ask_user_from_disk
        from unittest.mock import patch

        # Create message directory
        message_dir = tmp_path / "message" / "session_1"
        message_dir.mkdir(parents=True)

        # Mock _find_latest_notify_ask_user to raise an exception
        with patch(
            "opencode_monitor.core.monitor._find_latest_notify_ask_user",
            side_effect=Exception("File error"),
        ):
            result = check_pending_ask_user_from_disk(
                session_id="session_1",
                storage_path=tmp_path,
            )

            # Should return False on error
            assert result.has_pending is False


# ===========================================================================
# Tests for fetch_instance() 5-tuple return and idle_candidates
# ===========================================================================


class TestFetchInstanceIdleCandidates:
    """Tests for fetch_instance() returning idle candidates for ask_user detection"""

    @pytest.mark.asyncio
    async def test_returns_idle_candidates_for_post_processing(self):
        """Return idle session candidates for post-processing"""
        mock_client = AsyncMock()
        mock_client.get_status.return_value = {}  # No busy sessions
        mock_client.get_all_sessions.return_value = [
            {"id": "idle_ses_1", "title": "Idle Session", "directory": "/project"},
        ]

        with patch(
            "opencode_monitor.core.monitor.fetcher.OpenCodeClient", return_value=mock_client
        ):
            with patch(
                "opencode_monitor.core.monitor.fetcher.get_tty_for_port", return_value=""
            ):
                (
                    instance,
                    pending,
                    in_progress,
                    idle_candidates,
                    busy_ids,
                ) = await fetch_instance(8080)

                assert len(idle_candidates) == 1
                assert idle_candidates[0]["id"] == "idle_ses_1"
                assert busy_ids == set()

    @pytest.mark.asyncio
    async def test_excludes_subagents_from_idle_candidates(self):
        """Exclude sub-agents (sessions with parentID) from idle candidates"""
        mock_client = AsyncMock()
        mock_client.get_status.return_value = {}  # No busy sessions
        mock_client.get_all_sessions.return_value = [
            {"id": "parent_session", "title": "Parent", "directory": "/project"},
            {
                "id": "subagent",
                "title": "Sub-agent",
                "directory": "/project",
                "parentID": "parent_session",
            },
        ]

        with patch(
            "opencode_monitor.core.monitor.fetcher.OpenCodeClient", return_value=mock_client
        ):
            with patch(
                "opencode_monitor.core.monitor.fetcher.get_tty_for_port", return_value=""
            ):
                (
                    instance,
                    pending,
                    in_progress,
                    idle_candidates,
                    busy_ids,
                ) = await fetch_instance(8080)

                # Sub-agents should be excluded
                assert len(idle_candidates) == 1
                assert idle_candidates[0]["id"] == "parent_session"

    @pytest.mark.asyncio
    async def test_returns_busy_session_ids_set(self):
        """Return set of busy session IDs for cross-checking"""
        mock_client = AsyncMock()
        mock_client.get_status.return_value = {
            "busy_1": {"type": "busy"},
            "busy_2": {"type": "busy"},
        }
        mock_client.get_all_sessions.return_value = [
            {"id": "busy_1"},
            {"id": "busy_2"},
            {"id": "idle_1"},
        ]
        mock_client.fetch_session_data.return_value = {
            "info": {"title": "Session", "directory": "/project"},
            "messages": [],
            "todos": [],
        }

        with patch(
            "opencode_monitor.core.monitor.fetcher.OpenCodeClient", return_value=mock_client
        ):
            with patch(
                "opencode_monitor.core.monitor.fetcher.get_tty_for_port", return_value=""
            ):
                (
                    instance,
                    pending,
                    in_progress,
                    idle_candidates,
                    busy_ids,
                ) = await fetch_instance(8080)

                assert "busy_1" in busy_ids
                assert "busy_2" in busy_ids
                assert "idle_1" not in busy_ids


# ===========================================================================
# Additional edge case tests for full coverage
# ===========================================================================


class TestFindLatestNotifyAskUserEdgeCases:
    """Additional edge case tests for _find_latest_notify_ask_user()"""

    def test_skips_part_files_older_than_cutoff(self, tmp_path):
        """Skip part files that are older than cutoff time"""
        from opencode_monitor.core.monitor import _find_latest_notify_ask_user
        import time
        import os
        import json

        message_dir = tmp_path / "message" / "session_1"
        message_dir.mkdir(parents=True)
        part_dir = tmp_path / "part"
        part_dir.mkdir(parents=True)

        # Create a recent message file
        msg_file = message_dir / "msg_001.json"
        msg_file.write_text(
            '{"id": "msg_001", "time": {"created": 1000}, "role": "assistant"}'
        )

        # Create part directory with an OLD part file
        msg_part_dir = part_dir / "msg_001"
        msg_part_dir.mkdir(parents=True)

        part_data = {
            "type": "tool",
            "tool": "notify_ask_user",
            "state": {
                "status": "completed",
                "time": {"start": 1500},
                "input": {"title": "Old question"},
            },
        }
        part_file = msg_part_dir / "prt_001.json"
        part_file.write_text(json.dumps(part_data))

        # Set part file to be very old
        old_time = time.time() - 7200  # 2 hours ago
        os.utime(part_file, (old_time, old_time))

        # Use cutoff time of 1 hour ago
        cutoff_time = time.time() - 3600

        timestamp, notify_input, messages = _find_latest_notify_ask_user(
            message_dir, part_dir, cutoff_time
        )

        # Message should be found, but notify should be skipped (part file too old)
        assert len(messages) == 1
        assert timestamp == 0  # No notify found because part file was too old
        assert notify_input == {}

    def test_handles_malformed_part_json_in_find(self, tmp_path):
        """Handle malformed JSON in part files during _find_latest_notify_ask_user"""
        from opencode_monitor.core.monitor import _find_latest_notify_ask_user
        import time
        import json

        message_dir = tmp_path / "message" / "session_1"
        message_dir.mkdir(parents=True)
        part_dir = tmp_path / "part"
        part_dir.mkdir(parents=True)

        # Create message file
        msg_file = message_dir / "msg_001.json"
        msg_file.write_text(
            '{"id": "msg_001", "time": {"created": 1000}, "role": "assistant"}'
        )

        # Create part directory with malformed JSON
        msg_part_dir = part_dir / "msg_001"
        msg_part_dir.mkdir(parents=True)

        # Write invalid JSON
        part_file = msg_part_dir / "prt_001.json"
        part_file.write_text("not valid json {{{")

        # Also create a valid part file
        part_data = {
            "type": "tool",
            "tool": "notify_ask_user",
            "state": {
                "status": "completed",
                "time": {"start": 1500},
                "input": {"title": "Valid question"},
            },
        }
        part_file2 = msg_part_dir / "prt_002.json"
        part_file2.write_text(json.dumps(part_data))

        cutoff_time = time.time() - 3600

        timestamp, notify_input, messages = _find_latest_notify_ask_user(
            message_dir, part_dir, cutoff_time
        )

        # Should find the valid part file and skip the malformed one
        assert timestamp == 1500
        assert notify_input.get("title") == "Valid question"


class TestFetchAllInstancesEdgeCases:
    """Additional edge case tests for fetch_all_instances()"""

    @pytest.mark.asyncio
    async def test_skips_duplicate_session_in_idle_candidates(self):
        """Skip idle candidate if session already seen (deduplication)"""
        # Create an instance where idle_candidates contains a duplicate
        busy_agent = Agent(
            id="ses_dup",
            title="Busy Agent",
            dir="project",
            full_dir="/project",
            status=SessionStatus.BUSY,
            tools=[],
        )
        instance1 = Instance(port=8080, tty="", agents=[busy_agent])

        # Session also appears in idle_candidates of second instance
        idle_session = {"id": "ses_dup", "title": "Duplicate", "directory": "/project"}

        async def mock_find():
            return [8080, 9000]

        call_count = [0]

        async def mock_fetch(port):
            call_count[0] += 1
            if port == 8080:
                # First instance has the session as busy
                return (instance1, 0, 0, [], {"ses_dup"})
            else:
                # Second instance has the same session as idle candidate
                return (
                    Instance(port=9000, tty="", agents=[]),
                    0,
                    0,
                    [idle_session],
                    set(),
                )

        # Mock disk check (shouldn't be called for duplicate)
        check_called = [False]

        def mock_check_pending(session_id, storage_path=None):
            check_called[0] = True
            from opencode_monitor.core.monitor import AskUserResult

            return AskUserResult(has_pending=True, title="Test")

        with patch(
            "opencode_monitor.core.monitor.fetcher.find_opencode_ports",
            side_effect=mock_find,
        ):
            with patch(
                "opencode_monitor.core.monitor.fetcher.fetch_instance",
                side_effect=mock_fetch,
            ):
                with patch(
                    "opencode_monitor.core.monitor.fetcher.check_pending_ask_user_from_disk",
                    side_effect=mock_check_pending,
                ):
                    state = await fetch_all_instances()

                    # Should only have one agent with id "ses_dup" (not duplicated)
                    all_agent_ids = [
                        agent.id
                        for instance in state.instances
                        for agent in instance.agents
                    ]
                    assert all_agent_ids.count("ses_dup") == 1
                    # check_pending should NOT be called for duplicate session
                    assert check_called[0] is False
