"""
TracingDataService - Centralized service for tracing data.

Provides a unified interface for querying and aggregating tracing data
with standardized output format for dashboard consumption.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from .db import AnalyticsDB
from .queries.trace_queries import TraceQueries
from .queries.session_queries import SessionQueries
from .queries.tool_queries import ToolQueries
from .queries.delegation_queries import DelegationQueries
from ..utils.logger import debug, info

if TYPE_CHECKING:
    import duckdb


# Cost per 1K tokens (configurable, default Claude pricing)
DEFAULT_COST_PER_1K_INPUT = 0.003  # $3 per 1M input tokens
DEFAULT_COST_PER_1K_OUTPUT = 0.015  # $15 per 1M output tokens
DEFAULT_COST_PER_1K_CACHE = 0.0003  # $0.30 per 1M cache read tokens


@dataclass
class TracingConfig:
    """Configuration for tracing data calculations."""

    cost_per_1k_input: float = DEFAULT_COST_PER_1K_INPUT
    cost_per_1k_output: float = DEFAULT_COST_PER_1K_OUTPUT
    cost_per_1k_cache: float = DEFAULT_COST_PER_1K_CACHE


class TracingDataService:
    """Centralized service for tracing data queries.

    Provides standardized methods for retrieving session data,
    computing KPIs, and generating dashboard-ready output.

    All methods return dictionaries with a consistent structure:
    {
        "meta": {...},      # Query metadata
        "summary": {...},   # Key metrics for quick display
        "details": {...},   # Detailed breakdown
        "charts": {...}     # Pre-formatted chart data
    }
    """

    def __init__(
        self,
        db: Optional[AnalyticsDB] = None,
        config: Optional[TracingConfig] = None,
    ):
        """Initialize the tracing data service.

        Args:
            db: Analytics database instance. Creates new if not provided.
            config: Configuration for calculations. Uses defaults if not provided.
        """
        from .db import get_analytics_db

        self._db = db or get_analytics_db()
        self._config = config or TracingConfig()
        self._trace_q = TraceQueries(self._db)
        self._session_q = SessionQueries(self._db)
        self._tool_q = ToolQueries(self._db)
        self._delegation_q = DelegationQueries(self._db)

    @property
    def _conn(self) -> "duckdb.DuckDBPyConnection":
        """Get database connection."""
        return self._db.connect()

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

    def _extract_tool_display_info(
        self, tool_name: str, content: str, arguments: str
    ) -> str:
        """Extract display-friendly info from tool content/arguments.

        Args:
            tool_name: Name of the tool (read, edit, bash, etc.)
            content: Tool result content
            arguments: Tool arguments (JSON string)

        Returns:
            Short display string for the tool operation
        """
        import json
        import os

        # Try to parse arguments as JSON
        args = {}
        if arguments:
            try:
                args = json.loads(arguments)
            except (json.JSONDecodeError, TypeError):
                pass

        # Extract based on tool type
        if tool_name == "read":
            file_path = args.get("filePath", args.get("file_path", ""))
            if file_path:
                return os.path.basename(file_path)
            return "file"

        elif tool_name == "edit":
            file_path = args.get("filePath", args.get("file_path", ""))
            if file_path:
                return os.path.basename(file_path)
            return "file"

        elif tool_name == "write":
            file_path = args.get("filePath", args.get("file_path", ""))
            if file_path:
                return os.path.basename(file_path)
            return "file"

        elif tool_name == "bash":
            command = args.get("command", "")
            if command:
                # Truncate long commands
                short_cmd = command.split("\n")[0][:50]
                if len(command) > 50:
                    short_cmd += "..."
                return short_cmd
            return "command"

        elif tool_name == "glob":
            pattern = args.get("pattern", "")
            return pattern[:40] if pattern else "pattern"

        elif tool_name == "grep":
            pattern = args.get("pattern", "")
            return pattern[:40] if pattern else "search"

        elif tool_name == "task":
            subagent = args.get("subagent_type", args.get("description", ""))
            return subagent[:30] if subagent else "agent"

        elif tool_name in ("webfetch", "web_fetch"):
            url = args.get("url", "")
            if url:
                # Extract domain
                try:
                    from urllib.parse import urlparse

                    parsed = urlparse(url)
                    return parsed.netloc[:30]
                except Exception:
                    return url[:30]
            return "url"

        else:
            # For other tools, try to show something meaningful
            if args:
                first_value = str(list(args.values())[0])[:30]
                return first_value
            return ""

    def get_global_stats(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> dict:
        """Get global statistics for a time period.

        Args:
            start: Start of period (defaults to 30 days ago)
            end: End of period (defaults to now)

        Returns:
            Dict with aggregated statistics
        """
        from datetime import timedelta

        if end is None:
            end = datetime.now()
        if start is None:
            start = end - timedelta(days=30)

        try:
            # Sessions stats
            session_stats = self._conn.execute(
                """
                SELECT
                    COUNT(*) as total_sessions,
                    COUNT(DISTINCT directory) as unique_projects
                FROM sessions
                WHERE created_at >= ? AND created_at <= ?
                """,
                [start, end],
            ).fetchone()

            # Message/token stats
            token_stats = self._conn.execute(
                """
                SELECT
                    COUNT(*) as total_messages,
                    COALESCE(SUM(tokens_input), 0) as total_input,
                    COALESCE(SUM(tokens_output), 0) as total_output,
                    COALESCE(SUM(tokens_cache_read), 0) as total_cache
                FROM messages
                WHERE created_at >= ? AND created_at <= ?
                """,
                [start, end],
            ).fetchone()

            # Trace stats
            trace_stats = self._trace_q.get_trace_stats(start, end)

            # Tool stats
            tool_stats = self._conn.execute(
                """
                SELECT
                    COUNT(*) as total_calls,
                    COUNT(DISTINCT tool_name) as unique_tools
                FROM parts
                WHERE tool_name IS NOT NULL
                  AND created_at >= ? AND created_at <= ?
                """,
                [start, end],
            ).fetchone()

            total_tokens = (token_stats[1] or 0) + (token_stats[2] or 0)
            cost = self._calculate_cost(
                {
                    "input": token_stats[1] or 0,
                    "output": token_stats[2] or 0,
                    "cache_read": token_stats[3] or 0,
                }
            )

            return {
                "meta": {
                    "period": {
                        "start": start.isoformat(),
                        "end": end.isoformat(),
                    },
                    "generated_at": datetime.now().isoformat(),
                },
                "summary": {
                    "total_sessions": session_stats[0] or 0,
                    "unique_projects": session_stats[1] or 0,
                    "total_messages": token_stats[0] or 0,
                    "total_tokens": total_tokens,
                    "total_traces": trace_stats.get("total_traces", 0),
                    "total_tool_calls": tool_stats[0] or 0,
                    "estimated_cost_usd": round(cost, 2),
                },
                "details": {
                    "tokens": {
                        "input": token_stats[1] or 0,
                        "output": token_stats[2] or 0,
                        "cache_read": token_stats[3] or 0,
                    },
                    "traces": trace_stats,
                    "tools": {
                        "total_calls": tool_stats[0] or 0,
                        "unique_tools": tool_stats[1] or 0,
                    },
                },
            }

        except Exception as e:
            debug(f"get_global_stats failed: {e}")
            return {
                "meta": {"error": str(e)},
                "summary": {},
                "details": {},
            }

    def get_comparison(self, session_ids: list[str]) -> dict:
        """Compare metrics across multiple sessions.

        Args:
            session_ids: List of session IDs to compare

        Returns:
            Dict with comparison data for each session
        """
        comparisons = []
        for session_id in session_ids:
            summary = self.get_session_summary(session_id)
            comparisons.append(
                {
                    "session_id": session_id,
                    "title": summary["meta"].get("title", ""),
                    "metrics": summary["summary"],
                }
            )

        return {
            "meta": {
                "sessions_compared": len(session_ids),
                "generated_at": datetime.now().isoformat(),
            },
            "comparisons": comparisons,
        }

    def update_session_stats(self, session_id: str) -> None:
        """Update pre-calculated stats for a session.

        Called after data sync to refresh aggregation tables.

        Args:
            session_id: The session ID to update stats for
        """
        try:
            summary = self.get_session_summary(session_id)
            if not summary["summary"]:
                return

            s = summary["summary"]
            d = summary["details"]

            self._conn.execute(
                """
                INSERT OR REPLACE INTO session_stats (
                    session_id, total_messages, total_tokens_in, total_tokens_out,
                    total_tokens_cache, total_tool_calls, tool_success_rate,
                    total_file_reads, total_file_writes, unique_agents,
                    max_delegation_depth, estimated_cost_usd, duration_ms, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                [
                    session_id,
                    d["tokens"].get("message_count", 0),
                    d["tokens"].get("input", 0),
                    d["tokens"].get("output", 0),
                    d["tokens"].get("cache_read", 0),
                    s.get("total_tool_calls", 0),
                    d["tools"].get("success_rate", 0),
                    d["files"].get("total_reads", 0),
                    d["files"].get("total_writes", 0),
                    s.get("unique_agents", 0),
                    d["agents"].get("max_depth", 0),
                    s.get("estimated_cost_usd", 0),
                    s.get("duration_ms", 0),
                ],
            )
            debug(f"Updated session_stats for {session_id}")

        except Exception as e:
            debug(f"update_session_stats failed: {e}")

    def update_daily_stats(self, date: Optional[datetime] = None) -> None:
        """Update daily aggregation stats.

        Args:
            date: The date to update (defaults to today)
        """
        if date is None:
            date = datetime.now()
        date_str = date.strftime("%Y-%m-%d")

        try:
            # Calculate daily stats
            stats = self._conn.execute(
                """
                SELECT
                    COUNT(DISTINCT s.id) as sessions,
                    (SELECT COUNT(*) FROM agent_traces WHERE DATE(started_at) = ?) as traces,
                    COALESCE(SUM(m.tokens_input + m.tokens_output), 0) as tokens,
                    (SELECT COUNT(*) FROM parts WHERE DATE(created_at) = ? AND tool_name IS NOT NULL) as tools,
                    AVG(CASE WHEN s.duration_ms > 0 THEN s.duration_ms END) as avg_duration,
                    (SELECT CAST(SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS FLOAT) / 
                        NULLIF(COUNT(*), 0) * 100
                     FROM agent_traces WHERE DATE(started_at) = ?) as error_rate
                FROM sessions s
                LEFT JOIN messages m ON m.session_id = s.id AND DATE(m.created_at) = ?
                WHERE DATE(s.created_at) = ?
                """,
                [date_str, date_str, date_str, date_str, date_str],
            ).fetchone()

            if stats:
                self._conn.execute(
                    """
                    INSERT OR REPLACE INTO daily_stats (
                        date, total_sessions, total_traces, total_tokens,
                        total_tool_calls, avg_session_duration_ms, error_rate
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        date_str,
                        stats[0] or 0,
                        stats[1] or 0,
                        stats[2] or 0,
                        stats[3] or 0,
                        int(stats[4] or 0),
                        round(stats[5] or 0, 2),
                    ],
                )
                debug(f"Updated daily_stats for {date_str}")

        except Exception as e:
            debug(f"update_daily_stats failed: {e}")

    # --- Private helper methods ---

    def _get_session_info(self, session_id: str) -> Optional[dict]:
        """Get basic session information."""
        try:
            result = self._conn.execute(
                """
                SELECT id, title, directory, created_at, updated_at, parent_id
                FROM sessions
                WHERE id = ?
                """,
                [session_id],
            ).fetchone()

            if result:
                return {
                    "id": result[0],
                    "title": result[1],
                    "directory": result[2],
                    "created_at": result[3],
                    "updated_at": result[4],
                    "parent_id": result[5],
                    "status": "completed" if result[4] else "running",
                }
            return None
        except Exception:
            return None

    def _get_session_tokens_internal(self, session_id: str) -> dict:
        """Get token metrics for a session."""
        try:
            result = self._conn.execute(
                """
                SELECT
                    COUNT(*) as message_count,
                    COALESCE(SUM(tokens_input), 0) as input,
                    COALESCE(SUM(tokens_output), 0) as output,
                    COALESCE(SUM(tokens_reasoning), 0) as reasoning,
                    COALESCE(SUM(tokens_cache_read), 0) as cache_read,
                    COALESCE(SUM(tokens_cache_write), 0) as cache_write
                FROM messages
                WHERE session_id = ?
                """,
                [session_id],
            ).fetchone()

            input_tokens = result[1] or 0
            output_tokens = result[2] or 0
            cache_read = result[4] or 0
            total_input = input_tokens + cache_read

            # Get tokens by agent
            agent_results = self._conn.execute(
                """
                SELECT
                    COALESCE(agent, 'unknown') as agent,
                    SUM(tokens_input + tokens_output) as tokens
                FROM messages
                WHERE session_id = ?
                GROUP BY agent
                ORDER BY tokens DESC
                """,
                [session_id],
            ).fetchall()

            return {
                "message_count": result[0] or 0,
                "input": input_tokens,
                "output": output_tokens,
                "reasoning": result[3] or 0,
                "cache_read": cache_read,
                "cache_write": result[5] or 0,
                "total": input_tokens + output_tokens,
                "cache_hit_ratio": round(
                    (cache_read / total_input * 100) if total_input > 0 else 0, 1
                ),
                "by_agent": [
                    {"agent": row[0], "tokens": row[1] or 0} for row in agent_results
                ],
            }
        except Exception as e:
            debug(f"_get_session_tokens_internal failed: {e}")
            return {
                "message_count": 0,
                "input": 0,
                "output": 0,
                "reasoning": 0,
                "cache_read": 0,
                "cache_write": 0,
                "total": 0,
                "cache_hit_ratio": 0,
                "by_agent": [],
            }

    def _get_session_tools_internal(self, session_id: str) -> dict:
        """Get tool metrics for a session."""
        try:
            # Get overall stats
            result = self._conn.execute(
                """
                SELECT
                    COUNT(*) as total_calls,
                    COUNT(DISTINCT tool_name) as unique_tools,
                    SUM(CASE WHEN tool_status = 'completed' THEN 1 ELSE 0 END) as success,
                    SUM(CASE WHEN tool_status = 'error' THEN 1 ELSE 0 END) as errors,
                    AVG(duration_ms) as avg_duration
                FROM parts
                WHERE session_id = ? AND tool_name IS NOT NULL
                """,
                [session_id],
            ).fetchone()

            total = result[0] or 0
            success = result[2] or 0

            # Get top tools
            top_tools = self._conn.execute(
                """
                SELECT
                    tool_name,
                    COUNT(*) as count,
                    AVG(duration_ms) as avg_duration,
                    SUM(CASE WHEN tool_status = 'error' THEN 1 ELSE 0 END) as errors
                FROM parts
                WHERE session_id = ? AND tool_name IS NOT NULL
                GROUP BY tool_name
                ORDER BY count DESC
                LIMIT 10
                """,
                [session_id],
            ).fetchall()

            return {
                "total_calls": total,
                "unique_tools": result[1] or 0,
                "success_count": success,
                "error_count": result[3] or 0,
                "success_rate": round((success / total * 100) if total > 0 else 0, 1),
                "avg_duration_ms": int(result[4] or 0),
                "top_tools": [
                    {
                        "name": row[0],
                        "count": row[1],
                        "avg_duration_ms": int(row[2] or 0),
                        "error_count": row[3] or 0,
                    }
                    for row in top_tools
                ],
            }
        except Exception as e:
            debug(f"_get_session_tools_internal failed: {e}")
            return {
                "total_calls": 0,
                "unique_tools": 0,
                "success_count": 0,
                "error_count": 0,
                "success_rate": 0,
                "avg_duration_ms": 0,
                "top_tools": [],
            }

    def _get_session_files_internal(self, session_id: str) -> dict:
        """Get file operation metrics for a session."""
        try:
            # First try file_operations table
            result = self._conn.execute(
                """
                SELECT
                    SUM(CASE WHEN operation = 'read' THEN 1 ELSE 0 END) as reads,
                    SUM(CASE WHEN operation = 'write' THEN 1 ELSE 0 END) as writes,
                    SUM(CASE WHEN operation = 'edit' THEN 1 ELSE 0 END) as edits,
                    SUM(CASE WHEN risk_level IN ('high', 'critical') THEN 1 ELSE 0 END) as high_risk,
                    COUNT(DISTINCT file_path) as unique_files
                FROM file_operations
                WHERE session_id = ?
                """,
                [session_id],
            ).fetchone()

            # If no data, estimate from parts table
            if (
                not result
                or (result[0] or 0) + (result[1] or 0) + (result[2] or 0) == 0
            ):
                result = self._conn.execute(
                    """
                    SELECT
                        SUM(CASE WHEN tool_name = 'read' THEN 1 ELSE 0 END) as reads,
                        SUM(CASE WHEN tool_name = 'write' THEN 1 ELSE 0 END) as writes,
                        SUM(CASE WHEN tool_name = 'edit' THEN 1 ELSE 0 END) as edits,
                        0 as high_risk,
                        0 as unique_files
                    FROM parts
                    WHERE session_id = ? AND tool_name IN ('read', 'write', 'edit')
                    """,
                    [session_id],
                ).fetchone()

            # Get file extension breakdown
            ext_results = self._conn.execute(
                """
                SELECT
                    CASE
                        WHEN tool_name = 'read' THEN 'read'
                        WHEN tool_name = 'write' THEN 'write'
                        WHEN tool_name = 'edit' THEN 'edit'
                        ELSE 'other'
                    END as operation,
                    COUNT(*) as count
                FROM parts
                WHERE session_id = ? AND tool_name IN ('read', 'write', 'edit', 'glob', 'grep')
                GROUP BY operation
                """,
                [session_id],
            ).fetchall()

            return {
                "total_reads": result[0] or 0,
                "total_writes": result[1] or 0,
                "total_edits": result[2] or 0,
                "high_risk_count": result[3] or 0,
                "unique_files": result[4] or 0,
                "by_operation": [
                    {"operation": row[0], "count": row[1]} for row in ext_results
                ],
            }
        except Exception as e:
            debug(f"_get_session_files_internal failed: {e}")
            return {
                "total_reads": 0,
                "total_writes": 0,
                "total_edits": 0,
                "high_risk_count": 0,
                "unique_files": 0,
                "by_operation": [],
            }

    def _get_session_agents_internal(self, session_id: str) -> dict:
        """Get agent metrics for a session."""
        try:
            # Get unique agents from messages
            agent_results = self._conn.execute(
                """
                SELECT
                    COALESCE(agent, 'user') as agent,
                    COUNT(*) as message_count,
                    SUM(tokens_input + tokens_output) as tokens
                FROM messages
                WHERE session_id = ?
                GROUP BY agent
                ORDER BY message_count DESC
                """,
                [session_id],
            ).fetchall()

            # Get delegation depth from traces
            depth_result = self._conn.execute(
                """
                WITH RECURSIVE trace_depth AS (
                    SELECT trace_id, parent_trace_id, 0 as depth
                    FROM agent_traces
                    WHERE session_id = ? AND parent_trace_id IS NULL
                    
                    UNION ALL
                    
                    SELECT t.trace_id, t.parent_trace_id, td.depth + 1
                    FROM agent_traces t
                    JOIN trace_depth td ON t.parent_trace_id = td.trace_id
                    WHERE td.depth < 10
                )
                SELECT MAX(depth) FROM trace_depth
                """,
                [session_id],
            ).fetchone()

            return {
                "unique_count": len(agent_results),
                "max_depth": depth_result[0] or 0 if depth_result else 0,
                "agents": [
                    {
                        "agent": row[0],
                        "message_count": row[1],
                        "tokens": row[2] or 0,
                    }
                    for row in agent_results
                ],
            }
        except Exception as e:
            debug(f"_get_session_agents_internal failed: {e}")
            return {
                "unique_count": 0,
                "max_depth": 0,
                "agents": [],
            }

    def _calculate_duration(self, session_id: str) -> int:
        """Calculate session duration in milliseconds."""
        try:
            result = self._conn.execute(
                """
                SELECT
                    MIN(created_at) as first_event,
                    MAX(COALESCE(completed_at, created_at)) as last_event
                FROM messages
                WHERE session_id = ?
                """,
                [session_id],
            ).fetchone()

            if result and result[0] and result[1]:
                delta = result[1] - result[0]
                return int(delta.total_seconds() * 1000)
            return 0
        except Exception:
            return 0

    def _calculate_cost(self, tokens: dict) -> float:
        """Calculate estimated cost in USD."""
        input_cost = (tokens.get("input", 0) / 1000) * self._config.cost_per_1k_input
        output_cost = (tokens.get("output", 0) / 1000) * self._config.cost_per_1k_output
        cache_cost = (
            tokens.get("cache_read", 0) / 1000
        ) * self._config.cost_per_1k_cache
        return input_cost + output_cost + cache_cost

    def _tokens_chart_data(self, tokens: dict) -> list[dict]:
        """Format tokens data for pie chart."""
        return [
            {"label": "Input", "value": tokens.get("input", 0), "color": "#3498db"},
            {"label": "Output", "value": tokens.get("output", 0), "color": "#2ecc71"},
            {
                "label": "Cache",
                "value": tokens.get("cache_read", 0),
                "color": "#9b59b6",
            },
        ]

    def _tools_chart_data(self, tools: dict) -> list[dict]:
        """Format tools data for bar chart."""
        return [
            {"label": t["name"], "value": t["count"]}
            for t in tools.get("top_tools", [])[:5]
        ]

    def _files_chart_data(self, files: dict) -> list[dict]:
        """Format files data for pie chart."""
        return [
            {"label": "Read", "value": files.get("total_reads", 0), "color": "#3498db"},
            {
                "label": "Write",
                "value": files.get("total_writes", 0),
                "color": "#e74c3c",
            },
            {"label": "Edit", "value": files.get("total_edits", 0), "color": "#f39c12"},
        ]

    def _empty_response(self, session_id: str) -> dict:
        """Return empty response structure."""
        return {
            "meta": {
                "session_id": session_id,
                "generated_at": datetime.now().isoformat(),
                "error": "Session not found",
            },
            "summary": {},
            "details": {},
            "charts": {},
        }

    # --- Paginated list methods for API ---

    def _paginate(
        self,
        data: list,
        page: int = 1,
        per_page: int = 50,
        total: Optional[int] = None,
    ) -> dict:
        """Apply pagination to a list and return standardized response.

        Args:
            data: Full list of items (or pre-sliced if total is provided)
            page: Page number (1-based)
            per_page: Items per page (max 200)
            total: Total count if data is already sliced

        Returns:
            Dict with data and meta pagination info
        """
        per_page = min(per_page, 200)  # Max 200 per page
        page = max(page, 1)  # Min page 1

        if total is None:
            total = len(data)
            start = (page - 1) * per_page
            end = start + per_page
            paginated_data = data[start:end]
        else:
            paginated_data = data

        total_pages = (total + per_page - 1) // per_page if total > 0 else 0

        return {
            "success": True,
            "data": paginated_data,
            "meta": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages,
            },
        }

    def get_sessions_list(
        self,
        days: int = 30,
        limit: int = 100,
        page: int = 1,
        per_page: int = 50,
        search: Optional[str] = None,
    ) -> dict:
        """Get paginated list of sessions.

        Args:
            days: Filter sessions from last N days
            limit: Maximum total results
            page: Page number (1-based)
            per_page: Results per page
            search: Optional search query for title/directory

        Returns:
            Dict with data, meta (pagination info)
        """
        from datetime import timedelta

        try:
            start_date = datetime.now() - timedelta(days=days)
            offset = (page - 1) * per_page
            per_page = min(per_page, 200)

            # Build query with optional search
            if search:
                search_pattern = f"%{search}%"
                count_result = self._conn.execute(
                    """
                    SELECT COUNT(*) FROM sessions
                    WHERE created_at >= ?
                      AND (title LIKE ? OR directory LIKE ?)
                    """,
                    [start_date, search_pattern, search_pattern],
                ).fetchone()
                total = min(count_result[0] if count_result else 0, limit)

                rows = self._conn.execute(
                    """
                    SELECT id, title, directory, created_at, updated_at
                    FROM sessions
                    WHERE created_at >= ?
                      AND (title LIKE ? OR directory LIKE ?)
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    [start_date, search_pattern, search_pattern, per_page, offset],
                ).fetchall()
            else:
                count_result = self._conn.execute(
                    """
                    SELECT COUNT(*) FROM sessions
                    WHERE created_at >= ?
                    """,
                    [start_date],
                ).fetchone()
                total = min(count_result[0] if count_result else 0, limit)

                rows = self._conn.execute(
                    """
                    SELECT id, title, directory, created_at, updated_at
                    FROM sessions
                    WHERE created_at >= ?
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    [start_date, per_page, offset],
                ).fetchall()

            sessions = [
                {
                    "id": row[0],
                    "title": row[1],
                    "directory": row[2],
                    "created_at": row[3].isoformat() if row[3] else None,
                    "updated_at": row[4].isoformat() if row[4] else None,
                }
                for row in rows
            ]

            return self._paginate(sessions, page, per_page, total)

        except Exception as e:
            debug(f"get_sessions_list failed: {e}")
            return self._paginate([], page, per_page, 0)

    def get_traces_list(
        self,
        days: int = 30,
        limit: int = 500,
        page: int = 1,
        per_page: int = 50,
    ) -> dict:
        """Get paginated list of agent traces.

        Args:
            days: Filter traces from last N days
            limit: Maximum total results
            page: Page number (1-based)
            per_page: Results per page

        Returns:
            Dict with data, meta (pagination info)
        """
        from datetime import timedelta

        try:
            start_date = datetime.now() - timedelta(days=days)
            offset = (page - 1) * per_page
            per_page = min(per_page, 200)

            count_result = self._conn.execute(
                """
                SELECT COUNT(*) FROM agent_traces
                WHERE started_at >= ?
                """,
                [start_date],
            ).fetchone()
            total = min(count_result[0] if count_result else 0, limit)

            rows = self._conn.execute(
                """
                SELECT 
                    trace_id, session_id, parent_trace_id,
                    parent_agent, subagent_type,
                    started_at, ended_at, duration_ms,
                    tokens_in, tokens_out, status,
                    prompt_input, prompt_output
                FROM agent_traces
                WHERE started_at >= ?
                ORDER BY started_at DESC
                LIMIT ? OFFSET ?
                """,
                [start_date, per_page, offset],
            ).fetchall()

            traces = [
                {
                    "trace_id": row[0],
                    "session_id": row[1],
                    "parent_trace_id": row[2],
                    "parent_agent": row[3],
                    "subagent_type": row[4],
                    "started_at": row[5].isoformat() if row[5] else None,
                    "ended_at": row[6].isoformat() if row[6] else None,
                    "duration_ms": row[7],
                    "tokens_in": row[8],
                    "tokens_out": row[9],
                    "status": row[10],
                    "prompt_input": row[11],
                    "prompt_output": row[12],
                }
                for row in rows
            ]

            return self._paginate(traces, page, per_page, total)

        except Exception as e:
            debug(f"get_traces_list failed: {e}")
            return self._paginate([], page, per_page, 0)

    def get_delegations_list(
        self,
        days: int = 30,
        limit: int = 1000,
        page: int = 1,
        per_page: int = 50,
    ) -> dict:
        """Get paginated list of delegations.

        Args:
            days: Filter delegations from last N days
            limit: Maximum total results
            page: Page number (1-based)
            per_page: Results per page

        Returns:
            Dict with data, meta (pagination info)
        """
        from datetime import timedelta

        try:
            start_date = datetime.now() - timedelta(days=days)
            offset = (page - 1) * per_page
            per_page = min(per_page, 200)

            count_result = self._conn.execute(
                """
                SELECT COUNT(*) FROM delegations
                WHERE created_at >= ?
                """,
                [start_date],
            ).fetchone()
            total = min(count_result[0] if count_result else 0, limit)

            rows = self._conn.execute(
                """
                SELECT 
                    id, session_id, parent_agent, child_agent,
                    child_session_id, created_at
                FROM delegations
                WHERE created_at >= ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                [start_date, per_page, offset],
            ).fetchall()

            delegations = [
                {
                    "id": row[0],
                    "parent_session_id": row[1],
                    "parent_agent": row[2],
                    "child_agent": row[3],
                    "child_session_id": row[4],
                    "created_at": row[5].isoformat() if row[5] else None,
                }
                for row in rows
            ]

            return self._paginate(delegations, page, per_page, total)

        except Exception as e:
            debug(f"get_delegations_list failed: {e}")
            return self._paginate([], page, per_page, 0)

    def get_trace_details(self, trace_id: str) -> Optional[dict]:
        """Get full details of a specific trace.

        Args:
            trace_id: The trace ID to query

        Returns:
            Dict with trace details or None if not found
        """
        try:
            row = self._conn.execute(
                """
                SELECT 
                    t.trace_id, t.session_id, t.parent_trace_id,
                    t.parent_agent, t.subagent_type,
                    t.started_at, t.ended_at, t.duration_ms,
                    t.tokens_in, t.tokens_out, t.status,
                    t.prompt_input, t.prompt_output,
                    t.child_session_id,
                    s.title as session_title,
                    s.directory as session_directory
                FROM agent_traces t
                LEFT JOIN sessions s ON t.session_id = s.id
                WHERE t.trace_id = ?
                """,
                [trace_id],
            ).fetchone()

            if not row:
                return None

            # Get child traces
            children = self._conn.execute(
                """
                SELECT trace_id, subagent_type, status, duration_ms
                FROM agent_traces
                WHERE parent_trace_id = ?
                ORDER BY started_at ASC
                """,
                [trace_id],
            ).fetchall()

            # Get tools for this trace's session
            tools = []
            if row[13]:  # child_session_id
                tool_rows = self._conn.execute(
                    """
                    SELECT tool_name, tool_status, duration_ms, created_at
                    FROM parts
                    WHERE session_id = ? AND tool_name IS NOT NULL
                    ORDER BY created_at ASC
                    """,
                    [row[13]],
                ).fetchall()
                tools = [
                    {
                        "tool_name": t[0],
                        "status": t[1],
                        "duration_ms": t[2],
                        "created_at": t[3].isoformat() if t[3] else None,
                    }
                    for t in tool_rows
                ]

            return {
                "trace_id": row[0],
                "session_id": row[1],
                "parent_trace_id": row[2],
                "parent_agent": row[3],
                "subagent_type": row[4],
                "started_at": row[5].isoformat() if row[5] else None,
                "ended_at": row[6].isoformat() if row[6] else None,
                "duration_ms": row[7],
                "tokens_in": row[8],
                "tokens_out": row[9],
                "status": row[10],
                "prompt_input": row[11],
                "prompt_output": row[12],
                "child_session_id": row[13],
                "session_title": row[14],
                "session_directory": row[15],
                "children": [
                    {
                        "trace_id": c[0],
                        "subagent_type": c[1],
                        "status": c[2],
                        "duration_ms": c[3],
                    }
                    for c in children
                ],
                "tools": tools,
            }

        except Exception as e:
            debug(f"get_trace_details failed: {e}")
            return None

    def get_daily_stats(self, days: int = 7) -> list[dict]:
        """Get aggregated statistics per day.

        Args:
            days: Number of days to retrieve

        Returns:
            List of daily stat dicts
        """
        from datetime import timedelta

        try:
            start_date = datetime.now() - timedelta(days=days)

            rows = self._conn.execute(
                """
                SELECT 
                    CAST(started_at AS DATE) as date,
                    COUNT(*) as traces,
                    SUM(tokens_in + tokens_out) as tokens,
                    AVG(duration_ms) as avg_duration_ms,
                    SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors
                FROM agent_traces
                WHERE started_at >= ?
                GROUP BY CAST(started_at AS DATE)
                ORDER BY date DESC
                """,
                [start_date],
            ).fetchall()

            # Get session counts separately
            session_rows = self._conn.execute(
                """
                SELECT 
                    CAST(created_at AS DATE) as date,
                    COUNT(*) as sessions
                FROM sessions
                WHERE created_at >= ?
                GROUP BY CAST(created_at AS DATE)
                """,
                [start_date],
            ).fetchall()
            session_by_date = {
                row[0].strftime("%Y-%m-%d"): row[1] for row in session_rows
            }

            # Get tool counts separately
            tool_rows = self._conn.execute(
                """
                SELECT 
                    CAST(created_at AS DATE) as date,
                    COUNT(*) as tool_calls
                FROM parts
                WHERE tool_name IS NOT NULL AND created_at >= ?
                GROUP BY CAST(created_at AS DATE)
                """,
                [start_date],
            ).fetchall()
            tools_by_date = {row[0].strftime("%Y-%m-%d"): row[1] for row in tool_rows}

            return [
                {
                    "date": row[0].strftime("%Y-%m-%d") if row[0] else None,
                    "sessions": session_by_date.get(
                        row[0].strftime("%Y-%m-%d") if row[0] else "", 0
                    ),
                    "traces": row[1] or 0,
                    "tokens": row[2] or 0,
                    "avg_duration_ms": int(row[3] or 0),
                    "errors": row[4] or 0,
                    "tool_calls": tools_by_date.get(
                        row[0].strftime("%Y-%m-%d") if row[0] else "", 0
                    ),
                }
                for row in rows
            ]

        except Exception as e:
            debug(f"get_daily_stats failed: {e}")
            return []

    def search_sessions(self, query: str, limit: int = 20) -> list[dict]:
        """Search sessions by title or directory.

        Args:
            query: Search query string
            limit: Maximum results to return

        Returns:
            List of matching session dicts
        """
        try:
            search_pattern = f"%{query}%"
            rows = self._conn.execute(
                """
                SELECT 
                    s.id, s.title, s.directory, s.created_at, s.updated_at,
                    (SELECT COUNT(*) FROM messages WHERE session_id = s.id) as message_count,
                    (SELECT SUM(tokens_input + tokens_output) FROM messages WHERE session_id = s.id) as total_tokens
                FROM sessions s
                WHERE s.title LIKE ? OR s.directory LIKE ?
                ORDER BY s.created_at DESC
                LIMIT ?
                """,
                [search_pattern, search_pattern, limit],
            ).fetchall()

            return [
                {
                    "id": row[0],
                    "title": row[1],
                    "directory": row[2],
                    "created_at": row[3].isoformat() if row[3] else None,
                    "updated_at": row[4].isoformat() if row[4] else None,
                    "message_count": row[5] or 0,
                    "total_tokens": row[6] or 0,
                }
                for row in rows
            ]

        except Exception as e:
            debug(f"search_sessions failed: {e}")
            return []

    def get_session_cost_breakdown(self, session_id: str) -> dict:
        """Get detailed cost breakdown for a session.

        Args:
            session_id: The session ID to query

        Returns:
            Dict with cost breakdown by agent and token type
        """
        try:
            # Get token breakdown
            tokens = self._get_session_tokens_internal(session_id)

            # Calculate costs
            input_cost = (tokens["input"] / 1000) * self._config.cost_per_1k_input
            output_cost = (tokens["output"] / 1000) * self._config.cost_per_1k_output
            cache_cost = (tokens["cache_read"] / 1000) * self._config.cost_per_1k_cache
            total_cost = input_cost + output_cost + cache_cost

            # Get cost by agent
            by_agent = []
            for agent_data in tokens.get("by_agent", []):
                agent_tokens = agent_data.get("tokens", 0)
                # Estimate input/output split (rough 60/40 based on typical usage)
                est_input = int(agent_tokens * 0.6)
                est_output = agent_tokens - est_input
                agent_cost = (est_input / 1000) * self._config.cost_per_1k_input + (
                    est_output / 1000
                ) * self._config.cost_per_1k_output
                by_agent.append(
                    {
                        "agent": agent_data.get("agent", "unknown"),
                        "tokens": agent_tokens,
                        "estimated_cost_usd": round(agent_cost, 4),
                    }
                )

            return {
                "session_id": session_id,
                "total_cost_usd": round(total_cost, 4),
                "breakdown": {
                    "input": {
                        "tokens": tokens["input"],
                        "rate_per_1k": self._config.cost_per_1k_input,
                        "cost_usd": round(input_cost, 4),
                    },
                    "output": {
                        "tokens": tokens["output"],
                        "rate_per_1k": self._config.cost_per_1k_output,
                        "cost_usd": round(output_cost, 4),
                    },
                    "cache_read": {
                        "tokens": tokens["cache_read"],
                        "rate_per_1k": self._config.cost_per_1k_cache,
                        "cost_usd": round(cache_cost, 4),
                    },
                },
                "by_agent": by_agent,
                "cache_savings_usd": round(
                    (tokens["cache_read"] / 1000)
                    * (self._config.cost_per_1k_input - self._config.cost_per_1k_cache),
                    4,
                ),
            }

        except Exception as e:
            debug(f"get_session_cost_breakdown failed: {e}")
            return {
                "session_id": session_id,
                "total_cost_usd": 0,
                "breakdown": {},
                "by_agent": [],
                "cache_savings_usd": 0,
            }
