"""
Controller preferences commands for managing smart defaults
"""

import logging

import disnake
from disnake.ext import commands

from botshock.core.bot_protocol import SupportsBotAttrs

logger = logging.getLogger("BotShock.ControllerPreferences")


class ControllerPreferences(commands.Cog):
    """Commands for controllers to manage their default settings"""

    def __init__(self, bot: SupportsBotAttrs):
        self.bot = bot
        self.db = bot.db
        self.formatter = bot.formatter  # Use shared formatter

    @commands.slash_command(description="Manage your controller preferences and default settings")
    async def preferences(self, inter: disnake.ApplicationCommandInteraction):
        """Base command for preference management"""
        pass

    @preferences.sub_command(description="Set your default shock settings")
    async def set_defaults(
        self,
        inter: disnake.ApplicationCommandInteraction,
        intensity: int = commands.Param(
            description="Default intensity (1-100)", ge=1, le=100, default=30
        ),
        duration: int = commands.Param(
            description="Default duration in milliseconds (300-65535)",
            ge=300,
            le=65535,
            default=1000,
        ),
        shock_type: str = commands.Param(
            description="Default shock type", choices=["Shock", "Vibrate", "Sound"], default="Shock"
        ),
        target_user: disnake.User = commands.Param(
            description="Set defaults for a specific user (leave empty for all users)", default=None
        ),
    ):
        """Set your default shock settings"""
        await inter.response.defer(ephemeral=True)

        target_id = target_user.id if target_user else None
        target_name = target_user.display_name if target_user else "all users"

        success = await self.db.set_controller_defaults(
            inter.author.id,
            inter.guild.id,
            target_discord_id=target_id,
            default_intensity=intensity,
            default_duration=duration,
            default_shock_type=shock_type,
            use_smart_defaults=True,
        )

        if success:
            embed = disnake.Embed(
                title="✅ Defaults Updated",
                description=f"Your default settings for **{target_name}** have been saved!",
                color=disnake.Color.green(),
            )
            embed.add_field(
                name="Your Defaults",
                value=(
                    f"⚡ **Type:** {shock_type}\n"
                    f"📊 **Intensity:** {intensity}%\n"
                    f"⏱️ **Duration:** {duration}ms"
                ),
                inline=False,
            )
            embed.add_field(
                name="How It Works",
                value=(
                    "• When you use `/shock` without specifying intensity, duration, or type, these defaults will be used\n"
                    "• The bot also remembers your last-used settings as you shock\n"
                    "• Last-used settings take priority over configured defaults"
                ),
                inline=False,
            )
            if target_user is None:
                embed.add_field(
                    name="💡 Pro Tip",
                    value=(
                        "You can set different defaults for specific users!\n"
                        "Use the `target_user` parameter to customize per person."
                    ),
                    inline=False,
                )
            logger.info(
                f"Updated defaults for {inter.author.name} -> {target_name}: {shock_type} {intensity}% {duration}ms"
            )
        else:
            embed = self.formatter.error_embed(
                "Failed to Update", "Could not save your preferences. Please try again."
            )

        await inter.edit_original_response(embed=embed)

    @preferences.sub_command(description="View your current preferences and defaults")
    async def view(
        self,
        inter: disnake.ApplicationCommandInteraction,
        target_user: disnake.User = commands.Param(
            description="View preferences for a specific user", default=None
        ),
    ):
        """View your current preferences"""
        await inter.response.defer(ephemeral=True)

        target_id = target_user.id if target_user else None
        prefs = await self.db.get_controller_preferences(inter.author.id, inter.guild.id, target_id)

        embed = disnake.Embed(title="🎛️ Your Controller Preferences", color=disnake.Color.blue())

        if target_user:
            embed.description = f"Preferences for controlling **{target_user.display_name}**"
        else:
            embed.description = "Global preferences (used when no specific user preferences exist)"

        if prefs:
            # Show configured defaults
            default_fields = []
            if prefs.get("default_intensity"):
                default_fields.append(f"📊 **Intensity:** {prefs['default_intensity']}%")
            if prefs.get("default_duration"):
                default_fields.append(f"⏱️ **Duration:** {prefs['default_duration']}ms")
            if prefs.get("default_shock_type"):
                default_fields.append(f"⚡ **Type:** {prefs['default_shock_type']}")

            if default_fields:
                embed.add_field(
                    name="Configured Defaults", value="\n".join(default_fields), inline=True
                )

            # Show last-used values
            last_used_fields = []
            if prefs.get("last_used_intensity"):
                last_used_fields.append(f"📊 **Intensity:** {prefs['last_used_intensity']}%")
            if prefs.get("last_used_duration"):
                last_used_fields.append(f"⏱️ **Duration:** {prefs['last_used_duration']}ms")
            if prefs.get("last_used_shock_type"):
                last_used_fields.append(f"⚡ **Type:** {prefs['last_used_shock_type']}")

            if last_used_fields:
                embed.add_field(
                    name="Last Used Settings", value="\n".join(last_used_fields), inline=True
                )

            # Smart defaults status
            smart_enabled = prefs.get("use_smart_defaults", True)
            status_emoji = "✅" if smart_enabled else "❌"
            embed.add_field(
                name="Smart Defaults",
                value=f"{status_emoji} {'Enabled' if smart_enabled else 'Disabled'}",
                inline=False,
            )

            if smart_enabled:
                embed.add_field(
                    name="How It Works",
                    value=(
                        "When you use `/shock` without parameters:\n"
                        "1️⃣ Uses **last-used** settings if available\n"
                        "2️⃣ Falls back to **configured defaults** if no last-used\n"
                        "3️⃣ Uses **hardcoded defaults** (30%, 1000ms, Shock) if neither exist"
                    ),
                    inline=False,
                )
        else:
            embed.description = "No preferences set yet. Using system defaults."
            embed.add_field(
                name="Current Defaults",
                value="📊 **Intensity:** 30%\n⏱️ **Duration:** 1000ms\n⚡ **Type:** Shock",
                inline=False,
            )
            embed.add_field(
                name="💡 Get Started",
                value="Use `/preferences set_defaults` to configure your own defaults!",
                inline=False,
            )

        await inter.edit_original_response(embed=embed)

    @preferences.sub_command(description="Toggle smart defaults on/off")
    async def toggle(
        self,
        inter: disnake.ApplicationCommandInteraction,
        enabled: bool = commands.Param(description="Enable or disable smart defaults"),
    ):
        """Toggle smart defaults on or off"""
        await inter.response.defer(ephemeral=True)

        success = await self.db.set_controller_defaults(
            inter.author.id, inter.guild.id, use_smart_defaults=enabled
        )

        if success:
            status = "enabled" if enabled else "disabled"
            embed = disnake.Embed(
                title=f"✅ Smart Defaults {status.title()}",
                description=f"Smart defaults have been **{status}** for your shock commands.",
                color=disnake.Color.green() if enabled else disnake.Color.orange(),
            )

            if enabled:
                embed.add_field(
                    name="What This Means",
                    value=(
                        "• You can now use `/shock` without specifying intensity, duration, or type\n"
                        "• The bot will use your last-used settings or configured defaults\n"
                        "• If you only control one user, you don't even need to specify the target!"
                    ),
                    inline=False,
                )
            else:
                embed.add_field(
                    name="What This Means",
                    value=(
                        "• You must now specify all parameters when using `/shock`\n"
                        "• Your saved defaults will be kept but not automatically used\n"
                        "• Re-enable anytime with `/preferences toggle enabled:True`"
                    ),
                    inline=False,
                )

            logger.info(f"Smart defaults {status} for {inter.author.name}")
        else:
            embed = self.formatter.error_embed(
                "Failed to Toggle", "Could not update your preferences. Please try again."
            )

        await inter.edit_original_response(embed=embed)


def setup(bot: commands.InteractionBot):
    """Setup function to add the cog to the bot"""
    bot.add_cog(ControllerPreferences(bot))
    logger.info("ControllerPreferences cog has been loaded")
