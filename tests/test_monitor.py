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
        with patch("opencode_monitor.core.monitor.subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Command failed")
            result = await find_opencode_ports()
            assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_listening_ports(self):
        """When netstat has no LISTEN lines, return empty list"""
        mock_result = MagicMock()
        mock_result.stdout = "Active connections\nProto  Local Address\n"

        with patch("opencode_monitor.core.monitor.subprocess.run") as mock_run:
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

        with patch("opencode_monitor.core.monitor.subprocess.run") as mock_run:
            with patch(
                "opencode_monitor.core.monitor.check_opencode_port",
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

        with patch("opencode_monitor.core.monitor.subprocess.run") as mock_run:
            with patch(
                "opencode_monitor.core.monitor.check_opencode_port",
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

        with patch("opencode_monitor.core.monitor.subprocess.run") as mock_run:
            with patch(
                "opencode_monitor.core.monitor.check_opencode_port",
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

        with patch("opencode_monitor.core.monitor.subprocess.run") as mock_run:
            with patch(
                "opencode_monitor.core.monitor.check_opencode_port",
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
        with patch("opencode_monitor.core.monitor.subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Command failed")
            result = get_tty_for_port(8080)
            assert result == ""

    def test_returns_empty_string_when_no_opencode_process(self):
        """When no opencode process found, return empty string"""
        mock_result = MagicMock()
        mock_result.stdout = "COMMAND     PID   USER\nnode      1234   user"

        with patch("opencode_monitor.core.monitor.subprocess.run") as mock_run:
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

        with patch("opencode_monitor.core.monitor.subprocess.run") as mock_run:
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

        with patch("opencode_monitor.core.monitor.subprocess.run") as mock_run:
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

        with patch("opencode_monitor.core.monitor.subprocess.run") as mock_run:
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

        with patch("opencode_monitor.core.monitor.subprocess.run") as mock_run:
            mock_run.return_value = mock_lsof
            result = get_tty_for_port(8080)
            assert result == ""

    def test_handles_line_with_insufficient_parts(self):
        """Handle lines with fewer than 2 parts"""
        lsof_output = """LISTEN
"""
        mock_lsof = MagicMock()
        mock_lsof.stdout = lsof_output

        with patch("opencode_monitor.core.monitor.subprocess.run") as mock_run:
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

        with patch("opencode_monitor.core.monitor.subprocess.run") as mock_run:
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

        with patch(
            "opencode_monitor.core.monitor.OpenCodeClient", return_value=mock_client
        ):
            with patch(
                "opencode_monitor.core.monitor.get_tty_for_port", return_value="ttys001"
            ):
                instance, pending, in_progress = await fetch_instance(8080)

                assert instance is not None
                assert instance.port == 8080
                assert instance.tty == "ttys001"
                assert instance.agents == []
                assert pending == 0
                assert in_progress == 0

    @pytest.mark.asyncio
    async def test_returns_instance_with_no_agents_when_status_is_none(self):
        """Return instance with empty agents when status returns None"""
        mock_client = AsyncMock()
        mock_client.get_status.return_value = None

        with patch(
            "opencode_monitor.core.monitor.OpenCodeClient", return_value=mock_client
        ):
            with patch(
                "opencode_monitor.core.monitor.get_tty_for_port", return_value=""
            ):
                instance, pending, in_progress = await fetch_instance(8080)

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
        mock_client.fetch_session_data.return_value = {
            "info": {"title": "Test Session", "directory": "/home/user/project"},
            "messages": [],
            "todos": [{"status": "pending", "content": "Task 1"}],
        }

        with patch(
            "opencode_monitor.core.monitor.OpenCodeClient", return_value=mock_client
        ):
            with patch(
                "opencode_monitor.core.monitor.get_tty_for_port", return_value="ttys001"
            ):
                instance, pending, in_progress = await fetch_instance(8080)

                assert instance is not None
                assert len(instance.agents) == 1
                assert instance.agents[0].id == "ses_123"
                assert instance.agents[0].title == "Test Session"
                assert instance.agents[0].dir == "project"
                assert instance.agents[0].status == SessionStatus.BUSY
                assert pending == 1
                assert in_progress == 0

    @pytest.mark.asyncio
    async def test_handles_idle_session_status_type(self):
        """Handle session with idle status type"""
        mock_client = AsyncMock()
        mock_client.get_status.return_value = {
            "ses_123": {"type": "idle"},
        }
        mock_client.fetch_session_data.return_value = {
            "info": {"title": "Idle Session", "directory": ""},
            "messages": [],
            "todos": [],
        }

        with patch(
            "opencode_monitor.core.monitor.OpenCodeClient", return_value=mock_client
        ):
            with patch(
                "opencode_monitor.core.monitor.get_tty_for_port", return_value=""
            ):
                instance, pending, in_progress = await fetch_instance(8080)

                assert instance.agents[0].status == SessionStatus.IDLE

    @pytest.mark.asyncio
    async def test_extracts_tools_from_messages(self):
        """Extract running tools from session messages"""
        mock_client = AsyncMock()
        mock_client.get_status.return_value = {
            "ses_123": {"type": "busy"},
        }
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
            "opencode_monitor.core.monitor.OpenCodeClient", return_value=mock_client
        ):
            with patch(
                "opencode_monitor.core.monitor.get_tty_for_port", return_value=""
            ):
                instance, pending, in_progress = await fetch_instance(8080)

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
        mock_client.fetch_session_data.return_value = {
            "info": {"directory": "/project"},
            "messages": [],
            "todos": [],
        }

        with patch(
            "opencode_monitor.core.monitor.OpenCodeClient", return_value=mock_client
        ):
            with patch(
                "opencode_monitor.core.monitor.get_tty_for_port", return_value=""
            ):
                instance, pending, in_progress = await fetch_instance(8080)

                assert instance.agents[0].title == "Sans titre"

    @pytest.mark.asyncio
    async def test_handles_empty_directory(self):
        """Handle session with empty directory"""
        mock_client = AsyncMock()
        mock_client.get_status.return_value = {
            "ses_123": {"type": "busy"},
        }
        mock_client.fetch_session_data.return_value = {
            "info": {"title": "Test", "directory": ""},
            "messages": [],
            "todos": [],
        }

        with patch(
            "opencode_monitor.core.monitor.OpenCodeClient", return_value=mock_client
        ):
            with patch(
                "opencode_monitor.core.monitor.get_tty_for_port", return_value=""
            ):
                instance, pending, in_progress = await fetch_instance(8080)

                assert instance.agents[0].dir == "global"

    @pytest.mark.asyncio
    async def test_handles_none_info(self):
        """Handle session with None info"""
        mock_client = AsyncMock()
        mock_client.get_status.return_value = {
            "ses_123": {"type": "busy"},
        }
        mock_client.fetch_session_data.return_value = {
            "info": None,
            "messages": None,
            "todos": None,
        }

        with patch(
            "opencode_monitor.core.monitor.OpenCodeClient", return_value=mock_client
        ):
            with patch(
                "opencode_monitor.core.monitor.get_tty_for_port", return_value=""
            ):
                instance, pending, in_progress = await fetch_instance(8080)

                assert instance.agents[0].title == "Sans titre"
                assert instance.agents[0].dir == "global"

    @pytest.mark.asyncio
    async def test_handles_subagent_with_parent_id(self):
        """Handle sub-agent with parentID"""
        mock_client = AsyncMock()
        mock_client.get_status.return_value = {
            "ses_123": {"type": "busy"},
        }
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
            "opencode_monitor.core.monitor.OpenCodeClient", return_value=mock_client
        ):
            with patch(
                "opencode_monitor.core.monitor.get_tty_for_port", return_value=""
            ):
                instance, pending, in_progress = await fetch_instance(8080)

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
            "opencode_monitor.core.monitor.OpenCodeClient", return_value=mock_client
        ):
            with patch(
                "opencode_monitor.core.monitor.get_tty_for_port", return_value=""
            ):
                instance, pending, in_progress = await fetch_instance(8080)

                assert len(instance.agents) == 2
                assert pending == 1
                assert in_progress == 1


# ===========================================================================
# Tests for fetch_all_instances()
# ===========================================================================


class TestFetchAllInstances:
    """Tests for fetch_all_instances() async function"""

    @pytest.mark.asyncio
    async def test_returns_disconnected_state_when_no_ports(self):
        """Return disconnected state when no OpenCode ports found"""
        with patch(
            "opencode_monitor.core.monitor.find_opencode_ports", return_value=[]
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
            return (mock_instance, 1, 0)

        with patch(
            "opencode_monitor.core.monitor.find_opencode_ports",
            side_effect=mock_find,
        ):
            with patch(
                "opencode_monitor.core.monitor.fetch_instance",
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
                return (instance1, 2, 1)
            else:
                return (instance2, 3, 2)

        with patch(
            "opencode_monitor.core.monitor.find_opencode_ports",
            side_effect=mock_find,
        ):
            with patch(
                "opencode_monitor.core.monitor.fetch_instance",
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
            if port == 8080:
                return (valid_instance, 1, 0)
            else:
                return (None, 0, 0)

        with patch(
            "opencode_monitor.core.monitor.find_opencode_ports",
            side_effect=mock_find,
        ):
            with patch(
                "opencode_monitor.core.monitor.fetch_instance",
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
            return (None, 0, 0)

        with patch(
            "opencode_monitor.core.monitor.find_opencode_ports",
            side_effect=mock_find,
        ):
            with patch(
                "opencode_monitor.core.monitor.fetch_instance",
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
            if port == 8080:
                return (instance1, 0, 0)
            elif port == 9000:
                return (instance2, 0, 0)
            else:
                return (instance3, 0, 0)

        with patch(
            "opencode_monitor.core.monitor.find_opencode_ports",
            side_effect=mock_find,
        ):
            with patch(
                "opencode_monitor.core.monitor.fetch_instance",
                side_effect=mock_fetch,
            ):
                state = await fetch_all_instances()

                assert len(state.instances) == 3
                ports = [i.port for i in state.instances]
                assert 8080 in ports
                assert 9000 in ports
                assert 9001 in ports
