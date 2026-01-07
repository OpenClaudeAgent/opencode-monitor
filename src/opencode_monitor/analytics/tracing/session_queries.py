"""Session query methods for TracingDataService.

Contains all methods related to querying individual session data.
"""

import json
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

    # ===== Plan 34: Enriched Parts Methods =====

    def get_session_reasoning(self, session_id: str) -> dict:
        """Get reasoning parts (agent thought process) for a session.

        Returns the internal reasoning/thinking of the agent with
        Anthropic cryptographic signatures when available.

        Args:
            session_id: The session ID to query

        Returns:
            Dict with meta, summary, and list of reasoning entries
        """
        try:
            results = self._conn.execute(
                """
                SELECT 
                    id,
                    reasoning_text,
                    anthropic_signature,
                    created_at
                FROM parts
                WHERE session_id = ?
                  AND part_type = 'reasoning'
                  AND reasoning_text IS NOT NULL
                ORDER BY created_at ASC
                """,
                [session_id],
            ).fetchall()

            entries = []
            for row in results:
                entries.append(
                    {
                        "id": row[0],
                        "text": row[1],
                        "signature": row[2],
                        "timestamp": row[3].isoformat() if row[3] else None,
                        "has_signature": row[2] is not None,
                    }
                )

            return {
                "meta": {
                    "session_id": session_id,
                    "count": len(entries),
                    "generated_at": datetime.now().isoformat(),
                },
                "summary": {
                    "total_entries": len(entries),
                    "signed_entries": sum(1 for e in entries if e["has_signature"]),
                    "total_chars": sum(len(e["text"] or "") for e in entries),
                },
                "details": entries,
            }

        except Exception as e:
            debug(f"get_session_reasoning failed: {e}")
            return {
                "meta": {"session_id": session_id, "count": 0, "error": str(e)},
                "summary": {"total_entries": 0, "signed_entries": 0, "total_chars": 0},
                "details": [],
            }

    def get_session_steps(self, session_id: str) -> dict:
        """Get step events timeline with precise token counts and costs.

        Step events capture the beginning and end of each agent step,
        with accurate token counts and costs from step-finish events.

        Args:
            session_id: The session ID to query

        Returns:
            Dict with meta, summary (totals), and list of step events
        """
        try:
            results = self._conn.execute(
                """
                SELECT 
                    id,
                    event_type,
                    reason,
                    snapshot_hash,
                    cost,
                    tokens_input,
                    tokens_output,
                    tokens_reasoning,
                    tokens_cache_read,
                    tokens_cache_write,
                    created_at
                FROM step_events
                WHERE session_id = ?
                ORDER BY created_at ASC
                """,
                [session_id],
            ).fetchall()

            events = []
            total_cost = 0.0
            total_tokens_in = 0
            total_tokens_out = 0
            total_tokens_reasoning = 0

            for row in results:
                event_type = row[1]
                cost = float(row[4] or 0)

                if event_type == "finish":
                    total_cost += cost
                    total_tokens_in += row[5] or 0
                    total_tokens_out += row[6] or 0
                    total_tokens_reasoning += row[7] or 0

                events.append(
                    {
                        "id": row[0],
                        "event_type": event_type,
                        "reason": row[2],
                        "snapshot_hash": row[3],
                        "cost": cost,
                        "tokens": {
                            "input": row[5] or 0,
                            "output": row[6] or 0,
                            "reasoning": row[7] or 0,
                            "cache_read": row[8] or 0,
                            "cache_write": row[9] or 0,
                        },
                        "timestamp": row[10].isoformat() if row[10] else None,
                    }
                )

            return {
                "meta": {
                    "session_id": session_id,
                    "count": len(events),
                    "generated_at": datetime.now().isoformat(),
                },
                "summary": {
                    "total_steps": len(
                        [e for e in events if e["event_type"] == "finish"]
                    ),
                    "total_cost": round(total_cost, 6),
                    "total_tokens_input": total_tokens_in,
                    "total_tokens_output": total_tokens_out,
                    "total_tokens_reasoning": total_tokens_reasoning,
                    "total_tokens": total_tokens_in
                    + total_tokens_out
                    + total_tokens_reasoning,
                },
                "details": events,
            }

        except Exception as e:
            debug(f"get_session_steps failed: {e}")
            return {
                "meta": {"session_id": session_id, "count": 0, "error": str(e)},
                "summary": {
                    "total_steps": 0,
                    "total_cost": 0,
                    "total_tokens_input": 0,
                    "total_tokens_output": 0,
                    "total_tokens_reasoning": 0,
                    "total_tokens": 0,
                },
                "details": [],
            }

    def get_session_git_history(self, session_id: str) -> dict:
        """Get git patches history for a session.

        Returns all git commits made during the session with their
        affected files. Useful for understanding code changes.

        Args:
            session_id: The session ID to query

        Returns:
            Dict with meta, summary, and list of patches
        """
        try:
            results = self._conn.execute(
                """
                SELECT 
                    id,
                    git_hash,
                    files,
                    created_at
                FROM patches
                WHERE session_id = ?
                ORDER BY created_at ASC
                """,
                [session_id],
            ).fetchall()

            patches = []
            all_files = set()

            for row in results:
                files = row[2] or []
                # DuckDB returns list for VARCHAR[]
                if isinstance(files, list):
                    all_files.update(files)
                    file_list = files
                else:
                    file_list = []

                patches.append(
                    {
                        "id": row[0],
                        "hash": row[1],
                        "files": file_list,
                        "file_count": len(file_list),
                        "timestamp": row[3].isoformat() if row[3] else None,
                    }
                )

            return {
                "meta": {
                    "session_id": session_id,
                    "commits": len(patches),
                    "generated_at": datetime.now().isoformat(),
                },
                "summary": {
                    "total_commits": len(patches),
                    "unique_files": len(all_files),
                    "files_list": sorted(all_files)[:50],  # Limit for response size
                },
                "details": patches,
            }

        except Exception as e:
            debug(f"get_session_git_history failed: {e}")
            return {
                "meta": {"session_id": session_id, "commits": 0, "error": str(e)},
                "summary": {"total_commits": 0, "unique_files": 0, "files_list": []},
                "details": [],
            }

    def get_session_precise_cost(self, session_id: str) -> dict:
        """Get precise cost calculated from step-finish events.

        This provides more accurate cost data than message-level estimates
        by using the actual cost values from step-finish events.

        Args:
            session_id: The session ID to query

        Returns:
            Dict with meta, cost breakdown, and comparison with estimates
        """
        try:
            # Get precise cost from step_events
            step_result = self._conn.execute(
                """
                SELECT 
                    SUM(cost) as total_cost,
                    SUM(tokens_input) as tokens_in,
                    SUM(tokens_output) as tokens_out,
                    SUM(tokens_reasoning) as tokens_reasoning,
                    SUM(tokens_cache_read) as cache_read,
                    SUM(tokens_cache_write) as cache_write,
                    COUNT(*) as step_count
                FROM step_events
                WHERE session_id = ? AND event_type = 'finish'
                """,
                [session_id],
            ).fetchone()

            # Get estimated cost from messages (for comparison)
            msg_result = self._conn.execute(
                """
                SELECT 
                    SUM(cost) as estimated_cost,
                    SUM(tokens_input) as tokens_in,
                    SUM(tokens_output) as tokens_out
                FROM messages
                WHERE session_id = ?
                """,
                [session_id],
            ).fetchone()

            precise_cost = float(step_result[0] or 0) if step_result else 0
            estimated_cost = float(msg_result[0] or 0) if msg_result else 0

            # Calculate difference
            cost_diff = precise_cost - estimated_cost
            cost_diff_pct = (
                (cost_diff / estimated_cost * 100) if estimated_cost > 0 else 0
            )

            return {
                "meta": {
                    "session_id": session_id,
                    "generated_at": datetime.now().isoformat(),
                    "source": "step_events"
                    if step_result and step_result[6]
                    else "messages",
                },
                "precise": {
                    "cost_usd": round(precise_cost, 6),
                    "tokens_input": step_result[1] or 0 if step_result else 0,
                    "tokens_output": step_result[2] or 0 if step_result else 0,
                    "tokens_reasoning": step_result[3] or 0 if step_result else 0,
                    "tokens_cache_read": step_result[4] or 0 if step_result else 0,
                    "tokens_cache_write": step_result[5] or 0 if step_result else 0,
                    "step_count": step_result[6] or 0 if step_result else 0,
                },
                "estimated": {
                    "cost_usd": round(estimated_cost, 6),
                    "tokens_input": msg_result[1] or 0 if msg_result else 0,
                    "tokens_output": msg_result[2] or 0 if msg_result else 0,
                },
                "comparison": {
                    "difference_usd": round(cost_diff, 6),
                    "difference_pct": round(cost_diff_pct, 2),
                    "has_precise_data": bool(step_result and step_result[6]),
                },
            }

        except Exception as e:
            debug(f"get_session_precise_cost failed: {e}")
            return {
                "meta": {"session_id": session_id, "error": str(e)},
                "precise": {"cost_usd": 0, "tokens_input": 0, "tokens_output": 0},
                "estimated": {"cost_usd": 0, "tokens_input": 0, "tokens_output": 0},
                "comparison": {
                    "difference_usd": 0,
                    "difference_pct": 0,
                    "has_precise_data": False,
                },
            }

    # ===== Plan 45: Timeline & Aggregation Methods =====

    def get_session_timeline_full(
        self, session_id: str, include_children: bool = False, depth: int = 1
    ) -> dict:
        """Get complete chronological timeline for a session.

        Returns all events (prompts, reasoning, tool calls, responses) in order,
        with full content (no truncation).

        Args:
            session_id: The session ID to query
            include_children: Whether to include child session timelines recursively
            depth: Maximum depth for child session recursion (default 1)

        Returns:
            Dict with meta, session info, timeline events, and summary
        """
        try:
            # Get session info
            session = self._get_session_info(session_id)
            if not session:
                return {
                    "success": False,
                    "error": f"Session {session_id} not found",
                    "data": None,
                }

            # Get exchanges for this session
            exchanges_result = self._conn.execute(
                """
                SELECT 
                    id, exchange_number, user_message_id, assistant_message_id,
                    prompt_input, prompt_output,
                    started_at, ended_at, duration_ms,
                    tokens_in, tokens_out, tokens_reasoning, cost,
                    tool_count, reasoning_count, agent, model_id
                FROM exchanges
                WHERE session_id = ?
                ORDER BY exchange_number ASC
                """,
                [session_id],
            ).fetchall()

            timeline = []
            total_tokens = 0
            total_cost = 0.0
            total_tool_calls = 0
            total_reasoning = 0

            for ex_row in exchanges_result:
                exchange_num = ex_row[1]
                user_msg_id = ex_row[2]
                assistant_msg_id = ex_row[3]
                tokens_in = ex_row[9] or 0
                tokens_out = ex_row[10] or 0
                tokens_reasoning = ex_row[11] or 0
                cost = float(ex_row[12] or 0)
                tool_count = ex_row[13] or 0
                reasoning_count = ex_row[14] or 0

                total_tokens += tokens_in + tokens_out + tokens_reasoning
                total_cost += cost
                total_tool_calls += tool_count
                total_reasoning += reasoning_count

                # Add user prompt event
                if ex_row[4]:  # prompt_input
                    timeline.append(
                        {
                            "type": "user_prompt",
                            "exchange_number": exchange_num,
                            "timestamp": ex_row[6].isoformat() if ex_row[6] else None,
                            "content": ex_row[4],
                            "message_id": user_msg_id,
                        }
                    )

                # Get exchange trace events (reasoning, tools, etc.)
                trace_events = self._conn.execute(
                    """
                    SELECT event_type, event_order, event_data, timestamp,
                           duration_ms, tokens_in, tokens_out
                    FROM exchange_traces
                    WHERE exchange_id = ?
                    ORDER BY event_order ASC
                    """,
                    [ex_row[0]],
                ).fetchall()

                for evt in trace_events:
                    evt_type = evt[0]
                    # Parse event_data JSON string
                    raw_data = evt[2]
                    if isinstance(raw_data, str):
                        try:
                            evt_data = json.loads(raw_data)
                        except (json.JSONDecodeError, TypeError):
                            evt_data = {}
                    elif isinstance(raw_data, dict):
                        evt_data = raw_data
                    else:
                        evt_data = {}

                    if evt_type == "reasoning":
                        timeline.append(
                            {
                                "type": "reasoning",
                                "exchange_number": exchange_num,
                                "timestamp": evt[3].isoformat() if evt[3] else None,
                                "entries": [
                                    {
                                        "text": evt_data.get("text", ""),
                                        "has_signature": evt_data.get(
                                            "has_signature", False
                                        ),
                                        "signature": evt_data.get("signature"),
                                    }
                                ],
                            }
                        )
                    elif evt_type == "tool_call":
                        timeline.append(
                            {
                                "type": "tool_call",
                                "exchange_number": exchange_num,
                                "timestamp": evt[3].isoformat() if evt[3] else None,
                                "tool_name": evt_data.get("tool_name", ""),
                                "status": evt_data.get("status", "completed"),
                                "arguments": evt_data.get("arguments"),
                                "result_summary": evt_data.get("result_summary", ""),
                                "duration_ms": evt[4] or 0,
                                "child_session_id": evt_data.get("child_session_id"),
                            }
                        )
                    elif evt_type == "step_finish":
                        timeline.append(
                            {
                                "type": "step_finish",
                                "exchange_number": exchange_num,
                                "timestamp": evt[3].isoformat() if evt[3] else None,
                                "reason": evt_data.get("reason", ""),
                                "tokens": {
                                    "input": evt[5] or 0,
                                    "output": evt[6] or 0,
                                    "reasoning": evt_data.get("tokens_reasoning", 0),
                                    "cache_read": evt_data.get("tokens_cache_read", 0),
                                    "cache_write": evt_data.get(
                                        "tokens_cache_write", 0
                                    ),
                                },
                                "cost": evt_data.get("cost", 0),
                            }
                        )
                    elif evt_type == "patch":
                        timeline.append(
                            {
                                "type": "patch",
                                "exchange_number": exchange_num,
                                "timestamp": evt[3].isoformat() if evt[3] else None,
                                "git_hash": evt_data.get("git_hash", ""),
                                "files": evt_data.get("files", []),
                            }
                        )

                # Add assistant response event
                if ex_row[5]:  # prompt_output
                    timeline.append(
                        {
                            "type": "assistant_response",
                            "exchange_number": exchange_num,
                            "timestamp": ex_row[7].isoformat() if ex_row[7] else None,
                            "content": ex_row[5],
                            "tokens_out": tokens_out,
                        }
                    )

            # If no exchanges, fall back to direct parts query
            if not exchanges_result:
                timeline = self._build_timeline_from_parts(session_id)
                # Recalculate totals from parts
                stats = self._calculate_timeline_stats(session_id)
                total_tokens = stats["total_tokens"]
                total_cost = stats["total_cost"]
                total_tool_calls = stats["total_tool_calls"]
                total_reasoning = stats["total_reasoning"]

            # Include child session timelines if requested
            delegations = []
            if include_children and depth > 0:
                child_sessions = self._conn.execute(
                    """
                    SELECT DISTINCT child_session_id
                    FROM delegations
                    WHERE session_id = ? AND child_session_id IS NOT NULL
                    """,
                    [session_id],
                ).fetchall()

                for child_row in child_sessions:
                    child_id = child_row[0]
                    child_timeline = self.get_session_timeline_full(
                        child_id, include_children=True, depth=depth - 1
                    )
                    if child_timeline.get("success", True):
                        delegations.append(
                            {
                                "child_session_id": child_id,
                                "timeline": child_timeline.get("data", {}).get(
                                    "timeline", []
                                ),
                            }
                        )

            return {
                "success": True,
                "data": {
                    "meta": {
                        "session_id": session_id,
                        "generated_at": datetime.now().isoformat(),
                        "title": session.get("title", ""),
                        "directory": session.get("directory", ""),
                    },
                    "session": {
                        "id": session_id,
                        "title": session.get("title", ""),
                        "directory": session.get("directory", ""),
                        "agent": session.get("agent"),
                        "model": session.get("model_id"),
                        "started_at": session.get("created_at"),
                        "ended_at": session.get("updated_at"),
                        "duration_ms": session.get("duration_ms", 0),
                        "parent_session_id": session.get("parent_id"),
                        "depth": 0,
                    },
                    "timeline": timeline,
                    "delegations": delegations,
                    "summary": {
                        "total_exchanges": len(exchanges_result),
                        "total_tokens": total_tokens,
                        "total_cost_usd": round(total_cost, 6),
                        "total_tool_calls": total_tool_calls,
                        "total_reasoning_entries": total_reasoning,
                        "delegations": len(delegations),
                    },
                },
            }

        except Exception as e:
            debug(f"get_session_timeline_full failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": None,
            }

    def _build_timeline_from_parts(self, session_id: str) -> list[dict]:
        """Build timeline directly from parts table when exchanges not available."""
        timeline = []

        # Get all parts for this session
        parts = self._conn.execute(
            """
            SELECT 
                p.id, p.part_type, p.content, p.tool_name, p.tool_status,
                p.arguments, p.result_summary, p.reasoning_text,
                p.anthropic_signature, p.duration_ms, p.created_at,
                m.role
            FROM parts p
            LEFT JOIN messages m ON p.message_id = m.id
            WHERE p.session_id = ?
            ORDER BY p.created_at ASC
            """,
            [session_id],
        ).fetchall()

        exchange_num = 0
        last_role = None

        for part in parts:
            part_type = part[1]
            role = part[11]

            # Increment exchange number on user prompts
            if part_type == "text" and role == "user":
                exchange_num += 1
                timeline.append(
                    {
                        "type": "user_prompt",
                        "exchange_number": exchange_num,
                        "timestamp": part[10].isoformat() if part[10] else None,
                        "content": part[2] or "",
                        "message_id": None,
                    }
                )
            elif part_type == "reasoning":
                timeline.append(
                    {
                        "type": "reasoning",
                        "exchange_number": exchange_num,
                        "timestamp": part[10].isoformat() if part[10] else None,
                        "entries": [
                            {
                                "text": part[7] or "",
                                "has_signature": part[8] is not None,
                                "signature": part[8],
                            }
                        ],
                    }
                )
            elif part_type == "tool":
                timeline.append(
                    {
                        "type": "tool_call",
                        "exchange_number": exchange_num,
                        "timestamp": part[10].isoformat() if part[10] else None,
                        "tool_name": part[3] or "",
                        "status": part[4] or "completed",
                        "arguments": part[5],
                        "result_summary": part[6] or "",
                        "duration_ms": part[9] or 0,
                    }
                )
            elif part_type == "text" and role == "assistant":
                timeline.append(
                    {
                        "type": "assistant_response",
                        "exchange_number": exchange_num,
                        "timestamp": part[10].isoformat() if part[10] else None,
                        "content": part[2] or "",
                        "tokens_out": 0,
                    }
                )

            last_role = role

        return timeline

    def _calculate_timeline_stats(self, session_id: str) -> dict:
        """Calculate timeline stats from raw tables."""
        # Tokens
        tokens_result = self._conn.execute(
            """
            SELECT 
                COALESCE(SUM(tokens_input), 0) + 
                COALESCE(SUM(tokens_output), 0) + 
                COALESCE(SUM(tokens_reasoning), 0) as total_tokens
            FROM messages WHERE session_id = ?
            """,
            [session_id],
        ).fetchone()

        # Cost
        cost_result = self._conn.execute(
            """
            SELECT COALESCE(SUM(cost), 0) as total_cost
            FROM step_events WHERE session_id = ? AND event_type = 'finish'
            """,
            [session_id],
        ).fetchone()

        # Tool calls
        tools_result = self._conn.execute(
            """
            SELECT COUNT(*) FROM parts
            WHERE session_id = ? AND part_type = 'tool'
            """,
            [session_id],
        ).fetchone()

        # Reasoning
        reasoning_result = self._conn.execute(
            """
            SELECT COUNT(*) FROM parts
            WHERE session_id = ? AND part_type = 'reasoning'
            """,
            [session_id],
        ).fetchone()

        return {
            "total_tokens": tokens_result[0] if tokens_result else 0,
            "total_cost": float(cost_result[0]) if cost_result else 0.0,
            "total_tool_calls": tools_result[0] if tools_result else 0,
            "total_reasoning": reasoning_result[0] if reasoning_result else 0,
        }

    def get_session_exchanges(self, session_id: str) -> dict:
        """Get conversation turns (user->assistant pairs) for a session.

        Returns all exchanges with full prompt_input and prompt_output content.

        Args:
            session_id: The session ID to query

        Returns:
            Dict with meta and list of exchanges
        """
        try:
            # First try exchanges table
            exchanges = self._conn.execute(
                """
                SELECT 
                    id, exchange_number, user_message_id, assistant_message_id,
                    prompt_input, prompt_output,
                    started_at, ended_at, duration_ms,
                    tokens_in, tokens_out, tokens_reasoning, cost,
                    tool_count, reasoning_count, agent, model_id
                FROM exchanges
                WHERE session_id = ?
                ORDER BY exchange_number ASC
                """,
                [session_id],
            ).fetchall()

            if exchanges:
                exchange_list = []
                for row in exchanges:
                    exchange_list.append(
                        {
                            "number": row[1],
                            "user_message_id": row[2],
                            "assistant_message_id": row[3],
                            "user_prompt": row[4] or "",
                            "assistant_response": row[5] or "",
                            "started_at": row[6].isoformat() if row[6] else None,
                            "ended_at": row[7].isoformat() if row[7] else None,
                            "duration_ms": row[8] or 0,
                            "tokens": {
                                "input": row[9] or 0,
                                "output": row[10] or 0,
                                "reasoning": row[11] or 0,
                            },
                            "cost": float(row[12] or 0),
                            "tool_count": row[13] or 0,
                            "reasoning_count": row[14] or 0,
                            "agent": row[15],
                            "model_id": row[16],
                        }
                    )

                return {
                    "meta": {
                        "session_id": session_id,
                        "generated_at": datetime.now().isoformat(),
                        "count": len(exchange_list),
                    },
                    "exchanges": exchange_list,
                }

            # Fallback: build exchanges from messages/parts
            exchange_list = self._build_exchanges_from_messages(session_id)

            return {
                "meta": {
                    "session_id": session_id,
                    "generated_at": datetime.now().isoformat(),
                    "count": len(exchange_list),
                    "source": "messages_fallback",
                },
                "exchanges": exchange_list,
            }

        except Exception as e:
            debug(f"get_session_exchanges failed: {e}")
            return {
                "meta": {
                    "session_id": session_id,
                    "count": 0,
                    "error": str(e),
                },
                "exchanges": [],
            }

    def _build_exchanges_from_messages(self, session_id: str) -> list[dict]:
        """Build exchange list from messages when exchanges table empty."""
        # Get user messages
        user_msgs = self._conn.execute(
            """
            SELECT m.id, m.created_at, p.content
            FROM messages m
            LEFT JOIN parts p ON p.message_id = m.id AND p.part_type = 'text'
            WHERE m.session_id = ? AND m.role = 'user'
            ORDER BY m.created_at ASC
            """,
            [session_id],
        ).fetchall()

        # Get assistant messages
        assistant_msgs = self._conn.execute(
            """
            SELECT m.id, m.created_at, m.agent, m.model_id,
                   m.tokens_input, m.tokens_output, m.tokens_reasoning,
                   p.content
            FROM messages m
            LEFT JOIN parts p ON p.message_id = m.id AND p.part_type = 'text'
            WHERE m.session_id = ? AND m.role = 'assistant'
            ORDER BY m.created_at ASC
            """,
            [session_id],
        ).fetchall()

        exchanges = []
        for i, user_row in enumerate(user_msgs):
            exchange = {
                "number": i + 1,
                "user_message_id": user_row[0],
                "user_prompt": user_row[2] or "",
                "started_at": user_row[1].isoformat() if user_row[1] else None,
                "assistant_message_id": None,
                "assistant_response": "",
                "ended_at": None,
                "duration_ms": 0,
                "tokens": {"input": 0, "output": 0, "reasoning": 0},
                "cost": 0,
                "tool_count": 0,
                "reasoning_count": 0,
                "agent": None,
                "model_id": None,
            }

            # Match with assistant message
            if i < len(assistant_msgs):
                asst = assistant_msgs[i]
                exchange["assistant_message_id"] = asst[0]
                exchange["ended_at"] = asst[1].isoformat() if asst[1] else None
                exchange["agent"] = asst[2]
                exchange["model_id"] = asst[3]
                exchange["tokens"]["input"] = asst[4] or 0
                exchange["tokens"]["output"] = asst[5] or 0
                exchange["tokens"]["reasoning"] = asst[6] or 0
                exchange["assistant_response"] = asst[7] or ""

                # Calculate duration
                if user_row[1] and asst[1]:
                    delta = asst[1] - user_row[1]
                    exchange["duration_ms"] = int(delta.total_seconds() * 1000)

            exchanges.append(exchange)

        return exchanges

    def get_delegation_tree(self, session_id: str) -> dict:
        """Get recursive delegation tree structure for a session.

        Returns the full tree of agent delegations starting from this session.

        Args:
            session_id: The root session ID

        Returns:
            Dict with summary and nested tree structure
        """
        try:
            session = self._get_session_info(session_id)
            if not session:
                return {
                    "meta": {
                        "session_id": session_id,
                        "error": "Session not found",
                    },
                    "summary": {
                        "total_delegations": 0,
                        "max_depth": 0,
                        "agents_involved": [],
                    },
                    "tree": None,
                }

            # Build tree recursively
            tree, stats = self._build_delegation_tree_node(session_id, depth=0)

            return {
                "meta": {
                    "session_id": session_id,
                    "generated_at": datetime.now().isoformat(),
                },
                "summary": {
                    "total_delegations": stats["total_delegations"],
                    "max_depth": stats["max_depth"],
                    "agents_involved": list(stats["agents"]),
                },
                "tree": tree,
            }

        except Exception as e:
            debug(f"get_delegation_tree failed: {e}")
            return {
                "meta": {
                    "session_id": session_id,
                    "error": str(e),
                },
                "summary": {
                    "total_delegations": 0,
                    "max_depth": 0,
                    "agents_involved": [],
                },
                "tree": None,
            }

    def _build_delegation_tree_node(
        self, session_id: str, depth: int = 0
    ) -> tuple[dict, dict]:
        """Build a single node of the delegation tree.

        Returns:
            Tuple of (node_dict, stats_dict)
        """
        # Get session info
        session = self._get_session_info(session_id)

        # Get agent from first assistant message
        agent_result = self._conn.execute(
            """
            SELECT agent FROM messages
            WHERE session_id = ? AND role = 'assistant' AND agent IS NOT NULL
            LIMIT 1
            """,
            [session_id],
        ).fetchone()
        agent = agent_result[0] if agent_result else "unknown"

        # Get duration
        duration_result = self._conn.execute(
            """
            SELECT 
                MIN(created_at) as start,
                MAX(COALESCE(completed_at, created_at)) as end
            FROM messages
            WHERE session_id = ?
            """,
            [session_id],
        ).fetchone()

        duration_ms = 0
        if duration_result and duration_result[0] and duration_result[1]:
            delta = duration_result[1] - duration_result[0]
            duration_ms = int(delta.total_seconds() * 1000)

        # Get child delegations
        children_result = self._conn.execute(
            """
            SELECT id, child_agent, child_session_id, created_at
            FROM delegations
            WHERE session_id = ? AND child_session_id IS NOT NULL
            ORDER BY created_at ASC
            """,
            [session_id],
        ).fetchall()

        # Initialize stats
        stats = {
            "total_delegations": len(children_result),
            "max_depth": depth,
            "agents": {agent},
        }

        # Build children recursively
        children = []
        for child_row in children_result:
            child_session_id = child_row[2]
            child_agent = child_row[1]

            if child_session_id:
                child_node, child_stats = self._build_delegation_tree_node(
                    child_session_id, depth + 1
                )
                children.append(child_node)

                # Merge stats
                stats["total_delegations"] += child_stats["total_delegations"]
                stats["max_depth"] = max(stats["max_depth"], child_stats["max_depth"])
                stats["agents"].update(child_stats["agents"])

        node = {
            "session_id": session_id,
            "agent": agent,
            "title": session.get("title", "") if session else "",
            "delegated_at": (
                children_result[0][3].isoformat()
                if children_result and children_result[0][3]
                else None
            ),
            "duration_ms": duration_ms,
            "status": "completed",
            "children": children,
        }

        return node, stats
