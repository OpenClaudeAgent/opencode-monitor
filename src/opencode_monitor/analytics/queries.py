"""
Analytics queries for OpenCode data.

SQL query functions that return data model instances.
"""

from datetime import datetime, timedelta
from typing import Optional

from .db import AnalyticsDB
from .models import (
    AgentChain,
    AgentDelegationStats,
    AgentRole,
    AgentStats,
    DailyStats,
    DelegationMetrics,
    DelegationPattern,
    DelegationSession,
    DirectoryStats,
    HourlyDelegations,
    HourlyStats,
    ModelStats,
    PeriodStats,
    Project,
    ProjectStats,
    SessionStats,
    SessionTokenStats,
    SkillByAgent,
    SkillStats,
    Todo,
    TodoStats,
    TokenStats,
    ToolStats,
)


# Custom agents from open-flow (exclude generic agents like build, plan, compaction)
CUSTOM_AGENTS = {
    "executeur",  # FR
    "executor",  # EN
    "tester",
    "quality",
    "roadmap",
    "refactoring",
}


class AnalyticsQueries:
    """Provides analytics queries on the database."""

    def __init__(self, db: AnalyticsDB):
        """Initialize with a database instance."""
        self._db = db

    def get_period_stats(self, days: int) -> PeriodStats:
        """Get statistics for the last N days.

        Args:
            days: Number of days to analyze

        Returns:
            PeriodStats with all metrics
        """
        conn = self._db.connect()
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # Session count
        session_count = conn.execute(
            """
            SELECT COUNT(*) FROM sessions
            WHERE created_at >= ? AND created_at <= ?
            """,
            [start_date, end_date],
        ).fetchone()[0]

        # Message count and token totals
        msg_result = conn.execute(
            """
            SELECT
                COUNT(*) as msg_count,
                COALESCE(SUM(tokens_input), 0) as total_input,
                COALESCE(SUM(tokens_output), 0) as total_output,
                COALESCE(SUM(tokens_reasoning), 0) as total_reasoning,
                COALESCE(SUM(tokens_cache_read), 0) as total_cache_read,
                COALESCE(SUM(tokens_cache_write), 0) as total_cache_write
            FROM messages
            WHERE created_at >= ? AND created_at <= ?
            """,
            [start_date, end_date],
        ).fetchone()

        tokens = TokenStats(
            input=msg_result[1],
            output=msg_result[2],
            reasoning=msg_result[3],
            cache_read=msg_result[4],
            cache_write=msg_result[5],
        )

        # Agent stats
        agents = self._get_agent_stats(start_date, end_date)

        # Tool stats
        tools = self._get_tool_stats(start_date, end_date)

        # Skill stats
        skills = self._get_skill_stats(start_date, end_date)

        # Top sessions by tokens
        top_sessions = self._get_top_sessions(start_date, end_date)

        # Hourly usage patterns
        hourly_usage = self._get_hourly_usage(start_date, end_date)

        # Agent chains
        agent_chains = self._get_agent_chains(start_date, end_date)

        # Average session duration
        avg_duration = self._get_avg_session_duration(start_date, end_date)

        # Anomalies
        anomalies = self._get_anomalies(start_date, end_date)

        # Advanced delegation stats
        delegation_metrics = self._get_delegation_metrics(start_date, end_date)
        delegation_patterns = self._get_delegation_patterns(start_date, end_date)
        agent_roles = self._get_agent_roles(start_date, end_date)
        hourly_delegations = self._get_hourly_delegations(start_date, end_date)

        # Time series
        daily_stats = self._get_daily_stats(start_date, end_date)

        # Session token stats
        session_token_stats = self._get_session_token_stats(start_date, end_date)

        # New dimension metrics
        directories = self._get_directory_stats(start_date, end_date)
        models = self._get_model_stats(start_date, end_date)

        # Skills and delegation analysis
        skills_by_agent = self._get_skills_by_agent(start_date, end_date)
        delegation_sessions = self._get_delegation_sessions(start_date, end_date)
        agent_delegation_stats = self._get_agent_delegation_stats(start_date, end_date)

        return PeriodStats(
            start_date=start_date,
            end_date=end_date,
            session_count=session_count,
            message_count=msg_result[0],
            tokens=tokens,
            agents=agents,
            tools=tools,
            skills=skills,
            top_sessions=top_sessions,
            hourly_usage=hourly_usage,
            agent_chains=agent_chains,
            avg_session_duration_min=avg_duration,
            anomalies=anomalies,
            delegation_metrics=delegation_metrics,
            delegation_patterns=delegation_patterns,
            agent_roles=agent_roles,
            hourly_delegations=hourly_delegations,
            daily_stats=daily_stats,
            session_token_stats=session_token_stats,
            directories=directories,
            models=models,
            skills_by_agent=skills_by_agent,
            delegation_sessions=delegation_sessions,
            agent_delegation_stats=agent_delegation_stats,
        )

    def _get_agent_stats(
        self, start_date: datetime, end_date: datetime
    ) -> list[AgentStats]:
        """Get per-agent statistics."""
        conn = self._db.connect()

        results = conn.execute(
            """
            SELECT
                agent,
                COUNT(*) as msg_count,
                COALESCE(SUM(tokens_input), 0) as total_input,
                COALESCE(SUM(tokens_output), 0) as total_output,
                COALESCE(SUM(tokens_reasoning), 0) as total_reasoning,
                COALESCE(SUM(tokens_cache_read), 0) as total_cache_read,
                COALESCE(SUM(tokens_cache_write), 0) as total_cache_write
            FROM messages
            WHERE created_at >= ? AND created_at <= ?
                AND agent IS NOT NULL
            GROUP BY agent
            ORDER BY total_input + total_output DESC
            """,
            [start_date, end_date],
        ).fetchall()

        return [
            AgentStats(
                agent=row[0] or "unknown",
                message_count=row[1],
                tokens=TokenStats(
                    input=row[2],
                    output=row[3],
                    reasoning=row[4],
                    cache_read=row[5],
                    cache_write=row[6],
                ),
            )
            for row in results
        ]

    def _get_tool_stats(
        self, start_date: datetime, end_date: datetime
    ) -> list[ToolStats]:
        """Get per-tool statistics."""
        conn = self._db.connect()

        # Note: created_at may be NULL, so we don't filter by date for now
        results = conn.execute(
            """
            SELECT
                tool_name,
                COUNT(*) as invocations,
                SUM(CASE WHEN tool_status = 'error' THEN 1 ELSE 0 END) as failures
            FROM parts
            WHERE tool_name IS NOT NULL
            GROUP BY tool_name
            ORDER BY invocations DESC
            LIMIT 15
            """
        ).fetchall()

        return [
            ToolStats(
                tool_name=row[0],
                invocations=row[1],
                failures=row[2] or 0,
            )
            for row in results
        ]

    def _get_skill_stats(
        self, start_date: datetime, end_date: datetime
    ) -> list[SkillStats]:
        """Get skill usage statistics."""
        conn = self._db.connect()

        # Note: loaded_at may be NULL, so we don't filter by date for now
        results = conn.execute(
            """
            SELECT
                skill_name,
                COUNT(*) as load_count
            FROM skills
            WHERE skill_name IS NOT NULL
            GROUP BY skill_name
            ORDER BY load_count DESC
            """
        ).fetchall()

        return [
            SkillStats(
                skill_name=row[0],
                load_count=row[1],
            )
            for row in results
        ]

    def _get_top_sessions(
        self, start_date: datetime, end_date: datetime, limit: int = 10
    ) -> list[SessionStats]:
        """Get top sessions by token usage."""
        conn = self._db.connect()

        results = conn.execute(
            """
            SELECT
                s.id,
                s.title,
                COUNT(m.id) as msg_count,
                COALESCE(SUM(m.tokens_input), 0) as total_input,
                COALESCE(SUM(m.tokens_output), 0) as total_output,
                COALESCE(SUM(m.tokens_reasoning), 0) as total_reasoning,
                COALESCE(SUM(m.tokens_cache_read), 0) as total_cache_read,
                COALESCE(SUM(m.tokens_cache_write), 0) as total_cache_write,
                EXTRACT(EPOCH FROM (MAX(m.created_at) - MIN(m.created_at))) / 60 as duration_min
            FROM sessions s
            JOIN messages m ON s.id = m.session_id
            WHERE s.created_at >= ? AND s.created_at <= ?
            GROUP BY s.id, s.title
            ORDER BY total_input + total_output DESC
            LIMIT ?
            """,
            [start_date, end_date, limit],
        ).fetchall()

        return [
            SessionStats(
                session_id=row[0],
                title=row[1] or "Untitled",
                message_count=row[2],
                tokens=TokenStats(
                    input=row[3],
                    output=row[4],
                    reasoning=row[5],
                    cache_read=row[6],
                    cache_write=row[7],
                ),
                duration_minutes=int(row[8] or 0),
            )
            for row in results
        ]

    def _get_hourly_usage(
        self, start_date: datetime, end_date: datetime
    ) -> list[HourlyStats]:
        """Get usage patterns by hour of day."""
        conn = self._db.connect()

        results = conn.execute(
            """
            SELECT
                EXTRACT(HOUR FROM created_at) as hour,
                COUNT(*) as msg_count,
                COALESCE(SUM(tokens_input + tokens_output), 0) as total_tokens
            FROM messages
            WHERE created_at >= ? AND created_at <= ?
            GROUP BY EXTRACT(HOUR FROM created_at)
            ORDER BY hour
            """,
            [start_date, end_date],
        ).fetchall()

        return [
            HourlyStats(
                hour=int(row[0]),
                message_count=row[1],
                tokens=row[2],
            )
            for row in results
        ]

    def _get_agent_chains(
        self, start_date: datetime, end_date: datetime
    ) -> list[AgentChain]:
        """Get real agent delegation chains from task tool invocations.

        Uses the delegations table to find actual parent->child relationships
        built from task tool invocations with subagent_type.
        """
        conn = self._db.connect()

        # Query direct delegations from the delegations table
        results = conn.execute(
            """
            WITH direct_delegations AS (
                -- Get direct parent -> child relationships
                SELECT
                    parent_agent,
                    child_agent,
                    session_id,
                    created_at
                FROM delegations
                WHERE created_at >= ? AND created_at <= ?
                    AND parent_agent IS NOT NULL
                    AND child_agent IS NOT NULL
            ),
            delegation_pairs AS (
                -- Format as "parent -> child" and count occurrences
                SELECT
                    parent_agent || ' -> ' || child_agent as chain,
                    COUNT(*) as occurrences
                FROM direct_delegations
                GROUP BY parent_agent, child_agent
            )
            SELECT chain, occurrences, 2 as depth
            FROM delegation_pairs
            ORDER BY occurrences DESC
            LIMIT 15
            """,
            [start_date, end_date],
        ).fetchall()

        chains = [
            AgentChain(
                chain=row[0],
                occurrences=row[1],
                depth=row[2],
            )
            for row in results
        ]

        # If we have delegations, also try to find longer chains
        # by following child_session_id references
        if chains:
            extended = self._get_extended_chains(start_date, end_date)
            chains.extend(extended)
            # Sort by depth (longer chains first), then by occurrences
            chains.sort(key=lambda c: (-c.depth, -c.occurrences))

        return chains[:15]

    def _get_extended_chains(
        self, start_date: datetime, end_date: datetime
    ) -> list[AgentChain]:
        """Find extended chains (depth > 2) by following child_session_id.

        e.g., executeur -> tester -> refactoring
        """
        conn = self._db.connect()

        # Find chains of length 3 by joining delegations
        results = conn.execute(
            """
            WITH d1 AS (
                SELECT * FROM delegations
                WHERE created_at >= ? AND created_at <= ?
                    AND parent_agent IS NOT NULL
            ),
            d2 AS (
                SELECT * FROM delegations
                WHERE created_at >= ? AND created_at <= ?
                    AND parent_agent IS NOT NULL
            )
            SELECT
                d1.parent_agent || ' -> ' || d1.child_agent || ' -> ' || d2.child_agent as chain,
                COUNT(*) as occurrences
            FROM d1
            JOIN d2 ON d1.child_session_id = d2.session_id
            WHERE d2.parent_agent = d1.child_agent
            GROUP BY d1.parent_agent, d1.child_agent, d2.child_agent
            HAVING COUNT(*) >= 1
            ORDER BY occurrences DESC
            LIMIT 10
            """,
            [start_date, end_date, start_date, end_date],
        ).fetchall()

        return [
            AgentChain(
                chain=row[0],
                occurrences=row[1],
                depth=3,
            )
            for row in results
        ]

    def _get_avg_session_duration(
        self, start_date: datetime, end_date: datetime
    ) -> float:
        """Get average session duration in minutes."""
        conn = self._db.connect()

        result = conn.execute(
            """
            SELECT AVG(duration_min) FROM (
                SELECT
                    s.id,
                    EXTRACT(EPOCH FROM (MAX(m.created_at) - MIN(m.created_at))) / 60 as duration_min
                FROM sessions s
                JOIN messages m ON s.id = m.session_id
                WHERE s.created_at >= ? AND s.created_at <= ?
                GROUP BY s.id
                HAVING COUNT(m.id) > 1
            )
            """,
            [start_date, end_date],
        ).fetchone()

        return float(result[0] or 0)

    def _get_anomalies(self, start_date: datetime, end_date: datetime) -> list[str]:
        """Detect anomalies in usage patterns."""
        conn = self._db.connect()
        anomalies = []

        # Check for sessions with excessive task calls (> 10)
        try:
            excessive_tasks = conn.execute(
                """
                SELECT ANY_VALUE(s.title) as title, COUNT(*) as task_count
                FROM parts p
                JOIN messages m ON p.message_id = m.id
                JOIN sessions s ON m.session_id = s.id
                WHERE p.tool_name = 'task'
                    AND p.created_at >= ? AND p.created_at <= ?
                GROUP BY s.id
                HAVING task_count > 10
                ORDER BY task_count DESC
                LIMIT 5
                """,
                [start_date, end_date],
            ).fetchall()

            for title, count in excessive_tasks:
                short_title = (
                    title[:30] + "..."
                    if title and len(title) > 30
                    else (title or "Untitled")
                )
                anomalies.append(f"Session '{short_title}' has {count} task calls")
        except Exception:
            pass

        # Check for high tool failure rates (> 20%)
        try:
            high_failure_tools = conn.execute(
                """
                SELECT
                    tool_name,
                    COUNT(*) as total,
                    SUM(CASE WHEN tool_status = 'error' THEN 1 ELSE 0 END) as failures
                FROM parts
                WHERE created_at >= ? AND created_at <= ?
                    AND tool_name IS NOT NULL
                GROUP BY tool_name
                HAVING total >= 10 AND (failures * 100.0 / total) > 20
                """,
                [start_date, end_date],
            ).fetchall()

            for tool, total, failures in high_failure_tools:
                rate = (failures / total) * 100
                anomalies.append(
                    f"Tool '{tool}' has {rate:.0f}% failure rate ({failures}/{total})"
                )
        except Exception:
            pass

        return anomalies

    def get_anomalies(self, days: int) -> list[str]:
        """Public method for backward compatibility."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        return self._get_anomalies(start_date, end_date)

    def _get_skills_by_agent(
        self, start_date: datetime, end_date: datetime
    ) -> list[SkillByAgent]:
        """Get skill usage per agent."""
        conn = self._db.connect()

        try:
            results = conn.execute(
                """
                SELECT 
                    m.agent,
                    s.skill_name,
                    COUNT(*) as count
                FROM skills s
                JOIN messages m ON s.message_id = m.id
                WHERE m.agent IS NOT NULL
                GROUP BY m.agent, s.skill_name
                ORDER BY count DESC
                """
            ).fetchall()

            return [
                SkillByAgent(
                    agent=row[0],
                    skill_name=row[1],
                    count=row[2],
                )
                for row in results
            ]
        except Exception:
            return []

    def _get_delegation_sessions(
        self, start_date: datetime, end_date: datetime
    ) -> list[DelegationSession]:
        """Get sessions with multiple delegations."""
        conn = self._db.connect()

        try:
            results = conn.execute(
                """
                SELECT 
                    parent_agent,
                    session_id,
                    COUNT(*) as delegation_count,
                    STRING_AGG(child_agent, ' -> ' ORDER BY created_at) as sequence
                FROM delegations
                WHERE parent_agent IS NOT NULL
                  AND created_at >= ? AND created_at <= ?
                GROUP BY parent_agent, session_id
                HAVING COUNT(*) >= 2
                ORDER BY delegation_count DESC
                LIMIT 20
                """,
                [start_date, end_date],
            ).fetchall()

            return [
                DelegationSession(
                    agent=row[0],
                    session_id=row[1],
                    delegation_count=row[2],
                    sequence=row[3],
                )
                for row in results
            ]
        except Exception:
            return []

    def _get_agent_delegation_stats(
        self, start_date: datetime, end_date: datetime
    ) -> list[AgentDelegationStats]:
        """Get delegation statistics per agent."""
        conn = self._db.connect()

        try:
            results = conn.execute(
                """
                WITH session_delegations AS (
                    SELECT 
                        parent_agent,
                        session_id,
                        COUNT(*) as deleg_count
                    FROM delegations
                    WHERE parent_agent IS NOT NULL
                      AND created_at >= ? AND created_at <= ?
                    GROUP BY parent_agent, session_id
                )
                SELECT 
                    parent_agent,
                    COUNT(*) as sessions_count,
                    SUM(deleg_count) as total_delegations,
                    ROUND(AVG(deleg_count), 1) as avg_per_session,
                    MAX(deleg_count) as max_per_session
                FROM session_delegations
                GROUP BY parent_agent
                ORDER BY total_delegations DESC
                """,
                [start_date, end_date],
            ).fetchall()

            return [
                AgentDelegationStats(
                    agent=row[0],
                    sessions_with_delegations=row[1],
                    total_delegations=row[2],
                    avg_per_session=row[3],
                    max_per_session=row[4],
                )
                for row in results
            ]
        except Exception:
            return []

    def _get_directory_stats(
        self, start_date: datetime, end_date: datetime
    ) -> list[DirectoryStats]:
        """Get statistics per working directory."""
        conn = self._db.connect()

        try:
            results = conn.execute(
                """
                SELECT 
                    s.directory,
                    COUNT(DISTINCT s.id) as sessions,
                    COALESCE(SUM(m.tokens_input + m.tokens_output), 0) as tokens
                FROM sessions s
                LEFT JOIN messages m ON s.id = m.session_id
                WHERE s.created_at >= ? AND s.created_at <= ?
                  AND s.directory IS NOT NULL
                GROUP BY s.directory
                ORDER BY tokens DESC
                LIMIT 10
                """,
                [start_date, end_date],
            ).fetchall()

            return [
                DirectoryStats(
                    directory=row[0],
                    sessions=row[1],
                    tokens=row[2],
                )
                for row in results
            ]
        except Exception:
            return []

    def _get_model_stats(
        self, start_date: datetime, end_date: datetime
    ) -> list[ModelStats]:
        """Get statistics per model."""
        conn = self._db.connect()

        try:
            # First get total tokens for percentage calculation
            total_tokens = conn.execute(
                """
                SELECT COALESCE(SUM(tokens_input + tokens_output), 0)
                FROM messages
                WHERE created_at >= ? AND created_at <= ?
                """,
                [start_date, end_date],
            ).fetchone()[0]

            results = conn.execute(
                """
                SELECT 
                    model_id,
                    provider_id,
                    COUNT(*) as messages,
                    COALESCE(SUM(tokens_input + tokens_output), 0) as tokens
                FROM messages
                WHERE created_at >= ? AND created_at <= ?
                  AND model_id IS NOT NULL
                GROUP BY model_id, provider_id
                ORDER BY tokens DESC
                LIMIT 10
                """,
                [start_date, end_date],
            ).fetchall()

            return [
                ModelStats(
                    model_id=row[0],
                    provider_id=row[1] or "unknown",
                    messages=row[2],
                    tokens=row[3],
                    percentage=(row[3] / total_tokens * 100) if total_tokens > 0 else 0,
                )
                for row in results
            ]
        except Exception:
            return []

    def _get_delegation_metrics(
        self, start_date: datetime, end_date: datetime
    ) -> Optional[DelegationMetrics]:
        """Get overall delegation metrics."""
        conn = self._db.connect()

        try:
            # Total delegations
            total = conn.execute(
                "SELECT COUNT(*) FROM delegations WHERE created_at >= ? AND created_at <= ?",
                [start_date, end_date],
            ).fetchone()[0]

            if total == 0:
                return None

            # Sessions with delegations
            sessions = conn.execute(
                "SELECT COUNT(DISTINCT session_id) FROM delegations WHERE created_at >= ? AND created_at <= ?",
                [start_date, end_date],
            ).fetchone()[0]

            # Unique patterns
            patterns = conn.execute(
                """SELECT COUNT(DISTINCT parent_agent || child_agent) 
                   FROM delegations 
                   WHERE created_at >= ? AND created_at <= ?""",
                [start_date, end_date],
            ).fetchone()[0]

            # Recursive delegations
            recursive = conn.execute(
                """SELECT COUNT(*) FROM delegations 
                   WHERE parent_agent = child_agent 
                   AND created_at >= ? AND created_at <= ?""",
                [start_date, end_date],
            ).fetchone()[0]

            # Max depth - calculate dynamically by following chains
            try:
                depth_result = conn.execute(
                    """
                    WITH RECURSIVE chain AS (
                        SELECT child_session_id, 1 as depth
                        FROM delegations
                        WHERE created_at >= ? AND created_at <= ?
                          AND parent_agent IS NOT NULL
                        
                        UNION ALL
                        
                        SELECT d.child_session_id, c.depth + 1
                        FROM chain c
                        JOIN delegations d ON c.child_session_id = d.session_id
                        WHERE c.depth < 100  -- Safety limit only, not a real constraint
                    )
                    SELECT MAX(depth) FROM chain
                    """,
                    [start_date, end_date],
                ).fetchone()[0]

                # depth+1 = number of agents in chain
                max_depth = (depth_result + 1) if depth_result else 2
            except Exception:
                max_depth = 2

            return DelegationMetrics(
                total_delegations=total,
                sessions_with_delegations=sessions,
                unique_patterns=patterns,
                recursive_delegations=recursive,
                recursive_percentage=(recursive / total * 100) if total > 0 else 0,
                max_depth=max_depth,
                avg_per_session=(total / sessions) if sessions > 0 else 0,
            )
        except Exception:
            return None

    def _get_delegation_patterns(
        self, start_date: datetime, end_date: datetime
    ) -> list[DelegationPattern]:
        """Get detailed delegation patterns with token metrics."""
        conn = self._db.connect()

        try:
            total = conn.execute(
                "SELECT COUNT(*) FROM delegations WHERE created_at >= ? AND created_at <= ?",
                [start_date, end_date],
            ).fetchone()[0]

            if total == 0:
                return []

            # Query patterns with token totals from both parent and child sessions
            results = conn.execute(
                """
                SELECT 
                    d.parent_agent,
                    d.child_agent,
                    COUNT(*) as count,
                    SUM(COALESCE(parent_tokens.total, 0) + COALESCE(child_tokens.total, 0)) as total_tokens
                FROM delegations d
                LEFT JOIN (
                    SELECT session_id, SUM(tokens_input + tokens_output) as total
                    FROM messages GROUP BY session_id
                ) parent_tokens ON d.session_id = parent_tokens.session_id
                LEFT JOIN (
                    SELECT session_id, SUM(tokens_input + tokens_output) as total
                    FROM messages GROUP BY session_id
                ) child_tokens ON d.child_session_id = child_tokens.session_id
                WHERE d.created_at >= ? AND d.created_at <= ?
                  AND d.parent_agent IS NOT NULL AND d.child_agent IS NOT NULL
                GROUP BY d.parent_agent, d.child_agent
                ORDER BY total_tokens DESC
                LIMIT 20
                """,
                [start_date, end_date],
            ).fetchall()

            return [
                DelegationPattern(
                    parent=row[0],
                    child=row[1],
                    count=row[2],
                    percentage=(row[2] / total * 100) if total > 0 else 0,
                    tokens_total=row[3] or 0,
                    tokens_avg=(row[3] // row[2]) if row[3] and row[2] else 0,
                )
                for row in results
            ]
        except Exception:
            return []

    def _get_agent_roles(
        self, start_date: datetime, end_date: datetime
    ) -> list[AgentRole]:
        """Get agent classification based on delegation behavior."""
        conn = self._db.connect()

        try:
            # Get delegations sent per agent
            sent = dict(
                conn.execute(
                    """SELECT parent_agent, COUNT(*) FROM delegations 
                       WHERE created_at >= ? AND created_at <= ? AND parent_agent IS NOT NULL
                       GROUP BY parent_agent""",
                    [start_date, end_date],
                ).fetchall()
            )

            # Get delegations received per agent
            received = dict(
                conn.execute(
                    """SELECT child_agent, COUNT(*) FROM delegations 
                       WHERE created_at >= ? AND created_at <= ? AND child_agent IS NOT NULL
                       GROUP BY child_agent""",
                    [start_date, end_date],
                ).fetchall()
            )

            # Get tokens per agent
            tokens = dict(
                conn.execute(
                    """SELECT agent, SUM(tokens_input + tokens_output) FROM messages 
                       WHERE created_at >= ? AND created_at <= ? AND agent IS NOT NULL
                       GROUP BY agent""",
                    [start_date, end_date],
                ).fetchall()
            )

            # Combine all agents
            all_agents = set(sent.keys()) | set(received.keys())
            roles = []

            for agent in all_agents:
                s = sent.get(agent, 0)
                r = received.get(agent, 0)
                t = tokens.get(agent, 0)

                # Determine role
                if r == 0 and s > 0:
                    role = "orchestrator"
                elif s == 0 and r > 0:
                    role = "worker"
                else:
                    role = "hub"

                fan_out = (s / r) if r > 0 else float("inf") if s > 0 else 0
                tokens_per_task = (t // r) if r > 0 else 0

                roles.append(
                    AgentRole(
                        agent=agent,
                        role=role,
                        delegations_sent=s,
                        delegations_received=r,
                        fan_out=fan_out,
                        tokens_total=t,
                        tokens_per_task=tokens_per_task,
                    )
                )

            # Sort by total activity (sent + received)
            roles.sort(key=lambda x: -(x.delegations_sent + x.delegations_received))
            return roles
        except Exception:
            return []

    def _get_hourly_delegations(
        self, start_date: datetime, end_date: datetime
    ) -> list[HourlyDelegations]:
        """Get delegation counts by hour of day."""
        conn = self._db.connect()

        try:
            results = conn.execute(
                """
                SELECT EXTRACT(HOUR FROM created_at) as hour, COUNT(*) as count
                FROM delegations
                WHERE created_at >= ? AND created_at <= ?
                GROUP BY hour
                ORDER BY hour
                """,
                [start_date, end_date],
            ).fetchall()

            return [
                HourlyDelegations(hour=int(row[0]), count=row[1]) for row in results
            ]
        except Exception:
            return []

    def _get_session_token_stats(
        self, start_date: datetime, end_date: datetime
    ) -> Optional[SessionTokenStats]:
        """Get token statistics across sessions."""
        conn = self._db.connect()

        try:
            result = conn.execute(
                """
                SELECT 
                    COUNT(*) as sessions,
                    AVG(total_tokens) as avg_tokens,
                    MAX(total_tokens) as max_tokens,
                    MIN(CASE WHEN total_tokens > 0 THEN total_tokens END) as min_tokens,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY total_tokens) as median_tokens
                FROM (
                    SELECT session_id, SUM(tokens_input + tokens_output) as total_tokens
                    FROM messages
                    WHERE created_at >= ? AND created_at <= ?
                    GROUP BY session_id
                )
                """,
                [start_date, end_date],
            ).fetchone()

            if not result or result[0] == 0:
                return None

            return SessionTokenStats(
                total_sessions=result[0],
                avg_tokens=int(result[1] or 0),
                max_tokens=int(result[2] or 0),
                min_tokens=int(result[3] or 0),
                median_tokens=int(result[4] or 0),
            )
        except Exception:
            return None

    def _get_daily_stats(
        self, start_date: datetime, end_date: datetime
    ) -> list[DailyStats]:
        """Get daily activity statistics for time series chart."""
        conn = self._db.connect()

        try:
            # Get sessions per day
            sessions_per_day = dict(
                conn.execute(
                    """
                    SELECT DATE_TRUNC('day', created_at) as day, COUNT(*) as count
                    FROM sessions
                    WHERE created_at >= ? AND created_at <= ?
                    GROUP BY day
                    """,
                    [start_date, end_date],
                ).fetchall()
            )

            # Get messages and tokens per day
            messages_per_day = {}
            tokens_per_day = {}
            results = conn.execute(
                """
                SELECT 
                    DATE_TRUNC('day', created_at) as day,
                    COUNT(*) as msg_count,
                    COALESCE(SUM(tokens_input + tokens_output), 0) as tokens
                FROM messages
                WHERE created_at >= ? AND created_at <= ?
                GROUP BY day
                """,
                [start_date, end_date],
            ).fetchall()
            for day, msg_count, tokens in results:
                messages_per_day[day] = msg_count
                tokens_per_day[day] = tokens

            # Get delegations per day
            delegations_per_day = dict(
                conn.execute(
                    """
                    SELECT DATE_TRUNC('day', created_at) as day, COUNT(*) as count
                    FROM delegations
                    WHERE created_at >= ? AND created_at <= ?
                    GROUP BY day
                    """,
                    [start_date, end_date],
                ).fetchall()
            )

            # Combine all days
            all_days = (
                set(sessions_per_day.keys())
                | set(messages_per_day.keys())
                | set(delegations_per_day.keys())
            )

            daily_stats = []
            for day in sorted(all_days):
                daily_stats.append(
                    DailyStats(
                        date=day,
                        sessions=sessions_per_day.get(day, 0),
                        messages=messages_per_day.get(day, 0),
                        tokens=tokens_per_day.get(day, 0),
                        delegations=delegations_per_day.get(day, 0),
                    )
                )

            return daily_stats
        except Exception:
            return []

    # ===== NEW: Todos, Projects, and Enriched Stats =====

    def get_todos(
        self, session_id: Optional[str] = None, status: Optional[str] = None
    ) -> list[Todo]:
        """Get todos, optionally filtered by session or status."""
        conn = self._db.connect()

        try:
            query = "SELECT id, session_id, content, status, priority, position, created_at, updated_at FROM todos"
            params = []
            conditions = []

            if session_id:
                conditions.append("session_id = ?")
                params.append(session_id)
            if status:
                conditions.append("status = ?")
                params.append(status)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY session_id, position"

            results = conn.execute(query, params).fetchall()

            return [
                Todo(
                    id=row[0],
                    session_id=row[1],
                    content=row[2],
                    status=row[3],
                    priority=row[4],
                    position=row[5],
                    created_at=row[6],
                    updated_at=row[7],
                )
                for row in results
            ]
        except Exception:
            return []

    def get_todo_stats(self, days: int) -> Optional[TodoStats]:
        """Get todo statistics for the last N days."""
        conn = self._db.connect()
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        try:
            result = conn.execute(
                """
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled
                FROM todos
                WHERE created_at >= ? AND created_at <= ?
                """,
                [start_date, end_date],
            ).fetchone()

            if not result or result[0] == 0:
                return None

            total = result[0]
            completed = result[1] or 0
            completion_rate = (completed / total * 100) if total > 0 else 0

            return TodoStats(
                total=total,
                completed=completed,
                in_progress=result[2] or 0,
                pending=result[3] or 0,
                cancelled=result[4] or 0,
                completion_rate=completion_rate,
            )
        except Exception:
            return None

    def get_projects(self) -> list[Project]:
        """Get all projects."""
        conn = self._db.connect()

        try:
            results = conn.execute(
                """
                SELECT id, worktree, vcs, created_at, updated_at
                FROM projects
                ORDER BY updated_at DESC
                """
            ).fetchall()

            return [
                Project(
                    id=row[0],
                    worktree=row[1],
                    vcs=row[2],
                    created_at=row[3],
                    updated_at=row[4],
                )
                for row in results
            ]
        except Exception:
            return []

    def get_project_stats(self, days: int) -> list[ProjectStats]:
        """Get statistics per project for the last N days."""
        conn = self._db.connect()
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        try:
            results = conn.execute(
                """
                SELECT 
                    p.id,
                    p.worktree,
                    COUNT(DISTINCT s.id) as sessions,
                    COALESCE(SUM(m.tokens_input + m.tokens_output), 0) as tokens,
                    (SELECT COUNT(*) FROM todos t 
                     WHERE t.session_id IN (SELECT id FROM sessions WHERE project_id = p.id)) as todos_total,
                    (SELECT COUNT(*) FROM todos t 
                     WHERE t.session_id IN (SELECT id FROM sessions WHERE project_id = p.id)
                       AND t.status = 'completed') as todos_completed
                FROM projects p
                LEFT JOIN sessions s ON s.project_id = p.id 
                    AND s.created_at >= ? AND s.created_at <= ?
                LEFT JOIN messages m ON m.session_id = s.id
                GROUP BY p.id, p.worktree
                ORDER BY tokens DESC
                """,
                [start_date, end_date],
            ).fetchall()

            return [
                ProjectStats(
                    project_id=row[0],
                    worktree=row[1],
                    sessions=row[2],
                    tokens=row[3],
                    todos_total=row[4] or 0,
                    todos_completed=row[5] or 0,
                )
                for row in results
            ]
        except Exception:
            return []

    def get_code_stats(self, days: int) -> dict:
        """Get code change statistics (additions, deletions) for the last N days."""
        conn = self._db.connect()
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        try:
            result = conn.execute(
                """
                SELECT 
                    COALESCE(SUM(additions), 0) as total_additions,
                    COALESCE(SUM(deletions), 0) as total_deletions,
                    COALESCE(SUM(files_changed), 0) as total_files,
                    COUNT(CASE WHEN additions > 0 OR deletions > 0 THEN 1 END) as sessions_with_changes
                FROM sessions
                WHERE created_at >= ? AND created_at <= ?
                """,
                [start_date, end_date],
            ).fetchone()

            return {
                "additions": result[0] if result else 0,
                "deletions": result[1] if result else 0,
                "files_changed": result[2] if result else 0,
                "sessions_with_changes": result[3] if result else 0,
            }
        except Exception:
            return {
                "additions": 0,
                "deletions": 0,
                "files_changed": 0,
                "sessions_with_changes": 0,
            }

    def get_cost_stats(self, days: int) -> dict:
        """Get cost statistics for the last N days."""
        conn = self._db.connect()
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        try:
            result = conn.execute(
                """
                SELECT 
                    COALESCE(SUM(cost), 0) as total_cost,
                    COALESCE(AVG(cost), 0) as avg_cost_per_message,
                    COUNT(CASE WHEN cost > 0 THEN 1 END) as messages_with_cost
                FROM messages
                WHERE created_at >= ? AND created_at <= ?
                """,
                [start_date, end_date],
            ).fetchone()

            return {
                "total_cost": float(result[0]) if result else 0.0,
                "avg_cost_per_message": float(result[1]) if result else 0.0,
                "messages_with_cost": result[2] if result else 0,
            }
        except Exception:
            return {
                "total_cost": 0.0,
                "avg_cost_per_message": 0.0,
                "messages_with_cost": 0,
            }

    def get_tool_performance(self, days: int) -> list[dict]:
        """Get tool performance stats (duration) for the last N days."""
        conn = self._db.connect()
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        try:
            results = conn.execute(
                """
                SELECT 
                    tool_name,
                    COUNT(*) as invocations,
                    COALESCE(AVG(duration_ms), 0) as avg_duration_ms,
                    COALESCE(MAX(duration_ms), 0) as max_duration_ms,
                    COALESCE(MIN(duration_ms), 0) as min_duration_ms,
                    SUM(CASE WHEN tool_status = 'error' THEN 1 ELSE 0 END) as failures
                FROM parts
                WHERE created_at >= ? AND created_at <= ?
                    AND tool_name IS NOT NULL
                    AND duration_ms IS NOT NULL
                GROUP BY tool_name
                ORDER BY avg_duration_ms DESC
                LIMIT 20
                """,
                [start_date, end_date],
            ).fetchall()

            return [
                {
                    "tool_name": row[0],
                    "invocations": row[1],
                    "avg_duration_ms": int(row[2]),
                    "max_duration_ms": row[3],
                    "min_duration_ms": row[4],
                    "failures": row[5] or 0,
                }
                for row in results
            ]
        except Exception:
            return []

    def get_session_hierarchy(self, session_id: str) -> dict:
        """Get parent-child session hierarchy for a session."""
        conn = self._db.connect()

        try:
            # Get parent sessions (going up)
            parents: list = []
            current_id: Optional[str] = session_id
            while current_id:
                result = conn.execute(
                    "SELECT id, parent_id, title FROM sessions WHERE id = ?",
                    [current_id],
                ).fetchone()
                if result:
                    parents.insert(0, {"id": result[0], "title": result[2]})
                    current_id = result[1]
                else:
                    break

            # Get child sessions (going down)
            children = conn.execute(
                """
                SELECT id, title, parent_id FROM sessions
                WHERE parent_id = ?
                ORDER BY created_at
                """,
                [session_id],
            ).fetchall()

            return {
                "parents": parents,
                "current": session_id,
                "children": [{"id": row[0], "title": row[1]} for row in children],
            }
        except Exception:
            return {"parents": [], "current": session_id, "children": []}
