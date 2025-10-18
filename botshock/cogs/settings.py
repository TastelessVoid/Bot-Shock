"""
Settings commands cog for guild configuration
"""

import logging

import disnake
from disnake.ext import commands

from botshock.core.bot_protocol import SupportsBotAttrs

logger = logging.getLogger("BotShock.Settings")


class ConfirmationView(disnake.ui.View):
    """Confirmation dialog for destructive actions"""

    def __init__(self, timeout: int = 60):
        super().__init__(timeout=timeout)
        self.value = None

    @disnake.ui.button(label="Confirm", style=disnake.ButtonStyle.danger, emoji="⚠️")
    async def confirm(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        self.value = True
        self.stop()
        await interaction.response.defer()

    @disnake.ui.button(label="Cancel", style=disnake.ButtonStyle.secondary, emoji="❌")
    async def cancel(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        self.value = False
        self.stop()
        await interaction.response.defer()


class Settings(commands.Cog):
    """Commands for managing bot settings per guild"""

    def __init__(self, bot: SupportsBotAttrs):
        self.bot = bot
        self.db = bot.db
        self.permission_checker = bot.permission_checker
        self.formatter = bot.formatter

    @commands.slash_command(description="Manage bot settings")
    async def settings(self, inter: disnake.ApplicationCommandInteraction):
        """Base command for settings management"""
        pass

    @settings.sub_command(description="Set control roles for this server")
    async def set_control_roles(self, inter: disnake.ApplicationCommandInteraction):
        """Set which roles can manage other users' devices and triggers"""

        # Check if user has Manage Roles permission
        if not self.permission_checker.has_manage_roles_permission(inter.author):
            embed = self.formatter.error_embed(
                "Permission Denied",
                "You need the **Manage Roles** permission to configure bot settings.",
                field_1=("Required Permission", "Manage Roles or Administrator"),
            )
            await inter.response.send_message(embed=embed, ephemeral=True)
            logger.warning(
                f"Permission denied: {inter.author} ({inter.author.id}) tried to set control roles "
                f"without Manage Roles permission in {inter.guild.name}"
            )
            return

        # Create role select menu
        embed = self.formatter.info_embed(
            "⚠️ Control Roles Configuration",
            "This bot uses a consent-based controller system.\n\n"
            "Control roles are used for administrative purposes:\n"
            "• Sub users register with `/openshock setup`\n"
            "• They add their device with `/openshock add_shocker`\n"
            "• They choose who can control them with `/controllers add`",
            field_1=(
                "What control roles can do",
                "Members with these roles can:\n"
                "• View other users' settings (admin purposes)\n"
                "• Help troubleshoot configurations\n\n"
                "**They cannot shock users without explicit consent.**",
            ),
            field_2=(
                "Recommendation",
                "Leave this empty and let sub users manage their own controllers with `/controllers add`.",
            ),
        )

        await inter.response.send_message(
            embed=embed,
            components=[
                disnake.ui.RoleSelect(
                    placeholder="Select control roles (optional)...",
                    custom_id="control_role_select",
                    min_values=0,
                    max_values=25,
                )
            ],
            ephemeral=True,
        )

    @commands.Cog.listener("on_dropdown")
    async def on_role_select(self, inter: disnake.MessageInteraction):
        """Handle role selection from dropdown"""
        if inter.component.custom_id != "control_role_select":
            return

        # Check if user still has permission
        if not self.permission_checker.has_manage_roles_permission(inter.author):
            embed = self.formatter.error_embed(
                "Permission Denied", "You no longer have permission to configure settings."
            )
            await inter.response.send_message(embed=embed, ephemeral=True)
            return

        selected_role_ids = [int(role_id) for role_id in inter.values]

        selected_roles = [inter.guild.get_role(role_id) for role_id in selected_role_ids]
        selected_roles = [
            role for role in selected_roles if role is not None
        ]

        success = await self.db.set_guild_control_roles(
            guild_id=inter.guild.id, guild_name=inter.guild.name, role_ids=selected_role_ids
        )

        if success:
            if selected_role_ids:
                role_list = "\n".join([f"• {role.mention}" for role in selected_roles])
                embed = self.formatter.success_embed(
                    "Control Roles Updated",
                    "Users with these roles can now manage other users' devices and triggers:",
                    field_1=("Selected Roles", role_list),
                )
                logger.info(
                    f"Control roles updated in {inter.guild.name} ({inter.guild.id}) "
                    f"by {inter.author} ({inter.author.id}): {selected_role_ids}"
                )
            else:
                embed = self.formatter.success_embed(
                    "Control Roles Cleared",
                    "Control roles have been cleared. Only server administrators can manage others.",
                    field_1=(
                        "Note",
                        "You can set control roles again anytime using `/settings set_control_roles`",
                    ),
                )
                logger.info(
                    f"Control roles cleared in {inter.guild.name} ({inter.guild.id}) "
                    f"by {inter.author} ({inter.author.id})"
                )

            await inter.response.send_message(embed=embed, ephemeral=True)
        else:
            embed = self.formatter.error_embed(
                "Update Failed", "Failed to update control roles. Please try again."
            )
            await inter.response.send_message(embed=embed, ephemeral=True)

    @settings.sub_command(description="View current bot settings for this server")
    async def view(self, inter: disnake.ApplicationCommandInteraction):
        """View current bot settings"""
        await inter.response.defer(ephemeral=True)

        guild_settings = await self.db.get_guild_settings(inter.guild.id)

        embed = disnake.Embed(
            title="⚙️ Server Settings",
            description=f"Current bot configuration for **{inter.guild.name}**",
            color=self.formatter.COLOR_INFO,
            timestamp=disnake.utils.utcnow(),
        )

        # Control roles
        if guild_settings and guild_settings.get("control_role_ids"):
            role_ids = guild_settings["control_role_ids"]
            roles = [inter.guild.get_role(role_id) for role_id in role_ids]
            roles = [role for role in roles if role is not None]

            if roles:
                role_list = "\n".join([f"• {role.mention}" for role in roles])
                embed.add_field(name="🛡️ Control Roles", value=role_list, inline=False)
            else:
                embed.add_field(
                    name="🛡️ Control Roles",
                    value="*No control roles set (Administrators only)*",
                    inline=False,
                )
        else:
            embed.add_field(
                name="🛡️ Control Roles",
                value="*No control roles set (Administrators only)*",
                inline=False,
            )

        # User statistics
        user_count = len(await self.db.get_guild_users(inter.guild.id))
        embed.add_field(name="👥 Registered Users", value=f"{user_count} user(s)", inline=True)

        # Trigger count
        all_triggers = await self.db.get_all_enabled_triggers_for_guild(inter.guild.id)
        total_triggers = sum(len(triggers) for triggers in all_triggers.values())
        embed.add_field(
            name="⚡ Active Triggers", value=f"{total_triggers} trigger(s)", inline=True
        )

        # Reminder count
        reminders = await self.db.get_reminders_for_guild(inter.guild.id, include_completed=False)
        embed.add_field(
            name="⏰ Pending Reminders", value=f"{len(reminders)} reminder(s)", inline=True
        )

        embed.add_field(
            name="💡 Available Commands",
            value="• `/settings reset` - Reset all server settings\n"
            "• `/settings clear_all_data` - Remove all data for this server\n"
            "• `/settings export` - Export server configuration",
            inline=False,
        )

        embed.set_footer(text=f"Guild ID: {inter.guild.id}")

        await inter.edit_original_response(embed=embed)

    @settings.sub_command(description="Reset all bot settings for this server")
    async def reset(self, inter: disnake.ApplicationCommandInteraction):
        """Reset bot settings to defaults (keeps user data)"""

        if not inter.author.guild_permissions.administrator:
            embed = self.formatter.error_embed(
                "Permission Denied",
                "You need **Administrator** permission to reset server settings.",
                field_1=("Required Permission", "Administrator"),
            )
            await inter.response.send_message(embed=embed, ephemeral=True)
            return

        embed = self.formatter.warning_embed(
            "⚠️ Confirm Settings Reset",
            "This will reset the following settings to defaults:\n\n"
            "• Control roles will be cleared\n"
            "• Server configuration will be reset\n\n"
            "**User data (API tokens, shockers, triggers, reminders) will NOT be affected.**\n\n"
            "Are you sure you want to continue?",
            field_1=("Note", "This action can be reversed by reconfiguring settings."),
        )

        view = ConfirmationView(timeout=60)
        await inter.response.send_message(embed=embed, view=view, ephemeral=True)

        # Wait for confirmation
        await view.wait()

        if view.value is None:
            embed = self.formatter.warning_embed(
                "Timeout", "Settings reset cancelled due to timeout."
            )
            await inter.edit_original_response(embed=embed, view=None)
            return

        if not view.value:
            embed = self.formatter.info_embed(
                "Cancelled", "Settings reset cancelled. No changes were made."
            )
            await inter.edit_original_response(embed=embed, view=None)
            return

        success = await self.db.set_guild_control_roles(
            guild_id=inter.guild.id, guild_name=inter.guild.name, role_ids=[]
        )

        if success:
            embed = self.formatter.success_embed(
                "Settings Reset",
                "All bot settings have been reset to defaults.",
                field_1=("What was reset", "• Control roles cleared\n• Server configuration reset"),
                field_2=("Preserved", "• User registrations\n• Shockers\n• Triggers\n• Reminders"),
            )
            logger.info(
                f"Settings reset for guild {inter.guild.name} ({inter.guild.id}) "
                f"by {inter.author} ({inter.author.id})"
            )
        else:
            embed = self.formatter.error_embed(
                "Reset Failed", "Failed to reset settings. Please try again."
            )

        await inter.edit_original_response(embed=embed, view=None)

    @settings.sub_command(description="Clear ALL bot data for this server (DESTRUCTIVE)")
    async def clear_all_data(self, inter: disnake.ApplicationCommandInteraction):
        """Clear all bot data including users, triggers, reminders (DESTRUCTIVE)"""

        if not inter.author.guild_permissions.administrator:
            embed = self.formatter.error_embed(
                "Permission Denied",
                "You need **Administrator** permission to clear all data.",
                field_1=("Required Permission", "Administrator"),
            )
            await inter.response.send_message(embed=embed, ephemeral=True)
            return

        # Get counts for confirmation message
        user_count = len(await self.db.get_guild_users(inter.guild.id))
        all_triggers = await self.db.get_all_enabled_triggers_for_guild(inter.guild.id)
        trigger_count = sum(len(triggers) for triggers in all_triggers.values())
        reminder_count = len(
            await self.db.get_reminders_for_guild(inter.guild.id, include_completed=False)
        )

        # Show confirmation dialog with data counts
        embed = self.formatter.error_embed(
            "🚨 DESTRUCTIVE ACTION - Confirm Data Deletion",
            "**This will permanently delete ALL bot data for this server!**\n\n"
            f"The following will be deleted:\n"
            f"• **{user_count} user registration(s)** (with API tokens)\n"
            f"• **All shockers** for these users\n"
            f"• **{trigger_count} trigger(s)**\n"
            f"• **{reminder_count} reminder(s)**\n"
            f"• **All server settings**\n\n"
            "⚠️ **THIS CANNOT BE UNDONE!** ⚠️\n\n"
            "Users will need to re-register with `/openshock setup` after this.",
            field_1=(
                "Think carefully!",
                "This removes all configuration and user data. Only proceed if you're absolutely sure.",
            ),
        )

        view = ConfirmationView(timeout=60)
        await inter.response.send_message(embed=embed, view=view, ephemeral=True)

        # Wait for confirmation
        await view.wait()

        if view.value is None:
            # Timeout
            embed = self.formatter.warning_embed(
                "Timeout", "Data deletion cancelled due to timeout. No changes were made."
            )
            await inter.edit_original_response(embed=embed, view=None)
            return

        if not view.value:
            # User cancelled
            embed = self.formatter.info_embed(
                "Cancelled", "Data deletion cancelled. No changes were made."
            )
            await inter.edit_original_response(embed=embed, view=None)
            return

        # User confirmed - delete all data
        try:
            # Get all users for this guild
            users = await self.db.get_guild_users(inter.guild.id)
            deleted_users = 0

            for user in users:
                # Remove user (this cascades to shockers and triggers due to foreign keys)
                if await self.db.remove_user(user["discord_id"], inter.guild.id):
                    deleted_users += 1

            # Delete all reminders for this guild
            reminders = await self.db.get_reminders_for_guild(
                inter.guild.id, include_completed=True
            )
            deleted_reminders = 0
            for reminder in reminders:
                if await self.db.delete_reminder(reminder["id"], inter.guild.id):
                    deleted_reminders += 1

            # Reset guild settings
            await self.db.set_guild_control_roles(
                guild_id=inter.guild.id, guild_name=inter.guild.name, role_ids=[]
            )

            # Reload trigger manager for this guild
            await self.bot.trigger_manager.reload_guild(inter.guild.id)

            embed = self.formatter.success_embed(
                "All Data Cleared",
                f"Successfully deleted all bot data for **{inter.guild.name}**.",
                field_1=(
                    "Deleted",
                    f"• {deleted_users} user(s)\n"
                    f"• All associated shockers\n"
                    f"• {trigger_count} trigger(s)\n"
                    f"• {deleted_reminders} reminder(s)\n"
                    f"• All server settings",
                ),
                field_2=(
                    "Next Steps",
                    "Users can now re-register using `/openshock setup`\n"
                    "Reconfigure settings using `/settings set_control_roles`",
                ),
            )

            logger.warning(
                f"ALL DATA CLEARED for guild {inter.guild.name} ({inter.guild.id}) "
                f"by {inter.author} ({inter.author.id}) - "
                f"Deleted: {deleted_users} users, {trigger_count} triggers, {deleted_reminders} reminders"
            )
        except Exception as e:
            logger.error(f"Error clearing data for guild {inter.guild.id}: {e}", exc_info=True)
            embed = self.formatter.error_embed(
                "Deletion Failed",
                "An error occurred while clearing data. Some data may have been partially deleted.",
                field_1=("Error", str(e)),
            )

        await inter.edit_original_response(embed=embed, view=None)

    @settings.sub_command(description="Export server configuration as text")
    async def export(self, inter: disnake.ApplicationCommandInteraction):
        """Export current server configuration"""

        # Check if user has manage server permission
        if not (
            inter.author.guild_permissions.administrator
            or inter.author.guild_permissions.manage_guild
        ):
            embed = self.formatter.error_embed(
                "Permission Denied",
                "You need **Manage Server** or **Administrator** permission to export settings.",
            )
            await inter.response.send_message(embed=embed, ephemeral=True)
            return

        await inter.response.defer(ephemeral=True)

        # Gather all data
        guild_settings = await self.db.get_guild_settings(inter.guild.id)
        users = await self.db.get_guild_users(inter.guild.id)
        all_triggers = await self.db.get_all_enabled_triggers_for_guild(inter.guild.id)
        reminders = await self.db.get_reminders_for_guild(inter.guild.id, include_completed=False)

        # Build export text
        export_lines = [
            "BotShock Configuration Export",
            f"Server: {inter.guild.name}",
            f"Server ID: {inter.guild.id}",
            f"Exported by: {inter.author} ({inter.author.id})",
            f"Export Date: {disnake.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
            "=" * 60,
            "",
            "CONTROL ROLES:",
        ]

        if guild_settings and guild_settings.get("control_role_ids"):
            for role_id in guild_settings["control_role_ids"]:
                role = inter.guild.get_role(role_id)
                if role:
                    export_lines.append(f"  - {role.name} (ID: {role_id})")
        else:
            export_lines.append("  None configured (Administrators only)")

        export_lines.extend(
            [
                "",
                f"REGISTERED USERS: {len(users)}",
            ]
        )

        for user in users:
            member = inter.guild.get_member(user["discord_id"])
            username = member.display_name if member else user["discord_username"]
            shockers = await self.db.get_shockers(user["discord_id"], inter.guild.id)
            triggers = await self.db.get_triggers(user["discord_id"], inter.guild.id)
            export_lines.extend(
                [
                    f"  • {username} (ID: {user['discord_id']})",
                    f"    - Shockers: {len(shockers)}",
                    f"    - Triggers: {len(triggers)}",
                ]
            )

        total_triggers = sum(len(triggers) for triggers in all_triggers.values())
        export_lines.extend(
            [
                "",
                f"ACTIVE TRIGGERS: {total_triggers}",
            ]
        )

        for discord_id, triggers in all_triggers.items():
            member = inter.guild.get_member(discord_id)
            username = member.display_name if member else f"User {discord_id}"
            export_lines.append(f"  {username}:")
            for trigger in triggers:
                name = trigger["trigger_name"] or "Unnamed"
                export_lines.append(
                    f"    - [{trigger['id']}] {name}: {trigger['regex_pattern']} "
                    f"({trigger['shock_type']}, {trigger['intensity']}%, {trigger['duration']}ms)"
                )

        export_lines.extend(
            [
                "",
                f"PENDING REMINDERS: {len(reminders)}",
            ]
        )

        for reminder in reminders[:20]:  # Limit to 20 to avoid huge exports
            target = inter.guild.get_member(reminder["target_discord_id"])
            target_name = target.display_name if target else f"User {reminder['target_discord_id']}"
            scheduled = reminder["scheduled_time"]
            export_lines.append(
                f"  - [{reminder['id']}] {target_name} at {scheduled} "
                f"({reminder['shock_type']}, {reminder['intensity']}%)"
            )

        if len(reminders) > 20:
            export_lines.append(f"  ... and {len(reminders) - 20} more")

        export_lines.extend(
            [
                "",
                "=" * 60,
                "End of export",
            ]
        )

        export_text = "\n".join(export_lines)

        # Create embed
        embed = self.formatter.success_embed(
            "Configuration Exported",
            "Server configuration has been exported.",
            field_1=(
                "Summary",
                f"• {len(users)} registered user(s)\n"
                f"• {total_triggers} active trigger(s)\n"
                f"• {len(reminders)} pending reminder(s)",
            ),
        )

        # Send as file if text is too long
        if len(export_text) > 1900:
            import io

            file = disnake.File(
                io.BytesIO(export_text.encode("utf-8")),
                filename=f"botshock_config_{inter.guild.id}_{disnake.utils.utcnow().strftime('%Y%m%d_%H%M%S')}.txt",
            )
            await inter.edit_original_response(embed=embed, file=file)
        else:
            await inter.edit_original_response(embed=embed, content=f"```\n{export_text}\n```")

        logger.info(
            f"Configuration exported for guild {inter.guild.name} ({inter.guild.id}) "
            f"by {inter.author} ({inter.author.id})"
        )


def setup(bot: commands.InteractionBot):
    """Setup function to add the cog to the bot"""
    bot.add_cog(Settings(bot))
    logger.info("Settings cog has been loaded")
