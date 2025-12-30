"""
CSS Design System for analytics reports.

Based on 8px spacing scale with dark theme and blue tint.
"""

CSS_VARIABLES = """
:root {
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
}
"""

CSS_BASE = """
* { margin: 0; padding: 0; box-sizing: border-box; }

body { 
    font-family: var(--font-sans);
    font-size: 15px;
    line-height: 1.5;
    background: var(--bg-base);
    color: var(--text-primary);
    padding: var(--space-lg);
}

/* Container */
.container { 
    max-width: 1200px; 
    margin: 0 auto;
    padding: 0 var(--space-md);
}

/* Header */
h1 { 
    text-align: center; 
    font-size: 2rem;
    font-weight: 600;
    letter-spacing: -0.02em;
    margin-bottom: var(--space-sm);
    color: var(--text-primary);
}

.subtitle { 
    text-align: center; 
    color: var(--text-secondary);
    font-size: 0.95rem;
    margin-bottom: var(--space-xl);
}
"""

CSS_CARDS = """
/* Cards grid */
.cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: var(--space-md);
    margin-bottom: var(--space-xl);
}

.card {
    background: var(--bg-surface);
    border-radius: var(--radius-md);
    padding: var(--space-lg);
    text-align: center;
    box-shadow: var(--shadow-sm);
    border: 1px solid var(--border-subtle);
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.card:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
}

.card-value { 
    font-size: 2rem; 
    font-weight: 700;
    color: var(--accent-primary);
    line-height: 1.2;
}

.card-label { 
    color: var(--text-secondary);
    font-size: 0.85rem;
    margin-top: var(--space-sm);
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
"""

CSS_CHARTS = """
/* Chart containers */
.chart-container {
    background: var(--bg-surface);
    border-radius: var(--radius-md);
    padding: var(--space-lg);
    margin-bottom: var(--space-lg);
    box-shadow: var(--shadow-sm);
    border: 1px solid var(--border-subtle);
}

.chart-container h3 {
    font-size: 1rem;
    font-weight: 600;
    margin-bottom: var(--space-md);
    color: var(--text-primary);
}

/* Section titles */
.section-title {
    font-size: 1.25rem;
    font-weight: 600;
    margin: var(--space-2xl) 0 var(--space-lg);
    color: var(--text-primary);
    padding-bottom: var(--space-sm);
    border-bottom: 2px solid var(--border-default);
}
"""

CSS_TABLES = """
/* Tables */
table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    background: var(--bg-surface);
    border-radius: var(--radius-md);
    overflow: hidden;
    box-shadow: var(--shadow-sm);
    border: 1px solid var(--border-subtle);
}

th, td { 
    padding: var(--space-md); 
    text-align: left;
}

th { 
    background: var(--bg-elevated);
    color: var(--text-primary);
    font-weight: 600;
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-bottom: 1px solid var(--border-default);
}

td {
    border-bottom: 1px solid var(--border-subtle);
}

tbody tr:last-child td {
    border-bottom: none;
}

tbody tr:hover { 
    background: var(--bg-hover);
}
"""

CSS_COMPONENTS = """
/* Anomaly alerts */
.anomaly {
    background: rgba(239, 85, 59, 0.1);
    border-left: 3px solid var(--accent-error);
    padding: var(--space-md);
    margin: var(--space-sm) 0;
    border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
    font-size: 0.9rem;
}

/* Skills/Chains tags */
.chains { 
    display: flex; 
    flex-wrap: wrap; 
    gap: var(--space-sm);
    margin-top: var(--space-md);
}

.chain {
    background: var(--bg-elevated);
    padding: var(--space-sm) var(--space-md);
    border-radius: var(--radius-full);
    font-size: 0.875rem;
    border: 1px solid var(--border-subtle);
    display: inline-flex;
    align-items: center;
    gap: var(--space-sm);
}

.chain-count {
    background: var(--accent-primary);
    color: white;
    padding: 2px var(--space-sm);
    border-radius: var(--radius-full);
    font-size: 0.75rem;
    font-weight: 600;
}

/* Metrics grid */
.metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: var(--space-md);
    margin: var(--space-lg) 0;
}

.metric-box {
    background: var(--bg-elevated);
    border-radius: var(--radius-md);
    padding: var(--space-lg);
    text-align: center;
    border: 1px solid var(--border-subtle);
}

.metric-value { 
    font-size: 1.75rem;
    font-weight: 700;
    color: var(--accent-success);
    line-height: 1.2;
}

.metric-label { 
    font-size: 0.8rem;
    color: var(--text-secondary);
    margin-top: var(--space-sm);
    text-transform: uppercase;
    letter-spacing: 0.03em;
}

/* Agent roles */
.role-orchestrator { color: var(--accent-error); font-weight: 600; }
.role-hub { color: var(--accent-warning); font-weight: 600; }
.role-worker { color: var(--accent-success); font-weight: 600; }
"""

CSS_DELEGATION = """
/* Delegation flow */
.flow-bar {
    height: 24px;
    background: linear-gradient(90deg, var(--accent-primary), var(--accent-success));
    border-radius: var(--radius-sm);
}

.flow-label { 
    text-align: right;
    color: var(--text-primary);
}

.flow-target { 
    color: var(--text-primary);
}

.flow-count { 
    text-align: left;
    color: var(--text-secondary);
    font-size: 0.85rem;
}

/* Hour grid heatmap */
.hour-grid {
    display: grid;
    grid-template-columns: repeat(24, 1fr);
    gap: 3px;
    margin: var(--space-md) 0;
}

.hour-cell {
    aspect-ratio: 1;
    border-radius: var(--radius-sm);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.7rem;
    font-weight: 500;
    color: var(--text-primary);
}

/* Delegation chains visualization */
.chain-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-md) 0;
}

.chain-row:not(:last-child) {
    border-bottom: 1px solid var(--border-subtle);
}

.chain-agents {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
}

.chain-agent {
    color: var(--text-primary);
    font-family: var(--font-mono);
    font-size: 0.9rem;
    width: 120px;
    text-align: center;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.chain-arrow {
    color: var(--text-muted);
    font-size: 1.1rem;
}

.chain-meta {
    display: flex;
    align-items: center;
    gap: var(--space-lg);
}

.chain-depth {
    font-weight: 600;
    font-size: 0.9rem;
    min-width: 24px;
    text-align: center;
}

.chain-occ {
    color: var(--text-secondary);
    font-size: 0.9rem;
    min-width: 60px;
    text-align: left;
}

/* Header styling mixin */
.is-header {
    background: var(--bg-elevated);
    color: var(--text-primary);
    font-weight: 600;
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-bottom: 1px solid var(--border-default);
    border-radius: 0;
}

.is-header span,
.is-header div {
    font-family: var(--font-sans);
    color: var(--text-primary);
}

/* Delegation Sessions - Grid layout */
.deleg-session-header,
.deleg-session-row {
    display: grid;
    grid-template-columns: 120px 1fr 80px;
    align-items: center;
    gap: var(--space-lg);
    padding: var(--space-md);
}

.deleg-session-row {
    border-bottom: 1px solid var(--border-subtle);
}

.deleg-session-row:last-child {
    border-bottom: none;
}

.deleg-session-agent {
    font-family: var(--font-mono);
    font-weight: 600;
    font-size: 0.9rem;
}

.deleg-session-seq {
    display: flex;
    align-items: center;
    gap: var(--space-xs);
    font-family: var(--font-mono);
    font-size: 0.85rem;
    color: var(--text-secondary);
}

.deleg-arrow {
    color: var(--text-muted);
}

.deleg-more {
    color: var(--text-muted);
    font-size: 0.8rem;
}

.deleg-session-count {
    text-align: left;
    font-weight: 600;
    color: var(--accent-primary);
}
"""

CSS_FOOTER = """
/* Footer */
.footer {
    text-align: center;
    color: var(--text-muted);
    font-size: 0.85rem;
    margin-top: var(--space-2xl);
    padding-top: var(--space-lg);
    border-top: 1px solid var(--border-subtle);
}
"""


def get_full_css() -> str:
    """Get the complete CSS stylesheet."""
    return "\n".join(
        [
            CSS_VARIABLES,
            CSS_BASE,
            CSS_CARDS,
            CSS_CHARTS,
            CSS_TABLES,
            CSS_COMPONENTS,
            CSS_DELEGATION,
            CSS_FOOTER,
        ]
    )
