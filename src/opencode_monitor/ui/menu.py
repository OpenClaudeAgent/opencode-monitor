"""
Menu Builder - Constructs rumps menu items for OpenCode Monitor
"""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Callable, Any, List

import rumps

from ..core.models import State, SessionStatus, Usage, Agent
from ..security.analyzer import analyze_command, RiskLevel, get_level_emoji


@dataclass
class CategoryConfig:
    """Configuration for a security category in critical items menu."""

    emoji: str
    title: str
    getter: Callable
    path_attr: str  # "command", "file_path", "url"
    truncate_start: bool = True  # True: "text..." / False: "...text"
    show_operation: bool = False  # For file writes


# Truncation limits for menu items
TITLE_MAX_LENGTH = 40
TOOL_ARG_MAX_LENGTH = 30
TODO_CURRENT_MAX_LENGTH = 35
TODO_PENDING_MAX_LENGTH = 30


def truncate_with_tooltip(
    text: str, max_length: int, prefix: str = "", callback: Optional[Callable] = None
) -> rumps.MenuItem:
    """Create a menu item, adding a tooltip if text exceeds max_length.

    Args:
        text: The full text to display
        max_length: Maximum length before truncation
        prefix: Prefix to prepend (icons, indentation)
        callback: Optional click callback

    Returns:
        A rumps.MenuItem with tooltip set if text was truncated
    """
    is_truncated = len(text) > max_length

    if is_truncated:
        display_text = text[: max_length - 3] + "..."
    else:
        display_text = text

    item = rumps.MenuItem(f"{prefix}{display_text}", callback=callback)

    # Set native macOS tooltip only if truncated
    if is_truncated:
        item._menuitem.setToolTip_(text)

    return item


class MenuBuilder:
    """Builds menu items for the OpenCode Monitor app"""

    def __init__(self, port_names_cache: dict, port_names_limit: int = 50):
        """Initialize with a cache for port names.

        Args:
            port_names_cache: Dict mapping port -> last known agent name
            port_names_limit: Max cached names before cleanup
        """
        self._port_names = port_names_cache
        self._port_names_limit = port_names_limit

    def build_dynamic_items(
        self,
        state: Optional[State],
        usage: Optional[Usage],
        focus_callback: Callable[[str], None],
        alert_callback: Callable[[Any], None],
    ) -> list:
        """Build dynamic menu items for instances and usage.

        Args:
            state: Current application state
            usage: Current usage data
            focus_callback: Callback to focus terminal (takes tty string)
            alert_callback: Callback to track security alerts

        Returns:
            List of rumps.MenuItem objects
        """
        items = []

        if state is None or not state.connected:
            items.append(rumps.MenuItem("No OpenCode instances"))
            return items

        # Clean up port name cache (keep only active ports)
        active_ports = {inst.port for inst in state.instances}
        self._port_names = {
            p: n for p, n in self._port_names.items() if p in active_ports
        }

        # Build items for each instance
        for instance in state.instances:
            tty = instance.tty

            # Separate main agents from sub-agents
            main_agents = [a for a in instance.agents if not a.is_subagent]
            sub_agents_map: dict[str, list[Agent]] = {}
            for a in instance.agents:
                if a.is_subagent and a.parent_id is not None:
                    if a.parent_id not in sub_agents_map:
                        sub_agents_map[a.parent_id] = []
                    sub_agents_map[a.parent_id].append(a)

            if main_agents:
                # Cache the name
                self._port_names[instance.port] = main_agents[0].title

                # Rotate cache if too large
                if len(self._port_names) > self._port_names_limit:
                    keys = list(self._port_names.keys())
                    for k in keys[: len(keys) // 2]:
                        del self._port_names[k]

                # Build agent items
                for agent in main_agents:
                    items.extend(
                        self.build_agent_items(
                            agent, tty, 0, focus_callback, alert_callback
                        )
                    )
                    for sub_agent in sub_agents_map.get(agent.id, []):
                        items.extend(
                            self.build_agent_items(
                                sub_agent, tty, 1, focus_callback, alert_callback
                            )
                        )
            else:
                # Instance idle
                display_name = self._port_names.get(
                    instance.port, f"Port {instance.port}"
                )

                def make_focus_cb(t):
                    def cb(_):
                        if t:
                            focus_callback(t)

                    return cb

                items.append(
                    rumps.MenuItem(
                        f"💤 {display_name} (idle)", callback=make_focus_cb(tty)
                    )
                )

        # Add usage items
        if usage:
            items.append(None)  # separator
            items.extend(self.build_usage_items(usage))

        return items

    def build_agent_items(
        self,
        agent: Agent,
        tty: str,
        indent: int,
        focus_callback: Callable[[str], None],
        alert_callback: Callable[[Any], None],
    ) -> list:
        """Build menu items for an agent.

        Args:
            agent: The agent to build items for
            tty: TTY string for terminal focus
            indent: Indentation level (0 for main, 1 for sub-agent)
            focus_callback: Callback to focus terminal
            alert_callback: Callback to track security alerts

        Returns:
            List of rumps.MenuItem objects
        """
        items = []
        prefix = "    " * indent
        sub_prefix = "    " * (indent + 1)

        # Agent icon and callback
        if indent > 0:
            # Sub-agent icons (never have ask_user)
            status_icon = "└ ●" if agent.status == SessionStatus.BUSY else "└ ○"
            callback = None
        else:
            # Main agent icons
            if agent.has_pending_ask_user:
                status_icon = "🔔"  # Awaiting user response (MCP Notify)
            else:
                status_icon = "🤖"

            def make_focus_cb(t):
                def cb(_):
                    if t:
                        focus_callback(t)

                return cb

            callback = make_focus_cb(tty)

        # Clean title
        title = agent.title
        if "(@" in title:
            title = title.split("(@")[0].strip()

        # Create agent item
        items.append(
            truncate_with_tooltip(
                title,
                TITLE_MAX_LENGTH,
                prefix=f"{prefix}{status_icon} ",
                callback=callback,
            )
        )

        # Tools with security analysis and permission detection
        if agent.tools:
            for tool in agent.tools:
                alert = None
                if tool.name.lower() in ("bash", "shell", "execute"):
                    alert = analyze_command(tool.arg, tool.name)
                    alert.agent_id = agent.id
                    alert.agent_title = agent.title

                    if alert.level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                        alert_callback(alert)

                # Determine tool icon: permission > security > default
                if tool.may_need_permission:
                    tool_icon = "🔒"  # May be waiting for permission
                elif alert:
                    risk_emoji = get_level_emoji(alert.level)
                    tool_icon = risk_emoji if risk_emoji else "🔧"
                else:
                    tool_icon = "🔧"

                full_tool_text = f"{tool.name}: {tool.arg}"

                item = truncate_with_tooltip(
                    full_tool_text,
                    TOOL_ARG_MAX_LENGTH,
                    prefix=f"{sub_prefix}{tool_icon} ",
                )

                # Set tooltip based on state
                if tool.may_need_permission:
                    elapsed_sec = tool.elapsed_ms // 1000
                    if elapsed_sec >= 60:
                        mins, secs = divmod(elapsed_sec, 60)
                        duration = f"{mins}m {secs}s"
                    else:
                        duration = f"{elapsed_sec}s"
                    tooltip = f"🔒 May be waiting for permission (running {duration})\n\n{tool.arg}"
                    item._menuitem.setToolTip_(tooltip)
                elif alert and alert.level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                    tooltip = (
                        f"⚠️ {alert.reason}\nScore: {alert.score}/100\n\n{tool.arg}"
                    )
                    item._menuitem.setToolTip_(tooltip)

                items.append(item)

        # Pending ask_user (MCP Notify awaiting response)
        if agent.has_pending_ask_user and agent.ask_user_title:
            item = truncate_with_tooltip(
                agent.ask_user_title,
                TITLE_MAX_LENGTH,
                prefix=f"{sub_prefix}❓ ",
            )
            item._menuitem.setToolTip_(
                f"🔔 Awaiting user response\n\n{agent.ask_user_title}"
            )
            items.append(item)

        # Todos
        if agent.todos:
            if agent.todos.in_progress > 0 and agent.todos.current_label:
                items.append(
                    truncate_with_tooltip(
                        agent.todos.current_label,
                        TODO_CURRENT_MAX_LENGTH,
                        prefix=f"{sub_prefix}🔄 ",
                    )
                )

            if agent.todos.pending > 0 and agent.todos.next_label:
                suffix = (
                    f" (+{agent.todos.pending - 1})" if agent.todos.pending > 1 else ""
                )
                full_label = agent.todos.next_label + suffix
                items.append(
                    truncate_with_tooltip(
                        full_label,
                        TODO_PENDING_MAX_LENGTH,
                        prefix=f"{sub_prefix}⏳ ",
                    )
                )

        return items

    def build_usage_items(self, usage: Usage) -> list:
        """Build usage display items.

        Args:
            usage: Usage data

        Returns:
            List of rumps.MenuItem objects
        """
        items = []

        if usage.error:
            items.append(rumps.MenuItem(f"⚠️ Usage: {usage.error}"))
            return items

        five_h = usage.five_hour.utilization
        seven_d = usage.seven_day.utilization

        # Color icon based on usage
        if five_h >= 90:
            icon = "🔴"
        elif five_h >= 70:
            icon = "🟠"
        elif five_h >= 50:
            icon = "🟡"
        else:
            icon = "🟢"

        # Session reset time
        session_reset = ""
        if usage.five_hour.resets_at:
            try:
                reset_time = datetime.fromisoformat(
                    usage.five_hour.resets_at.replace("Z", "+00:00")
                )
                now = datetime.now(reset_time.tzinfo)
                diff = reset_time - now
                minutes = int(diff.total_seconds() / 60)
                if minutes > 60:
                    session_reset = f" (reset {minutes // 60}h{minutes % 60:02d}m)"
                elif minutes > 0:
                    session_reset = f" (reset {minutes}m)"
            except Exception:
                pass  # nosec B110 - invalid date format is ignored

        # Weekly reset time
        weekly_reset = ""
        if usage.seven_day.resets_at:
            try:
                reset_time = datetime.fromisoformat(
                    usage.seven_day.resets_at.replace("Z", "+00:00")
                )
                days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                day_name = days[reset_time.weekday()]
                weekly_reset = f" (reset {day_name} {reset_time.hour}h)"
            except Exception:
                pass  # nosec B110 - invalid date format is ignored

        items.append(rumps.MenuItem(f"{icon} Session: {five_h}%{session_reset}"))
        items.append(rumps.MenuItem(f"📅 Weekly: {seven_d}%{weekly_reset}"))
        items.append(
            rumps.MenuItem(
                "🌐 Open Claude Usage",
                callback=lambda _: __import__("subprocess").run(  # nosec B404 B603 B607
                    ["open", "https://console.anthropic.com/settings/usage"]
                ),
            )
        )

        return items

    def build_security_menu(
        self,
        auditor,
    ) -> rumps.MenuItem:
        """Build the security audit submenu.

        Args:
            auditor: SecurityAuditor instance

        Returns:
            rumps.MenuItem with security submenu
        """
        stats = auditor.get_stats()
        critical_count = stats.get("critical", 0) + stats.get("high", 0)

        # Menu title with alert indicator
        if critical_count > 0:
            security_title = f"🛡️ Security Audit ({critical_count} alerts)"
        else:
            security_title = "🛡️ Security Audit"

        menu = rumps.MenuItem(security_title)

        # Stats summary
        total_cmds = stats.get("total_commands", 0)
        total_reads = stats.get("total_reads", 0)
        total_writes = stats.get("total_writes", 0)
        total_fetches = stats.get("total_webfetches", 0)

        menu.add(
            rumps.MenuItem(
                f"🔢 {total_cmds} cmds, {total_reads} reads, {total_writes} writes, {total_fetches} fetches"
            )
        )
        menu.add(
            rumps.MenuItem(
                f"💻 Commands: 🔴{stats.get('critical', 0)} 🟠{stats.get('high', 0)} 🟡{stats.get('medium', 0)}"
            )
        )
        menu.add(
            rumps.MenuItem(
                f"📖 Reads: 🔴{stats.get('reads_critical', 0)} 🟠{stats.get('reads_high', 0)} 🟡{stats.get('reads_medium', 0)}"
            )
        )
        menu.add(
            rumps.MenuItem(
                f"✏️ Writes: 🔴{stats.get('writes_critical', 0)} 🟠{stats.get('writes_high', 0)} 🟡{stats.get('writes_medium', 0)}"
            )
        )
        menu.add(
            rumps.MenuItem(
                f"🌐 Fetches: 🔴{stats.get('webfetches_critical', 0)} 🟠{stats.get('webfetches_high', 0)} 🟡{stats.get('webfetches_medium', 0)}"
            )
        )

        # EDR/MITRE stats (from DB)
        edr_sequences = stats.get("edr_sequences", 0)
        edr_correlations = stats.get("edr_correlations", 0)
        mitre_tagged = stats.get("mitre_tagged", 0)

        if edr_sequences > 0 or edr_correlations > 0 or mitre_tagged > 0:
            menu.add(None)  # separator
            menu.add(rumps.MenuItem("🔍 ── EDR Heuristics ──"))
            if edr_sequences > 0:
                menu.add(rumps.MenuItem(f"⛓️ Kill chains detected: {edr_sequences}"))
            if edr_correlations > 0:
                menu.add(
                    rumps.MenuItem(f"🔗 Correlations detected: {edr_correlations}")
                )
            if mitre_tagged > 0:
                menu.add(rumps.MenuItem(f"🎯 MITRE tagged events: {mitre_tagged}"))

        menu.add(None)

        # Top critical/high items
        self._add_critical_items(menu, auditor)

        return menu

    def _format_mitre_techniques(self, mitre_json: str) -> str:
        """Format MITRE techniques for display"""
        try:
            techniques = json.loads(mitre_json) if mitre_json else []
            if techniques:
                return f"MITRE: {', '.join(techniques)}"
        except (json.JSONDecodeError, TypeError):
            pass
        return ""

    def _truncate_display_text(self, text: str, truncate_start: bool = True) -> str:
        """Truncate text for menu display (max 40 chars).

        Args:
            text: The text to truncate
            truncate_start: If True, keep start ("text..."). If False, keep end ("...text")

        Returns:
            Truncated text with ellipsis if needed
        """
        if len(text) <= 40:
            return text
        if truncate_start:
            return text[:40] + "..."
        return "..." + text[-40:]

    def _build_edr_info(self, item: Any) -> str:
        """Build EDR sequence/correlation info for commands.

        Args:
            item: The security item (command) with potential EDR attributes

        Returns:
            Formatted EDR info string or empty string
        """
        try:
            edr_seq = int(getattr(item, "edr_sequence_bonus", 0) or 0)
            edr_corr = int(getattr(item, "edr_correlation_bonus", 0) or 0)
            if edr_seq > 0 or edr_corr > 0:
                return f"\n⛓️ Sequence: +{edr_seq} | 🔗 Correlation: +{edr_corr}"
        except (TypeError, ValueError):
            pass
        return ""

    def _build_item_tooltip(self, item: Any, config: CategoryConfig) -> str:
        """Build tooltip for a security item.

        Args:
            item: The security item with risk_reason, risk_score, etc.
            config: Category configuration

        Returns:
            Formatted tooltip string
        """
        full_path = getattr(item, config.path_attr, "")
        tooltip = f"⚠️ {item.risk_reason}\nScore: {item.risk_score}/100"

        # Add operation for file writes
        if config.show_operation:
            tooltip += f"\nOperation: {item.operation}"

        # Add MITRE info if present
        mitre_techniques = getattr(item, "mitre_techniques", "") or ""
        mitre_info = self._format_mitre_techniques(mitre_techniques)
        if mitre_info:
            tooltip += f"\n🎯 {mitre_info}"

        # Add EDR info for commands
        if config.path_attr == "command":
            tooltip += self._build_edr_info(item)

        tooltip += f"\n\n{full_path}"
        return tooltip

    def _add_category_items(
        self, menu: rumps.MenuItem, config: CategoryConfig, items: List[Any]
    ) -> None:
        """Add items for a single security category.

        Args:
            menu: The parent menu to add items to
            config: Category configuration (emoji, title, path_attr, etc.)
            items: List of security items to add
        """
        if not items:
            return

        menu.add(rumps.MenuItem(f"{config.emoji} ── {config.title} ──"))
        for item in items:
            emoji = "🔴" if item.risk_level == "critical" else "🟠"
            full_path = getattr(item, config.path_attr, "")
            display_text = self._truncate_display_text(full_path, config.truncate_start)

            menu_item = rumps.MenuItem(f"{emoji} {display_text}")
            menu_item._menuitem.setToolTip_(self._build_item_tooltip(item, config))
            menu.add(menu_item)

    def _add_critical_items(self, menu: rumps.MenuItem, auditor) -> None:
        """Add critical/high risk items to security menu.

        Uses CategoryConfig to avoid code duplication across 4 categories.
        """
        categories = [
            CategoryConfig("💻", "Commands", auditor.get_critical_commands, "command"),
            CategoryConfig(
                "📖", "File Reads", auditor.get_sensitive_reads, "file_path", False
            ),
            CategoryConfig(
                "✏️",
                "File Writes",
                auditor.get_sensitive_writes,
                "file_path",
                False,
                True,
            ),
            CategoryConfig("🌐", "Web Fetches", auditor.get_risky_webfetches, "url"),
        ]

        has_items = False
        for config in categories:
            items = config.getter(5)
            if items:
                has_items = True
            self._add_category_items(menu, config, items)

        if not has_items:
            menu.add(rumps.MenuItem("✅ No critical items"))
