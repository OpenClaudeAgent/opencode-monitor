"""
Quick Check-in session test data.

Session Reference: "Quick check-in"
- 5 user turns total (EXACT)
- 6 tools: 2 webfetch + 1 bash + 1 read + 2 read in delegation (EXACT)
- 1 delegation to "roadmap" agent with 2 nested tools (EXACT)

All values are EXACT from the real session - NO approximations.
"""

# =============================================================================
# Session-level constants
# =============================================================================

SESSION_ID = "ses_quick_checkin_001"
SESSION_TITLE = "Quick check-in"
SESSION_DIRECTORY = "/Users/test/project"
SESSION_PROJECT_NAME = "project"  # Extracted from directory
SESSION_TOKENS_IN = 129
SESSION_TOKENS_OUT = 9101
SESSION_CACHE_READ = 417959

# =============================================================================
# User Turn 1 - Simple greeting (NO tools)
# =============================================================================

UT1_TRACE_ID = "exchange_msg_001"
UT1_PROMPT = "Salut, est-ce que ça va ?"
UT1_AGENT = "plan"
UT1_TOKENS_IN = 8
UT1_TOKENS_OUT = 305
UT1_DURATION_MS = 14708
UT1_TOOL_COUNT = 0

# =============================================================================
# User Turn 2 - Weather API (2 webfetch tools)
# =============================================================================

UT2_TRACE_ID = "exchange_msg_002"
UT2_PROMPT = "Cherche une API météo"
UT2_AGENT = "plan"
UT2_TOKENS_IN = 12
UT2_TOKENS_OUT = 558
UT2_DURATION_MS = 4673
UT2_TOOL_COUNT = 2
UT2_TOOL1_NAME = "webfetch"
UT2_TOOL1_DISPLAY = "https://www.weatherapi.com/"
UT2_TOOL1_ICON = "🌐"
UT2_TOOL1_DURATION_MS = 258
UT2_TOOL2_NAME = "webfetch"
UT2_TOOL2_DISPLAY = "https://openweathermap.org/api"
UT2_TOOL2_ICON = "🌐"
UT2_TOOL2_DURATION_MS = 173

# =============================================================================
# User Turn 3 - Create file (1 bash tool)
# =============================================================================

UT3_TRACE_ID = "exchange_msg_003"
UT3_PROMPT = "Crée un fichier test"
UT3_AGENT = "plan"
UT3_TOKENS_IN = 11
UT3_TOKENS_OUT = 143
UT3_DURATION_MS = 3918
UT3_TOOL_COUNT = 1
UT3_TOOL1_NAME = "bash"
UT3_TOOL1_DISPLAY = "touch /tmp/test.txt"
UT3_TOOL1_ICON = "🔧"
UT3_TOOL1_DURATION_MS = 37

# =============================================================================
# User Turn 4 - Read README (1 read tool)
# =============================================================================

UT4_TRACE_ID = "exchange_msg_004"
UT4_PROMPT = "Lis le README"
UT4_AGENT = "plan"
UT4_TOKENS_IN = 10
UT4_TOKENS_OUT = 1778
UT4_DURATION_MS = 5052
UT4_TOOL_COUNT = 1
UT4_TOOL1_NAME = "read"
UT4_TOOL1_DISPLAY = "/path/to/README.md"
UT4_TOOL1_ICON = "📖"
UT4_TOOL1_DURATION_MS = 2

# =============================================================================
# User Turn 5 - Delegation (1 agent with 2 tools)
# =============================================================================

UT5_TRACE_ID = "exchange_msg_005"
UT5_PROMPT = "Lance l'agent roadmap"
UT5_AGENT = "plan"
UT5_TOKENS_IN = 15
UT5_TOKENS_OUT = 500
UT5_DURATION_MS = 165000
UT5_DELEGATION_COUNT = 1
UT5_DIRECT_TOOL_COUNT = 0  # Tools are inside the delegation, not direct children

# =============================================================================
# Delegation details
# =============================================================================

DELEG_AGENT_TYPE = "roadmap"
DELEG_PARENT_AGENT = "plan"
DELEG_TOKENS_IN = 35
DELEG_TOKENS_OUT = 3127
DELEG_DURATION_MS = 158859
DELEG_TOOL_COUNT = 2
DELEG_TOOL1_NAME = "read"
DELEG_TOOL1_DISPLAY = "/path/to/roadmap/README.md"
DELEG_TOOL1_ICON = "📖"
DELEG_TOOL1_DURATION_MS = 2
DELEG_TOOL2_NAME = "read"
DELEG_TOOL2_DISPLAY = "/path/to/roadmap/SPRINTS.md"
DELEG_TOOL2_ICON = "📖"
DELEG_TOOL2_DURATION_MS = 1

# =============================================================================
# Total counts (EXACT)
# =============================================================================

TOTAL_USER_TURNS = 5
TOTAL_TOOLS = 6  # 2 + 1 + 1 + 2 (in delegation)
TOTAL_DELEGATIONS = 1
TOTAL_ROOT_CHILDREN = 5  # 5 user turns directly under root

# =============================================================================
# Expected labels (EXACT)
# =============================================================================

ROOT_LABEL = f"🌳 {SESSION_PROJECT_NAME}"
UT1_LABEL = f'💬 user → {UT1_AGENT}: "{UT1_PROMPT}"'
UT2_LABEL = f'💬 user → {UT2_AGENT}: "{UT2_PROMPT}"'
UT3_LABEL = f'💬 user → {UT3_AGENT}: "{UT3_PROMPT}"'
UT4_LABEL = f'💬 user → {UT4_AGENT}: "{UT4_PROMPT}"'
UT5_LABEL = f'💬 user → {UT5_AGENT}: "{UT5_PROMPT}"'
# Note: depth=2 (root→ut5→delegation), so icon is └─ not 🔗
DELEG_LABEL = f"└─ {DELEG_PARENT_AGENT} → {DELEG_AGENT_TYPE}"

# Tool labels (EXACT)
UT2_TOOL1_LABEL = f"{UT2_TOOL1_ICON} {UT2_TOOL1_NAME}: {UT2_TOOL1_DISPLAY}"
UT2_TOOL2_LABEL = f"{UT2_TOOL2_ICON} {UT2_TOOL2_NAME}: {UT2_TOOL2_DISPLAY}"
UT3_TOOL1_LABEL = f"{UT3_TOOL1_ICON} {UT3_TOOL1_NAME}: {UT3_TOOL1_DISPLAY}"
UT4_TOOL1_LABEL = f"{UT4_TOOL1_ICON} {UT4_TOOL1_NAME}: {UT4_TOOL1_DISPLAY}"
DELEG_TOOL1_LABEL = f"{DELEG_TOOL1_ICON} {DELEG_TOOL1_NAME}: {DELEG_TOOL1_DISPLAY}"
DELEG_TOOL2_LABEL = f"{DELEG_TOOL2_ICON} {DELEG_TOOL2_NAME}: {DELEG_TOOL2_DISPLAY}"


# =============================================================================
# Complete Mock Data Function
# =============================================================================


def quick_checkin_tracing_data() -> dict:
    """Create complete mock tracing data for Quick check-in session.

    This data structure matches exactly what the API returns and what
    the dashboard expects. Every value is from the real session.

    Returns:
        Dict with session_hierarchy for tracing section
    """
    return {
        "session_hierarchy": [
            {
                "session_id": SESSION_ID,
                "node_type": "session",
                "title": SESSION_TITLE,
                "directory": SESSION_DIRECTORY,
                "agent_type": "plan",
                "tokens_in": SESSION_TOKENS_IN,
                "tokens_out": SESSION_TOKENS_OUT,
                "cache_read": SESSION_CACHE_READ,
                "started_at": "2026-01-04T15:44:31.235000",
                "children": [
                    # ========== USER TURN 1 - No tools ==========
                    {
                        "node_type": "user_turn",
                        "trace_id": UT1_TRACE_ID,
                        "prompt_input": UT1_PROMPT,
                        "tokens_in": UT1_TOKENS_IN,
                        "tokens_out": UT1_TOKENS_OUT,
                        "duration_ms": UT1_DURATION_MS,
                        "cache_read": 0,
                        "parent_agent": "user",
                        "subagent_type": UT1_AGENT,
                        "session_id": SESSION_ID,
                        "started_at": "2026-01-04T15:44:31.248000",
                        "ended_at": "2026-01-04T15:44:45.956000",
                        "children": [],
                    },
                    # ========== USER TURN 2 - 2 webfetch tools ==========
                    {
                        "node_type": "user_turn",
                        "trace_id": UT2_TRACE_ID,
                        "prompt_input": UT2_PROMPT,
                        "tokens_in": UT2_TOKENS_IN,
                        "tokens_out": UT2_TOKENS_OUT,
                        "duration_ms": UT2_DURATION_MS,
                        "cache_read": 36680,
                        "parent_agent": "user",
                        "subagent_type": UT2_AGENT,
                        "session_id": SESSION_ID,
                        "started_at": "2026-01-04T15:45:48.773000",
                        "ended_at": "2026-01-04T15:45:53.446000",
                        "children": [
                            {
                                "node_type": "tool",
                                "tool_name": UT2_TOOL1_NAME,
                                "display_info": UT2_TOOL1_DISPLAY,
                                "arguments": f'{{"url": "{UT2_TOOL1_DISPLAY}", "format": "text"}}',
                                "duration_ms": UT2_TOOL1_DURATION_MS,
                                "tool_status": "completed",
                                "status": "completed",
                                "trace_id": "tool_prt_001",
                                "session_id": SESSION_ID,
                                "started_at": "2026-01-04T15:45:53.089000",
                                "children": [],
                            },
                            {
                                "node_type": "tool",
                                "tool_name": UT2_TOOL2_NAME,
                                "display_info": UT2_TOOL2_DISPLAY,
                                "arguments": f'{{"url": "{UT2_TOOL2_DISPLAY}", "format": "text"}}',
                                "duration_ms": UT2_TOOL2_DURATION_MS,
                                "tool_status": "completed",
                                "status": "completed",
                                "trace_id": "tool_prt_002",
                                "session_id": SESSION_ID,
                                "started_at": "2026-01-04T15:45:53.262000",
                                "children": [],
                            },
                        ],
                    },
                    # ========== USER TURN 3 - 1 bash tool ==========
                    {
                        "node_type": "user_turn",
                        "trace_id": UT3_TRACE_ID,
                        "prompt_input": UT3_PROMPT,
                        "tokens_in": UT3_TOKENS_IN,
                        "tokens_out": UT3_TOKENS_OUT,
                        "duration_ms": UT3_DURATION_MS,
                        "cache_read": 68618,
                        "parent_agent": "user",
                        "subagent_type": UT3_AGENT,
                        "session_id": SESSION_ID,
                        "started_at": "2026-01-04T15:46:10.000000",
                        "ended_at": "2026-01-04T15:46:13.918000",
                        "children": [
                            {
                                "node_type": "tool",
                                "tool_name": UT3_TOOL1_NAME,
                                "display_info": UT3_TOOL1_DISPLAY,
                                "arguments": f'{{"command": "{UT3_TOOL1_DISPLAY}", "description": "Create test file"}}',
                                "duration_ms": UT3_TOOL1_DURATION_MS,
                                "tool_status": "completed",
                                "status": "completed",
                                "trace_id": "tool_prt_003",
                                "session_id": SESSION_ID,
                                "started_at": "2026-01-04T15:46:10.500000",
                                "children": [],
                            },
                        ],
                    },
                    # ========== USER TURN 4 - 1 read tool ==========
                    {
                        "node_type": "user_turn",
                        "trace_id": UT4_TRACE_ID,
                        "prompt_input": UT4_PROMPT,
                        "tokens_in": UT4_TOKENS_IN,
                        "tokens_out": UT4_TOKENS_OUT,
                        "duration_ms": UT4_DURATION_MS,
                        "cache_read": 72980,
                        "parent_agent": "user",
                        "subagent_type": UT4_AGENT,
                        "session_id": SESSION_ID,
                        "started_at": "2026-01-04T15:47:00.000000",
                        "ended_at": "2026-01-04T15:47:05.052000",
                        "children": [
                            {
                                "node_type": "tool",
                                "tool_name": UT4_TOOL1_NAME,
                                "display_info": UT4_TOOL1_DISPLAY,
                                "arguments": f'{{"filePath": "{UT4_TOOL1_DISPLAY}"}}',
                                "duration_ms": UT4_TOOL1_DURATION_MS,
                                "tool_status": "completed",
                                "status": "completed",
                                "trace_id": "tool_prt_004",
                                "session_id": SESSION_ID,
                                "started_at": "2026-01-04T15:47:00.500000",
                                "children": [],
                            },
                        ],
                    },
                    # ========== USER TURN 5 - Delegation with nested tools ==========
                    {
                        "node_type": "user_turn",
                        "trace_id": UT5_TRACE_ID,
                        "prompt_input": UT5_PROMPT,
                        "tokens_in": UT5_TOKENS_IN,
                        "tokens_out": UT5_TOKENS_OUT,
                        "duration_ms": UT5_DURATION_MS,
                        "cache_read": 30128,
                        "parent_agent": "user",
                        "subagent_type": UT5_AGENT,
                        "session_id": SESSION_ID,
                        "started_at": "2026-01-04T15:48:00.000000",
                        "ended_at": "2026-01-04T15:50:45.000000",
                        "child_session_id": "ses_child_001",
                        "children": [
                            # DELEGATION to roadmap agent
                            {
                                "node_type": "agent",
                                "subagent_type": DELEG_AGENT_TYPE,
                                "parent_agent": DELEG_PARENT_AGENT,
                                "tokens_in": DELEG_TOKENS_IN,
                                "tokens_out": DELEG_TOKENS_OUT,
                                "duration_ms": DELEG_DURATION_MS,
                                "cache_read": 261028,
                                "trace_id": "prt_delegation_001",
                                "session_id": "ses_child_001",
                                "child_session_id": "ses_grandchild_001",
                                "started_at": "2026-01-04T15:48:00.500000",
                                "ended_at": "2026-01-04T15:50:38.859000",
                                "prompt_input": "Analyze roadmap structure",
                                "children": [
                                    # Tool 1 inside delegation
                                    {
                                        "node_type": "tool",
                                        "tool_name": DELEG_TOOL1_NAME,
                                        "display_info": DELEG_TOOL1_DISPLAY,
                                        "arguments": f'{{"filePath": "{DELEG_TOOL1_DISPLAY}"}}',
                                        "duration_ms": DELEG_TOOL1_DURATION_MS,
                                        "tool_status": "completed",
                                        "status": "completed",
                                        "trace_id": "tool_deleg_001",
                                        "session_id": "ses_child_001",
                                        "started_at": "2026-01-04T15:48:01.000000",
                                        "children": [],
                                    },
                                    # Tool 2 inside delegation
                                    {
                                        "node_type": "tool",
                                        "tool_name": DELEG_TOOL2_NAME,
                                        "display_info": DELEG_TOOL2_DISPLAY,
                                        "arguments": f'{{"filePath": "{DELEG_TOOL2_DISPLAY}"}}',
                                        "duration_ms": DELEG_TOOL2_DURATION_MS,
                                        "tool_status": "completed",
                                        "status": "completed",
                                        "trace_id": "tool_deleg_002",
                                        "session_id": "ses_child_001",
                                        "started_at": "2026-01-04T15:48:01.500000",
                                        "children": [],
                                    },
                                ],
                            },
                        ],
                    },
                ],
            }
        ],
    }
