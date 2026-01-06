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
