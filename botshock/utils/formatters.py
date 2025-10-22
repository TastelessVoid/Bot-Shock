"""
Response formatter for consistent Discord message formatting with embeds
"""

from datetime import datetime

import disnake


class ResponseFormatter:
    """Formats responses for Discord messages using embeds"""

    # Color constants
    COLOR_SUCCESS = 0x00FF00  # Green
    COLOR_ERROR = 0xFF0000  # Red
    COLOR_INFO = 0x3498DB  # Blue
    COLOR_WARNING = 0xFFA500  # Orange
    COLOR_OPENSHOCK = 0xFF6B35  # OpenShock brand color

    @staticmethod
    def _make_embed(
        prefix: str, title: str, description: str, color: int, **kwargs
    ) -> disnake.Embed:
        """Internal helper to build consistent embeds with optional fields

        Supports two field formats for clarity:
        1. field_N=(name, value) - legacy format, still works
        2. fields=[(name, value), ...] - modern list format
        """
        embed = disnake.Embed(
            title=f"{prefix} {title}",
            description=description,
            color=color,
            timestamp=datetime.now(),
        )

        # Handle new 'fields' parameter for list of tuples
        if "fields" in kwargs:
            for name, value in kwargs.pop("fields"):
                embed.add_field(name=name, value=value, inline=False)

        # Handle legacy field_N format
        for key, value in kwargs.items():
            if key.startswith("field_") and isinstance(value, (list, tuple)) and len(value) == 2:
                name, val = value
                embed.add_field(name=name, value=val, inline=False)
        return embed

    @staticmethod
    def add_fields(
        embed: disnake.Embed, fields: list[tuple[str, str]], inline: bool = False
    ) -> disnake.Embed:
        """
        Add multiple fields to an embed at once.

        Args:
            embed: The embed to add fields to
            fields: List of (name, value) tuples
            inline: Whether fields should be inline

        Returns:
            The modified embed
        """
        for name, value in fields:
            embed.add_field(name=name, value=value, inline=inline)
        return embed

    @staticmethod
    def success_embed(title: str, description: str, **kwargs) -> disnake.Embed:
        """Create a success embed"""
        return ResponseFormatter._make_embed(
            "✅", title, description, ResponseFormatter.COLOR_SUCCESS, **kwargs
        )

    @staticmethod
    def error_embed(title: str, description: str, **kwargs) -> disnake.Embed:
        """Create an error embed"""
        return ResponseFormatter._make_embed(
            "❌", title, description, ResponseFormatter.COLOR_ERROR, **kwargs
        )

    @staticmethod
    def info_embed(title: str, description: str, **kwargs) -> disnake.Embed:
        """Create an info embed"""
        return ResponseFormatter._make_embed(
            "ℹ️", title, description, ResponseFormatter.COLOR_INFO, **kwargs
        )

    @staticmethod
    def warning_embed(title: str, description: str, **kwargs) -> disnake.Embed:
        """Create a warning embed"""
        return ResponseFormatter._make_embed(
            "⚠️", title, description, ResponseFormatter.COLOR_WARNING, **kwargs
        )

    @staticmethod
    def openshock_button() -> disnake.ui.Button:
        """Create a button linking to OpenShock website"""
        return disnake.ui.Button(
            label="OpenShock Dashboard",
            url="https://openshock.app",
            style=disnake.ButtonStyle.link,
            emoji="🔗",
        )

    @staticmethod
    def docs_button() -> disnake.ui.Button:
        """Create a button linking to docs/help"""
        return disnake.ui.Button(
            label="Help & Documentation",
            url="https://github.com/OpenShock/BotShock",  # Update with actual URL
            style=disnake.ButtonStyle.link,
            emoji="📚",
        )

    @staticmethod
    def create_action_row(buttons: list) -> disnake.ui.View:
        """Create a view with a row of action buttons"""
        view = disnake.ui.View(timeout=180)
        for button in buttons:
            view.add_item(button)
        return view

    @staticmethod
    def create_confirm_view(
        confirm_label: str = "Confirm", cancel_label: str = "Cancel"
    ) -> disnake.ui.View:
        """Create a simple confirm/cancel button view"""
        view = disnake.ui.View(timeout=60)

        confirm_btn = disnake.ui.Button(
            label=confirm_label, style=disnake.ButtonStyle.success, emoji="✅", custom_id="confirm"
        )
        cancel_btn = disnake.ui.Button(
            label=cancel_label, style=disnake.ButtonStyle.secondary, emoji="❌", custom_id="cancel"
        )

        view.add_item(confirm_btn)
        view.add_item(cancel_btn)
        return view

    @staticmethod
    def progress_embed(
        title: str, step: int, total_steps: int, description: str = None
    ) -> disnake.Embed:
        """Create a progress indicator embed"""
        progress_bar = "█" * step + "░" * (total_steps - step)
        progress_text = f"{progress_bar} ({step}/{total_steps})"

        embed = disnake.Embed(
            title=f"⏳ {title}",
            description=description or f"Step {step} of {total_steps}",
            color=disnake.Color.blue(),
        )
        embed.add_field(name="Progress", value=progress_text, inline=False)
        return embed

    @staticmethod
    def format_list_embed(
        title: str, items: list, page: int, total_pages: int, item_formatter=None, color=None
    ) -> disnake.Embed:
        """Create a formatted list embed with pagination info"""
        embed = disnake.Embed(
            title=title,
            description=f"Page {page} of {total_pages}",
            color=color or ResponseFormatter.COLOR_INFO,
        )

        for i, item in enumerate(items, start=1):
            if item_formatter:
                name, value = item_formatter(item, i)
            else:
                name = f"Item {i}"
                value = str(item)

            embed.add_field(name=name, value=value, inline=False)

        embed.set_footer(text=f"Showing {len(items)} items • Page {page}/{total_pages}")
        return embed

    @staticmethod
    def status_indicator(
        is_active: bool, active_text: str = "Active", inactive_text: str = "Inactive"
    ) -> str:
        """Return a status indicator with emoji"""
        return f"🟢 {active_text}" if is_active else f"🔴 {inactive_text}"

    @staticmethod
    def format_duration(seconds: int) -> str:
        """Format duration in human-readable format"""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            remaining_seconds = seconds % 60
            return f"{minutes}m {remaining_seconds}s" if remaining_seconds else f"{minutes}m"
        else:
            hours = seconds // 3600
            remaining_minutes = (seconds % 3600) // 60
            return f"{hours}h {remaining_minutes}m" if remaining_minutes else f"{hours}h"

    @staticmethod
    def format_trigger_list(triggers: list, target_user_name: str = None) -> disnake.Embed:
        """Format trigger list as embed"""
        if target_user_name:
            title = f"Regex Triggers for {target_user_name}"
        else:
            title = "Your Regex Triggers"

        embed = disnake.Embed(
            title=f"⚡ {title}", color=ResponseFormatter.COLOR_INFO, timestamp=datetime.now()
        )

        if not triggers:
            embed.description = "*No triggers configured*"
            return embed

        for trigger in triggers[:25]:  # Discord field limit
            name = trigger["trigger_name"] or "Unnamed"
            status_emoji = "✅" if trigger["enabled"] else "❌"
            status = "ENABLED" if trigger["enabled"] else "DISABLED"

            value = (
                f"📝 Pattern: `{trigger['regex_pattern']}`\n"
                f"⚡ Action: {trigger['shock_type']} @ {trigger['intensity']}% for {trigger['duration']}ms\n"
                f"⏱️ Cooldown: {trigger['cooldown_seconds']}s"
            )

            embed.add_field(
                name=f"{status_emoji} #{trigger['id']} - {name} ({status})",
                value=value,
                inline=False,
            )

        if len(triggers) > 25:
            embed.set_footer(text=f"Showing 25 of {len(triggers)} triggers")

        return embed

    @staticmethod
    def format_shocker_list(shockers: list) -> disnake.Embed:
        """Format shocker list as embed"""
        embed = disnake.Embed(
            title="🔌 Your Registered Shockers",
            color=ResponseFormatter.COLOR_OPENSHOCK,
            timestamp=datetime.now(),
        )

        if not shockers:
            embed.description = "*No shockers registered*"
            embed.add_field(
                name="Getting Started",
                value="Use `/openshock setup` to add your API token, then `/openshock add_shocker` to add devices.",
                inline=False,
            )
            return embed

        for idx, shocker in enumerate(shockers, 1):
            name = shocker["shocker_name"] or "Unnamed"
            embed.add_field(
                name=f"{idx}. {name}", value=f"🆔 `{shocker['shocker_id']}`", inline=False
            )

        return embed

    @staticmethod
    def format_reminder_list(reminders: list, guild) -> disnake.Embed:
        """Format reminder list as embed"""
        embed = disnake.Embed(
            title="⏰ Your Scheduled Reminders",
            color=ResponseFormatter.COLOR_INFO,
            timestamp=datetime.now(),
        )

        if not reminders:
            embed.description = "*No pending reminders*"
            return embed

        from datetime import datetime as dt

        for reminder in reminders[:15]:  # Limit to 15
            target = guild.get_member(reminder["target_discord_id"]) if guild else None
            target_name = target.mention if target else f"User ID {reminder['target_discord_id']}"

            scheduled = dt.fromisoformat(reminder["scheduled_time"])
            time_str = scheduled.strftime("%Y-%m-%d %H:%M")

            status_emoji = "✅" if reminder.get("completed") else "⏳"
            reason = f"\n📝 {reminder['reason']}" if reminder.get("reason") else ""

            value = (
                f"👤 Target: {target_name}\n"
                f"📅 Scheduled: {time_str}\n"
                f"⚡ {reminder['shock_type']}, {reminder['intensity']}%{reason}"
            )

            embed.add_field(
                name=f"{status_emoji} Reminder #{reminder['id']}", value=value, inline=False
            )

        if len(reminders) > 15:
            embed.set_footer(text=f"Showing 15 of {len(reminders)} reminders")

        return embed

    @staticmethod
    def format_action_log(log_data: dict) -> str:
        """Format action log data as a string"""
        timestamp = log_data.get("timestamp", datetime.now())
        if isinstance(timestamp, datetime):
            time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        else:
            time_str = str(timestamp)

        controller_id = log_data.get("controller_id", "Unknown")
        target_id = log_data.get("target_id", "Unknown")
        action = log_data.get("action", "unknown")
        intensity = log_data.get("intensity", 0)
        duration = log_data.get("duration", 0)

        return (
            f"[{time_str}] Controller <@{controller_id}> sent {action} "
            f"to <@{target_id}> at {intensity}% intensity for {duration}s"
        )

    @staticmethod
    def format_permission_list(permissions: list) -> str:
        """Format permission list as a string"""
        if not permissions:
            return "No permissions found"

        lines = []
        for perm in permissions:
            controller_id = perm.get("controller_id", "Unknown")
            max_intensity = perm.get("max_intensity", 0)
            max_duration = perm.get("max_duration", 0)
            created_at = perm.get("created_at", datetime.now())

            if isinstance(created_at, datetime):
                time_str = created_at.strftime("%Y-%m-%d")
            else:
                time_str = str(created_at)

            lines.append(
                f"• Controller <@{controller_id}> - Max: {max_intensity}% / {max_duration}s (Since {time_str})"
            )

        return "\n".join(lines)

    @staticmethod
    def format_shock_success(
        target_name: str, shocker_name: str, shock_type: str, intensity: int, duration: int
    ) -> disnake.Embed:
        """Format shock command success as embed"""
        embed = disnake.Embed(
            title="⚡ Shock Sent Successfully",
            description=f"Shocked {target_name}!",
            color=ResponseFormatter.COLOR_OPENSHOCK,
            timestamp=datetime.now(),
        )

        embed.add_field(name="🔌 Shocker", value=shocker_name, inline=True)
        embed.add_field(name="📊 Intensity", value=f"{intensity}%", inline=True)
        embed.add_field(name="⏱️ Duration", value=f"{duration}ms", inline=True)
        embed.add_field(name="⚡ Type", value=shock_type, inline=True)

        return embed

    @staticmethod
    def format_trigger_added(
        trigger_id: int,
        name: str,
        pattern: str,
        shock_type: str,
        intensity: int,
        duration: int,
        cooldown: int,
        self_trigger: bool = True,
    ) -> disnake.Embed:
        """Format trigger added success as embed"""
        target = "you" if self_trigger else "the user"

        embed = disnake.Embed(
            title="✅ Trigger Added Successfully",
            description=f"This trigger will activate when {target} send messages matching the pattern.",
            color=ResponseFormatter.COLOR_SUCCESS,
            timestamp=datetime.now(),
        )

        embed.add_field(name="🆔 Trigger ID", value=f"#{trigger_id}", inline=True)
        embed.add_field(name="📝 Name", value=name or "Not set", inline=True)
        embed.add_field(name="⚡ Type", value=shock_type, inline=True)
        embed.add_field(name="📊 Intensity", value=f"{intensity}%", inline=True)
        embed.add_field(name="⏱️ Duration", value=f"{duration}ms", inline=True)
        embed.add_field(name="🔄 Cooldown", value=f"{cooldown}s", inline=True)
        embed.add_field(name="🔍 Pattern", value=f"`{pattern}`", inline=False)

        return embed

    @staticmethod
    def format_reminder_set(
        reminder_id: int,
        target_name: str,
        scheduled_time,
        shock_type: str,
        intensity: int,
        duration: int,
        reason: str = None,
    ) -> disnake.Embed:
        """Format reminder creation success as embed"""
        from datetime import datetime as dt

        from botshock.utils.time_parser import TimeParser

        time_diff = scheduled_time - dt.now()
        time_str = scheduled_time.strftime("%H:%M")
        duration_str = TimeParser.format_duration(time_diff)

        embed = disnake.Embed(
            title="⏰ Reminder Set Successfully",
            description="The target will be notified via DM or channel when executed.",
            color=ResponseFormatter.COLOR_SUCCESS,
            timestamp=dt.now(),
        )

        embed.add_field(name="🆔 Reminder ID", value=f"#{reminder_id}", inline=True)
        embed.add_field(name="👤 Target", value=target_name, inline=True)
        embed.add_field(name="⚡ Type", value=shock_type, inline=True)
        embed.add_field(name="📊 Intensity", value=f"{intensity}%", inline=True)
        embed.add_field(name="⏱️ Duration", value=f"{duration}ms", inline=True)
        embed.add_field(name="🕐 Scheduled", value=f"{time_str} (in {duration_str})", inline=True)

        if reason:
            embed.add_field(name="📝 Reason", value=reason, inline=False)

        return embed
