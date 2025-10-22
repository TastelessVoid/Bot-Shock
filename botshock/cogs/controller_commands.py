"""
Controller management commands cog - Consent-based access control
"""

import logging

import disnake
from disnake.ext import commands

from botshock.core.bot_protocol import SupportsBotAttrs
from botshock.utils.decorators import defer_response, require_registration
from botshock.utils.views import AuthorOnlyView

logger = logging.getLogger("BotShock.ControllerCommands")


class ControllerCommands(commands.Cog):
    """Commands for managing who can control your device (Sub users)"""

    def __init__(self, bot: SupportsBotAttrs):
        self.bot = bot
        self.db = bot.db
        self.formatter = bot.formatter
        self.helper = bot.command_helper

    @commands.slash_command(description="Manage who can control your OpenShock device")
    async def controllers(self, inter: disnake.ApplicationCommandInteraction):
        """Base command for controller management"""
        pass

    @controllers.sub_command_group(name="manage", description="Add, remove, or view controllers")
    async def manage_controllers(self, inter: disnake.ApplicationCommandInteraction):
        """Manage your device controllers"""
        pass

    @manage_controllers.sub_command(description="Add a user or role that can control your device")
    @defer_response(ephemeral=True)
    @require_registration(attr_name="db")
    async def add(self, inter: disnake.ApplicationCommandInteraction):
        """Add a controller (user or role) who can control your device"""
        embed = disnake.Embed(
            title="🎮 Add Controllers",
            description="Select users and/or roles you want to grant control permissions to.",
            color=disnake.Color.blue(),
        )

        embed.add_field(
            name="📝 How to use",
            value=(
                "• Select up to 25 users from the first dropdown (optional)\n"
                "• Select up to 25 roles from the second dropdown (optional)\n"
                "• Click **Continue** when ready to review your selections\n"
                "• You can select users only, roles only, or both!"
            ),
            inline=False,
        )

        embed.add_field(
            name="⚠️ Important",
            value="Only authorize people you completely trust. You'll see a confirmation screen before finalizing.",
            inline=False,
        )

        view = StreamlinedControllerSelectView(self.bot, self.db, self.formatter, inter.author)
        await inter.edit_original_response(embed=embed, view=view)

    @manage_controllers.sub_command(description="Remove a user or role from controlling your device")
    @defer_response(ephemeral=True)
    @require_registration(attr_name="db")
    async def remove(
        self,
        inter: disnake.ApplicationCommandInteraction,
        user: disnake.User = commands.Param(
            description="User to remove (leave empty to remove a role)", default=None
        ),
        role: disnake.Role = commands.Param(
            description="Role to remove (leave empty to remove a user)", default=None
        ),
    ):
        """Remove a controller's permission to control your device"""

        if (user is None) == (role is None):
            embed = self.formatter.error_embed(
                "Invalid Input",
                "Please provide either a **user** OR a **role**, not both or neither.",
            )
            await inter.edit_original_response(embed=embed)
            return

        if user:
            success = await self.db.remove_controller_permission(
                sub_discord_id=inter.author.id,
                guild_id=inter.guild.id,
                controller_discord_id=user.id,
            )
            controller_name = user.mention
        else:
            success = await self.db.remove_controller_permission(
                sub_discord_id=inter.author.id, guild_id=inter.guild.id, controller_role_id=role.id
            )
            controller_name = role.mention

        if success:
            logger.info(
                f"Controller removed: {inter.author} ({inter.author.id}) revoked control from "
                f"{controller_name} in guild {inter.guild.id}"
            )
            embed = self.formatter.success_embed(
                "✅ Controller Removed",
                f"You've revoked control permission from {controller_name}.",
                field_1=(
                    "Effect",
                    f"{controller_name} can no longer control your device or schedule actions for you.",
                ),
            )
            await inter.edit_original_response(embed=embed)
        else:
            embed = self.formatter.error_embed(
                "Failed to Remove Controller", f"{controller_name} was not in your controller list."
            )
            await inter.edit_original_response(embed=embed)

    @manage_controllers.sub_command(description="List all users and roles that can control your device")
    @defer_response(ephemeral=True)
    @require_registration(attr_name="db")
    async def list(self, inter: disnake.ApplicationCommandInteraction):
        """List all controllers who have permission to control your device"""
        permissions = await self.db.get_controller_permissions(inter.author.id, inter.guild.id)

        embed = disnake.Embed(
            title="🎮 Your Device Controllers",
            description="These users and roles have permission to control your device:",
            color=disnake.Color.blue(),
        )

        if permissions["users"]:
            user_list = []
            for user_id in permissions["users"]:
                user = await self.bot.fetch_user(user_id)
                user_list.append(f"• {user.mention} (`{user.name}`)")
            embed.add_field(
                name=f"👥 Authorized Users ({len(permissions['users'])})",
                value="\n".join(user_list),
                inline=False,
            )
        else:
            embed.add_field(
                name="👥 Authorized Users", value="*No individual users authorized*", inline=False
            )

        if permissions["roles"]:
            role_list = []
            for role_id in permissions["roles"]:
                role = inter.guild.get_role(role_id)
                if role:
                    role_list.append(f"• {role.mention} (`{role.name}`)")
                else:
                    role_list.append(f"• *Unknown role* (`ID: {role_id}`)")
            embed.add_field(
                name=f"🎭 Authorized Roles ({len(permissions['roles'])})",
                value="\n".join(role_list),
                inline=False,
            )
        else:
            embed.add_field(name="🎭 Authorized Roles", value="*No roles authorized*", inline=False)

        # Add footer with total count
        total = len(permissions["users"]) + len(permissions["roles"])
        embed.set_footer(
            text=f"Total: {total} controller(s) • You can manage these with /controllers add or /controllers remove"
        )

        if total == 0:
            embed.description = (
                "You haven't authorized anyone to control your device yet.\n\n"
                "**To get started:**\n"
                "• Use `/controllers add user:@someone` to allow a specific user\n"
                "• Use `/controllers add role:@RoleName` to allow everyone with a role\n\n"
                "**Remember:** Only people you explicitly authorize can control your device!"
            )
            embed = disnake.Embed(
                title=embed.title, description=embed.description, color=disnake.Color.orange()
            )

        await inter.edit_original_response(embed=embed)

    @manage_controllers.sub_command(description="Remove ALL controller permissions (revoke all access)")
    @defer_response(ephemeral=True)
    @require_registration(attr_name="db")
    async def clear(self, inter: disnake.ApplicationCommandInteraction):
        """Clear all controller permissions - revoke all access to your device"""
        permissions = await self.db.get_controller_permissions(inter.author.id, inter.guild.id)
        total = len(permissions["users"]) + len(permissions["roles"])

        if total == 0:
            embed = self.formatter.info_embed(
                "No Controllers",
                "You don't have any controllers to clear. Your device already has no authorized controllers.",
            )
            await inter.edit_original_response(embed=embed)
            return

        view = ConfirmClearView()
        embed = disnake.Embed(
            title="⚠️ Confirm Clear All Controllers",
            description=f"You are about to remove **{total} controller(s)** from your device.",
            color=disnake.Color.orange(),
        )
        embed.add_field(
            name="This will revoke access for:",
            value=f"• {len(permissions['users'])} user(s)\n• {len(permissions['roles'])} role(s)",
            inline=False,
        )
        embed.add_field(
            name="⚠️ Warning",
            value="After this, no one will be able to control your device until you add new controllers.",
            inline=False,
        )

        await inter.edit_original_response(embed=embed, view=view)

        try:
            original_msg = await inter.original_message()
            original_msg_id = original_msg.id
        except Exception:
            original_msg_id = None

        def check_button(i):
            return i.author.id == inter.author.id and (
                original_msg_id is None
                or (hasattr(i, "message") and i.message and i.message.id == original_msg_id)
            )

        try:
            button_inter = await self.bot.wait_for("button_click", check=check_button, timeout=30)
            await button_inter.response.defer()

            if button_inter.component.custom_id == "confirm_clear":
                success = await self.db.clear_all_controller_permissions(
                    inter.author.id, inter.guild.id
                )

                if success:
                    logger.info(
                        f"All controllers cleared: {inter.author} ({inter.author.id}) "
                        f"removed all {total} controller(s) in guild {inter.guild.id}"
                    )
                    embed = self.formatter.success_embed(
                        "✅ All Controllers Removed",
                        f"Successfully removed all {total} controller(s) from your device.",
                        field_1=(
                            "Next Steps",
                            "Use `/controllers add` when you're ready to authorize new controllers.",
                        ),
                    )
                else:
                    embed = self.formatter.error_embed(
                        "Failed to Clear Controllers",
                        "There was an error clearing your controllers. Please try again.",
                    )
            else:  # cancel
                embed = self.formatter.info_embed(
                    "Cancelled", "No changes were made to your controllers."
                )

            await inter.edit_original_response(embed=embed, view=None)

        except Exception:
            embed = self.formatter.warning_embed(
                "Timed Out", "Controller clear cancelled - no changes were made."
            )
            await inter.edit_original_response(embed=embed, view=None)

    @controllers.sub_command_group(name="settings", description="Configure cooldowns and other settings")
    async def settings_group(self, inter: disnake.ApplicationCommandInteraction):
        """Manage controller and device settings"""
        pass

    @settings_group.sub_command(description="Set cooldown duration for controllers")
    @defer_response(ephemeral=True)
    @require_registration(attr_name="db")
    async def cooldown(
        self,
        inter: disnake.ApplicationCommandInteraction,
        minutes: int = commands.Param(
            description="Cooldown duration in minutes (1-60)", ge=1, le=60, default=5
        ),
    ):
        """Set how long controllers must wait between actions"""

        cooldown_seconds = minutes * 60

        success = await self.db.set_controller_cooldown_duration(
            inter.author.id, inter.guild.id, cooldown_seconds
        )

        if success:
            logger.info(
                f"Controller cooldown set: {inter.author} ({inter.author.id}) set cooldown to "
                f"{minutes} minute(s) in guild {inter.guild.id}"
            )
            embed = self.formatter.success_embed(
                "✅ Controller Cooldown Updated",
                f"Controllers must now wait **{minutes} minute(s)** between actions on your device.",
                field_1=(
                    "What This Means",
                    f"• After a controller sends a command, they must wait {minutes} minute(s) before sending another\n"
                    f"• This prevents excessive use and ensures responsible control\n"
                    f"• You can change this anytime with `/controllers cooldown`\n"
                    f"• This doesn't affect you controlling your own device",
                ),
            )
            await inter.edit_original_response(embed=embed)
        else:
            embed = self.formatter.error_embed(
                "Failed to Update Cooldown",
                "There was an error updating the controller cooldown. Please try again.",
            )
            await inter.edit_original_response(embed=embed)

    @settings_group.sub_command(description="Set device-wide cooldown (owner only)")
    @defer_response(ephemeral=True)
    @require_registration(attr_name="db")
    async def device_cooldown(
        self,
        inter: disnake.ApplicationCommandInteraction,
        minutes: int = commands.Param(
            description="Device cooldown duration in minutes (1-60)", ge=1, le=60, default=5
        ),
    ):
        """Set global cooldown for all device access (owner/primary user only)"""
        is_owner = await self.db.is_device_owner(inter.author.id, inter.guild.id)

        if not is_owner:
            embed = self.formatter.error_embed(
                "Owner Only",
                "Only the device owner can set the device-wide cooldown.",
                field_1=(
                    "About This Setting",
                    "The device cooldown is a global limit that applies to all actions on the device, "
                    "including your own. This is different from the controller cooldown which only "
                    "limits controllers between their own actions."
                ),
            )
            await inter.edit_original_response(embed=embed)
            return

        cooldown_seconds = minutes * 60

        success = await self.db.set_device_cooldown_duration(
            inter.author.id, inter.guild.id, cooldown_seconds
        )

        if success:
            logger.info(
                f"Device cooldown set: {inter.author} ({inter.author.id}) set device cooldown to "
                f"{minutes} minute(s) in guild {inter.guild.id}"
            )
            embed = self.formatter.success_embed(
                "✅ Device Cooldown Updated",
                f"The device must now wait **{minutes} minute(s)** between any actions.",
                field_1=(
                    "What This Means",
                    f"• After any action (by you or controllers), the device waits {minutes} minute(s)\n"
                    f"• This applies globally to all device commands\n"
                    f"• Controllers still have their own individual cooldown\n"
                    f"• You can change this anytime with `/controllers device_cooldown`"
                ),
            )
            await inter.edit_original_response(embed=embed)
        else:
            embed = self.formatter.error_embed(
                "Failed to Update Device Cooldown",
                "There was an error updating the device cooldown. Please try again.",
            )
            await inter.edit_original_response(embed=embed)

    @controllers.sub_command_group(name="emergency", description="Emergency safety controls")
    async def emergency_group(self, inter: disnake.ApplicationCommandInteraction):
        """Emergency and safety controls"""
        pass

    @emergency_group.sub_command(
        description="🚨 EMERGENCY: Immediately halt ALL control and scheduled actions"
    )
    @defer_response(ephemeral=True)
    @require_registration(attr_name="db")
    async def safeword(self, inter: disnake.ApplicationCommandInteraction):
        """Emergency safeword - immediately stops all control, reminders, and triggers"""

        stopped_items = []
        error_items = []

        try:
            permissions = await self.db.get_controller_permissions(inter.author.id, inter.guild.id)
            total_controllers = len(permissions["users"]) + len(permissions["roles"])

            if total_controllers > 0:
                if await self.db.clear_all_controller_permissions(inter.author.id, inter.guild.id):
                    stopped_items.append(f"✅ Revoked {total_controllers} controller permission(s)")
                    logger.warning(
                        f"SAFEWORD: {inter.author} ({inter.author.id}) revoked {total_controllers} "
                        f"controller(s) in guild {inter.guild.id}"
                    )
                else:
                    error_items.append("⚠️ Failed to revoke controller permissions")
            else:
                stopped_items.append("ℹ️ No active controller permissions")

            reminders = await self.db.get_reminders_for_user(
                inter.guild.id, inter.author.id, include_completed=False
            )
            deleted_reminders = 0

            for reminder in reminders:
                if await self.db.delete_reminder(reminder["id"], inter.guild.id):
                    deleted_reminders += 1

            if deleted_reminders > 0:
                stopped_items.append(f"✅ Cancelled {deleted_reminders} pending reminder(s)")
                logger.warning(
                    f"SAFEWORD: {inter.author} ({inter.author.id}) cancelled {deleted_reminders} "
                    f"reminder(s) in guild {inter.guild.id}"
                )
            else:
                stopped_items.append("ℹ️ No pending reminders")

            triggers = await self.db.get_triggers(
                inter.author.id, inter.guild.id, enabled_only=True
            )
            disabled_triggers = 0

            for trigger in triggers:
                if await self.db.toggle_trigger(
                    inter.author.id, inter.guild.id, trigger["id"], False
                ):
                    disabled_triggers += 1

            if disabled_triggers > 0:
                stopped_items.append(f"✅ Disabled {disabled_triggers} active trigger(s)")
                logger.warning(
                    f"SAFEWORD: {inter.author} ({inter.author.id}) disabled {disabled_triggers} "
                    f"trigger(s) in guild {inter.guild.id}"
                )

                if hasattr(self.bot, "trigger_manager"):
                    await self.bot.trigger_manager.reload_guild(inter.guild.id)
            else:
                stopped_items.append("ℹ️ No active triggers")

            if error_items:
                embed_color = disnake.Color.orange()
                title = "⚠️ Safeword Activated (With Warnings)"
            else:
                embed_color = disnake.Color.red()
                title = "🚨 SAFEWORD ACTIVATED"

            embed = disnake.Embed(
                title=title,
                description=(
                    f"**Emergency stop executed for {inter.author.mention}**\n\n"
                    f"All control and scheduled actions have been immediately halted."
                ),
                color=embed_color,
                timestamp=disnake.utils.utcnow(),
            )

            stopped_text = "\n".join(stopped_items)
            embed.add_field(name="🛑 Actions Taken", value=stopped_text, inline=False)

            if error_items:
                error_text = "\n".join(error_items)
                embed.add_field(name="⚠️ Warnings", value=error_text, inline=False)

            embed.add_field(
                name="📋 Next Steps",
                value=(
                    "You are now completely safe. To resume:\n"
                    "• Use `/controllers add` to re-authorize controllers\n"
                    "• Use `/triggers toggle` to re-enable triggers\n"
                    "• Use `/reminder schedule` to create new reminders\n\n"
                    "**Take your time. Your safety comes first.**"
                ),
                inline=False,
            )

            embed.set_footer(text="Safeword logged • You can use this command anytime")

            await inter.edit_original_response(embed=embed)

            logger.critical(
                f"🚨 SAFEWORD ACTIVATED 🚨 User: {inter.author} ({inter.author.id}) | "
                f"Guild: {inter.guild.name} ({inter.guild.id}) | "
                f"Controllers: {total_controllers} | Reminders: {deleted_reminders} | "
                f"Triggers: {disabled_triggers}"
            )

        except Exception as e:
            logger.error(f"Error executing safeword for user {inter.author.id}: {e}", exc_info=True)
            embed = self.formatter.error_embed(
                "🚨 Safeword Error",
                "An error occurred while executing the safeword. Some actions may have been partially completed.",
                field_1=(
                    "What to do",
                    "• Try running `/controllers clear` to revoke permissions\n"
                    "• Contact a server administrator for assistance\n"
                    "• Your safety is the priority",
                ),
            )
            await inter.edit_original_response(embed=embed)


class ConfirmClearView(disnake.ui.View):
    """Confirmation view for clearing all controllers"""

    def __init__(self, timeout: int = 30):
        super().__init__(timeout=timeout)

    @disnake.ui.button(
        label="Yes, Remove All",
        style=disnake.ButtonStyle.danger,
        emoji="⚠️",
        custom_id="confirm_clear",
    )
    async def confirm_button(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        """Confirm button callback - handled by parent"""
        pass

    @disnake.ui.button(
        label="Cancel", style=disnake.ButtonStyle.secondary, emoji="❌", custom_id="cancel_clear"
    )
    async def cancel_button(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        """Cancel button callback - handled by parent"""
        pass


class StreamlinedControllerSelectView(AuthorOnlyView):
    """Streamlined view for selecting both users and roles"""

    def __init__(self, bot, db, formatter, author):
        super().__init__(author.id, timeout=120)  # Longer timeout for complex selection
        self.bot = bot
        self.db = db
        self.formatter = formatter
        self.author = author
        self.selected_users = []
        self.selected_roles = []

    @disnake.ui.user_select(
        placeholder="Select users (optional)...", min_values=0, max_values=25, row=0
    )
    async def user_select_callback(
        self, select: disnake.ui.UserSelect, inter: disnake.MessageInteraction
    ):
        """Handle user selection"""
        await inter.response.defer()
        self.selected_users = [u for u in select.values if u.id != self.author.id]
        await self._update_selection_display(inter)

    @disnake.ui.role_select(
        placeholder="Select roles (optional)...", min_values=0, max_values=25, row=1
    )
    async def role_select_callback(
        self, select: disnake.ui.RoleSelect, inter: disnake.MessageInteraction
    ):
        """Handle role selection"""
        await inter.response.defer()
        self.selected_roles = select.values
        await self._update_selection_display(inter)

    @disnake.ui.button(label="Continue", style=disnake.ButtonStyle.success, row=2)
    async def continue_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        """Handle continue button"""
        await inter.response.defer()

        if not self.selected_users and not self.selected_roles:
            embed = self.formatter.error_embed(
                "No Selection", "Please select at least one user or role before continuing."
            )
            await inter.edit_original_message(embed=embed, view=None)
            return

        await self._show_confirmation(inter)

    @disnake.ui.button(label="Cancel", style=disnake.ButtonStyle.secondary, row=2)
    async def cancel_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        """Handle cancel button"""
        embed = self.formatter.info_embed(
            "Cancelled", "No controllers were added. Your device remains secure."
        )
        await inter.response.edit_message(embed=embed, view=None)

    async def _update_selection_display(self, inter):
        """Update the embed to show current selections"""
        embed = disnake.Embed(
            title="👥 Select Users & Roles to Authorize",
            description="Choose users and/or roles you want to grant control permissions to.",
            color=disnake.Color.blue(),
        )

        if self.selected_users:
            user_list = ", ".join([u.mention for u in self.selected_users])
            embed.add_field(
                name=f"✅ Selected Users ({len(self.selected_users)})",
                value=user_list,
                inline=False,
            )
        else:
            embed.add_field(name="👤 Selected Users", value="*None selected*", inline=False)

        if self.selected_roles:
            role_list = ", ".join([r.mention for r in self.selected_roles])
            embed.add_field(
                name=f"✅ Selected Roles ({len(self.selected_roles)})",
                value=role_list,
                inline=False,
            )
        else:
            embed.add_field(name="🎭 Selected Roles", value="*None selected*", inline=False)

        embed.add_field(
            name="📝 Next Step",
            value="Click 'Continue' when you're ready to review and confirm your selections.",
            inline=False,
        )

        await inter.edit_original_message(embed=embed, view=self)

    async def _show_confirmation(self, inter):
        """Show the confirmation screen for adding controllers"""
        total_count = len(self.selected_users) + len(self.selected_roles)

        description_parts = ["You are about to grant control permission to:\n"]

        if self.selected_users:
            user_mentions = ", ".join([u.mention for u in self.selected_users])
            description_parts.append(f"**{len(self.selected_users)} User(s):** {user_mentions}")

        if self.selected_roles:
            role_mentions = ", ".join([r.mention for r in self.selected_roles])
            description_parts.append(f"**{len(self.selected_roles)} Role(s):** {role_mentions}")

        description_parts.append("\n**Please read carefully before proceeding:**")

        embed = disnake.Embed(
            title="⚠️ Important: Controller Authorization",
            description="\n".join(description_parts),
            color=disnake.Color.orange(),
            timestamp=disnake.utils.utcnow(),
        )

        embed.add_field(
            name="🎮 What They Can Do",
            value=(
                "If you authorize these controllers, they will be able to:\n"
                "• Send shock/vibrate/sound commands to your device\n"
                "• Schedule future reminders to shock you\n"
                "• Set the intensity and duration of shocks\n"
                "• Control you at any time they choose"
            ),
            inline=False,
        )

        embed.add_field(
            name="🛡️ Your Safety & Trust",
            value=(
                "**Only authorize people you completely trust.**\n\n"
                "Consider:\n"
                f"• Do you trust all {total_count} controllers with physical control over you?\n"
                f"• Have you discussed boundaries and limits with each of them?\n"
                f"• Do they respect safewords and consent?\n"
                f"• Are you comfortable with them having this power?"
            ),
            inline=False,
        )

        embed.add_field(
            name="✅ Your Rights",
            value=(
                "• You can revoke access anytime with `/controllers remove`\n"
                "• Use `/controllers safeword` for immediate emergency stop\n"
                "• All actions are logged for your safety\n"
                "• You maintain full control over your consent"
            ),
            inline=False,
        )

        embed.set_footer(
            text=f"Click 'Authorize All' only if you trust all {total_count} controllers completely"
        )

        view = ConfirmMultipleControllersView(
            bot=self.bot,
            db=self.db,
            formatter=self.formatter,
            author=self.author,
            controller_objs=self.selected_users + self.selected_roles,
            controller_type="mixed",
        )
        await inter.edit_original_message(embed=embed, view=view)


class ConfirmMultipleControllersView(disnake.ui.View):
    """Confirmation view for adding multiple controllers"""

    def __init__(self, bot, db, formatter, author, controller_objs, controller_type):
        super().__init__(timeout=60)
        self.bot = bot
        self.db = db
        self.formatter = formatter
        self.author = author
        self.controller_objs = controller_objs
        self.controller_type = controller_type

    async def interaction_check(self, interaction: disnake.MessageInteraction):
        """Ensure that only the original author can use these buttons"""
        if interaction.author.id != self.author.id:
            await interaction.response.send_message("You cannot use this button.", ephemeral=True)
            return False
        return True

    @disnake.ui.button(label="Authorize All", style=disnake.ButtonStyle.success)
    async def confirm_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        """Handle authorization confirmation"""
        await inter.response.defer()

        added_count = 0
        failed_count = 0
        added_names = []
        dm_failed = []

        for controller_obj in self.controller_objs:
            if isinstance(controller_obj, (disnake.User, disnake.Member)):
                success = await self.db.add_controller_permission(
                    sub_discord_id=self.author.id,
                    guild_id=inter.guild.id,
                    controller_discord_id=controller_obj.id,
                )
                obj_type = "user"

                if success:
                    try:
                        dm_embed = disnake.Embed(
                            title="🎮 You've Been Added as a Controller",
                            description=f"{self.author.mention} has granted you control permission in **{inter.guild.name}**!",
                            color=disnake.Color.green(),
                            timestamp=disnake.utils.utcnow(),
                        )
                        dm_embed.add_field(
                            name="What This Means",
                            value=(
                                f"• You can now use `/shock` commands on {self.author.mention}'s device\n"
                                f"• You can schedule reminders for them\n"
                                f"• Please respect their boundaries and consent\n"
                                f"• They can revoke your access at any time"
                            ),
                            inline=False,
                        )
                        dm_embed.add_field(
                            name="⚠️ Important Reminder",
                            value=(
                                "**This is a serious responsibility.**\n"
                                "• Always respect safewords and limits\n"
                                "• Only use commands they've consented to\n"
                                "• Communication and trust are essential"
                            ),
                            inline=False,
                        )
                        dm_embed.set_footer(text=f"Server: {inter.guild.name}")

                        await controller_obj.send(embed=dm_embed)
                        logger.info(
                            f"DM notification sent to controller {controller_obj} ({controller_obj.id}) "
                            f"for authorization by {self.author} ({self.author.id})"
                        )
                    except (disnake.Forbidden, disnake.HTTPException) as e:
                        dm_failed.append(controller_obj.mention)
                        logger.warning(
                            f"Failed to send DM to controller {controller_obj} ({controller_obj.id}): {e}"
                        )
            else:
                success = await self.db.add_controller_permission(
                    sub_discord_id=self.author.id,
                    guild_id=inter.guild.id,
                    controller_role_id=controller_obj.id,
                )
                obj_type = "role"

            if success:
                added_count += 1
                added_names.append(controller_obj.mention)
                logger.info(
                    f"Controller added: {self.author} ({self.author.id}) granted control to "
                    f"{obj_type} {controller_obj.mention} in guild {inter.guild.id}"
                )
            else:
                failed_count += 1

        if added_count > 0:
            embed = self.formatter.success_embed(
                f"✅ Controllers Added ({added_count})",
                f"You've granted control permission to {added_count} controller(s)!",
                field_1=(
                    "Added Controllers",
                    (
                        ", ".join(added_names)
                        if len(added_names) <= 10
                        else f"{', '.join(added_names[:10])}, and {len(added_names) - 10} more..."
                    ),
                ),
                field_2=(
                    "What this means",
                    "• These controllers can now use `/shock` on your device\n"
                    "• They can schedule reminders for you\n"
                    "• You can revoke permissions anytime with `/controllers remove`\n"
                    "• Use `/controllers safeword` for immediate emergency stop",
                ),
            )

            if failed_count > 0:
                embed.add_field(
                    name="⚠️ Note",
                    value=f"{failed_count} controller(s) were skipped (may already have permission)",
                    inline=False,
                )

            if dm_failed:
                dm_failed_text = ", ".join(dm_failed) if len(dm_failed) <= 5 else f"{', '.join(dm_failed[:5])}, and {len(dm_failed) - 5} more"
                embed.add_field(
                    name="📬 DM Notification",
                    value=(
                        f"⚠️ Couldn't send DM to: {dm_failed_text}\n"
                        f"They may have DMs disabled. Consider notifying them here in chat!"
                    ),
                    inline=False,
                )
        else:
            embed = self.formatter.error_embed(
                "Failed to Add Controllers",
                "All selected controllers may already have permission, or there was a database error.",
            )

        await inter.edit_original_message(embed=embed, view=None)

    @disnake.ui.button(label="Cancel", style=disnake.ButtonStyle.secondary)
    async def cancel_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        """Handle cancellation"""
        await inter.response.defer()

        count = len(self.controller_objs)
        embed = self.formatter.info_embed(
            "Cancelled",
            f"No permissions were granted to the {count} selected controller(s). Your device remains secure.",
        )
        await inter.edit_original_message(embed=embed, view=None)


def setup(bot: commands.InteractionBot):
    bot.add_cog(ControllerCommands(bot))
