"""
Decorators for reducing boilerplate in command handling.

This module provides reusable decorators to eliminate common patterns like
permission checking, registration validation, and error handling across cogs.
"""

import functools
import logging
from typing import Callable

import disnake

from botshock.utils.response_handler import ResponseHandler

logger = logging.getLogger("BotShock.Decorators")


def defer_response(ephemeral: bool = True):
    """
    Decorator to automatically defer responses.

    Usage:
        @defer_response(ephemeral=True)
        async def my_command(self, inter: disnake.ApplicationCommandInteraction):
            # Response automatically deferred
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self, inter: disnake.ApplicationCommandInteraction, *args, **kwargs):
            try:
                await inter.response.defer(ephemeral=ephemeral)
            except Exception as e:
                logger.warning(f"Failed to defer response: {e}")
            return await func(self, inter, *args, **kwargs)

        return wrapper

    return decorator


def require_registration(attr_name: str = "db"):
    """
    Decorator to require user registration before command execution.

    If user is not registered, sends error and returns.

    Usage:
        @require_registration(attr_name="db")
        async def my_command(self, inter: disnake.ApplicationCommandInteraction):
            # User guaranteed to be registered
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self, inter: disnake.ApplicationCommandInteraction, *args, **kwargs):
            db = getattr(self, attr_name, None)
            if not db:
                logger.error(f"Command {func.__name__} missing {attr_name}")
                return

            formatter = getattr(self, "formatter", None)
            handler = ResponseHandler(formatter) if formatter else None

            user_data = await db.get_user(inter.author.id, inter.guild.id)
            if not user_data:
                if handler:
                    await handler.not_registered_error(inter, inter.author)
                else:
                    embed = disnake.Embed(
                        title="❌ Not Registered",
                        description="You need to register first!",
                        color=0xFF0000,
                    )
                    await inter.edit_original_response(embed=embed)
                return

            return await func(self, inter, *args, **kwargs)

        return wrapper

    return decorator


def check_permission(
    author_attr: str = "inter.author", target_attr: str = "user", action_desc: str = "perform this action"
):
    """
    Decorator to check permissions before command execution.

    Usage:
        @check_permission(target_attr="target_user", action_desc="shock this user")
        async def my_command(self, inter: ..., target_user: disnake.User):
            # Permission already checked
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self, inter: disnake.ApplicationCommandInteraction, *args, **kwargs):
            permission_checker = getattr(self, "permission_checker", None)
            formatter = getattr(self, "formatter", None)

            if not permission_checker or not formatter:
                logger.error(f"Command {func.__name__} missing permission_checker or formatter")
                return await func(self, inter, *args, **kwargs)

            target = kwargs.get(target_attr)
            if not target:
                logger.warning(f"Decorator {check_permission.__name__}: target {target_attr} not found")
                return await func(self, inter, *args, **kwargs)

            can_manage, reason = await permission_checker.can_manage_user(inter.author, target)

            if not can_manage:
                handler = ResponseHandler(formatter)
                await handler.permission_denied_error(inter, reason, target)
                logger.warning(
                    f"Permission denied: {inter.author.id} -> {target.id} in guild {inter.guild.id}"
                )
                return

            return await func(self, inter, *args, **kwargs)

        return wrapper

    return decorator


def handle_errors(
    log_errors: bool = True, send_response: bool = True, response_title: str = "Error"
):
    """
    Decorator to automatically handle exceptions in commands.

    Usage:
        @handle_errors(log_errors=True, response_title="Command Failed")
        async def my_command(self, inter: ...):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self, inter: disnake.ApplicationCommandInteraction, *args, **kwargs):
            try:
                return await func(self, inter, *args, **kwargs)
            except Exception as e:
                if log_errors:
                    logger.exception(f"Error in {func.__name__}: {e}")

                if send_response:
                    formatter = getattr(self, "formatter", None)
                    if formatter:
                        handler = ResponseHandler(formatter)
                        await handler.send_error(
                            inter,
                            response_title,
                            f"An error occurred: {str(e)[:100]}",
                        )
                    else:
                        embed = disnake.Embed(
                            title=f"❌ {response_title}",
                            description=f"An error occurred: {str(e)[:100]}",
                            color=0xFF0000,
                        )
                        try:
                            await inter.edit_original_response(embed=embed)
                        except Exception:
                            await inter.followup.send(embed=embed, ephemeral=True)

        return wrapper

    return decorator


def cooldown_check(
    cooldown_seconds: int = 60, custom_message: str | None = None
):
    """
    Decorator to check shocker cooldown before command execution.

    Requires self.db to be available.

    Usage:
        @cooldown_check(cooldown_seconds=60)
        async def my_command(self, inter: ..., user: disnake.User, shocker_id: str):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self, inter: disnake.ApplicationCommandInteraction, *args, **kwargs):
            db = getattr(self, "db", None)
            formatter = getattr(self, "formatter", None)

            if not db or not formatter:
                return await func(self, inter, *args, **kwargs)

            # Extract target user and shocker_id from kwargs
            user = kwargs.get("user")
            shocker_id = kwargs.get("shocker_id")

            if not user or not shocker_id:
                return await func(self, inter, *args, **kwargs)

            is_ready = await db.check_shocker_cooldown(
                user.id, inter.guild.id, shocker_id, cooldown_seconds
            )

            if not is_ready:
                handler = ResponseHandler(formatter)
                message = (
                    custom_message
                    or f"Device is on cooldown. Please wait {cooldown_seconds}s."
                )
                await handler.send_warning(inter, "On Cooldown", message)
                return

            return await func(self, inter, *args, **kwargs)

        return wrapper

    return decorator

