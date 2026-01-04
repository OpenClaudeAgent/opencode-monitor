"""Session query methods for TracingDataService.

Contains all methods related to querying individual session data.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from ...utils.logger import debug

if TYPE_CHECKING:
    from .config import TracingConfig
    import duckdb


class SessionQueriesMixin:
    """Mixin providing session query methods for TracingDataService.

    Requires _conn property, _config attribute, and helper methods from HelpersMixin.
    """

    _config: "TracingConfig"

    @property
    def _conn(self) -> "duckdb.DuckDBPyConnection":
        """Get database connection (implemented by main class)."""
        raise NotImplementedError

    # Helper methods (from HelpersMixin, declared for type checking)
    def _get_session_info(self, session_id: str) -> dict | None:
        raise NotImplementedError

    def _get_session_tokens_internal(self, session_id: str) -> dict:
        raise NotImplementedError

    def _get_session_tools_internal(self, session_id: str) -> dict:
        raise NotImplementedError

    def _get_session_files_internal(self, session_id: str) -> dict:
        raise NotImplementedError

    def _get_session_agents_internal(self, session_id: str) -> dict:
        raise NotImplementedError

    def _calculate_duration(self, session_id: str) -> int:
        raise NotImplementedError

    def _calculate_cost(self, tokens: dict) -> float:
        raise NotImplementedError

    def _tokens_chart_data(self, tokens: dict) -> list[dict]:
        raise NotImplementedError

    def _tools_chart_data(self, tools: dict) -> list[dict]:
        raise NotImplementedError

    def _files_chart_data(self, files: dict) -> list[dict]:
        raise NotImplementedError

    def _empty_response(self, session_id: str) -> dict:
        raise NotImplementedError

    def _extract_tool_display_info(
        self, tool_name: str, content: str, arguments: str
    ) -> str:
        raise NotImplementedError

    def get_session_summary(self, session_id: str) -> dict:
        """Get complete summary of a session with all KPIs.

        This is the primary method for session detail views.
        Returns all metrics needed for the session detail dashboard.

        Args:
            session_id: The session ID to query

        Returns:
            Dict with meta, summary, details, and charts sections
        """
        try:
            # Get session basic info
            session = self._get_session_info(session_id)
            if not session:
                return self._empty_response(session_id)

            # Get token metrics
            tokens = self._get_session_tokens_internal(session_id)

            # Get tool metrics
            tools = self._get_session_tools_internal(session_id)

            # Get file metrics
            files = self._get_session_files_internal(session_id)

            # Get agent/delegation metrics
            agents = self._get_session_agents_internal(session_id)

            # Calculate duration
            duration_ms = self._calculate_duration(session_id)

            # Calculate cost
            cost_usd = self._calculate_cost(tokens)

            return {
                "meta": {
                    "session_id": session_id,
                    "generated_at": datetime.now().isoformat(),
                    "title": session.get("title", ""),
                    "directory": session.get("directory", ""),
                },
                "summary": {
                    "duration_ms": duration_ms,
                    "total_tokens": tokens["total"],
                    "total_tool_calls": tools["total_calls"],
                    "total_files": files["total_reads"] + files["total_writes"],
                    "unique_agents": agents["unique_count"],
                    "estimated_cost_usd": round(cost_usd, 4),
                    "status": session.get("status", "completed"),
                },
                "details": {
                    "tokens": tokens,
                    "tools": tools,
                    "files": files,
                    "agents": agents,
                },
                "charts": {
                    "tokens_by_type": self._tokens_chart_data(tokens),
                    "tools_by_name": self._tools_chart_data(tools),
                    "files_by_type": self._files_chart_data(files),
                },
            }
        except Exception as e:
            debug(f"get_session_summary failed: {e}")
            return self._empty_response(session_id)

    def get_session_tokens(self, session_id: str) -> dict:
        """Get detailed token metrics for a session.

        Args:
            session_id: The session ID to query

        Returns:
            Dict with token breakdown and charts
        """
        tokens = self._get_session_tokens_internal(session_id)
        return {
            "meta": {
                "session_id": session_id,
                "generated_at": datetime.now().isoformat(),
            },
            "summary": {
                "total": tokens["total"],
                "input": tokens["input"],
                "output": tokens["output"],
                "cache_read": tokens["cache_read"],
                "cache_hit_ratio": tokens["cache_hit_ratio"],
            },
            "details": tokens,
            "charts": {
                "tokens_by_type": self._tokens_chart_data(tokens),
                "tokens_by_agent": tokens.get("by_agent", []),
            },
        }

    def get_session_tools(self, session_id: str) -> dict:
        """Get detailed tool usage for a session.

        Args:
            session_id: The session ID to query

        Returns:
            Dict with tool breakdown and charts
        """
        tools = self._get_session_tools_internal(session_id)
        return {
            "meta": {
                "session_id": session_id,
                "generated_at": datetime.now().isoformat(),
            },
            "summary": {
                "total_calls": tools["total_calls"],
                "unique_tools": tools["unique_tools"],
                "success_rate": tools["success_rate"],
                "avg_duration_ms": tools["avg_duration_ms"],
            },
            "details": tools,
            "charts": {
                "tools_by_name": self._tools_chart_data(tools),
                "tools_by_status": tools.get("by_status", []),
            },
        }

    def get_session_files(self, session_id: str) -> dict:
        """Get detailed file operations for a session.

        Args:
            session_id: The session ID to query

        Returns:
            Dict with file operations breakdown
        """
        files = self._get_session_files_internal(session_id)
        return {
            "meta": {
                "session_id": session_id,
                "generated_at": datetime.now().isoformat(),
            },
            "summary": {
                "total_reads": files["total_reads"],
                "total_writes": files["total_writes"],
                "total_edits": files["total_edits"],
                "high_risk_count": files["high_risk_count"],
            },
            "details": files,
            "charts": {
                "files_by_type": self._files_chart_data(files),
                "files_by_extension": files.get("by_extension", []),
            },
        }

    def get_session_prompts(self, session_id: str) -> dict:
        """Get first user prompt and last assistant response for a session.

        Retrieves actual content from the parts table.

        Args:
            session_id: The session ID to query

        Returns:
            Dict with prompt_input (first user message) and prompt_output (last response)
        """
        try:
            # Get first user message content
            first_user = self._conn.execute(
                """
                SELECT p.content
                FROM parts p
                JOIN messages m ON p.message_id = m.id
                WHERE p.session_id = ?
                  AND p.part_type = 'text'
                  AND m.role = 'user'
                  AND p.content IS NOT NULL
                ORDER BY p.created_at ASC
                LIMIT 1
                """,
                [session_id],
            ).fetchone()

            # Get last assistant message content
            last_assistant = self._conn.execute(
                """
                SELECT p.content
                FROM parts p
                JOIN messages m ON p.message_id = m.id
                WHERE p.session_id = ?
                  AND p.part_type = 'text'
                  AND m.role = 'assistant'
                  AND p.content IS NOT NULL
                ORDER BY p.created_at DESC
                LIMIT 1
                """,
                [session_id],
            ).fetchone()

            prompt_input = first_user[0] if first_user else None
            prompt_output = last_assistant[0] if last_assistant else None

            # Fallback to session title if no content found
            if not prompt_input:
                session = self._get_session_info(session_id)
                prompt_input = (
                    session.get("title", "(No prompt content)")
                    if session
                    else "(No prompt content)"
                )

            return {
                "meta": {
                    "session_id": session_id,
                    "generated_at": datetime.now().isoformat(),
                },
                "prompt_input": prompt_input,
                "prompt_output": prompt_output or "(No response yet)",
            }
        except Exception as e:
            debug(f"get_session_prompts failed: {e}")
            return {
                "meta": {"session_id": session_id, "error": str(e)},
                "prompt_input": "(Unable to load prompt data)",
                "prompt_output": None,
            }

    def get_session_messages(self, session_id: str) -> list[dict]:
        """Get all messages with content for a session.

        Returns the full conversation history including:
        - User prompts
        - Assistant responses
        - Tool calls (without content, just metadata)

        Args:
            session_id: The session ID to query

        Returns:
            List of message dicts with role, content, timestamp, etc.
        """
        try:
            results = self._conn.execute(
                """
                SELECT 
                    m.id as message_id,
                    m.role,
                    m.agent,
                    p.part_type,
                    p.content,
                    p.tool_name,
                    p.tool_status,
                    COALESCE(p.created_at, m.created_at) as created_at,
                    m.tokens_input,
                    m.tokens_output
                FROM messages m
                LEFT JOIN parts p ON p.message_id = m.id
                WHERE m.session_id = ?
                ORDER BY COALESCE(p.created_at, m.created_at) ASC
                """,
                [session_id],
            ).fetchall()

            messages = []
            seen_messages = set()

            for row in results:
                msg_id = row[0]
                role = row[1]
                agent = row[2]
                part_type = row[3]
                content = row[4]
                tool_name = row[5]
                tool_status = row[6]
                created_at = row[7]
                tokens_in = row[8] or 0
                tokens_out = row[9] or 0

                # Skip duplicate message entries (one message can have multiple parts)
                entry_key = f"{msg_id}_{part_type}_{tool_name or ''}"
                if entry_key in seen_messages:
                    continue
                seen_messages.add(entry_key)

                msg = {
                    "message_id": msg_id,
                    "role": role,
                    "agent": agent,
                    "type": part_type or "message",
                    "timestamp": created_at.isoformat() if created_at else None,
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                }

                if part_type == "text" and content:
                    msg["content"] = content
                elif part_type == "tool" and tool_name:
                    msg["tool_name"] = tool_name
                    msg["tool_status"] = tool_status

                messages.append(msg)

            return messages

        except Exception as e:
            debug(f"get_session_messages failed: {e}")
            return []

    def get_session_timeline(self, session_id: str) -> list[dict]:
        """Get timeline of events for a session.

        Args:
            session_id: The session ID to query

        Returns:
            List of timeline events sorted chronologically
        """
        try:
            events = []

            # Get messages
            msg_results = self._conn.execute(
                """
                SELECT id, role, created_at, tokens_input, tokens_output
                FROM messages
                WHERE session_id = ?
                ORDER BY created_at ASC
                """,
                [session_id],
            ).fetchall()

            for row in msg_results:
                events.append(
                    {
                        "type": "message",
                        "id": row[0],
                        "role": row[1],
                        "timestamp": row[2].isoformat() if row[2] else None,
                        "tokens_in": row[3] or 0,
                        "tokens_out": row[4] or 0,
                    }
                )

            # Get tool calls
            tool_results = self._conn.execute(
                """
                SELECT id, tool_name, tool_status, created_at, duration_ms
                FROM parts
                WHERE session_id = ? AND tool_name IS NOT NULL
                ORDER BY created_at ASC
                """,
                [session_id],
            ).fetchall()

            for row in tool_results:
                events.append(
                    {
                        "type": "tool",
                        "id": row[0],
                        "tool_name": row[1],
                        "status": row[2],
                        "timestamp": row[3].isoformat() if row[3] else None,
                        "duration_ms": row[4] or 0,
                    }
                )

            # Sort by timestamp
            events.sort(key=lambda e: e.get("timestamp") or "")
            return events

        except Exception as e:
            debug(f"get_session_timeline failed: {e}")
            return []

    def get_session_agents(self, session_id: str) -> list[dict]:
        """Get agents involved in a session.

        Args:
            session_id: The session ID to query

        Returns:
            List of agent info dicts
        """
        agents = self._get_session_agents_internal(session_id)
        return agents.get("agents", [])

    def get_session_tool_operations(self, session_id: str) -> list[dict]:
        """Get detailed tool operations for a session.

        Returns tool calls with their arguments extracted from content.
        Used for displaying tools in the session tree.

        Args:
            session_id: The session ID to query

        Returns:
            List of tool operation dicts with name, arguments, status, etc.
        """
        try:
            results = self._conn.execute(
                """
                SELECT 
                    p.id,
                    p.tool_name,
                    p.tool_status,
                    p.content,
                    p.arguments,
                    p.created_at,
                    p.duration_ms
                FROM parts p
                WHERE p.session_id = ? 
                  AND p.tool_name IS NOT NULL
                ORDER BY p.created_at ASC
                """,
                [session_id],
            ).fetchall()

            operations = []
            for row in results:
                tool_name = row[1]
                content = row[3] or ""
                arguments = row[4] or ""

                # Extract meaningful info from tool based on type
                display_info = self._extract_tool_display_info(
                    tool_name, content, arguments
                )

                operations.append(
                    {
                        "id": row[0],
                        "tool_name": tool_name,
                        "status": row[2] or "completed",
                        "display_info": display_info,
                        "timestamp": row[5].isoformat() if row[5] else None,
                        "duration_ms": row[6] or 0,
                    }
                )

            return operations

        except Exception as e:
            debug(f"get_session_tool_operations failed: {e}")
            return []
