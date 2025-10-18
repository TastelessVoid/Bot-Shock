"""
Event listeners cog for handling Discord events
"""

import logging

import disnake
from disnake.ext import commands

from botshock.core.bot_protocol import SupportsBotAttrs

logger = logging.getLogger("BotShock.Events")


class EventListeners(commands.Cog):
    """Handles Discord events like messages and triggers"""

    def __init__(self, bot: SupportsBotAttrs):
        self.bot = bot
        self.db = bot.db
        self.trigger_manager = bot.trigger_manager

    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message):
        """Check messages against registered triggers"""
        if message.author.bot:
            return

        # Only process messages in guilds, not DMs
        if not message.guild:
            return

        # Ignore the user if they are not in the database
        user_record = await self.db.get_user(message.author.id, message.guild.id)
        if not user_record:
            return

        # Check for trigger matches
        matched, trigger = await self.trigger_manager.check_message(
            message.guild.id, message.author.id, message.content
        )

        if matched:
            logger.info(
                f"Trigger matched | Guild: {message.guild.name} ({message.guild.id}) | "
                f"User: {message.author} ({message.author.id}) | "
                f"Trigger: {trigger['name'] or trigger['id']} | "
                f"Pattern: {trigger['pattern'].pattern} | "
                f"Message: {message.content[:100]}"
            )

            await self._execute_trigger(message.guild.id, message.author, trigger)

    async def _execute_trigger(self, guild_id: int, user: disnake.User, trigger: dict):
        """Execute a trigger by sending a shock (respects both cooldowns)"""
        try:
            # Check trigger-specific cooldown first
            trigger_ready, seconds_remaining = await self.db.check_trigger_cooldown(trigger["id"])
            if not trigger_ready:
                logger.info(
                    f"Trigger on cooldown | User: {user.name} | "
                    f"Trigger: {trigger['name'] or trigger['id']} | "
                    f"Cooldown remaining: {seconds_remaining}s"
                )
                return

            # Get user data
            target_user = await self.db.get_user(user.id, guild_id)
            if not target_user:
                logger.warning(
                    f"Trigger fired but user {user.id} not registered in guild {guild_id}"
                )
                return

            # Get shockers
            shockers = await self.db.get_shockers(user.id, guild_id)
            if not shockers:
                logger.warning(
                    f"Trigger fired but user {user.id} has no shockers in guild {guild_id}"
                )
                return

            # Use first shocker
            target_shocker = shockers[0]

            # Check global device cooldown (default 60 seconds)
            device_ready = await self.db.check_shocker_cooldown(
                user.id, guild_id, target_shocker["shocker_id"], cooldown_seconds=60
            )

            if not device_ready:
                logger.info(
                    f"Device on cooldown | User: {user.name} | "
                    f"Shocker: {target_shocker['shocker_name'] or target_shocker['shocker_id']}"
                )
                return

            trigger_name = trigger["name"] or f"Trigger #{trigger['id']}"

            # Send shock via API client
            success, status_code, response_text = await self.bot.get_api_client().send_control(
                api_token=target_user["openshock_api_token"],
                shocker_id=target_shocker["shocker_id"],
                shock_type=trigger["shock_type"],
                intensity=trigger["intensity"],
                duration=trigger["duration"],
                custom_name=f"Trigger: {trigger_name}",
                base_url_override=target_user.get("api_server"),
            )

            if success:
                # Update both cooldowns
                await self.db.update_trigger_cooldown(trigger["id"])
                await self.db.update_shocker_cooldown(
                    user.id, guild_id, target_shocker["shocker_id"]
                )

                logger.info(
                    f"Trigger shock sent successfully | Guild: {guild_id} | User: {user.name} | "
                    f"Trigger: {trigger_name} | Type: {trigger['shock_type']} | "
                    f"Intensity: {trigger['intensity']}% | Duration: {trigger['duration']}ms"
                )
            else:
                logger.error(
                    f"Failed to send trigger shock | Guild: {guild_id} | User: {user.name} | "
                    f"Status: {status_code} | Response: {response_text}"
                )
        except Exception as e:
            logger.exception(f"Error executing trigger: {e}")


def setup(bot: commands.InteractionBot):
    """Setup function to add the cog to the bot"""
    bot.add_cog(EventListeners(bot))
    logger.info("EventListeners cog has been loaded")
