"""
User management commands cog
"""

import logging

import disnake
from disnake.ext import commands

from botshock.core.bot_protocol import SupportsBotAttrs
from botshock.utils.views import ShockerSelectView

logger = logging.getLogger("BotShock.UserCommands")


class RegisterModal(disnake.ui.Modal):
    """Modal for registering OpenShock API token"""

    def __init__(self):
        components = [
            disnake.ui.TextInput(
                label="OpenShock API Token",
                placeholder="kUtJ4rPbDkSRzfVk8nYi2Mo...",
                custom_id="api_token",
                style=disnake.TextInputStyle.short,
                min_length=10,
                max_length=200,
                required=True,
            ),
            disnake.ui.TextInput(
                label="Custom API Server (optional)",
                placeholder="https://api.openshock.app",
                custom_id="api_server",
                style=disnake.TextInputStyle.short,
                required=False,
            ),
        ]
        super().__init__(
            title="Register OpenShock API Token", components=components, custom_id="register_modal"
        )


class AddShockerModal(disnake.ui.Modal):
    """Modal for adding a shocker manually (fallback)"""

    def __init__(self, for_user: str = "yourself"):
        components = [
            disnake.ui.TextInput(
                label="Shocker ID",
                placeholder="Copy from OpenShock dashboard",
                custom_id="shocker_id",
                style=disnake.TextInputStyle.short,
                required=True,
            ),
            disnake.ui.TextInput(
                label="Friendly Name (optional)",
                placeholder="My Device",
                custom_id="shocker_name",
                style=disnake.TextInputStyle.short,
                required=False,
            ),
        ]
        super().__init__(
            title=f"Add Shocker for {for_user}",
            components=components,
            custom_id="add_shocker_modal",
        )


class UserCommands(commands.Cog):
    """Commands for user account and shocker management"""

    def __init__(self, bot: SupportsBotAttrs):
        self.bot = bot
        self.db = bot.db
        self.permission_checker = bot.permission_checker
        self.formatter = bot.formatter
        self.helper = bot.command_helper  # Add helper reference

    @commands.slash_command(description="Manage your OpenShock account and shockers")
    async def openshock(self, inter: disnake.ApplicationCommandInteraction):
        """Base command for OpenShock management"""
        pass

    @openshock.sub_command_group(name="shockers", description="Manage your registered shockers")
    async def shockers_group(self, inter: disnake.ApplicationCommandInteraction):
        """Manage your device shockers"""
        pass

    @openshock.sub_command(
        description="Complete setup: register API token and add shockers in one step"
    )
    async def setup(self, inter: disnake.ApplicationCommandInteraction):
        """Complete setup process - combines registration and shocker addition"""
        # Check if user is already registered
        existing_user = await self.db.get_user(inter.author.id, inter.guild.id)
        if existing_user:
            await self.helper.defer_response(inter)
            embed = self.formatter.info_embed(
                "Already Registered",
                "You already have an OpenShock account registered in this server.",
                field_1=(
                    "Current Setup",
                    "• Use `/openshock add_shocker` to add more devices\n"
                    "• Use `/openshock list_shockers` to view your devices\n"
                    "• Use `/openshock unregister` to start over",
                ),
            )
            await inter.edit_original_response(embed=embed)
            return

        # Show registration modal
        modal = RegisterModal()
        await inter.response.send_modal(modal)

        # Wait for modal submission using helper
        modal_inter = await self.helper.wait_for_modal(self.bot, modal.custom_id, inter.author.id)
        if not modal_inter:
            return

        # Send immediate response
        await modal_inter.response.send_message(
            embed=self.formatter.progress_embed(
                "Setting Up Your Account",
                step=1,
                total_steps=3,
                description="Validating your API token with OpenShock...",
            ),
            ephemeral=True,
        )

        api_token = modal_inter.text_values["api_token"]
        api_server = modal_inter.text_values.get("api_server", "").strip() or None

        # Validate the API token with OpenShock API (respect custom server if provided)
        is_valid, message, data = await self.bot.get_api_client().validate_token(
            api_token, base_url_override=api_server
        )

        if not is_valid:
            logger.warning(
                f"Setup - Token validation failed for {inter.author} ({inter.author.id}) in guild {inter.guild.id}: {message}"
            )
            embed = self.formatter.error_embed(
                "API Token Validation Failed",
                message,
                field_1=(
                    "What to do next",
                    "Please check your token at the OpenShock dashboard and try again with `/openshock setup`.",
                ),
            )
            await modal_inter.edit_original_response(
                embed=embed, components=[self.formatter.openshock_button()]
            )
            return

        # Show progress - step 2
        await modal_inter.edit_original_response(
            embed=self.formatter.progress_embed(
                "Setting Up Your Account",
                step=2,
                total_steps=3,
                description="✅ Token validated! Registering your account...",
            )
        )

        # Token is valid, register the user
        success = await self.db.add_user(
            discord_id=inter.author.id,
            guild_id=inter.guild.id,
            discord_username=str(inter.author),
            api_token=api_token,
            api_server=api_server,
        )

        if not success:
            logger.error(
                f"Setup - Failed to register user: {inter.author} ({inter.author.id}) in guild {inter.guild.name} ({inter.guild.id})"
            )
            embed = self.formatter.error_embed(
                "Registration Failed",
                "Failed to save your API token to database. Please try again.",
            )
            await modal_inter.edit_original_response(embed=embed)
            return

        logger.info(
            f"Setup - User registered: {inter.author} ({inter.author.id}) in guild {inter.guild.name} ({inter.guild.id})"
        )

        # Show progress - step 3
        await modal_inter.edit_original_response(
            embed=self.formatter.progress_embed(
                "Setting Up Your Account",
                step=3,
                total_steps=3,
                description="✅ Account registered! Fetching your devices...",
            )
        )

        # Get available shockers
        available_shockers = data.get("shockers", [])

        if not available_shockers:
            # Registration succeeded but no shockers found
            embed = self.formatter.success_embed(
                "✅ Account Registered (No Shockers Found)",
                "Your API token has been registered successfully!",
                field_1=(
                    "⚠️ No Shockers Available",
                    "No shockers were found in your OpenShock account. "
                    "Please add shockers to your OpenShock account first.",
                ),
                field_2=(
                    "📋 Next Steps",
                    "**1.** Add shockers at https://openshock.app\n"
                    "**2.** Come back and use `/openshock add_shocker`\n"
                    "**3.** Then use `/controllers add` to authorize controllers",
                ),
            )
            await modal_inter.edit_original_response(
                embed=embed, components=[self.formatter.openshock_button()]
            )
            return

        # Create shocker selection view
        embed = disnake.Embed(
            title="🎉 Account Registered Successfully!",
            description=f"Found **{len(available_shockers)}** shocker(s) in your OpenShock account.\n"
            f"Select the ones you want to add to this Discord server.",
            color=disnake.Color.green(),
        )
        embed.add_field(
            name="📝 Instructions",
            value="1. Select one or more shockers from the dropdown below\n"
            "2. Click the **Add Selected** button to complete setup\n"
            "3. Then use `/controllers add` to authorize who can control them",
            inline=False,
        )
        embed.add_field(
            name="⏭️ Skip This Step",
            value="You can click **Skip for Now** and add shockers later with `/openshock add_shocker`",
            inline=False,
        )

        view = ShockerSelectView(available_shockers, inter.author.id, multi_select=True)

        # Add confirm button
        confirm_button = disnake.ui.Button(
            label="Add Selected",
            style=disnake.ButtonStyle.success,
            emoji="✅",
            custom_id="setup_confirm_add",
        )

        # Add skip button
        skip_button = disnake.ui.Button(
            label="Skip for Now", style=disnake.ButtonStyle.secondary, emoji="⏭️", custom_id="setup_skip"
        )

        async def confirm_callback(button_inter: disnake.MessageInteraction):
            if button_inter.user.id != inter.author.id:
                await button_inter.response.send_message("This is not your setup!", ephemeral=True)
                return

            await button_inter.response.defer()

            # Ensure selection
            if not await self.helper.ensure_selection(
                button_inter, view.selected_shockers, view=view, include_skip_hint=True
            ):
                return

            # Add selected shockers to database (bulk helper)
            added_count, failed_count, added_names = await self.helper.add_shockers_bulk(
                button_inter,
                inter.author.id,
                inter.guild.id,
                view.selected_shockers,
                available_shockers,
                log_prefix="Setup - ",
            )

            # Show completion message
            if added_count > 0:
                shocker_list = "\n".join([f"• {name}" for name in added_names])
                embed = self.formatter.success_embed(
                    f"🎉 Setup Complete! Added {added_count} Shocker(s)",
                    shocker_list,
                    field_1=(
                        "🎯 Next Step: Add Controllers",
                        "Use `/controllers add` to choose who can control your devices!",
                    ),
                    field_2=(
                        "🛡️ Your Safety & Control",
                        "**You control who has access:**\n"
                        "• Only authorize people you completely trust\n"
                        "• Controllers can shock you at any intensity/duration\n"
                        "• You can revoke access anytime with `/controllers remove`\n"
                        "• Use `/controllers safeword` for emergency stop\n"
                        "• All actions are logged for your safety",
                    ),
                )

                if failed_count > 0:
                    embed.add_field(
                        name="⚠️ Note",
                        value=f"{failed_count} shocker(s) failed to add",
                        inline=False,
                    )

                # Delete ephemeral and send public
                await button_inter.delete_original_response()
                await button_inter.followup.send(embed=embed, ephemeral=False)
            else:
                embed = self.formatter.error_embed(
                    "Failed to Add Shockers",
                    "All selected shockers failed to add. Please try `/openshock add_shocker`.",
                )
                await button_inter.edit_original_response(embed=embed, view=None)

        async def skip_callback(button_inter: disnake.MessageInteraction):
            if button_inter.user.id != inter.author.id:
                await button_inter.response.send_message("This is not your setup!", ephemeral=True)
                return

            await button_inter.response.defer()

            embed = self.formatter.success_embed(
                "✅ Setup Complete (No Shockers Added)",
                "Your API token has been registered successfully!",
                field_1=(
                    "📋 Next Steps",
                    "**1.** Add your devices: `/openshock add_shocker`\n"
                    "**2.** Choose your controllers: `/controllers add`\n\n"
                    "⚠️ **Important:** Only users/roles you authorize will be able to control your device.",
                ),
            )

            # Delete ephemeral and send public
            await button_inter.delete_original_response()
            await button_inter.followup.send(embed=embed, ephemeral=False)

        confirm_button.callback = confirm_callback
        skip_button.callback = skip_callback
        view.add_item(confirm_button)
        view.add_item(skip_button)

        await inter.response.send_message(embed=embed, view=view, ephemeral=True)

    @shockers_group.sub_command(description="Add shockers to your account")
    async def add(self, inter: disnake.ApplicationCommandInteraction):
        """Add shockers to your account by selecting from available devices"""
        await inter.response.defer(ephemeral=True)

        # Check if user is registered
        user = await self.db.get_user(inter.author.id, inter.guild.id)
        if not user:
            embed = self.formatter.error_embed(
                "Registration Required",
                "You need to register your API token first before adding shockers!",
                field_1=("Next Steps", "Use `/openshock setup` to set up your account first."),
            )
            await inter.edit_original_response(embed=embed)
            return

        # Fetch available shockers from OpenShock API
        logger.info(f"Fetching available shockers for user {inter.author.name} ({inter.author.id})")
        is_valid, message, data = await self.bot.get_api_client().validate_token(
            user["openshock_api_token"], base_url_override=user.get("api_server")
        )

        if not is_valid:
            embed = self.formatter.error_embed(
                "API Error",
                "Failed to fetch your shockers from OpenShock.",
                field_1=("Details", message),
            )
            await inter.edit_original_response(embed=embed)
            return

        available_shockers = data.get("shockers", [])

        if not available_shockers:
            embed = self.formatter.error_embed(
                "No Shockers Found",
                "No shockers were found in your OpenShock account.",
                field_1=(
                    "What to do",
                    "Please add shockers to your OpenShock account first at https://openshock.app",
                ),
            )
            await inter.edit_original_response(
                embed=embed, components=[self.formatter.openshock_button()]
            )
            return

        # Get already added shockers to filter them out
        existing_shockers = await self.db.get_shockers(inter.author.id, inter.guild.id)
        existing_ids = {s["shocker_id"] for s in existing_shockers}

        # Filter out already added shockers
        new_shockers = [s for s in available_shockers if s.get("id") not in existing_ids]

        if not new_shockers:
            embed = self.formatter.error_embed(
                "All Shockers Already Added",
                "You've already added all available shockers from your OpenShock account.",
                field_1=("Current Shockers", f"{len(existing_shockers)} shocker(s) registered"),
            )
            await inter.edit_original_response(embed=embed)
            return

        # Create selection view
        embed = disnake.Embed(
            title="🔌 Select Shockers to Add",
            description=f"Found **{len(new_shockers)}** new shocker(s) in your OpenShock account.\n"
            f"Select the ones you want to add to this Discord server.",
            color=disnake.Color.blue(),
        )
        embed.add_field(
            name="📝 Instructions",
            value="1. Select one or more shockers from the dropdown below\n"
            "2. Click the **Add Selected** button\n"
            "3. Then use `/controllers add` to authorize who can control them",
            inline=False,
        )

        if existing_shockers:
            embed.add_field(
                name="Already Added", value=f"{len(existing_shockers)} shocker(s)", inline=True
            )

        view = ShockerSelectView(new_shockers, inter.author.id, multi_select=True)

        # Add confirm button
        confirm_button = disnake.ui.Button(
            label="Add Selected",
            style=disnake.ButtonStyle.success,
            emoji="✅",
            custom_id="confirm_add",
        )

        async def confirm_callback(button_inter: disnake.MessageInteraction):
            if button_inter.user.id != inter.author.id:
                await button_inter.response.send_message(
                    "This is not your selection!", ephemeral=True
                )
                return

            await button_inter.response.defer()

            # Ensure selection
            if not await self.helper.ensure_selection(
                button_inter, view.selected_shockers, view=view
            ):
                return

            # Add selected shockers to database (bulk helper)
            added_count, failed_count, added_names = await self.helper.add_shockers_bulk(
                button_inter,
                inter.author.id,
                inter.guild.id,
                view.selected_shockers,
                new_shockers,
            )

            # Show result
            if added_count > 0:
                shocker_list = "\n".join([f"• {name}" for name in added_names])
                embed = self.formatter.success_embed(
                    f"✅ Added {added_count} Shocker(s)",
                    shocker_list,
                    field_1=(
                        "✅ Next Step",
                        "Use `/controllers add` to choose who can control your devices!",
                    ),
                    field_2=(
                        "🛡️ Your Safety & Control",
                        "**You control who has access:**\n"
                        "• Only authorize people you completely trust\n"
                        "• Controllers can shock you at any intensity/duration\n"
                        "• You can revoke access anytime with `/controllers remove`\n"
                        "• Use `/controllers safeword` for emergency stop\n"
                        "• All actions are logged for your safety",
                    ),
                )

                if failed_count > 0:
                    embed.add_field(
                        name="⚠️ Note",
                        value=f"{failed_count} shocker(s) failed to add (may already exist)",
                        inline=False,
                    )

                # Delete ephemeral and send public
                await button_inter.delete_original_response()
                await button_inter.followup.send(embed=embed, ephemeral=False)
            else:
                embed = self.formatter.error_embed(
                    "Failed to Add Shockers",
                    "All selected shockers failed to add. They may already be registered.",
                )
                await button_inter.edit_original_response(embed=embed, view=None)

        confirm_button.callback = confirm_callback
        view.add_item(confirm_button)

        await inter.edit_original_response(embed=embed, view=view)

    @shockers_group.sub_command(description="Remove a shocker from your account")
    async def remove(
        self,
        inter: disnake.ApplicationCommandInteraction,
        shocker_id: str = commands.Param(description="The shocker ID to remove"),
    ):
        """Remove a shocker from your account"""
        await inter.response.defer(ephemeral=True)

        # Check if user is registered
        user = await self.db.get_user(inter.author.id, inter.guild.id)
        if not user:
            embed = self.formatter.error_embed(
                "Not Registered",
                "You don't have any registered devices.",
                field_1=("Next Steps", "Use `/openshock setup` to set up your API token first."),
            )
            await inter.edit_original_response(embed=embed)
            return

        success = await self.db.remove_shocker(inter.author.id, inter.guild.id, shocker_id)

        if success:
            embed = self.formatter.success_embed(
                "Shocker Removed", f"Successfully removed shocker `{shocker_id}` from your account."
            )
            logger.info(
                f"Shocker removed: {shocker_id} for user {inter.author} ({inter.author.id}) "
                f"in guild {inter.guild.name} ({inter.guild.id})"
            )
            await inter.edit_original_response(embed=embed)
        else:
            embed = self.formatter.error_embed(
                "Removal Failed", "Shocker not found or already removed."
            )
            await inter.edit_original_response(embed=embed)

    @shockers_group.sub_command(description="List your registered shockers")
    async def list(self, inter: disnake.ApplicationCommandInteraction):
        """List your registered shockers"""
        await inter.response.defer(ephemeral=True)

        # Check if user is registered
        user = await self.db.get_user(inter.author.id, inter.guild.id)
        if not user:
            embed = self.formatter.error_embed(
                "Not Registered",
                "You don't have any registered devices.",
                field_1=(
                    "Next Steps",
                    "Use `/openshock setup` to set up your API token and add shockers.",
                ),
            )
            await inter.edit_original_response(embed=embed)
            return

        shockers = await self.db.get_shockers(inter.author.id, inter.guild.id)
        embed = self.formatter.format_shocker_list(shockers)

        # Only show OpenShock button if user has no shockers (to help them get started)
        components = [self.formatter.openshock_button()] if not shockers else []

        await inter.edit_original_response(embed=embed, components=components)

    @openshock.sub_command(description="Toggle whether you're wearing your device")
    async def device_status(self, inter: disnake.ApplicationCommandInteraction):
        """Toggle your device worn status"""
        await inter.response.defer(ephemeral=True)

        # Check if user is registered
        user = await self.db.get_user(inter.author.id, inter.guild.id)
        if not user:
            embed = self.formatter.error_embed(
                "Not Registered",
                "You don't have a registered OpenShock account.",
                field_1=(
                    "Next Steps",
                    "Use `/openshock setup` to set up your API token and add shockers.",
                ),
            )
            await inter.edit_original_response(embed=embed)
            return

        # Get current device status
        is_worn = await self.db.get_device_worn_status(inter.author.id, inter.guild.id)

        # Toggle the status
        new_status = not is_worn
        success = await self.db.set_device_worn(inter.author.id, inter.guild.id, new_status)

        if success:
            status_text = "✅ Wearing" if new_status else "❌ Not Wearing"
            embed = self.formatter.success_embed(
                "Device Status Updated",
                f"You are now **{status_text}** your device.",
                field_1=(
                    "What this means",
                    "When you're not wearing your device, controllers won't be able to send shocks to you."
                    if not new_status
                    else "Controllers can now send shocks to you."
                ),
            )
            logger.info(
                f"Device status updated: {inter.author} ({inter.author.id}) in guild {inter.guild.id} - wearing: {new_status}"
            )
        else:
            embed = self.formatter.error_embed(
                "Update Failed",
                "Could not update your device status. Please try again later.",
            )

        await inter.edit_original_response(embed=embed)

    @openshock.sub_command(description="Check if you're currently wearing your device")
    async def check_device(self, inter: disnake.ApplicationCommandInteraction):
        """Check your current device worn status"""
        await inter.response.defer(ephemeral=True)

        # Check if user is registered
        user = await self.db.get_user(inter.author.id, inter.guild.id)
        if not user:
            embed = self.formatter.error_embed(
                "Not Registered",
                "You don't have a registered OpenShock account.",
                field_1=(
                    "Next Steps",
                    "Use `/openshock setup` to set up your API token and add shockers.",
                ),
            )
            await inter.edit_original_response(embed=embed)
            return

        # Get current device status
        is_worn = await self.db.get_device_worn_status(inter.author.id, inter.guild.id)

        status_text = "✅ **Wearing**" if is_worn else "❌ **Not Wearing**"
        description = (
            "Your device is currently being worn. Controllers can send shocks to you."
            if is_worn
            else "Your device is currently not being worn. Controllers cannot send shocks to you."
        )

        embed = self.formatter.info_embed(
            "Device Status",
            description,
            field_1=("Current Status", status_text),
            field_2=("Toggle Status", "Use `/openshock device_status` to change this."),
        )

        await inter.edit_original_response(embed=embed)

    @openshock.sub_command(description="Unregister your OpenShock account")
    async def unregister(self, inter: disnake.ApplicationCommandInteraction):
        """Unregister your OpenShock account"""
        await inter.response.defer(ephemeral=True)

        success = await self.db.remove_user(inter.author.id, inter.guild.id)

        if success:
            embed = self.formatter.success_embed(
                "Account Unregistered",
                "Your OpenShock API token and all associated shockers have been removed from this server.",
                field_1=("Note", "You can register again anytime using `/openshock setup`"),
            )
            logger.info(
                f"User unregistered: {inter.author} ({inter.author.id}) in guild {inter.guild.name} ({inter.guild.id})"
            )
        else:
            embed = self.formatter.error_embed(
                "Not Registered", "You don't have a registered OpenShock account in this server."
            )

        await inter.edit_original_response(embed=embed)


def setup(bot: commands.InteractionBot):
    """Setup function to add the cog to the bot"""
    bot.add_cog(UserCommands(bot))
    logger.info("UserCommands cog has been loaded")
