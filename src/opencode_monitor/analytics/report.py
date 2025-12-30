"""
Analytics report generation with HTML/Plotly rendering.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import html as html_module

from .db import AnalyticsDB
from .loader import load_opencode_data
from .queries import AnalyticsQueries, PeriodStats


def format_tokens(count: int) -> str:
    """Format token count for display."""
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    elif count >= 1_000:
        return f"{count / 1_000:.0f}K"
    return str(count)


def generate_html_report(stats: PeriodStats, period_label: str) -> str:
    """Generate an HTML report with Plotly charts."""
    from ..utils.logger import info, debug

    info("Generating HTML report...")

    try:
        info("Importing plotly...")
        import plotly.graph_objects as go

        info("Plotly imported successfully")
        has_plotly = True
    except ImportError:
        info("Plotly not available")
        has_plotly = False

    figures_html = []

    if has_plotly:
        # 1. Token breakdown pie chart
        if stats.tokens.total_with_cache > 0:
            fig_tokens = go.Figure(
                data=[
                    go.Pie(
                        labels=[
                            "Input",
                            "Output",
                            "Reasoning",
                            "Cache Read",
                            "Cache Write",
                        ],
                        values=[
                            stats.tokens.input,
                            stats.tokens.output,
                            stats.tokens.reasoning,
                            stats.tokens.cache_read,
                            stats.tokens.cache_write,
                        ],
                        hole=0.4,
                        marker_colors=[
                            "#636EFA",
                            "#EF553B",
                            "#00CC96",
                            "#AB63FA",
                            "#FFA15A",
                        ],
                    )
                ]
            )
            fig_tokens.update_layout(
                title_text="Token Distribution",
                height=350,
                margin=dict(t=50, b=20, l=20, r=20),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#eee",
                hoverlabel=dict(bgcolor="#1a1a2e", font_color="#eee"),
            )
            figures_html.append(
                fig_tokens.to_html(full_html=False, include_plotlyjs=False)
            )

        # 2. Agent usage bar chart
        if stats.agents:
            agent_names = [a.agent for a in stats.agents[:10]]
            agent_tokens = [a.tokens.total for a in stats.agents[:10]]

            fig_agents = go.Figure(
                data=[
                    go.Bar(
                        x=agent_tokens,
                        y=agent_names,
                        orientation="h",
                        marker_color="#636EFA",
                    )
                ]
            )
            fig_agents.update_layout(
                title_text="Token Usage by Agent",
                xaxis_title="Tokens",
                height=350,
                margin=dict(t=50, b=40, l=100, r=20),
                yaxis=dict(autorange="reversed"),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#eee",
                hoverlabel=dict(bgcolor="#1a1a2e", font_color="#eee"),
            )
            figures_html.append(
                fig_agents.to_html(full_html=False, include_plotlyjs=False)
            )

        # 3. Hourly usage pattern
        if stats.hourly_usage:
            hours = list(range(24))
            usage_by_hour = {h.hour: h.tokens for h in stats.hourly_usage}
            tokens_per_hour = [usage_by_hour.get(h, 0) for h in hours]

            fig_hourly = go.Figure(
                data=[go.Bar(x=hours, y=tokens_per_hour, marker_color="#00CC96")]
            )
            fig_hourly.update_layout(
                title_text="Usage by Hour of Day",
                xaxis_title="Hour",
                yaxis_title="Tokens",
                height=300,
                margin=dict(t=50, b=40, l=60, r=20),
                xaxis=dict(tickmode="linear", tick0=0, dtick=2),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#eee",
                hoverlabel=dict(bgcolor="#1a1a2e", font_color="#eee"),
            )
            figures_html.append(
                fig_hourly.to_html(full_html=False, include_plotlyjs=False)
            )

        # 4. Tool usage bar chart
        if stats.tools:
            tool_names = [t.tool_name for t in stats.tools[:10]]
            tool_counts = [t.invocations for t in stats.tools[:10]]
            tool_failures = [t.failures for t in stats.tools[:10]]

            fig_tools = go.Figure(
                data=[
                    go.Bar(
                        name="Success",
                        x=tool_names,
                        y=[c - f for c, f in zip(tool_counts, tool_failures)],
                        marker_color="#636EFA",
                    ),
                    go.Bar(
                        name="Failures",
                        x=tool_names,
                        y=tool_failures,
                        marker_color="#EF553B",
                    ),
                ]
            )
            fig_tools.update_layout(
                title_text="Tool Invocations",
                barmode="stack",
                height=350,
                margin=dict(t=50, b=80, l=60, r=20),
                xaxis_tickangle=-45,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#eee",
                hoverlabel=dict(bgcolor="#1a1a2e", font_color="#eee"),
            )
            figures_html.append(
                fig_tools.to_html(full_html=False, include_plotlyjs=False)
            )

        # 5. Daily activity time series
        if stats.daily_stats:
            dates = [d.date for d in stats.daily_stats]
            sessions = [d.sessions for d in stats.daily_stats]
            tokens_k = [d.tokens / 1000 for d in stats.daily_stats]  # In thousands
            delegations = [d.delegations for d in stats.daily_stats]

            fig_daily = go.Figure()

            # Sessions bar
            fig_daily.add_trace(
                go.Bar(
                    name="Sessions",
                    x=dates,
                    y=sessions,
                    marker_color="#636EFA",
                    yaxis="y",
                )
            )

            # Tokens line (secondary axis)
            fig_daily.add_trace(
                go.Scatter(
                    name="Tokens (K)",
                    x=dates,
                    y=tokens_k,
                    mode="lines+markers",
                    marker_color="#00CC96",
                    line=dict(width=2),
                    yaxis="y2",
                )
            )

            # Delegations line
            fig_daily.add_trace(
                go.Scatter(
                    name="Delegations",
                    x=dates,
                    y=delegations,
                    mode="lines+markers",
                    marker_color="#FFA15A",
                    line=dict(width=2, dash="dot"),
                    yaxis="y",
                )
            )

            fig_daily.update_layout(
                title_text="Daily Activity",
                height=400,
                margin=dict(t=50, b=40, l=60, r=60),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#eee",
                legend=dict(
                    orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
                ),
                xaxis=dict(title="Date", tickformat="%d %b"),
                yaxis=dict(title="Sessions / Delegations", side="left"),
                yaxis2=dict(title="Tokens (K)", side="right", overlaying="y"),
                hovermode="x unified",
                hoverlabel=dict(
                    bgcolor="#1a1a2e",
                    font_size=13,
                    font_color="#eee",
                    bordercolor="#636EFA",
                ),
            )
            figures_html.insert(
                0, fig_daily.to_html(full_html=False, include_plotlyjs=False)
            )

    # Build HTML
    start_date = stats.start_date.strftime("%Y-%m-%d")
    end_date = stats.end_date.strftime("%Y-%m-%d")

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>OpenCode Analytics - {period_label}</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        /* ========================================
           Design System - Base 8px spacing
           ======================================== */
        :root {{
            /* Spacing scale (8px base) */
            --space-xs: 4px;
            --space-sm: 8px;
            --space-md: 16px;
            --space-lg: 24px;
            --space-xl: 32px;
            --space-2xl: 48px;
            --space-3xl: 64px;
            
            /* Colors - Dark theme with blue tint */
            --bg-base: #12121a;
            --bg-surface: #1a1a2e;
            --bg-elevated: #1e2140;
            --bg-hover: #252850;
            
            /* Text colors - tinted grays */
            --text-primary: #f0f0f5;
            --text-secondary: #9090a8;
            --text-muted: #606078;
            
            /* Accent colors */
            --accent-primary: #636EFA;
            --accent-success: #00CC96;
            --accent-warning: #FFA15A;
            --accent-error: #EF553B;
            
            /* Borders - tinted */
            --border-subtle: rgba(100, 110, 250, 0.15);
            --border-default: rgba(100, 110, 250, 0.25);
            
            /* Shadows */
            --shadow-sm: 0 1px 3px rgba(0,0,0,0.2), 0 1px 2px rgba(0,0,0,0.15);
            --shadow-md: 0 4px 8px rgba(0,0,0,0.2), 0 2px 4px rgba(0,0,0,0.15);
            --shadow-lg: 0 8px 24px rgba(0,0,0,0.25), 0 4px 8px rgba(0,0,0,0.15);
            
            /* Border radius */
            --radius-sm: 6px;
            --radius-md: 10px;
            --radius-lg: 14px;
            --radius-full: 9999px;
            
            /* Typography */
            --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            --font-mono: "SF Mono", "Fira Code", "JetBrains Mono", monospace;
        }}
        
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{ 
            font-family: var(--font-sans);
            font-size: 15px;
            line-height: 1.5;
            background: var(--bg-base);
            color: var(--text-primary);
            padding: var(--space-lg);
        }}
        
        /* Container */
        .container {{ 
            max-width: 1200px; 
            margin: 0 auto;
            padding: 0 var(--space-md);
        }}
        
        /* Header */
        h1 {{ 
            text-align: center; 
            font-size: 2rem;
            font-weight: 600;
            letter-spacing: -0.02em;
            margin-bottom: var(--space-sm);
            color: var(--text-primary);
        }}
        
        .subtitle {{ 
            text-align: center; 
            color: var(--text-secondary);
            font-size: 0.95rem;
            margin-bottom: var(--space-xl);
        }}
        
        /* Cards grid */
        .cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: var(--space-md);
            margin-bottom: var(--space-xl);
        }}
        
        .card {{
            background: var(--bg-surface);
            border-radius: var(--radius-md);
            padding: var(--space-lg);
            text-align: center;
            box-shadow: var(--shadow-sm);
            border: 1px solid var(--border-subtle);
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }}
        
        .card:hover {{
            transform: translateY(-2px);
            box-shadow: var(--shadow-md);
        }}
        
        .card-value {{ 
            font-size: 2rem; 
            font-weight: 700;
            color: var(--accent-primary);
            line-height: 1.2;
        }}
        
        .card-label {{ 
            color: var(--text-secondary);
            font-size: 0.85rem;
            margin-top: var(--space-sm);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        
        /* Chart containers */
        .chart-container {{
            background: var(--bg-surface);
            border-radius: var(--radius-md);
            padding: var(--space-lg);
            margin-bottom: var(--space-lg);
            box-shadow: var(--shadow-sm);
            border: 1px solid var(--border-subtle);
        }}
        
        .chart-container h3 {{
            font-size: 1rem;
            font-weight: 600;
            margin-bottom: var(--space-md);
            color: var(--text-primary);
        }}
        
        /* Section titles */
        .section-title {{
            font-size: 1.25rem;
            font-weight: 600;
            margin: var(--space-2xl) 0 var(--space-lg);
            color: var(--text-primary);
            padding-bottom: var(--space-sm);
            border-bottom: 2px solid var(--border-default);
        }}
        
        /* Tables */
        table {{
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            background: var(--bg-surface);
            border-radius: var(--radius-md);
            overflow: hidden;
            box-shadow: var(--shadow-sm);
            border: 1px solid var(--border-subtle);
        }}
        
        th, td {{ 
            padding: var(--space-md); 
            text-align: left;
        }}
        
        th {{ 
            background: var(--bg-elevated);
            color: var(--text-primary);
            font-weight: 600;
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            border-bottom: 1px solid var(--border-default);
        }}
        
        td {{
            border-bottom: 1px solid var(--border-subtle);
        }}
        
        tbody tr:last-child td {{
            border-bottom: none;
        }}
        
        tbody tr:hover {{ 
            background: var(--bg-hover);
        }}
        
        /* Anomaly alerts */
        .anomaly {{
            background: rgba(239, 85, 59, 0.1);
            border-left: 3px solid var(--accent-error);
            padding: var(--space-md);
            margin: var(--space-sm) 0;
            border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
            font-size: 0.9rem;
        }}
        
        /* Skills/Chains tags */
        .chains {{ 
            display: flex; 
            flex-wrap: wrap; 
            gap: var(--space-sm);
            margin-top: var(--space-md);
        }}
        
        .chain {{
            background: var(--bg-elevated);
            padding: var(--space-sm) var(--space-md);
            border-radius: var(--radius-full);
            font-size: 0.875rem;
            border: 1px solid var(--border-subtle);
            display: inline-flex;
            align-items: center;
            gap: var(--space-sm);
        }}
        
        .chain-count {{
            background: var(--accent-primary);
            color: white;
            padding: 2px var(--space-sm);
            border-radius: var(--radius-full);
            font-size: 0.75rem;
            font-weight: 600;
        }}
        
        /* Metrics grid */
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: var(--space-md);
            margin: var(--space-lg) 0;
        }}
        
        .metric-box {{
            background: var(--bg-elevated);
            border-radius: var(--radius-md);
            padding: var(--space-lg);
            text-align: center;
            border: 1px solid var(--border-subtle);
        }}
        
        .metric-value {{ 
            font-size: 1.75rem;
            font-weight: 700;
            color: var(--accent-success);
            line-height: 1.2;
        }}
        
        .metric-label {{ 
            font-size: 0.8rem;
            color: var(--text-secondary);
            margin-top: var(--space-sm);
            text-transform: uppercase;
            letter-spacing: 0.03em;
        }}
        
        /* Agent roles */
        .role-orchestrator {{ color: var(--accent-error); font-weight: 600; }}
        .role-hub {{ color: var(--accent-warning); font-weight: 600; }}
        .role-worker {{ color: var(--accent-success); font-weight: 600; }}
        

        
        .flow-bar {{
            height: 24px;
            background: linear-gradient(90deg, var(--accent-primary), var(--accent-success));
            border-radius: var(--radius-sm);
        }}
        
        .flow-label {{ 
            text-align: right;
            color: var(--text-primary);
        }}
        
        .flow-target {{ 
            color: var(--text-primary);
        }}
        
        .flow-count {{ 
            text-align: left;
            color: var(--text-secondary);
            font-size: 0.85rem;
        }}
        
        /* Hour grid heatmap */
        .hour-grid {{
            display: grid;
            grid-template-columns: repeat(24, 1fr);
            gap: 3px;
            margin: var(--space-md) 0;
        }}
        
        .hour-cell {{
            aspect-ratio: 1;
            border-radius: var(--radius-sm);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.7rem;
            font-weight: 500;
            color: var(--text-primary);
        }}
        
        /* Footer */
        .footer {{
            text-align: center;
            color: var(--text-muted);
            font-size: 0.85rem;
            margin-top: var(--space-2xl);
            padding-top: var(--space-lg);
            border-top: 1px solid var(--border-subtle);
        }}
        
        /* Delegation chains visualization */
        .chain-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: var(--space-md) 0;
        }}
        
        .chain-row:not(:last-child) {{
            border-bottom: 1px solid var(--border-subtle);
        }}
        
        .chain-agents {{
            display: flex;
            align-items: center;
            gap: var(--space-sm);
        }}
        
        .chain-agent {{
            color: var(--text-primary);
            font-family: var(--font-mono);
            font-size: 0.9rem;
            width: 120px;
            text-align: center;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        
        .chain-arrow {{
            color: var(--text-muted);
            font-size: 1.1rem;
        }}
        
        .chain-meta {{
            display: flex;
            align-items: center;
            gap: var(--space-lg);
        }}
        
        .chain-depth {{
            font-weight: 600;
            font-size: 0.9rem;
            min-width: 24px;
            text-align: center;
        }}
        
        .chain-occ {{
            color: var(--text-secondary);
            font-size: 0.9rem;
            min-width: 60px;
            text-align: left;
        }}
        
        /* Header styling mixin - apply to any row to make it a header */
        .is-header {{
            background: var(--bg-elevated);
            color: var(--text-primary);
            font-weight: 600;
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            border-bottom: 1px solid var(--border-default);
            border-radius: 0;
        }}
        
        .is-header span,
        .is-header div {{
            font-family: var(--font-sans);
            color: var(--text-primary);
        }}
        
        /* Delegation Sessions - Grid layout */
        .deleg-session-header,
        .deleg-session-row {{
            display: grid;
            grid-template-columns: 120px 1fr 80px;
            align-items: center;
            gap: var(--space-lg);
            padding: var(--space-md);
        }}
        
        .deleg-session-header {{
            /* Inherits from is-header */
        }}
        
        .deleg-session-row {{
            border-bottom: 1px solid var(--border-subtle);
        }}
        
        .deleg-session-row:last-child {{
            border-bottom: none;
        }}
        
        .deleg-session-agent {{
            font-family: var(--font-mono);
            font-weight: 600;
            font-size: 0.9rem;
        }}
        
        .deleg-session-seq {{
            display: flex;
            align-items: center;
            gap: var(--space-xs);
            font-family: var(--font-mono);
            font-size: 0.85rem;
            color: var(--text-secondary);
        }}
        
        .deleg-arrow {{
            color: var(--text-muted);
        }}
        
        .deleg-more {{
            color: var(--text-muted);
            font-size: 0.8rem;
        }}
        
        .deleg-session-count {{
            text-align: left;
            font-weight: 600;
            color: var(--accent-primary);
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>OpenCode Analytics</h1>
        <p class="subtitle">{period_label} ({start_date} to {end_date})</p>
        
        <div class="cards">
            <div class="card">
                <div class="card-value">{stats.session_count}</div>
                <div class="card-label">Sessions</div>
            </div>
            <div class="card">
                <div class="card-value">{stats.message_count:,}</div>
                <div class="card-label">Messages</div>
            </div>
            <div class="card">
                <div class="card-value">{format_tokens(stats.tokens.input + stats.tokens.output)}</div>
                <div class="card-label">Tokens (In+Out)</div>
            </div>
            <div class="card">
                <div class="card-value">{format_tokens(stats.tokens.output)}</div>
                <div class="card-label">Output</div>
            </div>
            <div class="card">
                <div class="card-value">{stats.avg_session_duration_min:.0f}m</div>
                <div class="card-label">Avg Session</div>
            </div>
        </div>
        
        <div class="chart-container" style="margin-top: 20px;">
            <h3 style="margin-bottom: 15px; color: #fff;">Token Details</h3>
            <table style="width: 100%;">
                <tr>
                    <td colspan="3" style="padding: 8px; color: #636EFA; font-weight: bold;">Tokens Facturés</td>
                </tr>
                <tr>
                    <td style="padding: 8px 8px 8px 24px; color: #888;">Input</td>
                    <td style="padding: 8px; text-align: right; font-family: monospace;">{stats.tokens.input:,}</td>
                    <td></td>
                </tr>
                <tr>
                    <td style="padding: 8px 8px 8px 24px; color: #888;">Output</td>
                    <td style="padding: 8px; text-align: right; font-family: monospace;">{stats.tokens.output:,}</td>
                    <td></td>
                </tr>
                <tr style="border-top: 1px solid #333;">
                    <td style="padding: 8px; color: #fff; font-weight: bold;">Total Facturé</td>
                    <td style="padding: 8px; text-align: right; font-family: monospace; font-weight: bold;">{stats.tokens.input + stats.tokens.output:,}</td>
                    <td></td>
                </tr>
                <tr><td colspan="3" style="padding: 8px;"></td></tr>
                <tr>
                    <td colspan="3" style="padding: 8px; color: #00CC96; font-weight: bold;">Cache (économies)</td>
                </tr>
                <tr>
                    <td style="padding: 8px 8px 8px 24px; color: #888;">Cache Read</td>
                    <td style="padding: 8px; text-align: right; font-family: monospace;">{stats.tokens.cache_read:,}</td>
                    <td style="padding: 8px; color: #00CC96; font-size: 0.9em;">({stats.tokens.cache_hit_ratio:.0f}% hit rate)</td>
                </tr>
                <tr>
                    <td style="padding: 8px 8px 8px 24px; color: #888;">Cache Write</td>
                    <td style="padding: 8px; text-align: right; font-family: monospace;">{stats.tokens.cache_write:,}</td>
                    <td></td>
                </tr>
            </table>
        </div>
"""

    # Add charts
    for i, fig_html in enumerate(figures_html):
        html_content += f'<div class="chart-container">{fig_html}</div>\n'

    # Session Token Stats
    if stats.session_token_stats:
        sts = stats.session_token_stats
        html_content += f"""
        <h2 class="section-title">Session Metrics</h2>
        <div class="metrics-grid">
            <div class="metric-box">
                <div class="metric-value">{format_tokens(sts.avg_tokens)}</div>
                <div class="metric-label">Avg Tokens/Session</div>
            </div>
            <div class="metric-box">
                <div class="metric-value">{format_tokens(sts.median_tokens)}</div>
                <div class="metric-label">Median</div>
            </div>
            <div class="metric-box">
                <div class="metric-value">{format_tokens(sts.max_tokens)}</div>
                <div class="metric-label">Max</div>
            </div>
            <div class="metric-box">
                <div class="metric-value">{format_tokens(sts.min_tokens)}</div>
                <div class="metric-label">Min</div>
            </div>
        </div>
"""

    # Delegation Analytics Section
    if stats.delegation_metrics:
        dm = stats.delegation_metrics
        html_content += f"""
        <h2 class="section-title">Delegation Analytics</h2>
        <div class="metrics-grid">
            <div class="metric-box">
                <div class="metric-value">{dm.total_delegations}</div>
                <div class="metric-label">Total Delegations</div>
            </div>
            <div class="metric-box">
                <div class="metric-value">{dm.sessions_with_delegations}</div>
                <div class="metric-label">Sessions w/ Deleg.</div>
            </div>
            <div class="metric-box">
                <div class="metric-value">{dm.unique_patterns}</div>
                <div class="metric-label">Unique Patterns</div>
            </div>
            <div class="metric-box">
                <div class="metric-value">{dm.recursive_percentage:.0f}%</div>
                <div class="metric-label">Recursive</div>
            </div>
            <div class="metric-box">
                <div class="metric-value">{dm.avg_per_session:.1f}</div>
                <div class="metric-label">Avg/Session</div>
            </div>
            <div class="metric-box">
                <div class="metric-value">{dm.max_depth}</div>
                <div class="metric-label">Max Depth</div>
            </div>
        </div>
"""

    # Agent Roles Table
    if stats.agent_roles:
        html_content += """
        <h2 class="section-title">Agent Architecture</h2>
        <p style="color: var(--text-secondary); margin-bottom: var(--space-md); font-size: 0.9rem;">
            <span class="role-orchestrator">Orchestrator</span> = delegates only |
            <span class="role-hub">Hub</span> = delegates & receives |
            <span class="role-worker">Worker</span> = receives only
        </p>
        <table>
            <thead><tr><th>Agent</th><th>Role</th><th>Sent</th><th>Received</th><th>Fan-out</th><th>Tokens/Task</th></tr></thead>
            <tbody>
"""
        for role in stats.agent_roles:
            role_class = f"role-{role.role}"
            fan_out_str = (
                f"{role.fan_out:.1f}x" if role.fan_out != float("inf") else "∞"
            )
            tokens_str = (
                format_tokens(role.tokens_per_task) if role.tokens_per_task > 0 else "-"
            )
            html_content += f'<tr><td><strong>{html_module.escape(role.agent)}</strong></td><td class="{role_class}">{role.role}</td><td>{role.delegations_sent}</td><td>{role.delegations_received}</td><td>{fan_out_str}</td><td>{tokens_str}</td></tr>\n'
        html_content += "</tbody></table>\n"

    # Delegation Flow Visualization
    if stats.delegation_patterns:
        # Sort by count descending (largest to smallest)
        sorted_patterns = sorted(
            stats.delegation_patterns, key=lambda p: p.count, reverse=True
        )[:12]
        max_count = max(p.count for p in sorted_patterns) if sorted_patterns else 1

        html_content += """
        <h2 class="section-title">Delegation Flow</h2>
        <table>
            <thead><tr><th>From</th><th>To</th><th>Count</th><th>Tokens</th></tr></thead>
            <tbody>
"""
        for pattern in sorted_patterns:
            html_content += f"<tr><td>{html_module.escape(pattern.parent)}</td><td>{html_module.escape(pattern.child)}</td><td>{pattern.count}x</td><td>{format_tokens(pattern.tokens_total)}</td></tr>\n"
        html_content += "</tbody></table>\n"

    # Hourly Delegations Heatmap
    if stats.hourly_delegations:
        max_hourly = (
            max(h.count for h in stats.hourly_delegations)
            if stats.hourly_delegations
            else 1
        )
        hourly_map = {h.hour: h.count for h in stats.hourly_delegations}
        html_content += """
        <h2 class="section-title">Delegation Activity by Hour</h2>
        <div class="chart-container">
            <div class="hour-grid">
"""
        for h in range(24):
            count = hourly_map.get(h, 0)
            intensity = count / max_hourly if max_hourly > 0 else 0
            # Color from dark blue to bright green
            r = int(15 + (0 - 15) * intensity)
            g = int(33 + (204 - 33) * intensity)
            b = int(96 + (150 - 96) * intensity)
            html_content += f'<div class="hour-cell" style="background: rgb({r},{g},{b});" title="{h}h: {count}">{h}</div>\n'
        html_content += """
            </div>
            <p style="color: #888; font-size: 0.85em; margin-top: 10px;">Darker = less activity, Brighter = more activity</p>
        </div>
"""

    # Agent chains section - visual pipeline representation
    if stats.agent_chains:
        html_content += """
        <h2 class="section-title">Top Delegation Chains</h2>
        <table>
            <thead><tr><th>Chain</th><th>Depth</th><th>Count</th></tr></thead>
            <tbody>
"""
        for chain in stats.agent_chains[:10]:
            depth_color = (
                "var(--accent-warning)" if chain.depth >= 3 else "var(--accent-success)"
            )
            escaped_chain = html_module.escape(chain.chain)
            html_content += f'<tr><td style="font-family: var(--font-mono);">{escaped_chain}</td><td style="color: {depth_color}; font-weight: 600;">{chain.depth}</td><td>{chain.occurrences}x</td></tr>\n'
        html_content += "</tbody></table>\n"

    # Top sessions table
    if stats.top_sessions:
        html_content += """
        <h2 class="section-title">Top Sessions by Token Usage</h2>
        <table>
            <thead><tr><th>Session</th><th>Messages</th><th>Tokens</th><th>Duration</th></tr></thead>
            <tbody>
"""
        for session in stats.top_sessions[:10]:
            title = (
                session.title[:50] + "..." if len(session.title) > 50 else session.title
            )
            escaped_title = html_module.escape(title)
            html_content += f"<tr><td>{escaped_title}</td><td>{session.message_count}</td><td>{format_tokens(session.tokens.total)}</td><td>{session.duration_minutes}m</td></tr>\n"
        html_content += "</tbody></table>\n"

    # Skills section
    if stats.skills:
        html_content += (
            '<h2 class="section-title">Skills Used</h2>\n<div class="chains">\n'
        )
        for skill in stats.skills:
            escaped_skill = html_module.escape(skill.skill_name)
            html_content += f'<div class="chain">{escaped_skill}<span class="chain-count">{skill.load_count}</span></div>\n'
        html_content += "</div>\n"

    # Skills by Agent section
    if stats.skills_by_agent:
        html_content += """
        <h2 class="section-title">Skills by Agent</h2>
        <table>
            <thead><tr><th>Agent</th><th>Skill</th><th>Uses</th></tr></thead>
            <tbody>
"""
        for sba in stats.skills_by_agent[:15]:
            html_content += f'<tr><td><strong>{html_module.escape(sba.agent)}</strong></td><td style="font-family: monospace;">{html_module.escape(sba.skill_name)}</td><td>{sba.count}</td></tr>\n'
        html_content += "</tbody></table>\n"

    # Agent Delegation Stats section
    if stats.agent_delegation_stats:
        html_content += """
        <h2 class="section-title">Delegation Statistics by Agent</h2>
        <table>
            <thead><tr><th>Agent</th><th>Sessions</th><th>Total Delegations</th><th>Avg/Session</th><th>Max/Session</th></tr></thead>
            <tbody>
"""
        for ads in stats.agent_delegation_stats:
            html_content += f"<tr><td><strong>{html_module.escape(ads.agent)}</strong></td><td>{ads.sessions_with_delegations}</td><td>{ads.total_delegations}</td><td>{ads.avg_per_session:.1f}</td><td>{ads.max_per_session}</td></tr>\n"
        html_content += "</tbody></table>\n"

    # Delegation Sessions section (sessions with multiple sequential delegations)
    if stats.delegation_sessions:
        html_content += """
        <h2 class="section-title">Sessions with Multiple Delegations</h2>
        <table>
            <thead><tr><th>Agent</th><th>Delegation Sequence</th><th>Count</th></tr></thead>
            <tbody>
"""
        for ds in stats.delegation_sessions[:12]:
            sequence_display = ds.sequence.replace(" -> ", " → ")
            if len(sequence_display) > 60:
                sequence_display = sequence_display[:57] + "..."
            html_content += f'<tr><td><strong>{html_module.escape(ds.agent)}</strong></td><td style="font-family: var(--font-mono); font-size: 0.85rem;">{html_module.escape(sequence_display)}</td><td>{ds.delegation_count}</td></tr>\n'
        html_content += "</tbody></table>\n"

    # Models section
    if stats.models:
        html_content += """
        <h2 class="section-title">Models Used</h2>
        <table>
            <thead><tr><th>Provider</th><th>Model</th><th>Tokens</th><th>Share</th></tr></thead>
            <tbody>
"""
        for model in stats.models[:8]:
            html_content += f"<tr><td>{html_module.escape(model.provider_id)}</td><td>{html_module.escape(model.model_id)}</td><td>{format_tokens(model.tokens)}</td><td>{model.percentage:.0f}%</td></tr>\n"
        html_content += "</tbody></table>\n"

    # Directories section
    if stats.directories:
        html_content += """
        <h2 class="section-title">Top Directories</h2>
        <table>
            <thead><tr><th>Directory</th><th>Sessions</th><th>Tokens</th></tr></thead>
            <tbody>
"""
        for d in stats.directories[:8]:
            short_dir = (
                "..." + d.directory[-45:] if len(d.directory) > 45 else d.directory
            )
            html_content += f'<tr><td style="font-family: monospace; font-size: 0.9em;">{html_module.escape(short_dir)}</td><td>{d.sessions}</td><td>{format_tokens(d.tokens)}</td></tr>\n'
        html_content += "</tbody></table>\n"

    # Anomalies section
    if stats.anomalies:
        html_content += '<h2 class="section-title">Anomalies Detected</h2>\n'
        for anomaly in stats.anomalies:
            escaped_anomaly = html_module.escape(anomaly)
            html_content += f'<div class="anomaly">{escaped_anomaly}</div>\n'

    # Footer
    html_content += f"""
        <p class="footer">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    </div>
</body>
</html>
"""
    return html_content


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
        lines = []
        lines.append("=" * 50)
        lines.append("       OPENCODE ANALYTICS REPORT")
        lines.append("=" * 50)
        lines.append("")
        lines.append(f"Period: {self.period_label}")
        lines.append(f"Sessions: {self.stats.session_count}")
        lines.append(f"Messages: {self.stats.message_count}")
        lines.append(f"Tokens: {format_tokens(self.stats.tokens.total)}")
        lines.append(f"Cache Hit Ratio: {self.stats.tokens.cache_hit_ratio:.0f}%")

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
    """Generate an analytics report for the specified period."""
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
