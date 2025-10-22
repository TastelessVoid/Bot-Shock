"""
Centralized response handling for consistent error/success messaging.

This module provides the ResponseHandler class to eliminate redundant
error/success response patterns across all cogs.
"""

import logging

import disnake

from botshock.utils.formatters import ResponseFormatter

logger = logging.getLogger("BotShock.ResponseHandler")


class ResponseHandler:
    """Centralized handler for consistent response patterns."""

    def __init__(self, formatter: ResponseFormatter | None = None):
        """
        Initialize the response handler.

        Args:
            formatter: ResponseFormatter instance (creates default if None)
        """
        self.formatter = formatter or ResponseFormatter()

    async def defer(
        self,
        inter: disnake.ApplicationCommandInteraction,
        ephemeral: bool = True,
    ) -> bool:
        """
        Safely defer a response.

        Args:
            inter: The interaction to defer
            ephemeral: Whether response should be ephemeral

        Returns:
            True if successful, False otherwise
        """
        try:
            await inter.response.defer(ephemeral=ephemeral)
            return True
        except Exception as e:
            logger.warning(f"Failed to defer response: {e}")
            return False

    async def send_success(
        self,
        inter: disnake.ApplicationCommandInteraction,
        title: str,
        description: str,
        log_message: str | None = None,
        view: disnake.ui.View | None = None,
        **embed_fields,
    ) -> None:
        """
        Send a success response and optionally log.

        Args:
            inter: The interaction
            title: Embed title
            description: Embed description
            log_message: Optional message to log
            view: Optional view to attach
            **embed_fields: Additional embed fields (field_1=(name, value), etc.)
        """
        embed = self.formatter.success_embed(title, description, **embed_fields)
        try:
            await inter.edit_original_response(embed=embed, view=view)
        except Exception:
            try:
                await inter.followup.send(embed=embed, view=view, ephemeral=True)
            except Exception as e:
                logger.error(f"Failed to send success response: {e}")

        if log_message:
            logger.info(log_message)

    async def send_error(
        self,
        inter: disnake.ApplicationCommandInteraction,
        title: str,
        description: str,
        log_message: str | None = None,
        view: disnake.ui.View | None = None,
        **embed_fields,
    ) -> None:
        """
        Send an error response and optionally log.

        Args:
            inter: The interaction
            title: Embed title
            description: Embed description
            log_message: Optional message to log
            view: Optional view to attach
            **embed_fields: Additional embed fields (field_1=(name, value), etc.)
        """
        embed = self.formatter.error_embed(title, description, **embed_fields)
        try:
            await inter.edit_original_response(embed=embed, view=view)
        except Exception:
            try:
                await inter.followup.send(embed=embed, view=view, ephemeral=True)
            except Exception as e:
                logger.error(f"Failed to send error response: {e}")

        if log_message:
            logger.warning(log_message)

    async def send_warning(
        self,
        inter: disnake.ApplicationCommandInteraction,
        title: str,
        description: str,
        log_message: str | None = None,
        view: disnake.ui.View | None = None,
        **embed_fields,
    ) -> None:
        """
        Send a warning response and optionally log.

        Args:
            inter: The interaction
            title: Embed title
            description: Embed description
            log_message: Optional message to log
            view: Optional view to attach
            **embed_fields: Additional embed fields
        """
        embed = self.formatter.warning_embed(title, description, **embed_fields)
        try:
            await inter.edit_original_response(embed=embed, view=view)
        except Exception:
            try:
                await inter.followup.send(embed=embed, view=view, ephemeral=True)
            except Exception as e:
                logger.error(f"Failed to send warning response: {e}")

        if log_message:
            logger.warning(log_message)

    async def send_info(
        self,
        inter: disnake.ApplicationCommandInteraction,
        title: str,
        description: str,
        view: disnake.ui.View | None = None,
        **embed_fields,
    ) -> None:
        """
        Send an info response.

        Args:
            inter: The interaction
            title: Embed title
            description: Embed description
            view: Optional view to attach
            **embed_fields: Additional embed fields
        """
        embed = self.formatter.info_embed(title, description, **embed_fields)
        try:
            await inter.edit_original_response(embed=embed, view=view)
        except Exception:
            try:
                await inter.followup.send(embed=embed, view=view, ephemeral=True)
            except Exception as e:
                logger.error(f"Failed to send info response: {e}")

    async def not_registered_error(
        self,
        inter: disnake.ApplicationCommandInteraction,
        user: disnake.User | None = None,
    ) -> None:
        """
        Send standard "not registered" error message.

        Args:
            inter: The interaction
            user: Optional user for context (defaults to command author)
        """
        user_context = user.mention if user else "You"
        await self.send_error(
            inter,
            "Not Registered",
            f"{user_context} need to register your device first!",
            field_1=(
                "Next Steps",
                "Use `/openshock setup` to set up your API token and device.",
            ),
        )

    async def permission_denied_error(
        self,
        inter: disnake.ApplicationCommandInteraction,
        reason: str,
        user: disnake.User | None = None,
    ) -> None:
        """
        Send standard "permission denied" error message.

        Args:
            inter: The interaction
            reason: The reason for denial (from PermissionChecker)
            user: Optional target user for context
        """
        # Use permission checker's standard error messages if available
        error_msg = (
            f"❌ **Permission Denied**\n"
            f"Reason: {reason}\n\n"
            f"You may need to ask {user.mention if user else 'the target user'} "
            f"to grant you permissions using `/controllers add`."
        )

        await self.send_error(inter, "Permission Denied", error_msg)

    async def no_selection_error(
        self,
        inter: disnake.ApplicationCommandInteraction,
        item_type: str = "shocker",
        view: disnake.ui.View | None = None,
        skip_available: bool = False,
    ) -> None:
        """
        Send standard "no selection" error message.

        Args:
            inter: The interaction
            item_type: Type of item not selected (default: "shocker")
            view: Optional view to preserve
            skip_available: Whether skip option is available
        """
        hint = (
            f"Please select at least one {item_type} from the dropdown menu"
        )
        if skip_available:
            hint += ", or click **Skip for Now**."
        else:
            hint += "."

        await self.send_error(
            inter,
            "No Selection",
            hint,
            view=view,
        )

    async def item_not_found_error(
        self,
        inter: disnake.ApplicationCommandInteraction,
        item_type: str,
        item_id: str | None = None,
    ) -> None:
        """
        Send standard "item not found" error message.

        Args:
            inter: The interaction
            item_type: Type of item (e.g., "shocker", "reminder")
            item_id: Optional ID of missing item
        """
        desc = f"The {item_type} could not be found or is no longer available."
        if item_id:
            desc += f" (ID: {item_id[:20]})"

        await self.send_error(inter, "Not Found", desc)

    async def timeout_warning(
        self,
        inter: disnake.ApplicationCommandInteraction,
        action: str = "operation",
    ) -> None:
        """
        Send standard "timeout" warning message.

        Args:
            inter: The interaction
            action: The action that timed out
        """
        await self.send_warning(
            inter,
            "Timeout",
            f"The {action} timed out. Please try again.",
        )

    async def cooldown_warning(
        self,
        inter: disnake.ApplicationCommandInteraction,
        seconds_remaining: int | None = None,
    ) -> None:
        """
        Send standard "on cooldown" warning message.

        Args:
            inter: The interaction
            seconds_remaining: Optional seconds remaining on cooldown
        """
        desc = "This device is on cooldown. Please wait before trying again.\n\n**Why?** Cooldowns prevent excessive shocking and protect device hardware."
        if seconds_remaining:
            desc += f"\n\nWait ~{seconds_remaining}s before trying again."

        await self.send_warning(inter, "On Cooldown", desc)

