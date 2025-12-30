"""
Menu Builder - Constructs rumps menu items for OpenCode Monitor
"""

from datetime import datetime
from typing import Optional, Callable, Any

import rumps

from ..core.models import State, SessionStatus, Usage, Agent
from ..security.analyzer import analyze_command, RiskLevel, get_level_emoji


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
            sub_agents_map = {}
            for a in instance.agents:
                if a.is_subagent:
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
                pass

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
                pass

        items.append(rumps.MenuItem(f"{icon} Session: {five_h}%{session_reset}"))
        items.append(rumps.MenuItem(f"📅 Weekly: {seven_d}%{weekly_reset}"))
        items.append(
            rumps.MenuItem(
                "🌐 Open Claude Usage",
                callback=lambda _: __import__("subprocess").run(
                    ["open", "https://console.anthropic.com/settings/usage"]
                ),
            )
        )

        return items

    def build_security_menu(
        self,
        auditor,
        report_callback: Callable,
        export_callback: Callable,
    ) -> rumps.MenuItem:
        """Build the security audit submenu.

        Args:
            auditor: SecurityAuditor instance
            report_callback: Callback for viewing full report
            export_callback: Callback for exporting data

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
        menu.add(None)

        # Top critical/high items
        self._add_critical_items(menu, auditor)

        menu.add(None)
        menu.add(rumps.MenuItem("📋 View Full Report", callback=report_callback))
        menu.add(rumps.MenuItem("📤 Export All Data", callback=export_callback))

        return menu

    def _add_critical_items(self, menu: rumps.MenuItem, auditor) -> None:
        """Add critical/high risk items to security menu."""
        # Commands
        critical_cmds = auditor.get_critical_commands(5)
        if critical_cmds:
            menu.add(rumps.MenuItem("💻 ── Commands ──"))
            for cmd in critical_cmds:
                emoji = "🔴" if cmd.risk_level == "critical" else "🟠"
                cmd_short = (
                    cmd.command[:40] + "..." if len(cmd.command) > 40 else cmd.command
                )
                item = rumps.MenuItem(f"{emoji} {cmd_short}")
                item._menuitem.setToolTip_(
                    f"⚠️ {cmd.risk_reason}\nScore: {cmd.risk_score}/100\n\n{cmd.command}"
                )
                menu.add(item)

        # File reads
        sensitive_reads = auditor.get_sensitive_reads(5)
        if sensitive_reads:
            menu.add(rumps.MenuItem("📖 ── File Reads ──"))
            for read in sensitive_reads:
                emoji = "🔴" if read.risk_level == "critical" else "🟠"
                path_short = (
                    "..." + read.file_path[-40:]
                    if len(read.file_path) > 40
                    else read.file_path
                )
                item = rumps.MenuItem(f"{emoji} {path_short}")
                item._menuitem.setToolTip_(
                    f"⚠️ {read.risk_reason}\nScore: {read.risk_score}/100\n\n{read.file_path}"
                )
                menu.add(item)

        # File writes
        sensitive_writes = auditor.get_sensitive_writes(5)
        if sensitive_writes:
            menu.add(rumps.MenuItem("✏️ ── File Writes ──"))
            for write in sensitive_writes:
                emoji = "🔴" if write.risk_level == "critical" else "🟠"
                path_short = (
                    "..." + write.file_path[-40:]
                    if len(write.file_path) > 40
                    else write.file_path
                )
                item = rumps.MenuItem(f"{emoji} {path_short}")
                item._menuitem.setToolTip_(
                    f"⚠️ {write.risk_reason}\nScore: {write.risk_score}/100\nOperation: {write.operation}\n\n{write.file_path}"
                )
                menu.add(item)

        # Webfetches
        risky_fetches = auditor.get_risky_webfetches(5)
        if risky_fetches:
            menu.add(rumps.MenuItem("🌐 ── Web Fetches ──"))
            for fetch in risky_fetches:
                emoji = "🔴" if fetch.risk_level == "critical" else "🟠"
                url_short = fetch.url[:40] + "..." if len(fetch.url) > 40 else fetch.url
                item = rumps.MenuItem(f"{emoji} {url_short}")
                item._menuitem.setToolTip_(
                    f"⚠️ {fetch.risk_reason}\nScore: {fetch.risk_score}/100\n\n{fetch.url}"
                )
                menu.add(item)

        if (
            not critical_cmds
            and not sensitive_reads
            and not sensitive_writes
            and not risky_fetches
        ):
            menu.add(rumps.MenuItem("✅ No critical items"))

    def build_analytics_menu(
        self,
        analytics_callback: Callable[[int], None],
        refresh_callback: Callable,
    ) -> rumps.MenuItem:
        """Build the analytics submenu.

        Args:
            analytics_callback: Callback for viewing analytics (takes days param)
            refresh_callback: Callback for refreshing data

        Returns:
            rumps.MenuItem with analytics submenu
        """
        menu = rumps.MenuItem("📈 OpenCode Analytics")

        # Period options
        def make_period_callback(days: int):
            def callback(_):
                analytics_callback(days)

            return callback

        menu.add(rumps.MenuItem("📅 Last 24 hours", callback=make_period_callback(1)))
        menu.add(rumps.MenuItem("📅 Last 7 days", callback=make_period_callback(7)))
        menu.add(rumps.MenuItem("📅 Last 30 days", callback=make_period_callback(30)))
        menu.add(None)  # separator
        menu.add(rumps.MenuItem("🔃 Refresh data", callback=refresh_callback))

        return menu
