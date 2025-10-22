"""
Validation utilities for command parameters
"""

import logging
import re

import disnake

from botshock.exceptions import ValidationError

logger = logging.getLogger("BotShock.Validators")


def validate_intensity(intensity: int) -> int:
    """
    Validate intensity is within acceptable range (1-100).

    Args:
        intensity: Intensity value to validate

    Returns:
        The validated intensity value

    Raises:
        ValidationError: If intensity is out of range
    """
    if not isinstance(intensity, int) or not 1 <= intensity <= 100:
        raise ValidationError(f"Intensity must be between 1 and 100, got {intensity}")
    return intensity


def validate_duration(duration: int) -> int:
    """
    Validate duration is within acceptable range (1-15 seconds).

    Args:
        duration: Duration value to validate

    Returns:
        The validated duration value

    Raises:
        ValidationError: If duration is out of range
    """
    if not isinstance(duration, int) or not 1 <= duration <= 15:
        raise ValidationError(f"Duration must be between 1 and 15 seconds, got {duration}")
    return duration


def validate_action_type(action: str) -> str:
    """
    Validate action type is one of the allowed values.

    Args:
        action: Action type to validate

    Returns:
        The validated action type

    Raises:
        ValidationError: If action type is invalid
    """
    valid_actions = {"shock", "vibrate", "beep"}
    action = action.lower()
    if action not in valid_actions:
        raise ValidationError(f"Action must be one of {valid_actions}, got '{action}'")
    return action


async def _validate_permission_and_target(
    db,
    permission_checker,
    author: disnake.User,
    target: disnake.User,
    guild_id: int,
    *,
    require_shockers: bool,
) -> tuple[bool, str | None]:
    """
    Shared validation: permissions, target registration, and optional shockers check.

    Returns (is_valid, error_message)
    """
    # Derive a safe target label (mention if available, else ID)
    target_id = getattr(target, "id", "?")
    target_label = getattr(target, "mention", f"User ID {target_id}")

    # Check permissions
    can_manage, reason = await permission_checker.can_manage_user(author, target)
    if not can_manage:
        error_msg = await permission_checker.get_permission_error_message(reason, target, None)
        return False, error_msg

    # Check if target is registered
    target_user = await db.get_user(target_id, guild_id)
    if not target_user:
        return False, (
            f"User {target_label} is not registered with OpenShock in this server!\n"
            "They need to use `/openshock setup` first."
        )

    if require_shockers:
        # Check if target has shockers
        shockers = await db.get_shockers(target_id, guild_id)
        if not shockers:
            return False, f"User {target_label} has no shockers registered in this server!"

    return True, None


class ReminderValidator:
    """Validates reminder command parameters"""

    def __init__(self, db, permission_checker):
        self.db = db
        self.permission_checker = permission_checker

    async def validate_reminder_creation(
        self, author: disnake.User, target: disnake.User, guild_id: int
    ) -> tuple[bool, str | None]:
        """
        Validate if a reminder can be created for a target user

        Args:
            author: The user creating the reminder
            target: The target user to be shocked
            guild_id: The guild ID

        Returns:
            Tuple of (is_valid, error_message)
        """
        return await _validate_permission_and_target(
            self.db, self.permission_checker, author, target, guild_id, require_shockers=True
        )


class ShockValidator:
    """Validates shock command parameters"""

    def __init__(self, db, permission_checker):
        self.db = db
        self.permission_checker = permission_checker

    async def validate_shock_request(
        self,
        author: disnake.User,
        target: disnake.User,
        guild_id: int,
        shocker_id: str | None = None,
    ) -> tuple[bool, str | None, dict | None, dict | None]:
        """
        Validate if a shock can be sent to a target user

        Args:
            author: The user sending the shock
            target: The target user to be shocked
            guild_id: The guild ID
            shocker_id: Optional specific shocker ID

        Returns:
            Tuple of (is_valid, error_message, target_user_data, shocker_data)
        """
        # Shared checks: permissions, registration, shockers present
        ok, err = await _validate_permission_and_target(
            self.db, self.permission_checker, author, target, guild_id, require_shockers=True
        )
        if not ok:
            return False, err, None, None

        # Get target user and shockers
        target_user = await self.db.get_user(target.id, guild_id)
        shockers = await self.db.get_shockers(target.id, guild_id)

        # Check if device is worn
        device_worn = await self.db.get_device_worn_status(target.id, guild_id)
        if not device_worn:
            target_label = getattr(target, "mention", f"User ID {target.id}")
            return False, f"User {target_label} is not wearing their device right now!", None, None

        # Select shocker
        if shocker_id:
            target_shocker = next((s for s in shockers if s["shocker_id"] == shocker_id), None)
            if not target_shocker:
                return False, "Specified shocker ID not found!", None, None
        else:
            target_shocker = shockers[0]

        return True, None, target_user, target_shocker


class TriggerValidator:
    """Validates trigger command parameters"""

    def __init__(self, db, permission_checker):
        self.db = db
        self.permission_checker = permission_checker

    async def validate_trigger_creation(
        self, author: disnake.User, target: disnake.User, guild_id: int, regex_pattern: str
    ) -> tuple[bool, str | None]:
        """
        Validate if a trigger can be created for a target user

        Args:
            author: The user creating the trigger
            target: The target user
            guild_id: The guild ID
            regex_pattern: The regex pattern to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Shared checks: permissions, registration, shockers present
        ok, err = await _validate_permission_and_target(
            self.db, self.permission_checker, author, target, guild_id, require_shockers=True
        )
        if not ok:
            return False, err

        # Validate regex pattern
        try:
            re.compile(regex_pattern)
        except re.error as e:
            return False, f"Invalid regex pattern: {str(e)}"

        return True, None
