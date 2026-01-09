# Plan 46: UI Design Specification - Enriched Data Visualization

## Overview

This document defines visual specifications for displaying enriched data in the dashboard without changing the existing UI structure. All enhancements integrate seamlessly with the current design system.

## Design Principles

1. **Non-Intrusive**: Enrichments enhance, not replace existing elements
2. **Progressive Disclosure**: Show summary first, details on interaction
3. **Visual Hierarchy**: Important info prominent, secondary data subtle
4. **Consistency**: Use existing colors, fonts, and spacing system
5. **Accessibility**: Color-blind safe, keyboard navigable, screen reader friendly

---

## Color Palette (from existing `colors.py`)

### Agent Type Colors (NEW - to add)

```python
# Agent type colors for badges
"agent_main": "#3b82f6",       # Blue 500 - main/user agent
"agent_main_bg": "rgba(59, 130, 246, 0.15)",
"agent_executor": "#22c55e",  # Green 500 - executor agent
"agent_executor_bg": "rgba(34, 197, 94, 0.15)",
"agent_subagent": "#a855f7",  # Violet 500 - delegated agents
"agent_subagent_bg": "rgba(168, 85, 247, 0.15)",
"agent_tea": "#f59e0b",       # Amber 500 - TEA agent
"agent_tea_bg": "rgba(245, 158, 11, 0.15)",
"agent_default": "#6b7280",   # Gray 500 - unknown
"agent_default_bg": "rgba(107, 114, 128, 0.15)",
```

### Existing Colors Used

| Purpose | Color Key | Hex Value |
|---------|-----------|-----------|
| Error indicator | `error` | `#ef4444` |
| Success | `success` | `#22c55e` |
| Warning | `warning` | `#f59e0b` |
| Primary text | `text_primary` | `#f5f5f5` |
| Secondary text | `text_secondary` | `#b3b3b3` |
| Muted text | `text_muted` | `#737373` |

---

## 1. Session Card Subtitle (`summary_title`)

### Location
Session items in the tree view, below the main title.

### Visual Specification

```
+--------------------------------------------------+
| [icon] Session Title                    10:30:45 |
|        A meaningful summary of what happened...  |  <-- NEW subtitle
|                                                  |
+--------------------------------------------------+
```

| Property | Value | Notes |
|----------|-------|-------|
| Font size | `FONTS["size_xs"]` (11px) | Smaller than title |
| Font weight | `FONTS["weight_normal"]` (400) | Light weight |
| Color | `COLORS["text_muted"]` | Subdued, non-competing |
| Max characters | 80 | Truncate with `...` |
| Line count | 1 | Single line only |
| Top margin | `SPACING["xs"]` (4px) | Tight to title |
| Indentation | Same as title | Aligned with content |

### Fallback Behavior
When `summary_title` is not available:
- **Option A**: Show nothing (current behavior) - RECOMMENDED
- **Option B**: Show truncated first user prompt

### Implementation

```python
# In tree item creation
if summary_title := data.get("summary_title"):
    subtitle = summary_title[:80] + "..." if len(summary_title) > 80 else summary_title
    # Add as tooltip and/or second line
    item.setToolTip(0, summary_title)  # Full text on hover
```

### ASCII Mockup

```
Without subtitle (current):
┌────────────────────────────────────────────────────────────┐
│ 🌳 opencode-monitor                    01-08 14:32   2m 5s │
├────────────────────────────────────────────────────────────┤

With subtitle (enhanced):
┌────────────────────────────────────────────────────────────┐
│ 🌳 opencode-monitor                    01-08 14:32   2m 5s │
│    Fix authentication bug in login flow                    │ ← text_muted
├────────────────────────────────────────────────────────────┤
```

---

## 2. Tool Labels with Enriched Data

### Current State
Shows: `[icon] tool_name: display_info`

### Enhanced State
Shows: `[icon] title` (with `result_summary` in tooltip)

### Visual Specification

| Element | Current | Enhanced |
|---------|---------|----------|
| Primary label | `tool_name` | `title` (fallback: `tool_name`) |
| Info preview | `display_info` | `display_info` (unchanged) |
| Tooltip | None | `result_summary` |
| Cost/tokens | Not shown | Shown on hover or in detail |

### Label Display Logic

```python
def get_tool_label(part: dict) -> str:
    title = part.get("title")
    tool_name = part.get("tool_name", "")
    
    if title:
        return title  # Human-readable: "Read the main.py file"
    else:
        return format_tool_name(tool_name)  # "bash" → "Bash"
```

### Tooltip Content Format

```
┌─────────────────────────────────────────┐
│ Result: File read successfully (245 lines)     │
│ ─────────────────────────────────────── │
│ Cost: $0.0012  │  Tokens: 1.2K in / 0 out     │
└─────────────────────────────────────────┘
```

| Property | Value |
|----------|-------|
| Max width | 300px |
| Font | `FONTS["mono"]` for values |
| Background | `COLORS["bg_elevated"]` |
| Border | `COLORS["border_default"]` |
| Padding | `SPACING["sm"]` |

### Cost/Tokens Display

Only show in expanded detail view or tooltip - NOT in tree row (avoid clutter).

```
Cost Display Format:
- < $0.01:  "$0.001" (3 decimals)
- >= $0.01: "$0.01" (2 decimals)  
- >= $1.00: "$1.23" (2 decimals)

Tokens Display Format:
- Use existing format_tokens_short()
- Show as "1.2K in / 500 out"
```

### ASCII Mockup

```
Current:
  ⚙️ bash: git status --porcelain

Enhanced (with title):
  ⚙️ Check git repository status                  ← Uses title
     └─ Tooltip: "Status: clean, 3 files modified • $0.002 • 1.2K tokens"

Enhanced (fallback):
  ⚙️ Bash: git status --porcelain               ← Formatted tool_name
```

---

## 3. Agent Type Badges

### Design: Pill Badge

Compact pill/chip that appears next to the agent/role indicator.

### Visual Specification

```
┌──────────────────────────────────────────────┐
│ 💬 user → assistant [main]        10:30:45   │
│                      ^^^^^^                  │
│                      Agent badge             │
└──────────────────────────────────────────────┘
```

| Property | Value |
|----------|-------|
| Shape | Pill (border-radius: full) |
| Font size | `FONTS["size_xs"]` (11px) |
| Font weight | `FONTS["weight_medium"]` (500) |
| Padding | `2px 6px` |
| Text transform | lowercase |
| Min width | 32px |
| Height | 16px |

### Color Scheme by Agent Type

| Agent Type | Text Color | Background | Icon |
|------------|------------|------------|------|
| `main` | `agent_main` | `agent_main_bg` | None |
| `executor` | `agent_executor` | `agent_executor_bg` | None |
| `subagent` | `agent_subagent` | `agent_subagent_bg` | None |
| `tea` | `agent_tea` | `agent_tea_bg` | None |
| `(unknown)` | `agent_default` | `agent_default_bg` | None |

### Placement

- **In tree row**: After the agent name in column 0
- **In timeline**: In the event header, after the type label
- **In detail panel**: In the header next to role

### ASCII Mockup

```
Tree View:
┌─────────────────────────────────────────────────────────────┐
│ 💬 user → coder [executor]              01-08 14:32   1m 2s │
│           ^^^^^ ^^^^^^^^^^                                  │
│           agent   badge                                     │
└─────────────────────────────────────────────────────────────┘

Badge styling:
  [main]      → Blue pill:   ┌───────┐  bg: rgba(59,130,246,0.15)
                             │ main  │  text: #3b82f6
                             └───────┘

  [executor]  → Green pill:  ┌──────────┐  bg: rgba(34,197,94,0.15)  
                             │ executor │  text: #22c55e
                             └──────────┘

  [tea]       → Amber pill:  ┌─────┐  bg: rgba(245,158,11,0.15)
                             │ tea │  text: #f59e0b
                             └─────┘
```

---

## 4. Error Indicators

### Location
- Tree items (parts row)
- Timeline events
- Detail panel header

### Icon Specification

| Context | Icon | Size | Color |
|---------|------|------|-------|
| Tree row (column 5) | `✗` | Default | `COLORS["error"]` |
| Inline with text | `⚠` | 12px | `COLORS["error"]` |
| Detail header | Badge | Standard | Error style |

### Tooltip Content

```
┌─────────────────────────────────────────┐
│ ⚠ Error: FileNotFoundError             │
│ ───────────────────────────────────────│
│ The file '/path/to/file.py' was not    │
│ found in the filesystem.               │
│                                         │
│ Path: /path/to/file.py                 │
└─────────────────────────────────────────┘
```

| Property | Value |
|----------|-------|
| Error name | Bold, `COLORS["error"]` |
| Error data | Normal, `COLORS["text_secondary"]` |
| Max tooltip width | 350px |
| Word wrap | Yes |

### ASCII Mockup

```
Tree row with error:
┌──────────────────────────────────────────────────────────────┐
│   📖 read: /path/to/missing.py                          ✗   │
│                                                         ↑   │
│                                         error indicator     │
└──────────────────────────────────────────────────────────────┘
     └─ Tooltip: "Error: FileNotFoundError - File not found"

Timeline event with error:
┌──────────────────────────────────────────────────────────────┐
│ ⚠ Tool Call                                        10:32:15 │
│   read: /path/to/missing.py                                 │
│   └─ FileNotFoundError: File not found                      │ ← error_muted bg
└──────────────────────────────────────────────────────────────┘
```

---

## 5. Image Thumbnails

### Context
File parts with `file_url` containing base64 image data.

### Size Options

| Context | Size | Notes |
|---------|------|-------|
| Tree view | Not shown | Too cluttered |
| Timeline | 48x48 px | Small preview |
| Detail panel | 128x128 px | Larger preview |
| Expanded view | 400px max-width | Full size (click to expand) |

### Visual Specification

```
┌────────────────────────────────────────────────────────────┐
│ 📎 screenshot.png                                          │
│ ┌────────┐                                                 │
│ │        │  File: screenshot.png                           │
│ │  IMG   │  Size: 1920x1080                                │
│ │        │  Type: image/png                                │
│ │ 48x48  │                                                 │
│ └────────┘  [Click to expand]                              │
└────────────────────────────────────────────────────────────┘
```

| Property | Value |
|----------|-------|
| Border radius | `RADIUS["sm"]` (4px) |
| Border | `1px solid COLORS["border_default"]` |
| Background | `COLORS["bg_hover"]` (placeholder) |
| Object fit | `cover` (maintain aspect ratio) |
| Cursor | `pointer` (indicates clickable) |

### Supported Formats
- PNG (`image/png`)
- JPEG (`image/jpeg`, `image/jpg`)
- GIF (`image/gif`)
- WebP (`image/webp`)

### Click-to-Expand Behavior

1. Click thumbnail → Open modal/overlay
2. Modal shows full-size image (max 90% viewport)
3. ESC or click outside → Close modal
4. Keyboard accessible: Enter to open, ESC to close

### ASCII Mockup

```
Timeline with image:
┌────────────────────────────────────────────────────────────┐
│ 📎 File Attachment                               10:35:22  │
│   ┌──────┐                                                 │
│   │ ▓▓▓▓ │  screenshot.png                                │
│   │ ▓▓▓▓ │  1920 x 1080 • 245 KB                          │
│   └──────┘                                                 │
└────────────────────────────────────────────────────────────┘
       ↑
   48x48 thumbnail

Detail panel expanded:
┌────────────────────────────────────────────────────────────┐
│ 📎 File: screenshot.png                                    │
│ ────────────────────────────────────────────────────────── │
│ ┌────────────────────────────────────────────────────────┐ │
│ │                                                        │ │
│ │                   [Image Preview]                      │ │
│ │                      128x128                           │ │
│ │                                                        │ │
│ └────────────────────────────────────────────────────────┘ │
│                                                            │
│ Filename: screenshot.png                                   │
│ Dimensions: 1920 x 1080                                    │
│ Size: 245 KB                                               │
│ Format: PNG                                                │
└────────────────────────────────────────────────────────────┘
```

---

## 6. Typography Summary

| Element | Font Size | Weight | Color |
|---------|-----------|--------|-------|
| Session title | `size_md` (14px) | `semibold` (600) | `text_primary` |
| Session subtitle | `size_xs` (11px) | `normal` (400) | `text_muted` |
| Tool title | `size_sm` (12px) | `medium` (500) | `text_secondary` |
| Tool info | `size_sm` (12px) | `normal` (400) | `text_muted` |
| Agent badge | `size_xs` (11px) | `medium` (500) | (varies by type) |
| Error text | `size_sm` (12px) | `medium` (500) | `error` |
| Tooltip text | `size_sm` (12px) | `normal` (400) | `text_primary` |
| Token/cost | `size_xs` (11px) | `normal` (400) | `text_muted` |

---

## 7. Spacing Summary

| Element | Spacing | Value |
|---------|---------|-------|
| Subtitle margin-top | `SPACING["xs"]` | 4px |
| Badge padding | `2px 6px` | Custom |
| Badge margin-left | `SPACING["xs"]` | 4px |
| Tooltip padding | `SPACING["sm"]` | 8px |
| Thumbnail margin | `SPACING["sm"]` | 8px |
| Error icon margin | `SPACING["xs"]` | 4px |

---

## 8. Accessibility Considerations

### Color Contrast
- All text meets WCAG AA contrast (4.5:1 for normal, 3:1 for large)
- Error indicators use icon + color (not color alone)
- Agent badges use text labels (not just color)

### Keyboard Navigation
- All interactive elements focusable with Tab
- Enter/Space to activate
- ESC to close modals/tooltips
- Arrow keys for tree navigation (existing)

### Screen Reader Support
- Tooltips read on focus
- Images have alt text: "Screenshot: {filename}"
- Error states announced: "Error: {error_name}"
- Agent badges: "Agent type: {type}"

### Reduced Motion
- Respect `prefers-reduced-motion` for animations
- Instant expand/collapse option

---

## 9. Implementation Priority

### Phase 1 (MVP)
1. Tool labels with `title` field
2. Agent badges (basic color only)
3. Error indicators in tree

### Phase 2 (Enhanced)
4. Session subtitle (`summary_title`)
5. Tooltips with `result_summary`
6. Cost/tokens in detail view

### Phase 3 (Complete)
7. Image thumbnails
8. Click-to-expand images
9. Full accessibility audit

---

## 10. Files to Modify

| File | Changes |
|------|---------|
| `styles/colors.py` | Add agent type colors |
| `tracing/tree_items.py` | Tool labels, agent badges, error icons |
| `tracing/tree_builder.py` | Session subtitles |
| `tracing/views/timeline.py` | Agent badges, image thumbnails |
| `tracing/detail_panel/panel.py` | Cost/tokens display, images |
| `tracing/widgets.py` | New AgentBadge widget |
| `tracing/helpers.py` | New formatting functions |

---

## Appendix A: Complete ASCII Mockup

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Traces                                                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│ Type / Name                              Time      Duration  In    Out      │
├─────────────────────────────────────────────────────────────────────────────┤
│ 🌳 opencode-monitor                      01-08     2m 5s     45K   12K      │
│    Implement dashboard data enrichment                                 ← subtitle
│ ├─ 💬 user → coder [main]                14:32     1m 2s     5K    2K       │
│ │  ├─ 📖 Read the project structure      14:32:05  250ms     1K    -    ✓   │
│ │  ├─ 🔧 Check git status                14:32:10  180ms     500   -    ✓   │
│ │  │     └─ Tooltip: "3 files modified, working tree clean"                 │
│ │  ├─ ✏️ Update the colors.py file       14:32:15  120ms     800   -    ✓   │
│ │  └─ 📖 read: missing.py                14:32:20  50ms      200   -    ✗   │
│ │        └─ Error: FileNotFoundError                                        │
│ │                                                                           │
│ └─ 💬 user → analyst [executor]          14:33     45s       8K    3K       │
│    ├─ 📖 Analyze codebase structure      14:33:05  1.2s      2K    -    ✓   │
│    └─ 📎 screenshot.png                  14:33:10  -         -     -        │
│          ┌──────┐                                                           │
│          │ img  │ 1920x1080 • 245KB                                         │
│          └──────┘                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Appendix B: Agent Badge Widget Code

```python
class AgentBadge(QLabel):
    """Pill badge showing agent type with color coding."""
    
    AGENT_STYLES = {
        "main": ("main", "agent_main", "agent_main_bg"),
        "executor": ("exec", "agent_executor", "agent_executor_bg"),
        "subagent": ("sub", "agent_subagent", "agent_subagent_bg"),
        "tea": ("tea", "agent_tea", "agent_tea_bg"),
    }
    
    def __init__(self, agent_type: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.set_agent(agent_type)
    
    def set_agent(self, agent_type: str) -> None:
        if not agent_type:
            self.hide()
            return
            
        agent_lower = agent_type.lower()
        text, text_color, bg_color = self.AGENT_STYLES.get(
            agent_lower, 
            (agent_lower[:4], "agent_default", "agent_default_bg")
        )
        
        self.setText(text)
        self.setStyleSheet(f"""
            font-size: {FONTS["size_xs"]}px;
            font-weight: {FONTS["weight_medium"]};
            padding: 2px 6px;
            border-radius: {RADIUS["full"]}px;
            background-color: {COLORS[bg_color]};
            color: {COLORS[text_color]};
        """)
        self.show()
```

---

*Document created: 2026-01-09*
*Author: @ux-designer (Sally)*
*Status: Ready for Architecture Review*
