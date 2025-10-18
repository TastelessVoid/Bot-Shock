"""
Shock command cog for sending manual shocks
"""

import logging

import disnake
from disnake.ext import commands

from botshock.core.bot_protocol import SupportsBotAttrs
from botshock.utils.validators import ShockValidator

logger = logging.getLogger("BotShock.ShockCommand")


class ShockCommand(commands.Cog):
    """Command for manually sending shocks to users"""

    def __init__(self, bot: SupportsBotAttrs):
        self.bot = bot
        self.db = bot.db
        self.formatter = bot.formatter  # Use shared formatter
        self.permission_checker = bot.permission_checker
        self.validator = ShockValidator(bot.db, bot.permission_checker)
        self.helper = bot.command_helper  # Use shared command helper

    @commands.slash_command(description="Send a shock command to a user's OpenShock device")
    async def shock(
        self,
        inter: disnake.ApplicationCommandInteraction,
        user: disnake.User = commands.Param(description="The Discord user to shock", default=None),
        intensity: int = commands.Param(
            description="Shock intensity (1-100)", ge=1, le=100, default=None
        ),
        duration: int = commands.Param(
            description="Duration in milliseconds (300-65535)", ge=300, le=65535, default=None
        ),
        shock_type: str = commands.Param(
            description="Type of shock", choices=["Shock", "Vibrate", "Sound"], default=None
        ),
        shocker_id: str = commands.Param(
            description="Specific shocker ID (optional)", default=None
        ),
    ):
        """Send a shock command to a user's OpenShock device with smart defaults"""

        await inter.response.defer(ephemeral=True)

        # Get controller's role IDs for permission checking
        controller_role_ids = (
            [role.id for role in inter.author.roles] if hasattr(inter.author, "roles") else []
        )

        # Smart defaults: auto-select target user if controller only controls one person
        if user is None:
            controllable_users = await self.db.get_controllable_users(
                inter.author.id, inter.guild.id, controller_role_ids
            )

            if len(controllable_users) == 0:
                embed = self.formatter.error_embed(
                    "No Target Specified",
                    "You must specify a user to shock, or you need permission to control at least one user.",
                    field_1=(
                        "Need Permission?",
                        "Ask a user to grant you control with `/controllers add`",
                    ),
                )
                await inter.edit_original_response(embed=embed)
                return
            elif len(controllable_users) == 1:
                # Auto-select the only controllable user
                user = await inter.bot.fetch_user(controllable_users[0])
                logger.info(
                    f"Auto-selected target user {user.name} for controller {inter.author.name}"
                )
            else:
                # Multiple users - need to specify
                embed = self.formatter.error_embed(
                    "Target Required",
                    f"You can control {len(controllable_users)} users. Please specify which one:",
                    field_1=("Tip", "Use the `user` parameter to select your target."),
                )
                await inter.edit_original_response(embed=embed)
                return

        # Get or create preferences for smart defaults
        prefs = await self.db.get_controller_preferences(inter.author.id, inter.guild.id, user.id)

        # Apply smart defaults for missing parameters
        if prefs and prefs.get("use_smart_defaults"):
            # Use last-used values if available, otherwise configured defaults
            if intensity is None:
                intensity = prefs.get("last_used_intensity") or prefs.get("default_intensity") or 30
            if duration is None:
                duration = prefs.get("last_used_duration") or prefs.get("default_duration") or 1000
            if shock_type is None:
                shock_type = (
                    prefs.get("last_used_shock_type") or prefs.get("default_shock_type") or "Shock"
                )
        else:
            # Use hardcoded defaults if no preferences or smart defaults disabled
            if intensity is None:
                intensity = 30
            if duration is None:
                duration = 1000
            if shock_type is None:
                shock_type = "Shock"

        logger.info(
            f"Shock command initiated | Executor: {inter.author} ({inter.author.id}) | "
            f"Target: {user} ({user.id}) | Type: {shock_type} | "
            f"Intensity: {intensity}% | Duration: {duration}ms | Smart defaults: {prefs is not None}"
        )

        # Validate shock request
        is_valid, error_msg, target_user, target_shocker = (
            await self.validator.validate_shock_request(
                inter.author, user, inter.guild.id, shocker_id
            )
        )

        if not is_valid:
            embed = self.formatter.error_embed("Shock Failed", error_msg)
            await inter.edit_original_response(embed=embed)
            logger.warning(
                f"Validation failed: {inter.author} ({inter.author.id}) tried to shock "
                f"{user} ({user.id}) in guild {inter.guild.id}"
            )
            return

        # If no specific shocker provided and user has multiple, delegate selection to helper
        if not shocker_id:
            user_shockers = await self.db.get_shockers(user.id, inter.guild.id)
            if len(user_shockers) > 1:
                target_shocker = await self.helper.handle_shocker_selection(
                    inter,
                    user_shockers,
                    {"type": shock_type, "intensity": intensity, "duration": duration},
                )
                if not target_shocker:
                    return

        # Check global device cooldown (60 seconds default)
        device_ready = await self.db.check_shocker_cooldown(
            user.id, inter.guild.id, target_shocker["shocker_id"], cooldown_seconds=60
        )

        if not device_ready:
            shocker_name = target_shocker["shocker_name"] or "device"
            logger.info(
                f"Shock command blocked by cooldown | Guild: {inter.guild.name} ({inter.guild.id}) | "
                f"Executor: {inter.author.name} | Target: {user.name} | Shocker: {shocker_name}"
            )
            embed = self.formatter.error_embed(
                "Cooldown Active",
                f"The shocker for {user.mention} is on cooldown. Please wait before sending another shock.",
                field_1=(
                    "Why?",
                    "Cooldowns prevent excessive shocking and protect device hardware.",
                ),
            )
            await inter.edit_original_response(embed=embed, view=None)
            return

        # Check controller cooldown (only if not self-controlling)
        if inter.author.id != user.id:
            # Get the configured cooldown duration for this target (default: 300 seconds = 5 minutes)
            cooldown_duration = await self.db.get_controller_cooldown_duration(
                user.id, inter.guild.id
            )
            controller_ready, seconds_remaining = await self.db.check_controller_cooldown(
                inter.author.id, user.id, inter.guild.id, cooldown_seconds=cooldown_duration
            )

            if not controller_ready:
                time_str = self.helper.format_time_remaining(seconds_remaining)

                logger.info(
                    f"Shock command blocked by controller cooldown | Guild: {inter.guild.name} ({inter.guild.id}) | "
                    f"Controller: {inter.author.name} | Target: {user.name} | Remaining: {seconds_remaining}s"
                )
                embed = self.formatter.error_embed(
                    "Controller Cooldown Active",
                    f"You need to wait **{time_str}** before you can control {user.mention} again.",
                    field_1=(
                        "Rate Limiting",
                        f"Controllers have a {cooldown_duration // 60} minute cooldown between actions to ensure responsible use.",
                    ),
                )
                await inter.edit_original_response(embed=embed, view=None)
                return

        # Send the shock via API client
        success, status_code, response_text = await self.bot.get_api_client().send_control(
            api_token=target_user["openshock_api_token"],
            shocker_id=target_shocker["shocker_id"],
            shock_type=shock_type,
            intensity=intensity,
            duration=duration,
            custom_name=f"Discord Bot - {inter.author.name}",
            base_url_override=target_user.get("api_server"),
        )

        # Log the controller action
        await self.db.log_controller_action(
            guild_id=inter.guild.id,
            controller_discord_id=inter.author.id,
            controller_username=str(inter.author),
            target_discord_id=user.id,
            target_username=str(user),
            action_type="shock",
            shock_type=shock_type,
            intensity=intensity,
            duration=duration,
            shocker_id=target_shocker["shocker_id"],
            shocker_name=target_shocker["shocker_name"],
            success=success,
            error_message=response_text if not success else None,
            source="manual",
        )

        if success:
            # Update the device cooldown
            await self.db.update_shocker_cooldown(
                user.id, inter.guild.id, target_shocker["shocker_id"]
            )

            # Update controller cooldown (only if not self-controlling)
            if inter.author.id != user.id:
                cooldown_duration = await self.db.get_controller_cooldown_duration(
                    user.id, inter.guild.id
                )
                await self.db.update_controller_cooldown(
                    inter.author.id, user.id, inter.guild.id, cooldown_duration
                )

            # Update last-used values for smart defaults
            await self.db.update_last_used_values(
                inter.author.id, inter.guild.id, user.id, intensity, duration, shock_type
            )

            shocker_name = target_shocker["shocker_name"] or "Unnamed Shocker"
            logger.info(
                f"Shock command successful  Guild: {inter.guild.name} ({inter.guild.id})  "
                f"Executor: {inter.author.name}  Target: {user.name}  "
                f"Type: {shock_type}  Intensity: {intensity}%  Duration: {duration}ms"
            )

            embed = self.formatter.format_shock_success(
                user.mention, shocker_name, shock_type, intensity, duration
            )
            embed.set_footer(
                text=f"Executed by {inter.author.display_name}",
                icon_url=inter.author.display_avatar.url,
            )

            # Success is visible to everyone - delete ephemeral and send public
            await inter.delete_original_response()
            await inter.followup.send(embed=embed)
        else:
            # Handle specific error codes - errors remain ephemeral
            # Try to parse the error response for more details
            error_type = None
            try:
                import json

                error_data = json.loads(response_text)
                error_type = error_data.get("type", "")
            except Exception:
                pass

            if status_code == 403:
                error_msg = f"Access forbidden. The API token for {user.mention} may be invalid."
                help_text = "The user may need to re-register their API token."
            elif status_code == 404:
                # Check if this is a "Shocker.Control.NotFound" error
                if error_type == "Shocker.Control.NotFound":
                    error_msg = "Cannot control this shocker."
                    help_text = (
                        "**Root Cause:** The API token cannot control this specific shocker.\n\n"
                        "**Most Common Reasons:**\n\n"
                        "1\u20e3 **Wrong Account**: The API token is for a different OpenShock account than the one that owns this shocker.\n"
                        f"   • {user.mention} needs to make sure the API token belongs to the same OpenShock account that owns the shocker\n"
                        f"   • To fix: Run `/openshock setup` with the CORRECT account's API token\n\n"
                        "2\u20e3 **Shared Shocker**: This might be a shared shocker, and API tokens can only control shockers you OWN, not shared ones.\n"
                        f"   • {user.mention} must use their own shocker, not one shared with them\n"
                        f"   • To fix: Remove this shocker and add your own shocker instead\n\n"
                        "3\u20e3 **Deleted Shocker**: The shocker was removed from the OpenShock account.\n"
                        f"   • To fix: {user.mention} should run `/openshock remove_shocker` then `/openshock add_shocker` again\n\n"
                        "**How to Fix:**\n"
                        "• Make absolutely sure the API token and shocker belong to the SAME OpenShock account\n"
                        "• Go to https://openshock.app and verify you're logged into the correct account\n"
                        "• Use `/openshock setup` to re-register with the correct API token\n"
                        "• Then run `/openshock add_shocker` to add your shockers again"
                    )
                else:
                    # Generic 404 error
                    error_msg = "Shocker not found or not accessible."
                    help_text = (
                        "**Possible Causes:**\n\n"
                        "1. The API token might lack the `shockers.use` permission\n"
                        "   • Go to https://openshock.app/#/dashboard/tokens\n"
                        "   • Make sure `shockers.use` permission is CHECKED ✓\n\n"
                        "2. The shocker ID in the database might be incorrect\n"
                        f"   • {user.mention} should run `/openshock remove_shocker` then `/openshock add_shocker`\n\n"
                        "3. The shocker was deleted from the OpenShock account"
                    )
            elif status_code == 412:
                error_msg = "Precondition failed. The shocker may be offline or paused."
                help_text = "Check the shocker status in the OpenShock dashboard."
            elif status_code == 0:
                error_msg = "Connection error. Unable to reach OpenShock server."
                help_text = f"Error details: {response_text}"
            else:
                error_msg = f"Failed to send shock. Status: {status_code}"
                help_text = f"Error details: {response_text if len(response_text) < 500 else response_text[:500] + '...'}"

            logger.error(
                f"Shock command failed | Status: {status_code} | Error Type: {error_type or 'Unknown'} | "
                f"Target: {user.name} | Response: {response_text}"
            )
            embed = self.formatter.error_embed(
                "Shock Failed", error_msg, field_1=("Troubleshooting", help_text)
            )
            # Don't mix view and components - choose one or the other
            await inter.edit_original_response(
                embed=embed, components=[self.formatter.openshock_button()]
            )


def setup(bot: commands.InteractionBot):
    """Cog setup function"""
    bot.add_cog(ShockCommand(bot))
