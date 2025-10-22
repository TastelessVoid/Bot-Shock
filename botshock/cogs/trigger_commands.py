"""
Trigger management commands cog
"""

import logging

import disnake
from disnake.ext import commands

from botshock.core.bot_protocol import SupportsBotAttrs
from botshock.utils.decorators import defer_response
from botshock.utils.validators import TriggerValidator

logger = logging.getLogger("BotShock.TriggerCommands")


class AddTriggerModal(disnake.ui.Modal):
    """Modal for adding a trigger"""

    def __init__(self, for_user: str = "yourself"):
        components = [
            disnake.ui.TextInput(
                label="Trigger Name",
                placeholder="My Trigger",
                custom_id="trigger_name",
                style=disnake.TextInputStyle.short,
                required=False,
            ),
            disnake.ui.TextInput(
                label="Regex Pattern (case-insensitive)",
                placeholder="bad word|naughty phrase",
                custom_id="regex_pattern",
                style=disnake.TextInputStyle.short,
                required=True,
            ),
        ]
        super().__init__(title=f"Add Trigger for {for_user}", components=components)


class TriggerCommands(commands.Cog):
    """Commands for managing regex triggers"""

    def __init__(self, bot: SupportsBotAttrs):
        self.bot = bot
        self.db = bot.db
        self.trigger_manager = bot.trigger_manager
        self.formatter = bot.formatter  # Use shared formatter
        self.permission_checker = bot.permission_checker
        self.validator = TriggerValidator(bot.db, bot.permission_checker)

    @commands.slash_command(description="Manage regex triggers")
    async def trigger(self, inter: disnake.ApplicationCommandInteraction):
        """Base command for trigger management"""
        pass

    @trigger.sub_command_group(name="manage", description="Create, remove, and manage triggers")
    async def manage_group(self, inter: disnake.ApplicationCommandInteraction):
        """Manage your triggers"""
        pass

    @manage_group.sub_command(description="Add a regex trigger")
    async def add(
        self,
        inter: disnake.ApplicationCommandInteraction,
        intensity: int = commands.Param(
            description="Shock intensity (1-100)", ge=1, le=100, default=50
        ),
        duration: int = commands.Param(
            description="Duration in milliseconds (300-65535)", ge=300, le=65535, default=1000
        ),
        shock_type: str = commands.Param(
            description="Type of shock", choices=["Shock", "Vibrate", "Sound"], default="Shock"
        ),
        cooldown: int = commands.Param(
            description="Cooldown in seconds (0-3600)", ge=0, le=3600, default=60
        ),
        user: disnake.User = commands.Param(
            description="User to add trigger for (leave empty for yourself)", default=None
        ),
    ):
        """Add a regex trigger for automatic shocks using a modal"""
        target_user = self.bot.command_helper.resolve_target_user(user, inter.author)
        is_for_self = target_user == inter.author

        if not await self.bot.command_helper.check_permission_with_logging(
            inter, inter.author, target_user, "add trigger"
        ):
            return

        modal = AddTriggerModal(
            for_user=target_user.display_name if not is_for_self else "yourself"
        )
        await inter.response.send_modal(modal)

        try:
            modal_inter: disnake.ModalInteraction = await self.bot.wait_for(
                "modal_submit",
                check=lambda i: i.custom_id == modal.custom_id and i.author.id == inter.author.id,
                timeout=300,
            )
        except Exception:
            return

        # Send an immediate response instead of deferring
        await modal_inter.response.send_message(
            embed=self.formatter.info_embed("Processing", "Creating trigger, please wait..."),
            ephemeral=True,
        )

        regex_pattern = modal_inter.text_values["regex_pattern"].strip()
        trigger_name = modal_inter.text_values.get("trigger_name", "").strip() or None

        # Validate trigger creation
        is_valid, error_msg = await self.validator.validate_trigger_creation(
            inter.author, target_user, inter.guild.id, regex_pattern
        )

        if not is_valid:
            embed = self.formatter.error_embed("Validation Failed", error_msg)
            await modal_inter.edit_original_response(embed=embed)
            logger.warning(
                f"Trigger validation failed: {inter.author} ({inter.author.id}) tried to add trigger for "
                f"{target_user} ({target_user.id}) - Error: {error_msg}"
            )
            return

        # Show confirmation with pattern preview
        pattern_preview = regex_pattern[:100] + "..." if len(regex_pattern) > 100 else regex_pattern

        embed = disnake.Embed(
            title="✅ Trigger Pattern Valid",
            description=f"Ready to create trigger for **{target_user.display_name}**",
            color=disnake.Color.green(),
        )

        embed.add_field(
            name="📝 Trigger Details",
            value=(
                f"**Name:** {trigger_name or '*Unnamed*'}\n"
                f"**Pattern:** `{pattern_preview}`\n"
                f"**Type:** {shock_type}\n"
                f"**Intensity:** {intensity}%\n"
                f"**Duration:** {duration}ms\n"
                f"**Cooldown:** {cooldown}s"
            ),
            inline=False,
        )

        embed.add_field(
            name="⚡ How It Works",
            value=(
                f"Whenever **{target_user.display_name}** sends a message matching this pattern, "
                f"they will receive a {shock_type.lower()} at {intensity}% for {duration}ms."
            ),
            inline=False,
        )

        embed.add_field(
            name="💡 Example Matches",
            value=(
                "Test your pattern carefully! The bot will react to any message containing these words/phrases.\n"
                "*Pattern is case-insensitive*"
            ),
            inline=False,
        )

        await modal_inter.edit_original_response(embed=embed)

        # Add trigger to database
        trigger_id = await self.db.add_trigger(
            discord_id=target_user.id,
            guild_id=inter.guild.id,
            regex_pattern=regex_pattern,
            trigger_name=trigger_name,
            shock_type=shock_type,
            intensity=intensity,
            duration=duration,
            cooldown_seconds=cooldown,
        )

        if trigger_id:
            await self.trigger_manager.reload_guild(inter.guild.id)

            logger.info(
                f"Trigger {trigger_id} added for {target_user} ({target_user.id}) "
                f"by {inter.author} ({inter.author.id}) in guild {inter.guild.id}"
            )

            embed = self.formatter.format_trigger_added(
                trigger_id,
                trigger_name,
                regex_pattern,
                shock_type,
                intensity,
                duration,
                cooldown,
                target_user == inter.author,
            )

            # Success is public for everyone to see
            await modal_inter.delete_original_response()
            await modal_inter.followup.send(embed=embed)
        else:
            logger.error(f"Failed to add trigger for user {target_user.id}")
            embed = self.formatter.error_embed(
                "Database Error", "Failed to add trigger. Please try again."
            )
            await inter.edit_original_response(embed=embed)

    @manage_group.sub_command(description="List your triggers")
    async def list(
        self,
        inter: disnake.ApplicationCommandInteraction,
    ):
        """List triggers for the invoking user (manage group)"""
        target_user = inter.author

        # No elevated permission required when listing your own triggers
        triggers = await self.db.get_triggers(target_user.id, inter.guild.id)

        embed = self.formatter.format_trigger_list(triggers, None)
        await inter.response.send_message(embed=embed, ephemeral=True)

    async def remove(
        self,
        inter: disnake.ApplicationCommandInteraction,
        trigger_id: int = commands.Param(description="The trigger ID to remove"),
        user: disnake.User = commands.Param(
            description="User whose trigger to remove (leave empty for yourself)", default=None
        ),
    ):
        """Remove a trigger"""

        target_user = self.bot.command_helper.resolve_target_user(user, inter.author)

        # Permission check
        if not await self.bot.command_helper.check_permission_with_logging(
            inter, inter.author, target_user, "remove trigger"
        ):
            return

        success = await self.db.remove_trigger(target_user.id, inter.guild.id, trigger_id)

        if success:
            await self.trigger_manager.reload_guild(inter.guild.id)

            logger.info(
                f"Trigger {trigger_id} removed for {target_user} ({target_user.id}) "
                f"by {inter.author} ({inter.author.id})"
            )
            embed = self.formatter.success_embed(
                "Trigger Removed", f"Successfully removed trigger #{trigger_id}"
            )
            # Success is public
            await inter.delete_original_response()
            await inter.followup.send(embed=embed)
        else:
            embed = self.formatter.error_embed(
                "Removal Failed",
                f"Trigger #{trigger_id} not found or you don't have permission to remove it.",
            )
            await inter.edit_original_response(embed=embed)

    @trigger.sub_command(description="Toggle a trigger on/off")
    @defer_response(ephemeral=True)
    async def toggle(
        self,
        inter: disnake.ApplicationCommandInteraction,
        trigger_id: int = commands.Param(description="The trigger ID to toggle"),
        enabled: bool = commands.Param(description="Enable or disable the trigger"),
        user: disnake.User = commands.Param(
            description="User whose trigger to toggle (leave empty for yourself)", default=None
        ),
    ):
        """Toggle a trigger on or off"""

        target_user = self.bot.command_helper.resolve_target_user(user, inter.author)

        # Permission check
        if not await self.bot.command_helper.check_permission_with_logging(
            inter, inter.author, target_user, "toggle trigger"
        ):
            return

        success = await self.db.toggle_trigger(target_user.id, inter.guild.id, trigger_id, enabled)

        if success:
            await self.trigger_manager.reload_guild(inter.guild.id)

            status = "enabled" if enabled else "disabled"
            status_emoji = "✅" if enabled else "❌"
            logger.info(
                f"Trigger {trigger_id} {status} for {target_user} ({target_user.id}) "
                f"by {inter.author} ({inter.author.id})"
            )
            embed = self.formatter.success_embed(
                f"Trigger {status_emoji} {status.title()}",
                f"Successfully {status} trigger #{trigger_id}",
            )
            # Success is public
            await inter.delete_original_response()
            await inter.followup.send(embed=embed)
        else:
            embed = self.formatter.error_embed(
                "Toggle Failed",
                f"Trigger #{trigger_id} not found or you don't have permission to modify it.",
            )
            await inter.edit_original_response(embed=embed)

    @trigger.sub_command(description="List all triggers")
    @defer_response(ephemeral=False)
    async def list(
        self,
        inter: disnake.ApplicationCommandInteraction,
        user: disnake.User = commands.Param(
            description="User whose triggers to list (leave empty for yourself)", default=None
        ),
    ):
        """List all triggers for a user"""

        target_user = self.bot.command_helper.resolve_target_user(user, inter.author)

        if target_user != inter.author and not await self.bot.command_helper.check_permission_with_logging(
            inter, inter.author, target_user, "list triggers"
        ):
            return

        triggers = await self.db.get_triggers(target_user.id, inter.guild.id)

        target_name = None if target_user == inter.author else target_user.display_name
        embed = self.formatter.format_trigger_list(triggers, target_name)

        await inter.edit_original_response(embed=embed)


def setup(bot: commands.InteractionBot):
    """Setup function to add the cog to the bot"""
    bot.add_cog(TriggerCommands(bot))
    logger.info("TriggerCommands cog has been loaded")
