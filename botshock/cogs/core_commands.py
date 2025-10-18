"""
Core utility commands (small, always-on commands like /ping).
"""

import logging
from datetime import datetime, UTC

import disnake
from disnake.ext import commands

logger = logging.getLogger("BotShock.CoreCommands")


class CoreCommands(commands.Cog):
    """Small utility commands."""

    def __init__(self, bot: commands.InteractionBot):
        self.bot = bot

    @commands.slash_command(name="ping", description="Check if the bot is responsive")
    async def ping(self, inter: disnake.ApplicationCommandInteraction):
        """Respond with basic latency and health info."""
        ping_embed = disnake.Embed(
            title="Pong!",
            description=f"Latency: {round(self.bot.latency * 1000)} ms",
            color=disnake.Color.green(),
            timestamp=datetime.now(UTC),
        )
        await inter.response.send_message(embed=ping_embed)


def setup(bot: commands.InteractionBot):
    bot.add_cog(CoreCommands(bot))
    logger.info("CoreCommands cog has been loaded")

