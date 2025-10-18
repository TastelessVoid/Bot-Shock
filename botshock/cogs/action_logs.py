"""
Action logs cog for viewing and exporting controller action history
"""

import logging
from datetime import datetime
from io import BytesIO

import disnake
from disnake.ext import commands

from botshock.core.bot_protocol import SupportsBotAttrs

logger = logging.getLogger("BotShock.ActionLogs")


class LogsPaginationView(disnake.ui.View):
    """View for paginating through action logs"""

    def __init__(
        self,
        author_id: int,
        guild_id: int,
        days: int,
        total_pages: int,
        current_page: int,
        db,
        formatter,
        format_log_entry_func,
    ):
        super().__init__(timeout=180)
        self.author_id = author_id
        self.guild_id = guild_id
        self.days = days
        self.total_pages = total_pages
        self.current_page = current_page
        self.db = db
        self.formatter = formatter
        self.format_log_entry = format_log_entry_func

        # Disable buttons if at boundaries
        if current_page <= 1:
            self.prev_button.disabled = True
        if current_page >= total_pages:
            self.next_button.disabled = True

    @disnake.ui.button(label="◀️ Previous", style=disnake.ButtonStyle.primary, custom_id="prev")
    async def prev_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        if inter.author.id != self.author_id:
            await inter.response.send_message(
                "This is not your pagination control.", ephemeral=True
            )
            return

        self.current_page -= 1
        await self._update_page(inter)

    @disnake.ui.button(label="Next ▶️", style=disnake.ButtonStyle.primary, custom_id="next")
    async def next_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        if inter.author.id != self.author_id:
            await inter.response.send_message(
                "This is not your pagination control.", ephemeral=True
            )
            return

        self.current_page += 1
        await self._update_page(inter)

    async def _update_page(self, inter: disnake.MessageInteraction):
        """Update the message with a new page"""
        await inter.response.defer()

        # Get logs for this page
        logs_per_page = 10
        offset = (self.current_page - 1) * logs_per_page
        logs = await self.db.get_action_logs_for_target(
            target_discord_id=self.author_id,
            guild_id=self.guild_id,
            limit=logs_per_page,
            offset=offset,
            days=self.days,
        )

        if not logs:
            await inter.edit_original_message(
                embed=self.formatter.info_embed("No Logs", f"Page {self.current_page} is empty.")
            )
            return

        # Build embed
        embed = disnake.Embed(
            title=f"📊 Your Controller Action Logs (Last {self.days} Days)",
            description=f"Page {self.current_page} of {self.total_pages}",
            color=disnake.Color.blue(),
        )

        # Add each log entry
        for log in logs:
            field_name, field_value = self.format_log_entry(log)
            embed.add_field(name=field_name, value=field_value, inline=False)

        embed.set_footer(text=f"Page {self.current_page}/{self.total_pages}")

        # Update button states
        self.prev_button.disabled = self.current_page <= 1
        self.next_button.disabled = self.current_page >= self.total_pages

        await inter.edit_original_message(embed=embed, view=self)


def _generate_csv_export(logs: list) -> str:
    """Generate a CSV export of action logs"""
    lines = [
        "Timestamp,Controller,Controller ID,Action Type,Shock Type,Intensity,Duration,Device,Success,Error,Source"
    ]

    # CSV Header

    # CSV Data
    for log in logs:
        timestamp = datetime.fromisoformat(log["timestamp"])
        timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")

        # Escape fields that might contain commas
        controller = (log.get("controller_username") or "").replace('"', '""')
        error_msg = (log.get("error_message") or "").replace('"', '""')
        device_name = (log.get("shocker_name") or "").replace('"', '""')

        intensity = log.get("intensity")
        duration = log.get("duration")
        shock_type = log.get("shock_type") or ""

        row = [
            timestamp_str,
            f'"{controller}"',
            str(log.get("controller_discord_id") or ""),
            str(log.get("action_type") or ""),
            shock_type,
            str(intensity) if intensity is not None else "",
            str(duration) if duration is not None else "",
            f'"{device_name}"',
            "Yes" if log.get("success") else "No",
            f'"{error_msg}"',
            str(log.get("source") or ""),
        ]

        lines.append(",".join(row))

    return "\n".join(lines)


class ActionLogs(commands.Cog):
    """Commands for viewing and exporting controller action logs"""

    def __init__(self, bot: SupportsBotAttrs):
        self.bot = bot
        self.db = bot.db
        self.formatter = bot.formatter  # Use shared formatter
        self.helper = bot.command_helper  # Use shared command helper

    @commands.slash_command(description="View and manage your controller action logs")
    async def logs(self, inter: disnake.ApplicationCommandInteraction):
        """Base command for action logs"""
        pass

    @logs.sub_command(description="View recent controller actions on your device")
    async def view(
        self,
        inter: disnake.ApplicationCommandInteraction,
        days: int = commands.Param(
            description="Show logs from the last N days (1-90)", ge=1, le=90, default=7
        ),
        page: int = commands.Param(description="Page number (10 logs per page)", ge=1, default=1),
    ):
        """View recent controller actions on your device"""
        await self.helper.defer_response(inter)

        # Check if user is registered using helper
        if not await self.helper.require_user_registered(inter, inter.author.id, inter.guild.id):
            return

        # Get action logs
        logs_per_page = 10
        offset = (page - 1) * logs_per_page
        logs = await self.db.get_action_logs_for_target(
            target_discord_id=inter.author.id,
            guild_id=inter.guild.id,
            limit=logs_per_page,
            offset=offset,
            days=days,
        )

        total_count = await self.db.get_action_log_count(inter.author.id, inter.guild.id, days=days)
        total_pages = max(1, (total_count + logs_per_page - 1) // logs_per_page)

        if not logs:
            if page == 1:
                embed = self.formatter.info_embed(
                    "No Action Logs",
                    f"No controller actions found in the last {days} day(s).",
                    field_1=(
                        "What are action logs?",
                        "Action logs record every time someone uses a command on your device, "
                        "including shocks, reminders, and triggers.",
                    ),
                )
            else:
                embed = self.formatter.info_embed(
                    "No More Logs",
                    f"Page {page} is empty. You only have {total_pages} page(s) of logs.",
                )
            await inter.edit_original_response(embed=embed)
            return

        # Build embed
        embed = disnake.Embed(
            title=f"📊 Your Controller Action Logs (Last {days} Days)",
            description=f"Page {page} of {total_pages} • Total: {total_count} action(s)",
            color=disnake.Color.blue(),
        )

        # Add each log entry using helper
        for log in logs:
            field_name, field_value = self.helper.build_action_log_entry(log)
            embed.add_field(name=field_name, value=field_value, inline=False)

        # Add pagination view with navigation buttons
        embed.set_footer(text=f"Page {page}/{total_pages} • Use buttons to navigate")

        # Create pagination view
        view = LogsPaginationView(
            author_id=inter.author.id,
            guild_id=inter.guild.id,
            days=days,
            total_pages=total_pages,
            current_page=page,
            db=self.db,
            formatter=self.formatter,
            format_log_entry_func=self.helper.build_action_log_entry,
        )

        await inter.edit_original_response(embed=embed, view=view)

    @logs.sub_command(description="Export your controller action logs to a text file")
    async def export(
        self,
        inter: disnake.ApplicationCommandInteraction,
        days: int = commands.Param(
            description="Export logs from the last N days (1-365)", ge=1, le=365, default=30
        ),
        format: str = commands.Param(
            description="Export format", choices=["text", "csv"], default="text"
        ),
    ):
        """Export controller action logs to a downloadable file"""
        await self.helper.defer_response(inter)

        # Check if user is registered using helper
        if not await self.helper.require_user_registered(inter, inter.author.id, inter.guild.id):
            return

        # Get all action logs (up to 1000)
        logs = await self.db.get_action_logs_for_target(
            target_discord_id=inter.author.id,
            guild_id=inter.guild.id,
            limit=1000,
            offset=0,
            days=days,
        )

        if not logs:
            embed = self.formatter.info_embed(
                "No Logs to Export", f"No controller actions found in the last {days} day(s)."
            )
            await inter.edit_original_response(embed=embed)
            return

        # Generate the export file
        if format == "csv":
            content = _generate_csv_export(logs)
            filename = (
                f"action_logs_{inter.author.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )
        else:
            content = self._generate_text_export(logs, inter.author.name, days)
            filename = (
                f"action_logs_{inter.author.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )

        # Create file object (as bytes)
        file = disnake.File(BytesIO(content.encode("utf-8")), filename=filename)

        # Build success embed
        embed = disnake.Embed(
            title="📥 Action Logs Exported",
            description="Your action logs have been exported successfully!",
            color=disnake.Color.green(),
        )
        embed.add_field(
            name="Export Details",
            value=(
                f"**Period:** Last {days} day(s)\n"
                f"**Total Actions:** {len(logs)}\n"
                f"**Format:** {format.upper()}\n"
                f"**File:** {filename}"
            ),
            inline=False,
        )
        embed.add_field(
            name="🔒 Privacy Note",
            value="This file contains your personal action history. Keep it secure and do not share publicly.",
            inline=False,
        )
        embed.set_footer(text=f"Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Try to send via DM first for privacy
        dm_sent = False
        try:
            await inter.author.send(
                "📊 **Your Action Log Export**\n\n"
                "Here's your requested action log export. This file is private and should be kept secure.",
                embed=embed,
                file=file,
            )
            dm_sent = True
            logger.info(
                f"Action logs exported via DM: User {inter.author} ({inter.author.id}) exported "
                f"{len(logs)} logs covering {days} days in {format} format"
            )
        except disnake.Forbidden:
            logger.info(f"Cannot send DM to {inter.author.id} - DMs are disabled")
        except disnake.HTTPException as e:
            logger.warning(f"Failed to send DM to {inter.author.id}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error sending DM to {inter.author.id}: {e}")

        if dm_sent:
            # Confirm in the original response that DM was sent
            confirmation_embed = disnake.Embed(
                title="✅ Sent to Your DMs",
                description=(
                    f"Your action log export has been sent to your Direct Messages for privacy.\n\n"
                    f"📊 **{len(logs)} action(s)** exported covering the last **{days} day(s)**"
                ),
                color=disnake.Color.green(),
            )
            confirmation_embed.add_field(
                name="🔒 Why DMs?",
                value="Action logs contain sensitive information about your usage history, so we send them privately.",
                inline=False,
            )
            await inter.edit_original_response(embed=confirmation_embed)
        else:
            # Fallback: send as ephemeral message in the channel
            # Need to recreate the file since it was already used
            file_fallback = disnake.File(BytesIO(content.encode("utf-8")), filename=filename)

            fallback_embed = embed.copy()
            fallback_embed.add_field(
                name="⚠️ DMs Disabled",
                value=(
                    "Could not send via DM (you may have DMs disabled for this server). "
                    "The file is attached below, but only you can see it.\n\n"
                    "**Tip:** Enable DMs from server members in Privacy Settings for more secure delivery."
                ),
                inline=False,
            )

            await inter.edit_original_response(embed=fallback_embed, file=file_fallback)

            logger.info(
                f"Action logs exported via ephemeral: User {inter.author} ({inter.author.id}) exported "
                f"{len(logs)} logs covering {days} days in {format} format (DMs disabled)"
            )

    @staticmethod
    def _generate_text_export(logs: list, username: str, days: int) -> str:
        """Generate a human-readable text export of action logs"""
        lines = [
            "=" * 80,
            f"CONTROLLER ACTION LOGS - {username}",
            "=" * 80,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Period: Last {days} day(s)",
            f"Total Actions: {len(logs)}",
            "=" * 80,
            "",
        ]

        for i, log in enumerate(logs, 1):
            timestamp = datetime.fromisoformat(log["timestamp"])
            timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")

            lines.append(f"[{i}] {timestamp_str}")
            lines.append(f"    Controller: {log['controller_username']}")
            lines.append(f"    Action: {log['action_type'].upper()}")
            lines.append(f"    Source: {log['source']}")
            lines.append(f"    Status: {'SUCCESS' if log['success'] else 'FAILED'}")

            if log.get("shock_type"):
                lines.append(f"    Shock Type: {log['shock_type']}")
            if log.get("intensity") is not None:
                lines.append(f"    Intensity: {log['intensity']}%")
            if log.get("duration") is not None:
                lines.append(f"    Duration: {log['duration']}ms")
            if log.get("shocker_name"):
                lines.append(f"    Device: {log['shocker_name']}")
            if log.get("shocker_id"):
                lines.append(f"    Device ID: {log['shocker_id']}")

            if (not log.get("success")) and log.get("error_message"):
                lines.append(f"    Error: {log['error_message']}")

            lines.append("")

        lines.append("=" * 80)
        lines.append("END OF REPORT")
        lines.append("=" * 80)

        return "\n".join(lines)

    @logs.sub_command(description="View statistics about controller actions on your device")
    async def stats(
        self,
        inter: disnake.ApplicationCommandInteraction,
        days: int = commands.Param(
            description="Show stats from the last N days (1-365)", ge=1, le=365, default=30
        ),
    ):
        """View statistics about controller actions"""
        await self.helper.defer_response(inter)

        # Check if user is registered using helper
        if not await self.helper.require_user_registered(inter, inter.author.id, inter.guild.id):
            return

        # Get all logs for analysis
        logs = await self.db.get_action_logs_for_target(
            target_discord_id=inter.author.id,
            guild_id=inter.guild.id,
            limit=10000,  # High limit for stats
            offset=0,
            days=days,
        )

        if not logs:
            embed = self.formatter.info_embed(
                "No Statistics Available", f"No controller actions found in the last {days} day(s)."
            )
            await inter.edit_original_response(embed=embed)
            return

        # Calculate statistics
        total_actions = len(logs)
        successful_actions = sum(1 for log in logs if log["success"])
        failed_actions = total_actions - successful_actions

        # Count by controller
        controller_counts = {}
        for log in logs:
            controller = log["controller_username"]
            controller_counts[controller] = controller_counts.get(controller, 0) + 1

        # Count by action type
        action_type_counts = {}
        for log in logs:
            action_type = log["action_type"]
            action_type_counts[action_type] = action_type_counts.get(action_type, 0) + 1

        # Count by shock type
        shock_type_counts = {}
        for log in logs:
            if log["shock_type"]:
                shock_type = log["shock_type"]
                shock_type_counts[shock_type] = shock_type_counts.get(shock_type, 0) + 1

        # Average intensity and duration
        intensities = [log["intensity"] for log in logs if log.get("intensity") is not None]
        durations = [log["duration"] for log in logs if log.get("duration") is not None]

        avg_intensity = sum(intensities) / len(intensities) if intensities else 0
        avg_duration = sum(durations) / len(durations) if durations else 0

        # Build embed
        embed = disnake.Embed(
            title=f"📊 Your Action Statistics (Last {days} Days)",
            description=f"Analysis of {total_actions} controller action(s)",
            color=disnake.Color.blue(),
            timestamp=datetime.now(),
        )

        # Overall stats
        success_rate = (successful_actions / total_actions * 100) if total_actions > 0 else 0
        embed.add_field(
            name="Overall Statistics",
            value=(
                f"**Total Actions:** {total_actions}\n"
                f"**Successful:** {successful_actions} ({success_rate:.1f}%)\n"
                f"**Failed:** {failed_actions}\n"
                f"**Avg Intensity:** {avg_intensity:.1f}%\n"
                f"**Avg Duration:** {avg_duration:.0f}ms"
            ),
            inline=False,
        )

        # Top controllers
        top_controllers = sorted(controller_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        if top_controllers:
            controller_text = "\n".join(
                f"{i+1}. {name}: {count} action(s)"
                for i, (name, count) in enumerate(top_controllers)
            )
            embed.add_field(name="Top Controllers", value=controller_text, inline=True)

        # Action type breakdown
        if action_type_counts:
            action_text = "\n".join(
                f"**{action}:** {count}"
                for action, count in sorted(
                    action_type_counts.items(), key=lambda x: x[1], reverse=True
                )
            )
            embed.add_field(name="Action Types", value=action_text, inline=True)

        # Shock type breakdown
        if shock_type_counts:
            shock_text = "\n".join(
                f"**{shock}:** {count}"
                for shock, count in sorted(
                    shock_type_counts.items(), key=lambda x: x[1], reverse=True
                )
            )
            embed.add_field(name="Shock Types", value=shock_text, inline=True)

        embed.set_footer(text="Use /logs export to download detailed logs")

        await inter.edit_original_response(embed=embed)


def setup(bot: commands.InteractionBot):
    """Setup function to add the cog to the bot"""
    bot.add_cog(ActionLogs(bot))
    logger.info("ActionLogs cog has been loaded")
