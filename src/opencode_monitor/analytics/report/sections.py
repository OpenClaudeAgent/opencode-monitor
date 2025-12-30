"""
HTML section generators for analytics reports.
"""

import html as html_module

from ..models import PeriodStats


def format_tokens(count: int) -> str:
    """Format token count for display."""
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    elif count >= 1_000:
        return f"{count / 1_000:.0f}K"
    return str(count)


def generate_header(stats: PeriodStats, period_label: str) -> str:
    """Generate the page header with title and summary cards."""
    start_date = stats.start_date.strftime("%Y-%m-%d")
    end_date = stats.end_date.strftime("%Y-%m-%d")

    return f"""
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
"""


def generate_token_details(stats: PeriodStats) -> str:
    """Generate the token details breakdown table."""
    return f"""
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


def generate_session_metrics(stats: PeriodStats) -> str:
    """Generate session token statistics section."""
    if not stats.session_token_stats:
        return ""

    sts = stats.session_token_stats
    return f"""
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


def generate_delegation_analytics(stats: PeriodStats) -> str:
    """Generate delegation analytics metrics section."""
    if not stats.delegation_metrics:
        return ""

    dm = stats.delegation_metrics
    return f"""
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


def generate_agent_roles(stats: PeriodStats) -> str:
    """Generate agent architecture/roles table."""
    if not stats.agent_roles:
        return ""

    html = """
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
        fan_out_str = f"{role.fan_out:.1f}x" if role.fan_out != float("inf") else "∞"
        tokens_str = (
            format_tokens(role.tokens_per_task) if role.tokens_per_task > 0 else "-"
        )
        html += f'<tr><td><strong>{html_module.escape(role.agent)}</strong></td><td class="{role_class}">{role.role}</td><td>{role.delegations_sent}</td><td>{role.delegations_received}</td><td>{fan_out_str}</td><td>{tokens_str}</td></tr>\n'
    html += "</tbody></table>\n"
    return html


def generate_delegation_flow(stats: PeriodStats) -> str:
    """Generate delegation flow table."""
    if not stats.delegation_patterns:
        return ""

    sorted_patterns = sorted(
        stats.delegation_patterns, key=lambda p: p.count, reverse=True
    )[:12]

    html = """
        <h2 class="section-title">Delegation Flow</h2>
        <table>
            <thead><tr><th>From</th><th>To</th><th>Count</th><th>Tokens</th></tr></thead>
            <tbody>
"""
    for pattern in sorted_patterns:
        html += f"<tr><td>{html_module.escape(pattern.parent)}</td><td>{html_module.escape(pattern.child)}</td><td>{pattern.count}x</td><td>{format_tokens(pattern.tokens_total)}</td></tr>\n"
    html += "</tbody></table>\n"
    return html


def generate_hourly_heatmap(stats: PeriodStats) -> str:
    """Generate hourly delegations heatmap."""
    if not stats.hourly_delegations:
        return ""

    max_hourly = max(h.count for h in stats.hourly_delegations)
    hourly_map = {h.hour: h.count for h in stats.hourly_delegations}

    html = """
        <h2 class="section-title">Delegation Activity by Hour</h2>
        <div class="chart-container">
            <div class="hour-grid">
"""
    for h in range(24):
        count = hourly_map.get(h, 0)
        intensity = count / max_hourly if max_hourly > 0 else 0
        r = int(15 + (0 - 15) * intensity)
        g = int(33 + (204 - 33) * intensity)
        b = int(96 + (150 - 96) * intensity)
        html += f'<div class="hour-cell" style="background: rgb({r},{g},{b});" title="{h}h: {count}">{h}</div>\n'
    html += """
            </div>
            <p style="color: #888; font-size: 0.85em; margin-top: 10px;">Darker = less activity, Brighter = more activity</p>
        </div>
"""
    return html


def generate_agent_chains(stats: PeriodStats) -> str:
    """Generate top delegation chains table."""
    if not stats.agent_chains:
        return ""

    html = """
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
        html += f'<tr><td style="font-family: var(--font-mono);">{escaped_chain}</td><td style="color: {depth_color}; font-weight: 600;">{chain.depth}</td><td>{chain.occurrences}x</td></tr>\n'
    html += "</tbody></table>\n"
    return html


def generate_top_sessions(stats: PeriodStats) -> str:
    """Generate top sessions by token usage table."""
    if not stats.top_sessions:
        return ""

    html = """
        <h2 class="section-title">Top Sessions by Token Usage</h2>
        <table>
            <thead><tr><th>Session</th><th>Messages</th><th>Tokens</th><th>Duration</th></tr></thead>
            <tbody>
"""
    for session in stats.top_sessions[:10]:
        title = session.title[:50] + "..." if len(session.title) > 50 else session.title
        escaped_title = html_module.escape(title)
        html += f"<tr><td>{escaped_title}</td><td>{session.message_count}</td><td>{format_tokens(session.tokens.total)}</td><td>{session.duration_minutes}m</td></tr>\n"
    html += "</tbody></table>\n"
    return html


def generate_skills(stats: PeriodStats) -> str:
    """Generate skills used section."""
    if not stats.skills:
        return ""

    html = '<h2 class="section-title">Skills Used</h2>\n<div class="chains">\n'
    for skill in stats.skills:
        escaped_skill = html_module.escape(skill.skill_name)
        html += f'<div class="chain">{escaped_skill}<span class="chain-count">{skill.load_count}</span></div>\n'
    html += "</div>\n"
    return html


def generate_skills_by_agent(stats: PeriodStats) -> str:
    """Generate skills by agent table."""
    if not stats.skills_by_agent:
        return ""

    html = """
        <h2 class="section-title">Skills by Agent</h2>
        <table>
            <thead><tr><th>Agent</th><th>Skill</th><th>Uses</th></tr></thead>
            <tbody>
"""
    for sba in stats.skills_by_agent[:15]:
        html += f'<tr><td><strong>{html_module.escape(sba.agent)}</strong></td><td style="font-family: monospace;">{html_module.escape(sba.skill_name)}</td><td>{sba.count}</td></tr>\n'
    html += "</tbody></table>\n"
    return html


def generate_agent_delegation_stats(stats: PeriodStats) -> str:
    """Generate delegation statistics by agent table."""
    if not stats.agent_delegation_stats:
        return ""

    html = """
        <h2 class="section-title">Delegation Statistics by Agent</h2>
        <table>
            <thead><tr><th>Agent</th><th>Sessions</th><th>Total Delegations</th><th>Avg/Session</th><th>Max/Session</th></tr></thead>
            <tbody>
"""
    for ads in stats.agent_delegation_stats:
        html += f"<tr><td><strong>{html_module.escape(ads.agent)}</strong></td><td>{ads.sessions_with_delegations}</td><td>{ads.total_delegations}</td><td>{ads.avg_per_session:.1f}</td><td>{ads.max_per_session}</td></tr>\n"
    html += "</tbody></table>\n"
    return html


def generate_delegation_sessions(stats: PeriodStats) -> str:
    """Generate sessions with multiple delegations table."""
    if not stats.delegation_sessions:
        return ""

    html = """
        <h2 class="section-title">Sessions with Multiple Delegations</h2>
        <table>
            <thead><tr><th>Agent</th><th>Delegation Sequence</th><th>Count</th></tr></thead>
            <tbody>
"""
    for ds in stats.delegation_sessions[:12]:
        sequence_display = ds.sequence.replace(" -> ", " → ")
        if len(sequence_display) > 60:
            sequence_display = sequence_display[:57] + "..."
        html += f'<tr><td><strong>{html_module.escape(ds.agent)}</strong></td><td style="font-family: var(--font-mono); font-size: 0.85rem;">{html_module.escape(sequence_display)}</td><td>{ds.delegation_count}</td></tr>\n'
    html += "</tbody></table>\n"
    return html


def generate_models(stats: PeriodStats) -> str:
    """Generate models used table."""
    if not stats.models:
        return ""

    html = """
        <h2 class="section-title">Models Used</h2>
        <table>
            <thead><tr><th>Provider</th><th>Model</th><th>Tokens</th><th>Share</th></tr></thead>
            <tbody>
"""
    for model in stats.models[:8]:
        html += f"<tr><td>{html_module.escape(model.provider_id)}</td><td>{html_module.escape(model.model_id)}</td><td>{format_tokens(model.tokens)}</td><td>{model.percentage:.0f}%</td></tr>\n"
    html += "</tbody></table>\n"
    return html


def generate_directories(stats: PeriodStats) -> str:
    """Generate top directories table."""
    if not stats.directories:
        return ""

    html = """
        <h2 class="section-title">Top Directories</h2>
        <table>
            <thead><tr><th>Directory</th><th>Sessions</th><th>Tokens</th></tr></thead>
            <tbody>
"""
    for d in stats.directories[:8]:
        short_dir = "..." + d.directory[-45:] if len(d.directory) > 45 else d.directory
        html += f'<tr><td style="font-family: monospace; font-size: 0.9em;">{html_module.escape(short_dir)}</td><td>{d.sessions}</td><td>{format_tokens(d.tokens)}</td></tr>\n'
    html += "</tbody></table>\n"
    return html


def generate_anomalies(stats: PeriodStats) -> str:
    """Generate anomalies section."""
    if not stats.anomalies:
        return ""

    html = '<h2 class="section-title">Anomalies Detected</h2>\n'
    for anomaly in stats.anomalies:
        escaped_anomaly = html_module.escape(anomaly)
        html += f'<div class="anomaly">{escaped_anomaly}</div>\n'
    return html
