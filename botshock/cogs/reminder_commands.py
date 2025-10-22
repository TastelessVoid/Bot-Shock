"""
Reminder commands cog for managing scheduled shocks
"""

import logging
from datetime import datetime

import disnake
from disnake.ext import commands

from botshock.core.bot_protocol import SupportsBotAttrs
from botshock.utils.decorators import defer_response
from botshock.utils.recurrence import RecurrencePattern
from botshock.utils.time_parser import TimeParser
from botshock.utils.validators import ReminderValidator
from botshock.utils.views import AuthorOnlyViewWithCustomMessage

logger = logging.getLogger("BotShock.ReminderCommands")


class ReminderListView(AuthorOnlyViewWithCustomMessage):
    """Paginated view for reminders with quick actions"""

    def __init__(
        self,
        author_id: int,
        guild_id: int,
        reminders: list,
        page: int,
        total_pages: int,
        db,
        formatter,
    ):
        super().__init__(author_id, "You can't use these buttons!", timeout=180)
        self.guild_id = guild_id
        self.reminders = reminders
        self.page = page
        self.total_pages = total_pages
        self.db = db
        self.formatter = formatter

        # Update button states
        self.prev_btn.disabled = page == 1
        self.next_btn.disabled = page >= total_pages

        # Add quick cancel buttons for each reminder (up to 5)
        for i, reminder in enumerate(reminders[:5]):
            btn = disnake.ui.Button(
                label=f"Cancel #{reminder['id']}",
                style=disnake.ButtonStyle.danger,
                emoji="🗑️",
                custom_id=f"cancel_reminder_{reminder['id']}",
                row=2 if i < 3 else 3,
            )
            btn.callback = self.create_cancel_callback(reminder["id"])
            self.add_item(btn)

    def create_cancel_callback(self, reminder_id: int):
        """Create a cancel callback for a specific reminder"""

        async def callback(interaction: disnake.MessageInteraction):
            await interaction.response.defer()
            success = await self.db.delete_reminder(reminder_id, self.guild_id)
            if success:
                await interaction.followup.send(
                    embed=self.formatter.success_embed(
                        "Reminder Cancelled", f"Successfully cancelled reminder #{reminder_id}"
                    ),
                    ephemeral=True,
                )
                # Refresh the list
                # Note: This would require re-fetching data, simplified here
            else:
                await interaction.followup.send(
                    embed=self.formatter.error_embed(
                        "Failed", f"Could not cancel reminder #{reminder_id}"
                    ),
                    ephemeral=True,
                )

        return callback

    @disnake.ui.button(
        label="◀️ Previous",
        style=disnake.ButtonStyle.primary,
        custom_id="prev",
        row=0,
        disabled=True,
    )
    async def prev_btn(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        """Previous page button"""
        await interaction.response.send_message(
            "Use `/remind list page:N` to navigate pages", ephemeral=True
        )

    @disnake.ui.button(label="Next ▶️", style=disnake.ButtonStyle.primary, custom_id="next", row=0)
    async def next_btn(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        """Next page button"""
        await interaction.response.send_message(
            "Use `/remind list page:N` to navigate pages", ephemeral=True
        )

    @disnake.ui.button(
        label="➕ Add Reminder",
        style=disnake.ButtonStyle.success,
        emoji="➕",
        custom_id="add_reminder",
        row=1,
    )
    async def add_btn(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        """Quick add button"""
        await interaction.response.send_message(
            "💡 Use `/remind set` to create a new reminder!", ephemeral=True
        )


class ReminderCommands(commands.Cog):
    """Commands for managing scheduled shock reminders"""

    def __init__(self, bot: SupportsBotAttrs):
        self.bot = bot
        self.db = bot.db
        self.formatter = bot.formatter  # Use shared formatter
        self.permission_checker = bot.permission_checker
        self.time_parser = TimeParser()
        self.validator = ReminderValidator(bot.db, bot.permission_checker)

    @commands.slash_command(description="Manage shock reminders")
    async def remind(self, inter: disnake.ApplicationCommandInteraction):
        """Base command for reminder management"""
        pass

    @remind.sub_command_group(name="manage", description="Create, cancel, and view reminders")
    async def manage_group(self, inter: disnake.ApplicationCommandInteraction):
        """Manage your reminders"""
        pass

    async def time_autocomplete(
        self, inter: disnake.ApplicationCommandInteraction, user_input: str
    ):
        """Autocomplete callback that shows parsed time preview"""
        if not user_input:
            return self.time_parser.get_example_suggestions()

        preview = self.time_parser.format_preview(user_input)
        return [preview]

    @staticmethod
    async def recurrence_autocomplete(
        inter: disnake.ApplicationCommandInteraction, user_input: str
    ):
        """Autocomplete callback for recurrence patterns"""
        if not user_input:
            return RecurrencePattern.get_examples()

        # Filter examples based on input
        examples = RecurrencePattern.get_examples()
        filtered = [ex for ex in examples if user_input.lower() in ex.lower()]
        return filtered[:25] if filtered else examples[:25]

    @manage_group.sub_command(description="Set a reminder to shock a user at a specific time")
    @defer_response(ephemeral=True)
    async def set(
        self,
        inter: disnake.ApplicationCommandInteraction,
        user: disnake.User = commands.Param(
            description="User to shock (defaults to yourself)", default=None
        ),
        time: str = commands.Param(
            description="When to shock (e.g., '15:00', '10:30', '2h', '30m', '5d')",
            autocomplete=time_autocomplete,
        ),
        reason: str = commands.Param(description="Reason for the reminder", default=None),
        intensity: int = commands.Param(
            description="Shock intensity (1-100)", ge=1, le=100, default=50
        ),
        duration: int = commands.Param(
            description="Duration in milliseconds (300-65535)", ge=300, le=65535, default=1000
        ),
        shock_type: str = commands.Param(
            description="Type of shock", choices=["Shock", "Vibrate", "Sound"], default="Shock"
        ),
        recurring: str = commands.Param(
            description="Make it recurring (e.g., 'daily', 'every monday', 'weekdays')",
            default=None,
            autocomplete=recurrence_autocomplete,
        ),
    ):
        """Set a reminder to shock a user at a specific time (with optional recurrence)"""
        if user is None:
            user = inter.author

        is_valid, error_msg = await self.validator.validate_reminder_creation(
            inter.author, user, inter.guild.id
        )
        if not is_valid:
            embed = self.formatter.error_embed("Permission Denied", error_msg)
            await inter.edit_original_response(embed=embed)
            logger.warning(
                f"Permission denied: {inter.author} ({inter.author.id}) tried to set reminder for "
                f"{user} ({user.id}) in guild {inter.guild.id}"
            )
            return

        # Parse time
        scheduled_time = self.time_parser.parse(time)

        # Handle case where user selected from autocomplete (contains preview)
        if not scheduled_time and "→" in time:
            # Extract original time from preview string
            original_time = time.split("→")[0].strip()
            scheduled_time = self.time_parser.parse(original_time)

        if not scheduled_time:
            embed = self.formatter.error_embed(
                "Invalid Time Format",
                "Unable to parse the time you provided.",
                field_1=(
                    "Supported Formats",
                    "• `HH:MM` (e.g., `15:00`, `09:30`) for specific time today\n"
                    "• `Xd` (e.g., `5d`, `2d`) for days from now\n"
                    "• `Xh` (e.g., `2h`, `1h30m`) for hours from now\n"
                    "• `Xm` (e.g., `30m`, `90m`) for minutes from now",
                ),
            )
            await inter.edit_original_response(embed=embed)
            return

        # Check if time is in the past
        if scheduled_time <= datetime.now():
            embed = self.formatter.error_embed(
                "Invalid Time", "Cannot set reminder in the past. Please specify a future time."
            )
            await inter.edit_original_response(embed=embed)
            return

        # Handle recurring pattern if provided
        is_recurring = False
        recurrence_pattern = None
        if recurring:
            is_valid_pattern, pattern_desc = RecurrencePattern.validate_pattern(recurring)
            if not is_valid_pattern:
                embed = self.formatter.error_embed(
                    "Invalid Recurrence Pattern",
                    pattern_desc,
                    field_1=(
                        "Examples",
                        "• `daily` - Every day at the same time\n"
                        "• `every monday` - Every Monday\n"
                        "• `weekdays` - Monday through Friday\n"
                        "• `every 3 days` - Every 3 days\n"
                        "• `every 12 hours` - Every 12 hours",
                    ),
                )
                await inter.edit_original_response(embed=embed)
                return
            is_recurring = True
            recurrence_pattern = recurring.lower().strip()

        # Create reminder (Database method is asynchronous)
        reminder_id = await self.db.add_reminder(
            guild_id=inter.guild.id,
            target_discord_id=user.id,
            creator_discord_id=inter.author.id,
            scheduled_time=scheduled_time,
            reason=reason,
            shock_type=shock_type,
            intensity=intensity,
            duration=duration,
            channel_id=(
                inter.channel.id if isinstance(inter.channel, disnake.TextChannel) else None
            ),
            is_recurring=is_recurring,
            recurrence_pattern=recurrence_pattern,
        )

        if reminder_id:
            logger.info(
                f"Reminder {reminder_id} set for {user} ({user.id}) by {inter.author} ({inter.author.id}) "
                f"at {scheduled_time}"
                + (f" - Recurring: {recurrence_pattern}" if is_recurring else "")
            )

            embed = self.formatter.format_reminder_set(
                reminder_id, user.mention, scheduled_time, shock_type, intensity, duration, reason
            )

            # Add recurring information to embed
            if is_recurring:
                pattern_dict = RecurrencePattern.parse_pattern(recurrence_pattern)
                if pattern_dict:
                    embed.add_field(
                        name="🔄 Recurring",
                        value=RecurrencePattern.format_pattern(pattern_dict),
                        inline=False,
                    )
                    embed.color = 0x9B59B6  # Purple color for recurring reminders

            embed.set_footer(
                text=f"Set by {inter.author.display_name}", icon_url=inter.author.display_avatar.url
            )

            # Success is public
            await inter.delete_original_response()
            await inter.followup.send(embed=embed)
        else:
            embed = self.formatter.error_embed(
                "Database Error", "Failed to create reminder. Please try again."
            )
            await inter.edit_original_response(embed=embed)

    @manage_group.sub_command(description="Cancel a scheduled reminder")
    @defer_response(ephemeral=True)
    async def cancel(
        self,
        inter: disnake.ApplicationCommandInteraction,
        reminder_id: int = commands.Param(description="The reminder ID to cancel"),
    ):
        """Cancel a scheduled reminder"""

        reminder = await self.db.get_reminder(reminder_id, inter.guild.id)

        if not reminder:
            embed = self.formatter.error_embed("Not Found", f"Reminder #{reminder_id} not found.")
            await inter.edit_original_response(embed=embed)
            return

        can_cancel = (
            reminder["creator_discord_id"] == inter.author.id
            or inter.author.guild_permissions.administrator
            or await self.permission_checker.has_control_role(inter.author)
        )

        if not can_cancel:
            embed = self.formatter.error_embed(
                "Permission Denied",
                "You can only cancel reminders you created, or you need administrator/control permissions.",
            )
            await inter.edit_original_response(embed=embed)
            return

        success = await self.db.delete_reminder(reminder_id, inter.guild.id)

        if success:
            logger.info(f"Reminder {reminder_id} cancelled by {inter.author} ({inter.author.id})")
            embed = self.formatter.success_embed(
                "Reminder Cancelled", f"Successfully cancelled reminder #{reminder_id}"
            )
            await inter.delete_original_response()
            await inter.followup.send(embed=embed)
        else:
            embed = self.formatter.error_embed(
                "Cancellation Failed", "Failed to cancel reminder. Please try again."
            )
            await inter.edit_original_response(embed=embed)

    @manage_group.sub_command(description="List your scheduled reminders")
    @defer_response(ephemeral=True)
    async def list(
        self,
        inter: disnake.ApplicationCommandInteraction,
        user: disnake.User = commands.Param(
            description="User to list reminders for (optional)", default=None
        ),
        page: int = commands.Param(description="Page number to display", default=1, ge=1),
    ):
        """List scheduled reminders"""

        target_user = user if user else inter.author

        if target_user != inter.author:
            can_manage, reason = await self.permission_checker.can_manage_user(
                inter.author, target_user
            )
            if not can_manage:
                error_msg = await self.permission_checker.get_permission_error_message(
                    reason, target_user, inter.guild
                )
                embed = self.formatter.error_embed("Permission Denied", error_msg)
                await inter.edit_original_response(embed=embed)
                return

        reminders = await self.db.get_reminders_for_user(inter.guild.id, target_user.id)

        items_per_page = 5
        total_reminders = len(reminders)
        total_pages = (total_reminders // items_per_page) + (
            1 if total_reminders % items_per_page > 0 else 0
        )

        if total_pages == 0:
            total_pages = 1
        if page > total_pages:
            page = total_pages
        if page < 1:
            page = 1

        start = (page - 1) * items_per_page
        end = start + items_per_page
        paginated_reminders = reminders[start:end]

        embed = self.formatter.format_reminder_list(paginated_reminders, inter.guild)

        if target_user != inter.author:
            embed.title = f"⏰ Reminders for {target_user.display_name}"

        # Add pagination footer
        embed.set_footer(text=f"Page {page} of {total_pages}")

        # Add view for pagination buttons
        view = ReminderListView(
            inter.author.id, inter.guild.id, reminders, page, total_pages, self.db, self.formatter
        )
        await inter.edit_original_response(embed=embed, view=view)


def setup(bot: commands.InteractionBot):
    """Setup function to add the cog to the bot"""
    bot.add_cog(ReminderCommands(bot))
    logger.info("ReminderCommands cog has been loaded")
