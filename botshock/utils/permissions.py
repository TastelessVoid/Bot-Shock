"""
Permission checking utilities for consent-based access control
"""

import logging

import disnake
from disnake.ext import commands

logger = logging.getLogger("BotShock.Permissions")


class PermissionChecker:
    """Handle permission checks for consent-based access control"""

    def __init__(self, database):
        self.db = database

    async def has_control_role(self, member: disnake.Member) -> bool:
        """
        Check if a member has any of the configured control roles for their guild

        Args:
            member: The member to check

        Returns:
            bool: True if member has a control role
        """
        if not isinstance(member, disnake.Member):
            return False

        # Get guild's control roles from database
        control_role_ids = await self.db.get_guild_control_roles(member.guild.id)

        if not control_role_ids:
            # No control roles configured
            return False

        # Check if member has any of the control roles
        member_role_ids = [role.id for role in member.roles]
        return any(rid in member_role_ids for rid in control_role_ids)

    @staticmethod
    def has_manage_roles_permission(member: disnake.Member) -> bool:
        """Check if a member has Manage Roles or Administrator permission."""
        try:
            perms = getattr(member, "guild_permissions", None)
            if perms is None:
                return False
            return bool(perms.administrator or perms.manage_roles)
        except Exception:
            return False

    async def can_manage_user(
        self, executor: disnake.Member, target: disnake.User, check_consent: bool = True
    ) -> tuple[bool, str]:
        """
        Check if executor can manage/control the target user.

        Primary check is consent-based permissions.
        Users must explicitly grant permission to be controlled.

        Args:
            executor: The person executing the command
            target: The target user being managed
            check_consent: Whether to check consent-based permissions (default True)

        Returns:
            tuple: (can_manage: bool, reason: str)
            Reasons: "self", "consent_user", "consent_role", "no_consent", "not_registered", "no_guild"
        """
        # Users can always manage themselves
        if executor.id == target.id:
            return True, "self"

        # Check if executor has the control role
        if not isinstance(executor, disnake.Member):
            return False, "no_guild"

        # Check consent-based permissions
        if check_consent:
            # Get executor's role IDs
            executor_role_ids = [role.id for role in executor.roles]

            # Check if target has given explicit consent
            has_permission = await self.db.can_user_control(
                controller_discord_id=executor.id,
                sub_discord_id=target.id,
                guild_id=executor.guild.id,
                controller_role_ids=executor_role_ids,
            )

            if has_permission:
                # Determine if it's user or role based
                permissions = await self.db.get_controller_permissions(target.id, executor.guild.id)
                if executor.id in permissions["users"]:
                    return True, "consent_user"
                else:
                    return True, "consent_role"
            else:
                # Check if target is registered (to provide better error messages)
                target_user = await self.db.get_user(target.id, executor.guild.id)
                if not target_user:
                    return False, "not_registered"
                return False, "no_consent"

        return False, "no_permission"

    async def get_permission_error_message(
        self, reason: str, target: disnake.User = None, guild: disnake.Guild = None
    ) -> str:
        """
        Get a user-friendly error message for permission denial

        Args:
            reason: The reason for denial
            target: The target user (optional)
            guild: The guild context (optional)

        Returns:
            str: Error message
        """
        if reason == "no_consent":
            return (
                f"❌ **Permission Denied - Consent Required**\n\n"
                f"{target.mention if target else 'This user'} has not given you permission to control their device.\n\n"
                f"**How it works:**\n"
                f"• Sub users must register their device first with `/openshock setup`\n"
                f"• Then they choose who can control them with `/controllers add`\n"
                f"• This ensures consent is always explicit and can be revoked anytime"
            )
        elif reason == "not_registered":
            return (
                f"❌ **User Not Registered**\n\n"
                f"{target.mention if target else 'This user'} needs to register their device first.\n\n"
                f"They should use `/openshock setup` to set up their API token and device."
            )
        elif reason == "no_permission":
            if guild:
                control_role_ids = await self.db.get_guild_control_roles(guild.id)
                if control_role_ids:
                    role_names = []
                    for role_id in control_role_ids:
                        role = guild.get_role(role_id)
                        if role:
                            role_names.append(f"**{role.name}**")
                    if role_names:
                        return (
                            f"You don't have permission to manage other users.\n"
                            f"You need one of these roles: {', '.join(role_names)}"
                        )
            return (
                "You don't have permission to manage other users.\n"
                "Ask an administrator to configure control roles with `/settings set_control_roles`."
            )
        elif reason == "no_guild":
            return "This command can only be used in a server, not in DMs."
        else:
            return "Permission denied."


def require_control_role():
    """
    Decorator to require control role for managing other users.
    Self-management is always allowed.

    Use consent-based checks for user control operations.
    """

    async def predicate(inter: disnake.ApplicationCommandInteraction) -> bool:
        # Get the permission checker from the bot
        if not hasattr(inter.bot, "permission_checker"):
            return False

        checker = inter.bot.permission_checker

        # Check if there's a 'user' parameter in the command
        user_param = inter.filled_options.get("user")

        # If no user specified, they're managing themselves - allow
        if user_param is None:
            return True

        # If user is specified, check permissions
        can_manage, reason = await checker.can_manage_user(inter.author, user_param)

        if not can_manage:
            # Send error message
            error_msg = await checker.get_permission_error_message(reason, user_param, inter.guild)
            await inter.response.send_message(error_msg, ephemeral=True)
            return False

        return True

    return commands.check(predicate)
