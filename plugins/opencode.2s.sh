#!/bin/bash
#
# SwiftBar Plugin: OpenCode Status + Usage
# Displays OpenCode instances and Claude usage
#

STATE_FILE="/tmp/opencode-state.json"
USAGE_FILE="/tmp/opencode-usage.json"

# === Helper Functions ===

format_time_remaining() {
    local reset_time="$1"
    
    if [[ -z "$reset_time" ]] || [[ "$reset_time" == "null" ]]; then
        echo "N/A"
        return
    fi
    
    local clean_time="${reset_time%%.*}"
    clean_time="${clean_time//+00:00/}"
    clean_time="${clean_time//Z/}"
    
    local reset=$(TZ=UTC date -j -f "%Y-%m-%dT%H:%M:%S" "$clean_time" +%s 2>/dev/null || echo 0)
    local now=$(date +%s)
    
    if [[ $reset -eq 0 ]]; then
        echo "N/A"
        return
    fi
    
    local diff=$((reset - now))
    
    if [[ $diff -lt 60 ]]; then
        echo "<1min"
        return
    fi
    
    local hours=$((diff / 3600))
    local minutes=$(((diff % 3600) / 60))
    
    if [[ $hours -gt 0 ]]; then
        echo "${hours}h${minutes}m"
    else
        echo "${minutes}min"
    fi
}

format_weekly_reset() {
    local reset_time="$1"
    
    if [[ -z "$reset_time" ]] || [[ "$reset_time" == "null" ]]; then
        echo "N/A"
        return
    fi
    
    local clean_time="${reset_time%%.*}"
    clean_time="${clean_time//+00:00/}"
    clean_time="${clean_time//Z/}"
    
    local reset=$(TZ=UTC date -j -f "%Y-%m-%dT%H:%M:%S" "$clean_time" +%s 2>/dev/null || echo 0)
    
    if [[ $reset -eq 0 ]]; then
        echo "N/A"
        return
    fi
    
    local day_names=("Sun" "Mon" "Tue" "Wed" "Thu" "Fri" "Sat")
    local day_num=$(date -r $reset +%w)
    local hour=$(date -r $reset +%H)
    local day_name="${day_names[$day_num]}"
    
    echo "${day_name} ${hour}h"
}

# === Read OpenCode State ===

if [[ ! -f "$STATE_FILE" ]]; then
    CONNECTED="false"
else
    CONNECTED=$(jq -r '.connected // false' "$STATE_FILE" 2>/dev/null)
fi

INSTANCE_COUNT=$(jq -r '.instance_count // 0' "$STATE_FILE" 2>/dev/null)
BUSY_COUNT=$(jq -r '.busy_count // 0' "$STATE_FILE" 2>/dev/null)
PERM_COUNT=$(jq -r '.permissions_pending // 0' "$STATE_FILE" 2>/dev/null)
TODO_PENDING=$(jq -r '.todos.pending // 0' "$STATE_FILE" 2>/dev/null)
TODO_IN_PROGRESS=$(jq -r '.todos.in_progress // 0' "$STATE_FILE" 2>/dev/null)
TODO_ACTIVE=$((TODO_PENDING + TODO_IN_PROGRESS))
TOOLS_RUNNING=$(jq -r '.tools_running // []' "$STATE_FILE" 2>/dev/null)
TOOLS_COUNT=$(echo "$TOOLS_RUNNING" | jq 'length' 2>/dev/null || echo 0)

# === Read Usage State ===

USAGE_ERROR=""
FIVE_HOUR_UTIL=0
SEVEN_DAY_UTIL=0

if [[ -f "$USAGE_FILE" ]]; then
    USAGE_ERROR=$(jq -r '.error // empty' "$USAGE_FILE" 2>/dev/null)
    if [[ -z "$USAGE_ERROR" || "$USAGE_ERROR" == "null" ]]; then
        FIVE_HOUR_UTIL=$(jq -r '.five_hour.utilization // 0' "$USAGE_FILE" 2>/dev/null)
        FIVE_HOUR_RESET=$(jq -r '.five_hour.resets_at // null' "$USAGE_FILE" 2>/dev/null)
        SEVEN_DAY_UTIL=$(jq -r '.seven_day.utilization // 0' "$USAGE_FILE" 2>/dev/null)
        SEVEN_DAY_RESET=$(jq -r '.seven_day.resets_at // null' "$USAGE_FILE" 2>/dev/null)
    fi
fi

# === Determine Usage Color ===

if [[ $FIVE_HOUR_UTIL -ge 90 ]]; then
    USAGE_COLOR="red"
    USAGE_ICON="🔴"
elif [[ $FIVE_HOUR_UTIL -ge 70 ]]; then
    USAGE_COLOR="orange"
    USAGE_ICON="🟠"
elif [[ $FIVE_HOUR_UTIL -ge 50 ]]; then
    USAGE_COLOR="yellow"
    USAGE_ICON="🟡"
else
    USAGE_COLOR="green"
    USAGE_ICON="🟢"
fi

# === Menu Bar Display ===

MENU=""
MENU_COLOR=""

# Sessions busy
if [[ $BUSY_COUNT -gt 0 ]]; then
    MENU="${BUSY_COUNT}"
fi

# Todos active
if [[ $TODO_ACTIVE -gt 0 ]]; then
    [[ -n "$MENU" ]] && MENU="${MENU} "
    MENU="${MENU}⏳${TODO_ACTIVE}"
fi

# Tools running
if [[ $TOOLS_COUNT -gt 0 ]]; then
    [[ -n "$MENU" ]] && MENU="${MENU} "
    MENU="${MENU}⚙️${TOOLS_COUNT}"
fi

# Permissions pending
if [[ $PERM_COUNT -gt 0 ]]; then
    [[ -n "$MENU" ]] && MENU="${MENU} "
    MENU="${MENU}🔐${PERM_COUNT}"
    MENU_COLOR="orange"
fi

# Usage
if [[ -z "$USAGE_ERROR" ]] && [[ -f "$USAGE_FILE" ]]; then
    [[ -n "$MENU" ]] && MENU="${MENU} "
    MENU="${MENU}${USAGE_ICON} ${FIVE_HOUR_UTIL}%"
    # Set color based on usage level (if not already set by permission)
    if [[ -z "$MENU_COLOR" ]]; then
        MENU_COLOR="$USAGE_COLOR"
    elif [[ $FIVE_HOUR_UTIL -ge 90 ]]; then
        MENU_COLOR="red"
    fi
fi

# Final output
if [[ "$CONNECTED" != "true" ]]; then
    # No OpenCode running - only show usage if available
    if [[ -f "$USAGE_FILE" ]] && [[ -z "$USAGE_ERROR" || "$USAGE_ERROR" == "null" ]]; then
        echo "${USAGE_ICON} ${FIVE_HOUR_UTIL}% | color=$USAGE_COLOR"
    fi
elif [[ -n "$MENU_COLOR" ]]; then
    echo "🤖 $MENU | color=$MENU_COLOR"
elif [[ -n "$MENU" ]]; then
    echo "🤖 $MENU"
else
    echo "🤖"
fi

# === Dropdown Menu ===

echo "---"

# Connection status
if [[ "$CONNECTED" != "true" ]]; then
    echo "OpenCode not connected | color=gray"
    echo "---"
else
    # Instances section
    echo "Instances ($INSTANCE_COUNT) | size=12 color=gray"
    
    jq -c '.instances[]' "$STATE_FILE" 2>/dev/null | while read -r instance; do
        port=$(echo "$instance" | jq -r '.port')
        inst_agent_count=$(echo "$instance" | jq -r '.agent_count')
        inst_busy_count=$(echo "$instance" | jq -r '.busy_count')
        inst_tty=$(echo "$instance" | jq -r '.tty // ""')
        
        if [[ $inst_busy_count -gt 0 ]]; then
            echo "  ● Port $port ($inst_busy_count busy / $inst_agent_count) | color=#4CAF50 size=12"
        else
            echo "  ○ Port $port ($inst_agent_count idle) | color=gray size=12"
        fi
        
        # Show agents for this instance
        echo "$instance" | jq -c '.agents[]' 2>/dev/null | while read -r agent; do
            title=$(echo "$agent" | jq -r '.title')
            status=$(echo "$agent" | jq -r '.status')
            perm_pending=$(echo "$agent" | jq -r '.permission_pending // false')
            
            # Truncate if too long
            if [[ ${#title} -gt 40 ]]; then
                display_title="${title:0:37}..."
            else
                display_title="$title"
            fi
            
            # Add permission indicator
            if [[ "$perm_pending" == "true" ]]; then
                display_title="🔐 $display_title"
            fi
            
            # Build click action: focus iTerm2 tab by TTY
            click_action=""
            if [[ -n "$inst_tty" ]]; then
                click_action="bash=$HOME/.local/bin/focus-iterm-tab param1=\"/dev/$inst_tty\" terminal=false"
            fi
            
            if [[ "$perm_pending" == "true" ]]; then
                echo "      ▸ $display_title | color=orange size=11 $click_action"
            elif [[ "$status" == "busy" ]]; then
                echo "      ▸ $display_title | color=#2196F3 size=11 $click_action"
            else
                echo "      ▹ $display_title | color=gray size=11 $click_action"
            fi
        done
    done
    
    echo "---"
    
    # Tools section
    if [[ $TOOLS_COUNT -gt 0 ]]; then
        echo "Tools ($TOOLS_COUNT) | size=12 color=gray"
        echo "$TOOLS_RUNNING" | jq -r '.[]' 2>/dev/null | while read -r tool; do
            echo "  ⚙️ $tool | color=#2196F3 size=12"
        done
        echo "---"
    fi

    # Todos section
    if [[ $TODO_ACTIVE -gt 0 ]]; then
        echo "Todos ($TODO_ACTIVE) | size=12 color=gray"
        if [[ $TODO_IN_PROGRESS -gt 0 ]]; then
            echo "  🔄 $TODO_IN_PROGRESS in progress | color=#2196F3 size=12"
        fi
        if [[ $TODO_PENDING -gt 0 ]]; then
            echo "  ⏳ $TODO_PENDING pending | color=#FF9800 size=12"
        fi
        echo "---"
    fi
fi

# Usage section
if [[ -f "$USAGE_FILE" ]]; then
    if [[ -n "$USAGE_ERROR" && "$USAGE_ERROR" != "null" ]]; then
        echo "Usage: error ($USAGE_ERROR) | color=red size=12"
    else
        FIVE_HOUR_TIME=$(format_time_remaining "$FIVE_HOUR_RESET")
        SEVEN_DAY_TIME=$(format_weekly_reset "$SEVEN_DAY_RESET")
        
        echo "Session | size=12 color=gray"
        echo "  ${USAGE_ICON} ${FIVE_HOUR_UTIL}% used | color=$USAGE_COLOR size=12"
        echo "  Reset in ${FIVE_HOUR_TIME} | size=11"
        echo "---"
        echo "Weekly | size=12 color=gray"
        echo "  ${SEVEN_DAY_UTIL}% used | size=12"
        echo "  Reset ${SEVEN_DAY_TIME} | size=11"
    fi
    echo "---"
fi

echo "Open Claude Usage | href=https://claude.ai/settings/usage"
echo "Refresh | refresh=true"
