"""
Main report generator - orchestrates HTML report generation.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ..db import AnalyticsDB
from ..loader import load_opencode_data
from ..models import PeriodStats
from ..queries import AnalyticsQueries
from .charts import generate_all_charts
from .sections import (
    format_tokens,
    generate_agent_chains,
    generate_agent_delegation_stats,
    generate_agent_roles,
    generate_anomalies,
    generate_delegation_analytics,
    generate_delegation_flow,
    generate_delegation_sessions,
    generate_directories,
    generate_header,
    generate_hourly_heatmap,
    generate_models,
    generate_session_metrics,
    generate_skills,
    generate_skills_by_agent,
    generate_token_details,
    generate_top_sessions,
)
from .styles import get_full_css


def generate_html_report(stats: PeriodStats, period_label: str) -> str:
    """Generate an HTML report with Plotly charts.

    Args:
        stats: Period statistics to render
        period_label: Human-readable period description

    Returns:
        Complete HTML document as string
    """
    # Generate all charts
    charts = generate_all_charts(stats)

    # Build HTML document
    html_parts = [
        f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>OpenCode Analytics - {period_label}</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        {get_full_css()}
    </style>
</head>
<body>
    <div class="container">
""",
        generate_header(stats, period_label),
        generate_token_details(stats),
    ]

    # Add charts
    for chart_html in charts:
        html_parts.append(f'<div class="chart-container">{chart_html}</div>\n')

    # Add all sections
    html_parts.extend(
        [
            generate_session_metrics(stats),
            generate_delegation_analytics(stats),
            generate_agent_roles(stats),
            generate_delegation_flow(stats),
            generate_hourly_heatmap(stats),
            generate_agent_chains(stats),
            generate_top_sessions(stats),
            generate_skills(stats),
            generate_skills_by_agent(stats),
            generate_agent_delegation_stats(stats),
            generate_delegation_sessions(stats),
            generate_models(stats),
            generate_directories(stats),
            generate_anomalies(stats),
        ]
    )

    # Footer
    html_parts.append(f"""
        <p class="footer">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    </div>
</body>
</html>
""")

    return "".join(html_parts)


@dataclass
class AnalyticsReport:
    """Represents a formatted analytics report."""

    period_label: str
    stats: PeriodStats

    def to_html(self) -> str:
        """Generate HTML report with Plotly charts."""
        return generate_html_report(self.stats, self.period_label)

    def to_text(self) -> str:
        """Generate text representation of the report."""
        lines = [
            "=" * 50,
            "       OPENCODE ANALYTICS REPORT",
            "=" * 50,
            "",
            f"Period: {self.period_label}",
            f"Sessions: {self.stats.session_count}",
            f"Messages: {self.stats.message_count}",
            f"Tokens: {format_tokens(self.stats.tokens.total)}",
            f"Cache Hit Ratio: {self.stats.tokens.cache_hit_ratio:.0f}%",
        ]

        if self.stats.agents:
            lines.append("\nAgents:")
            for agent in self.stats.agents[:10]:
                lines.append(f"  {agent.agent}: {format_tokens(agent.tokens.total)}")

        return "\n".join(lines)


def generate_report(
    days: int,
    db: Optional[AnalyticsDB] = None,
    refresh_data: bool = False,
) -> AnalyticsReport:
    """Generate an analytics report for the specified period.

    Args:
        days: Number of days to analyze
        db: Optional database instance (creates new if None)
        refresh_data: Whether to reload data from OpenCode storage

    Returns:
        AnalyticsReport instance
    """
    if db is None:
        db = AnalyticsDB()

    if refresh_data:
        load_opencode_data(db, clear_first=True)

    queries = AnalyticsQueries(db)
    stats = queries.get_period_stats(days)

    if days == 1:
        period_label = "Last 24 hours"
    elif days == 7:
        period_label = "Last 7 days"
    elif days == 30:
        period_label = "Last 30 days"
    else:
        period_label = f"Last {days} days"

    return AnalyticsReport(period_label=period_label, stats=stats)
