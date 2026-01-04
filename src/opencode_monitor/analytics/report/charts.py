"""
Plotly chart generation for analytics reports.
"""

from typing import TYPE_CHECKING

from ..models import PeriodStats

if TYPE_CHECKING:
    pass


# Chart color palette
COLORS = {
    "primary": "#636EFA",
    "secondary": "#EF553B",
    "success": "#00CC96",
    "purple": "#AB63FA",
    "warning": "#FFA15A",
}

# Common layout settings for dark theme
DARK_LAYOUT = {
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
    "font_color": "#eee",
    "hoverlabel": {"bgcolor": "#1a1a2e", "font_color": "#eee"},
}


def create_token_pie_chart(stats: PeriodStats) -> str:
    """Create token distribution pie chart."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        return ""

    if stats.tokens.total_with_cache <= 0:
        return ""

    fig = go.Figure(
        data=[
            go.Pie(
                labels=["Input", "Output", "Reasoning", "Cache Read", "Cache Write"],
                values=[
                    stats.tokens.input,
                    stats.tokens.output,
                    stats.tokens.reasoning,
                    stats.tokens.cache_read,
                    stats.tokens.cache_write,
                ],
                hole=0.4,
                marker_colors=[
                    COLORS["primary"],
                    COLORS["secondary"],
                    COLORS["success"],
                    COLORS["purple"],
                    COLORS["warning"],
                ],
            )
        ]
    )
    fig.update_layout(
        title_text="Token Distribution",
        height=350,
        margin=dict(t=50, b=20, l=20, r=20),
        **DARK_LAYOUT,
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)


def create_agent_bar_chart(stats: PeriodStats) -> str:
    """Create agent token usage bar chart."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        return ""

    if not stats.agents:
        return ""

    agent_names = [a.agent for a in stats.agents[:10]]
    agent_tokens = [a.tokens.total for a in stats.agents[:10]]

    fig = go.Figure(
        data=[
            go.Bar(
                x=agent_tokens,
                y=agent_names,
                orientation="h",
                marker_color=COLORS["primary"],
            )
        ]
    )
    fig.update_layout(
        title_text="Token Usage by Agent",
        xaxis_title="Tokens",
        height=350,
        margin=dict(t=50, b=40, l=100, r=20),
        yaxis=dict(autorange="reversed"),
        **DARK_LAYOUT,
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)


def create_hourly_bar_chart(stats: PeriodStats) -> str:
    """Create hourly usage pattern bar chart."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        return ""

    if not stats.hourly_usage:
        return ""

    hours = list(range(24))
    usage_by_hour = {h.hour: h.tokens for h in stats.hourly_usage}
    tokens_per_hour = [usage_by_hour.get(h, 0) for h in hours]

    fig = go.Figure(
        data=[go.Bar(x=hours, y=tokens_per_hour, marker_color=COLORS["success"])]
    )
    fig.update_layout(
        title_text="Usage by Hour of Day",
        xaxis_title="Hour",
        yaxis_title="Tokens",
        height=300,
        margin=dict(t=50, b=40, l=60, r=20),
        xaxis=dict(tickmode="linear", tick0=0, dtick=2),
        **DARK_LAYOUT,
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)


def create_tool_stacked_bar(stats: PeriodStats) -> str:
    """Create tool invocations stacked bar chart."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        return ""

    if not stats.tools:
        return ""

    tool_names = [t.tool_name for t in stats.tools[:10]]
    tool_counts = [t.invocations for t in stats.tools[:10]]
    tool_failures = [t.failures for t in stats.tools[:10]]

    fig = go.Figure(
        data=[
            go.Bar(
                name="Success",
                x=tool_names,
                y=[c - f for c, f in zip(tool_counts, tool_failures)],
                marker_color=COLORS["primary"],
            ),
            go.Bar(
                name="Failures",
                x=tool_names,
                y=tool_failures,
                marker_color=COLORS["secondary"],
            ),
        ]
    )
    fig.update_layout(
        title_text="Tool Invocations",
        barmode="stack",
        height=350,
        margin=dict(t=50, b=80, l=60, r=20),
        xaxis_tickangle=-45,
        **DARK_LAYOUT,
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)


def create_daily_activity_chart(stats: PeriodStats) -> str:
    """Create daily activity time series chart."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        return ""

    if not stats.daily_stats:
        return ""

    dates = [d.date for d in stats.daily_stats]
    sessions = [d.sessions for d in stats.daily_stats]
    tokens_k = [d.tokens / 1000 for d in stats.daily_stats]
    delegations = [d.delegations for d in stats.daily_stats]

    fig = go.Figure()

    # Sessions bar
    fig.add_trace(
        go.Bar(
            name="Sessions",
            x=dates,
            y=sessions,
            marker_color=COLORS["primary"],
            yaxis="y",
        )
    )

    # Tokens line (secondary axis)
    fig.add_trace(
        go.Scatter(
            name="Tokens (K)",
            x=dates,
            y=tokens_k,
            mode="lines+markers",
            marker_color=COLORS["success"],
            line=dict(width=2),
            yaxis="y2",
        )
    )

    # Delegations line
    fig.add_trace(
        go.Scatter(
            name="Delegations",
            x=dates,
            y=delegations,
            mode="lines+markers",
            marker_color=COLORS["warning"],
            line=dict(width=2, dash="dot"),
            yaxis="y",
        )
    )

    fig.update_layout(
        title_text="Daily Activity",
        height=400,
        margin=dict(t=50, b=40, l=60, r=60),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#eee",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(title="Date", tickformat="%d %b"),
        yaxis=dict(title="Sessions / Delegations", side="left"),
        yaxis2=dict(title="Tokens (K)", side="right", overlaying="y"),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="#1a1a2e",
            font_size=13,
            font_color="#eee",
            bordercolor=COLORS["primary"],
        ),
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)


def generate_all_charts(stats: PeriodStats) -> list[str]:
    """Generate all charts and return as list of HTML strings.

    Returns charts in display order:
    1. Daily activity (if available)
    2. Token pie chart
    3. Agent bar chart
    4. Hourly usage
    5. Tool invocations
    """
    charts = []

    # Daily activity first (most important)
    daily = create_daily_activity_chart(stats)
    if daily:
        charts.append(daily)

    # Token distribution
    tokens = create_token_pie_chart(stats)
    if tokens:
        charts.append(tokens)

    # Agent usage
    agents = create_agent_bar_chart(stats)
    if agents:
        charts.append(agents)

    # Hourly pattern
    hourly = create_hourly_bar_chart(stats)
    if hourly:
        charts.append(hourly)

    # Tool invocations
    tools = create_tool_stacked_bar(stats)
    if tools:
        charts.append(tools)

    return charts
